-- 0019_create_simulation_event.sql
-- Milestone 4, Step 4.1. Implements the "EVENTS" leg of Document 5's
-- CURRENT STATE + EVENTS + SNAPSHOTS pattern and the tick cycle's "Event
-- Generation & Logs" step (Document 6). First writer will be the needs
-- shortfall policy decided in ADR-0009 (Decision 2).
--
-- Design notes:
--   * BIGINT key: "BIGINT for high-volume Operational Data, Ticks, and
--     Events" (ADR register). One run can emit many events per tick.
--   * SimulationRunID + SimulationTickID + SimulationDate are all stored.
--     SimulationTickID is a per-run counter (tick 5 exists in every run),
--     so it is only meaningful together with SimulationRunID. The date is
--     kept alongside so events can be read without a join, but the three
--     are deliberately separate columns (Temporal Data Architecture: never
--     conflate SimulationDate, SimulationTickID and CreatedDateTime).
--   * SimulationTickID >= 1: ticks are numbered from 1; a run's
--     CurrentSimulationTickID of 0 means "no tick has executed yet".
--   * EventType is a plain code string, with no reference table, for now.
--     Same reasoning as InventoryLedgerEntry.Notes in 0013: the set of
--     event types is not known until real emitters exist. A reference
--     table can be added later, once the types have stabilized.
--   * Payload is optional JSON (NVARCHAR(MAX) + ISJSON check) so new event
--     types can carry structured detail without a schema change - the
--     "minimal extensible events" requirement from Document 4.
--   * CityID is nullable: some events are run-wide, not city-specific.
--
-- ISJSON requires database compatibility level 130 (SQL Server 2016) or
-- higher. If this migration fails on that check, the runner rolls the
-- whole batch back and nothing is left half-applied.

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SimulationEvent')
BEGIN
    CREATE TABLE dbo.SimulationEvent (
        SimulationEventID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        SimulationRunID   INT                  NOT NULL,
        SimulationTickID  BIGINT               NOT NULL,
        SimulationDate    DATE                 NOT NULL,
        CityID            INT                  NULL,
        EventType         NVARCHAR(50)         NOT NULL,
        Description       NVARCHAR(500)        NULL,
        Payload           NVARCHAR(MAX)        NULL,
        CreatedDateTime   DATETIME2(3)         NOT NULL CONSTRAINT DF_SimulationEvent_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_SimulationEvent_SimulationRun FOREIGN KEY (SimulationRunID) REFERENCES dbo.SimulationRun (SimulationRunID),
        CONSTRAINT FK_SimulationEvent_City FOREIGN KEY (CityID) REFERENCES dbo.City (CityID),
        CONSTRAINT CK_SimulationEvent_SimulationTickID_Positive CHECK (SimulationTickID >= 1),
        CONSTRAINT CK_SimulationEvent_Payload_IsJson CHECK (Payload IS NULL OR ISJSON(Payload) = 1)
    );

    CREATE NONCLUSTERED INDEX IX_SimulationEvent_Run_Tick ON dbo.SimulationEvent (SimulationRunID, SimulationTickID);
END
GO
