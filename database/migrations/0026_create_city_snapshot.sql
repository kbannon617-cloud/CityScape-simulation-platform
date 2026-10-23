-- 0026_create_city_snapshot.sql
-- Milestone 4, Step 4.7. Implements the SNAPSHOTS leg of Document 5's
-- CURRENT STATE + EVENTS + SNAPSHOTS pattern (SimulationEvent, migration
-- 0019, implemented the EVENTS leg).
--
-- One row per city per month-boundary tick (see simulation/snapshot_step.py).
-- "Snapshot frequency can vary by entity" (Document 2) - monthly is the
-- cadence already used by Aging/Production/Construction, so this reuses
-- it rather than introducing a new one.
--
-- Payload is a JSON blob (mirrors SimulationEvent.Payload) rather than
-- dozens of normalized columns - the point-in-time values it captures
-- (population, treasury balance, key inventory, building/vehicle counts)
-- are already each authoritatively tracked elsewhere; this table is a
-- read-optimized point-in-time rollup for history/analysis, not a new
-- source of truth.

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'CitySnapshot')
BEGIN
    CREATE TABLE dbo.CitySnapshot (
        CitySnapshotID    BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        SimulationRunID   INT                  NOT NULL,
        SimulationTickID  BIGINT               NOT NULL,
        SimulationDate    DATE                 NOT NULL,
        CityID            INT                  NOT NULL,
        Payload           NVARCHAR(MAX)        NOT NULL,
        CreatedDateTime   DATETIME2(3)         NOT NULL CONSTRAINT DF_CitySnapshot_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_CitySnapshot_SimulationRun FOREIGN KEY (SimulationRunID) REFERENCES dbo.SimulationRun (SimulationRunID),
        CONSTRAINT FK_CitySnapshot_City FOREIGN KEY (CityID) REFERENCES dbo.City (CityID),
        CONSTRAINT CK_CitySnapshot_SimulationTickID_Positive CHECK (SimulationTickID >= 1),
        CONSTRAINT CK_CitySnapshot_Payload_IsJson CHECK (ISJSON(Payload) = 1)
    );

    CREATE NONCLUSTERED INDEX IX_CitySnapshot_Run_Tick ON dbo.CitySnapshot (SimulationRunID, SimulationTickID);
END
GO
