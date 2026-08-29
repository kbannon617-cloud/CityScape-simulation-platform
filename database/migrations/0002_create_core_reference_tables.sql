-- 0002_create_core_reference_tables.sql
-- Implements the initial core tables from Document 5 (Physical Database
-- Design & SQL Server Implementation): Simulation, Scenario, SimulationRun,
-- Currency, UnitOfMeasure, World, Region, City.
--
-- Created in dependency order: reference tables with no FKs first, then
-- geography (World -> Region -> City), then simulation control
-- (Simulation -> Scenario -> SimulationRun).

-- ============================================================
-- Currency (reference data - INT identity per ID Precision Strategy)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Currency')
BEGIN
    CREATE TABLE dbo.Currency (
        CurrencyID      INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code            NVARCHAR(10)      NOT NULL,
        Name            NVARCHAR(100)     NOT NULL,
        Symbol          NVARCHAR(5)       NULL,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_Currency_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_Currency_Code UNIQUE (Code)
    );
END
GO

-- ============================================================
-- UnitOfMeasure (reference data)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'UnitOfMeasure')
BEGIN
    CREATE TABLE dbo.UnitOfMeasure (
        UnitOfMeasureID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code            NVARCHAR(10)      NOT NULL,
        Name            NVARCHAR(100)     NOT NULL,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_UnitOfMeasure_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_UnitOfMeasure_Code UNIQUE (Code)
    );
END
GO

-- ============================================================
-- World (reference data - predetermined, authoritative geography)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'World')
BEGIN
    CREATE TABLE dbo.World (
        WorldID         INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Name            NVARCHAR(100)     NOT NULL,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_World_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_World_Name UNIQUE (Name)
    );
END
GO

-- ============================================================
-- Region (FK -> World)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Region')
BEGIN
    CREATE TABLE dbo.Region (
        RegionID        INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        WorldID         INT               NOT NULL,
        Name            NVARCHAR(100)     NOT NULL,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_Region_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Region_World FOREIGN KEY (WorldID) REFERENCES dbo.World (WorldID),
        CONSTRAINT UQ_Region_WorldID_Name UNIQUE (WorldID, Name)
    );

    CREATE NONCLUSTERED INDEX IX_Region_WorldID ON dbo.Region (WorldID);
END
GO

-- ============================================================
-- City (FK -> Region)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'City')
BEGIN
    CREATE TABLE dbo.City (
        CityID          INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        RegionID        INT               NOT NULL,
        Name            NVARCHAR(100)     NOT NULL,
        -- MVP scope is exactly one primary active city (Document 4).
        IsPrimaryActive BIT               NOT NULL CONSTRAINT DF_City_IsPrimaryActive DEFAULT 0,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_City_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_City_Region FOREIGN KEY (RegionID) REFERENCES dbo.Region (RegionID),
        CONSTRAINT UQ_City_RegionID_Name UNIQUE (RegionID, Name)
    );

    CREATE NONCLUSTERED INDEX IX_City_RegionID ON dbo.City (RegionID);
END
GO

-- ============================================================
-- Simulation (top-level named simulation/config)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Simulation')
BEGIN
    CREATE TABLE dbo.Simulation (
        SimulationID    INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Name            NVARCHAR(100)     NOT NULL,
        Description     NVARCHAR(500)     NULL,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_Simulation_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_Simulation_Name UNIQUE (Name)
    );
END
GO

-- ============================================================
-- Scenario (FK -> Simulation; self-FK for inheritance/delta overrides)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Scenario')
BEGIN
    CREATE TABLE dbo.Scenario (
        ScenarioID       INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        SimulationID     INT               NOT NULL,
        -- NULL = base scenario. Non-NULL = child scenario inheriting base
        -- context and storing delta overrides only (per approved ADR).
        ParentScenarioID INT               NULL,
        Name             NVARCHAR(100)     NOT NULL,
        Description      NVARCHAR(500)     NULL,
        CreatedDateTime  DATETIME2(3)      NOT NULL CONSTRAINT DF_Scenario_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Scenario_Simulation FOREIGN KEY (SimulationID) REFERENCES dbo.Simulation (SimulationID),
        CONSTRAINT FK_Scenario_ParentScenario FOREIGN KEY (ParentScenarioID) REFERENCES dbo.Scenario (ScenarioID),
        CONSTRAINT UQ_Scenario_SimulationID_Name UNIQUE (SimulationID, Name)
    );

    CREATE NONCLUSTERED INDEX IX_Scenario_SimulationID ON dbo.Scenario (SimulationID);
    CREATE NONCLUSTERED INDEX IX_Scenario_ParentScenarioID ON dbo.Scenario (ParentScenarioID);
END
GO

-- ============================================================
-- SimulationRun (FK -> Scenario)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SimulationRun')
BEGIN
    CREATE TABLE dbo.SimulationRun (
        SimulationRunID          INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ScenarioID               INT               NOT NULL,
        StartSimulationDate      DATE              NOT NULL,
        CurrentSimulationDate    DATE              NOT NULL,
        -- BIGINT: tick counts grow across a run's lifetime (ADR register:
        -- "BIGINT for high-volume Operational Data, Ticks, and Events").
        CurrentSimulationTickID  BIGINT            NOT NULL CONSTRAINT DF_SimulationRun_CurrentSimulationTickID DEFAULT 0,
        Status                   NVARCHAR(20)      NOT NULL CONSTRAINT DF_SimulationRun_Status DEFAULT 'Active',
        CreatedDateTime          DATETIME2(3)      NOT NULL CONSTRAINT DF_SimulationRun_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_SimulationRun_Scenario FOREIGN KEY (ScenarioID) REFERENCES dbo.Scenario (ScenarioID),
        CONSTRAINT CK_SimulationRun_Status CHECK (Status IN ('Active', 'Completed', 'Failed', 'Cancelled'))
    );

    CREATE NONCLUSTERED INDEX IX_SimulationRun_ScenarioID ON dbo.SimulationRun (ScenarioID);
END
GO
