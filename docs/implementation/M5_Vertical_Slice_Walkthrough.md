# M5 — First Vertical Slice: Walkthrough

**Milestone:** M5 (Document 8: "end-to-end single-day tick across population, production, inventory, and market")
**Baseline:** M4 complete at `5362d4d`, 609 tests. **M5 delivered:** 643 tests (+34).
**Commits:** `78ae431` (5.1), `3618190` + `2c1111d` (5.2), `e2fb596` + `3c03dc5` (5.3), `5437771` (5.4).
**Scope of change:** tests and test support only. No `src/` changes, no migrations, no schema or foreign-key changes, so no ADR was required.

## 1. What M5 proves

One real `SimulationEngine` tick, run against a fully isolated synthetic Test city, exercises every domain Document 8 names (population, production, inventory, market) plus construction, in one transaction, and the committed result matches an independently computed expectation field by field.

It also proves the failure half of the same claim: when a step fails mid-tick, nothing from that tick survives in any domain.

**Not proven here, by design:**

- Anything against the real CityScape city or the Cinis Baseline scenario. The first real-data run is **M6**. The slice and rollback tests and the builder smoke test each assert that a fingerprint of the real city (population, buildings, inventory and ledgers, treasury, market, projects, snapshots, baseline runs and prices) is identical before and after.
- Balance. Every rate, price and flow is still an unbalanced placeholder.
- More than one tick. Multi-day behaviour on synthetic data was already proven in M4 Step 4.7.

## 2. The day

The tick runs on a **month-boundary day** (start `1880-01-31`, tick lands on `1880-02-01`). Aging, Production, Construction and Snapshot run only on month-boundary ticks (ADR-0009), so an ordinary day would exercise only NeedsConsumption.

Step order follows Document 6 (orders first, market after consumption, snapshot last). The two **scripted** steps are test-only wrappers around the real command services; every other step is the real one.

| # | Step | What happens on the slice city |
|---|---|---|
| 1 | `ScriptedOrders` *(test-only)* | Order 1 Construction Crew (B-007): free, 50 Timber + 50 Stone, 1-month duration |
| 2 | `PopulationAging` | floor(200 × 1.5%) = 3 children become adults |
| 3 | `Production` | 103 labor. Two Wheat Farms staffed (+200 Wheat); Saw Mill staffed (−100 Timber, +50 Lumber) |
| 4 | `Construction` | The Crew completes in the same tick: Building row added, `ConstructionCompleted` event |
| 5 | `NeedsConsumption` | FOOD 201.5 from Wheat, HEATING 161.2 from Timber; BASIC_GOODS has no mapping and is skipped |
| 6 | `ScriptedTrades` *(test-only)* | Sell the 50 Lumber produced at 3.00; buy 100 Wheat at 2.00 |
| 7 | `Snapshot` | One `CitySnapshot` capturing end-of-tick state, including the trades |

### Result (verified on the real SQL Server, 2026-10-28)

| | Before | After |
|---|---|---|
| Adults / children | 100 / 200 | 103 / 197 |
| Wheat (R-001) | 1000 | 1098.5 |
| Stone (R-003) | 1000 | 950 |
| Timber (R-004) | 1000 | 688.8 |
| Lumber (R-005) | 0 | 0 (50 made, 50 sold) |
| Treasury | 1000.00 | 950.00 (+150 sale, −200 purchase) |
| Buildings | B-002 ×2, B-009 ×1 | + B-007 ×1 |

## 3. How it is built

Files are under `tests/integration/` unless a full path is shown.

| File | Role |
|---|---|
| `isolated_city.py` | `build_isolated_city()` creates and commits one synthetic Test city (World, Region, City, Simulation, Scenario, parameters, run at tick 0, population, buildings, opening stock, Treasury, Market, explicit prices). Also the shared read helpers and `real_city_fingerprint()`. |
| `scripted_steps.py` | The two test-only `TickStep`s and `build_slice_steps()`, which redirects the five real steps to the Test city and inserts the scripted steps at their Document 6 slots. |
| `slice_oracle.py` | An independent model of the day (section 5). Pure Python, no database. |
| `test_slice_oracle.py` | 14 database-free tests of the oracle, including a known-answer test using the real seeded catalog numbers. |
| `test_isolated_city_builder.py` | 7 smoke tests of the builder, including the real-city fingerprint check. |
| `test_vertical_slice.py` | Three tests: step-order guard (no database), the happy-path day, and the rollback day. |
| `conftest.py`, `test_cleanup_of_test_rows.py`, `tests/unit/test_cleanup_coverage.py` | The hardened test-row cleanup (section 7). |

The builder commits for real, because the engine opens its own session per tick. Everything it creates is `Test`-named or foreign-keyed to a Test city or scenario, and the session-end cleanup removes it.

## 4. The scripted steps are not a design

`MarketService.buy`/`sell` and `ConstructionService.order_project` are commands, not tick steps; nothing in `src/` calls them automatically (M4 Step 4.6). To exercise them inside a real tick, the slice wraps them in two throwaway steps. That gives one transaction, every ledger entry stamped with the tick's run and tick, Document 6 ordering, and a snapshot that sees the trades.

They live in `tests/`, nothing in `src/` imports them, and they must not be read as approval of any command-queue design. Whether baseline runs get a real scheduled-commands mechanism is an open **M6** decision (section 9).

## 5. The oracle

`slice_oracle.expected_day()` models the six steps from the documented rules (ADR-0008, 0009, 0010, 0011, Document 6) with its own floor arithmetic. It never imports or calls the services, rules or repositories under test, and it is fed only by raw SQL reads of the catalog and start state. If the engine and the oracle disagree, either the engine composes the steps wrongly or one side misreads a rule.

The slice test compares the committed end state against it for population, buildings, inventory, treasury, the construction project, events, market transactions, both ledgers and the snapshot. It also checks invariants the oracle does not supply: every inventory quantity equals the sum of its ledger, and every entry the tick wrote carries the tick's run and tick id.

Expected values are read from the live catalog and the Test scenario's own parameters, so rebalancing placeholders does not break the test. Preconditions at the top of the happy-path test (children actually age, both production flows run, the Crew completes, no shortfall) fail loudly if a catalog change turns the day into a vacuous pass.

`Order` and `Trade` are shared by the oracle and the scripted steps, so the script the engine executes and the script the oracle models are written in the same types.

## 6. The rollback day

Same city and orders, but the trades are a valid Wheat buy followed by a sale of one more Lumber than the Saw Mill made. The buy is already staged in the tick's open transaction when the sale raises `InsufficientInventoryError`. The test then proves:

- the oracle also rejects the day (`ModelError`);
- every step before the failure ran, and Snapshot never did; mid-tick, the open transaction already held the aged population and the produced Lumber;
- afterwards the city's state is identical to before in every domain, including row counts for both ledgers, trades, projects, events and snapshots;
- the run is `Failed` at tick 0 on the start date, and a further `run_tick` raises `SimulationRunNotActiveError` and changes nothing;
- the real CityScape is untouched.

## 7. Test-row cleanup: a defect found and fixed (Step 5.1)

The session-end cleanup of `Test` rows had been silently failing since M1. Four early `Test`-named Simulations owned Scenarios whose names lacked the prefix; the name-only Scenario delete skipped them, `DELETE Simulation` then failed on `FK_Scenario_Simulation`, and the swallowed `pyodbc.Error` rolled back the whole cleanup every session. 157 Test Simulations and 109 Test Cities had accumulated.

Fixes, all in test infrastructure:

- A `Test`-named Simulation now owns all its Scenarios, whatever they are named.
- Market, MarketTransaction, MarketResourcePrice and untraced Treasury ledger entries are covered.
- `tests/unit/test_cleanup_coverage.py` derives the foreign-key graph from the migrations and fails if a table referencing a cleaned table is missing from the cleanup or deleted after its parent. A future domain table that references City or Scenario cannot be forgotten silently.
- `test_cleanup_of_test_rows.py` executes the real cleanup SQL inside one transaction that always rolls back.
- A failed cleanup now rolls back and emits a `RuntimeWarning` instead of staying silent. It still never fails a session.

## 8. Running it

```powershell
python -m pytest -q                                          # full suite: 643 passed
python -m pytest -s -q tests/integration/test_vertical_slice.py   # prints the day's report
```

A `cleanup FAILED` warning at the end of a run means Test rows from that session were left behind; run `tests/integration/test_cleanup_of_test_rows.py` to find the failing statement.

## 9. Carried forward

| Item | Category |
|---|---|
| Whether the scripted steps become a real scheduled-commands mechanism, so baseline runs can trade and order | Next Milestone (M6 decision) |
| How a command issued outside a tick is stamped: the ledger trace requires tick ≥ 1, so a command before a run's first tick cannot carry a trace; M5 stamps in-tick commands with the current tick | Next Milestone (M6 decision) |
| First run against real CityScape data. Use the SAVEPOINT-restart recipe (bridge document, section 6) or a deliberate, agreed real commit; never share one session across `run_tick()` calls | Next Milestone (M6) |
| Shortage-day variant (Wheat under-stocked, fallthrough to Trout, `NeedsShortfall`) | Future Feature (M7 scenario validation) |
| Step 4.7's isolated-city setup duplicated in `isolated_city.py` | Technical Debt (low) |
| Balancing, unit reconciliation (ADR-0010), maintenance wiring, workbook Ore/Flax swap, opening-stock dating | Unchanged; see the M4 to M5 bridge document (section 8) and Issues & Technical Debt |

## 10. Maintaining it

- **Step-order test fails:** the real default step list changed. Revisit the slice deliberately (where do the scripted steps belong now?) rather than editing the test to pass.
- **Happy-path precondition fails:** the catalog or stock changed so a domain no longer has anything observable to do. Retune the slice city; the engine is not at fault.
- **Oracle and engine disagree on a number:** compare the oracle's step comment against the rule in `src/`; the printed day report (`-s`) shows each step's expected effect.
- **Coverage test fails after a new migration:** add the new table to `_cleanup_test_rows` in the right order, or list it in `KNOWN_UNPOPULATED_BY_TESTS` with a reason.
