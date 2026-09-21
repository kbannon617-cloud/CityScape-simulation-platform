"""
Unit tests for SimulationEngine against a fake session (no database).

Real transactional behavior (rollback actually undoing writes) is covered
in tests/integration/test_simulation_engine.py.
"""

from __future__ import annotations

import datetime

import pytest

from cinis.models.simulation import SimulationRun
from cinis.repositories.simulation_run_repository import SimulationRunNotFoundError
from cinis.simulation.engine import SimulationEngine, SimulationRunNotActiveError
from cinis.simulation.tick import StepCadence, TickContext, TickStep

D = datetime.date


class _FakeSession:
    def __init__(self, runs, fail_commit=False):
        self._runs = runs
        self._fail_commit = fail_commit
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def get(self, model, key):
        assert model is SimulationRun
        return self._runs.get(key)

    def commit(self):
        if self._fail_commit:
            raise RuntimeError("commit failed")
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


class _FakeDatabase:
    """Hands out a new fake session per call, all sharing one set of runs."""

    def __init__(self, run, fail_commit_on_sessions=(), fail_all_after_first=False):
        self.runs = {run.SimulationRunID: run}
        self.sessions: list[_FakeSession] = []
        self._fail_commit_on = set(fail_commit_on_sessions)
        self._fail_all_after_first = fail_all_after_first

    def __call__(self):
        index = len(self.sessions)
        fail = index in self._fail_commit_on or (self._fail_all_after_first and index >= 1)
        session = _FakeSession(self.runs, fail_commit=fail)
        self.sessions.append(session)
        return session


def _run(status="Active", date=D(1880, 1, 1), tick=0):
    return SimulationRun(
        SimulationRunID=1,
        ScenarioID=9,
        StartSimulationDate=date,
        CurrentSimulationDate=date,
        CurrentSimulationTickID=tick,
        Status=status,
    )


def _recording_step(log, name, cadence=StepCadence.EVERY_TICK):
    return TickStep(name=name, execute=lambda ctx: log.append((name, ctx)), cadence=cadence)


def test_tick_advances_the_run_commits_once_and_closes_the_session():
    run = _run()
    db = _FakeDatabase(run)

    result = SimulationEngine(db).run_tick(1)

    assert (run.CurrentSimulationDate, run.CurrentSimulationTickID) == (D(1880, 1, 2), 1)
    assert (result.simulation_tick_id, result.simulation_date) == (1, D(1880, 1, 2))
    assert result.is_month_boundary is False
    assert result.executed_steps == ()
    assert len(db.sessions) == 1
    assert (db.sessions[0].commits, db.sessions[0].rollbacks) == (1, 0)
    assert db.sessions[0].closed


def test_steps_run_in_the_order_given():
    log = []
    steps = [_recording_step(log, "First"), _recording_step(log, "Second"), _recording_step(log, "Third")]

    result = SimulationEngine(_FakeDatabase(_run()), steps).run_tick(1)

    assert [name for name, _ in log] == ["First", "Second", "Third"]
    assert result.executed_steps == ("First", "Second", "Third")


def test_steps_receive_the_tick_context():
    log = []
    db = _FakeDatabase(_run(date=D(1880, 3, 10), tick=68))

    SimulationEngine(db, [_recording_step(log, "Probe")]).run_tick(1)

    (_, context), = log
    assert isinstance(context, TickContext)
    assert context.simulation_run_id == 1
    assert context.scenario_id == 9
    assert context.simulation_tick_id == 69
    assert context.simulation_date == D(1880, 3, 11)
    assert context.previous_date == D(1880, 3, 10)
    assert context.is_month_boundary is False
    assert context.session is db.sessions[0]


def test_month_boundary_steps_are_skipped_on_an_ordinary_day():
    log = []
    steps = [
        _recording_step(log, "Daily"),
        _recording_step(log, "Monthly", StepCadence.MONTH_BOUNDARY),
    ]

    result = SimulationEngine(_FakeDatabase(_run(date=D(1880, 1, 14))), steps).run_tick(1)

    assert result.executed_steps == ("Daily",)


def test_month_boundary_steps_run_on_the_first_tick_of_a_new_month():
    log = []
    steps = [
        _recording_step(log, "Monthly", StepCadence.MONTH_BOUNDARY),
        _recording_step(log, "Daily"),
    ]

    result = SimulationEngine(_FakeDatabase(_run(date=D(1880, 1, 31))), steps).run_tick(1)

    assert result.is_month_boundary is True
    assert result.executed_steps == ("Monthly", "Daily")


def test_consecutive_ticks_continue_from_the_committed_state():
    run = _run(date=D(1880, 1, 30))
    engine = SimulationEngine(_FakeDatabase(run))

    first = engine.run_tick(1)
    second = engine.run_tick(1)

    assert (first.simulation_tick_id, first.is_month_boundary) == (1, False)
    assert (second.simulation_tick_id, second.is_month_boundary) == (2, True)
    assert run.CurrentSimulationDate == D(1880, 2, 1)


def test_a_failing_step_rolls_back_marks_the_run_failed_and_reraises_the_original_error():
    run = _run()
    db = _FakeDatabase(run)
    boom = RuntimeError("step blew up")
    log = []

    def failing(ctx):
        raise boom

    steps = [
        _recording_step(log, "Before"),
        TickStep(name="Fails", execute=failing),
        _recording_step(log, "After"),
    ]

    with pytest.raises(RuntimeError) as raised:
        SimulationEngine(db, steps).run_tick(1)

    assert raised.value is boom
    assert [name for name, _ in log] == ["Before"]  # later steps never ran

    tick_session, failure_session = db.sessions
    assert (tick_session.commits, tick_session.rollbacks) == (0, 1)
    assert tick_session.closed
    assert failure_session.commits == 1  # Failed status saved in its own transaction
    assert failure_session.closed
    assert run.Status == "Failed"


def test_a_failing_commit_is_treated_as_a_failed_tick():
    run = _run()
    db = _FakeDatabase(run, fail_commit_on_sessions={0})

    with pytest.raises(RuntimeError, match="commit failed"):
        SimulationEngine(db).run_tick(1)

    assert db.sessions[0].rollbacks == 1
    assert run.Status == "Failed"


def test_if_marking_failed_also_fails_the_original_error_still_propagates():
    run = _run()
    db = _FakeDatabase(run, fail_all_after_first=True)
    original = ValueError("original")

    def failing(ctx):
        raise original

    with pytest.raises(ValueError) as raised:
        SimulationEngine(db, [TickStep(name="Fails", execute=failing)]).run_tick(1)

    assert raised.value is original
    assert all(session.closed for session in db.sessions)


def test_a_run_that_is_not_active_is_refused_without_rollback_or_status_change():
    run = _run(status="Completed")
    db = _FakeDatabase(run)

    with pytest.raises(SimulationRunNotActiveError, match="Completed"):
        SimulationEngine(db).run_tick(1)

    assert run.Status == "Completed"
    assert run.CurrentSimulationTickID == 0
    assert len(db.sessions) == 1
    assert (db.sessions[0].commits, db.sessions[0].rollbacks) == (0, 0)
    assert db.sessions[0].closed


def test_a_failed_run_cannot_be_ticked_again():
    run = _run()
    db = _FakeDatabase(run)

    def failing(ctx):
        raise RuntimeError("boom")

    engine = SimulationEngine(db, [TickStep(name="Fails", execute=failing)])
    with pytest.raises(RuntimeError):
        engine.run_tick(1)

    with pytest.raises(SimulationRunNotActiveError, match="Failed"):
        engine.run_tick(1)


def test_a_missing_run_raises_not_found():
    db = _FakeDatabase(_run())

    with pytest.raises(SimulationRunNotFoundError):
        SimulationEngine(db).run_tick(999)

    assert db.sessions[0].closed


def test_duplicate_step_names_are_rejected():
    noop = lambda ctx: None  # noqa: E731
    with pytest.raises(ValueError, match="unique"):
        SimulationEngine(
            _FakeDatabase(_run()),
            [TickStep(name="Same", execute=noop), TickStep(name="Same", execute=noop)],
        )
