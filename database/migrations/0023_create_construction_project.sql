-- 0023_create_construction_project.sql
-- Milestone 4, Step 4.5a. Implements ADR-0011: the Construction Projects
-- domain. One row per building order.
--
-- Per the design-concept workbook's Construction Projects sheet:
--   "Costs and materials remain order-time deductions; building effects
--    remain completion-based."
-- Cost/Timber/Stone are snapshotted at order time (protects history if
-- BuildingType's catalog values change later); the Building row is only
-- incremented when the project reaches Complete (Step 4.5b/c).
--
-- AdjustedDurationMonths is computed once, at order time, from:
--   BaseDurationMonths = CEILING(TotalConstructionCost / MonthlyConstructionBudget)
--   SpeedBonus         = (completed Construction Crew buildings at order time)
--                         * ConstructionBonusPerCompletedCrew
--   AdjustedDurationMonths = CEILING(BaseDurationMonths / (1 + SpeedBonus))
-- (both ScenarioParameters seeded in 0024). It is not recalculated if the
-- crew count or parameters change after ordering - matches the workbook.
--
-- MonthsElapsed is a plain counter, incremented once per month-boundary
-- tick (Step 4.5c), compared against AdjustedDurationMonths to decide
-- completion. This is a deliberate simplification versus the workbook's
-- absolute-calendar-month arithmetic (ADR-0011): functionally equivalent,
-- avoids reimplementing month-difference math, and matches how aging and
-- production already track progress by tick, not by date arithmetic.
--
-- Max concurrent projects per city (currently 1, per ADR-0011 - the owner
-- intends to raise this later) is enforced in the service layer via the
-- MaxActiveConstructionProjectsPerCity ScenarioParameter (0024), NOT a
-- database constraint - unlike City.IsPrimaryActive, this limit is
-- expected to change, and a unique index would make raising it an
-- ADR-gated schema change instead of a data change.

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'ConstructionProject')
BEGIN
    CREATE TABLE dbo.ConstructionProject (
        ConstructionProjectID   INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        CityID                  INT                NOT NULL,
        BuildingTypeID          INT                NOT NULL,
        BuildingsOrdered        INT                NOT NULL,
        OrderSimulationDate     DATE               NOT NULL,
        TotalConstructionCost   DECIMAL(18,4)      NOT NULL,
        TotalTimberRequired     DECIMAL(18,4)      NOT NULL,
        TotalStoneRequired      DECIMAL(18,4)      NOT NULL,
        AdjustedDurationMonths  INT                NOT NULL,
        MonthsElapsed           INT                NOT NULL CONSTRAINT DF_ConstructionProject_MonthsElapsed DEFAULT 0,
        Status                  NVARCHAR(20)       NOT NULL CONSTRAINT DF_ConstructionProject_Status DEFAULT 'InProgress',
        CompletedSimulationDate DATE               NULL,
        Notes                   NVARCHAR(500)      NULL,
        CreatedDateTime         DATETIME2(3)       NOT NULL CONSTRAINT DF_ConstructionProject_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_ConstructionProject_City FOREIGN KEY (CityID) REFERENCES dbo.City (CityID),
        CONSTRAINT FK_ConstructionProject_BuildingType FOREIGN KEY (BuildingTypeID) REFERENCES dbo.BuildingType (BuildingTypeID),
        CONSTRAINT CK_ConstructionProject_BuildingsOrdered_Positive CHECK (BuildingsOrdered >= 1),
        CONSTRAINT CK_ConstructionProject_AdjustedDurationMonths_Positive CHECK (AdjustedDurationMonths >= 1),
        CONSTRAINT CK_ConstructionProject_MonthsElapsed_NonNegative CHECK (MonthsElapsed >= 0),
        CONSTRAINT CK_ConstructionProject_Status CHECK (Status IN ('InProgress', 'Complete')),
        CONSTRAINT CK_ConstructionProject_Completed_Consistency CHECK (
            (Status = 'InProgress' AND CompletedSimulationDate IS NULL)
            OR (Status = 'Complete' AND CompletedSimulationDate IS NOT NULL)
        )
    );

    -- Not unique (see notes above): every order-time and tick-time lookup
    -- filters a city's projects by status.
    CREATE NONCLUSTERED INDEX IX_ConstructionProject_City_Status ON dbo.ConstructionProject (CityID, Status);
END
GO
