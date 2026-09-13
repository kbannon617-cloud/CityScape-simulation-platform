-- 0005_create_population_tables.sql
-- Implements the Population domain per Document 8 Milestone 2 scope:
-- aggregate population groups and the essential-needs/aging configuration
-- that drives them. Per ADR-0005, this models POPULATION NEEDS AS
-- CATEGORIES (e.g. "Food"), not specific Resource items - the Resource
-- Catalog itself (Wheat, Trout, etc.) is Economy/Inventory domain scope,
-- assigned to Milestone 3. Wiring a need category to real inventory is
-- M3+ work, not built here.
--
-- ScenarioParameter is introduced as a general-purpose, scenario-scoped
-- configuration mechanism (key/value), so the aging rate below - and any
-- future M2/M3 rate that needs to be tunable without a schema or code
-- change - has a home. This directly serves ADR-0005's explicit
-- requirement that these rates be data, not hardcoded constants.

-- ============================================================
-- PopulationGroupType (reference data)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'PopulationGroupType')
BEGIN
    CREATE TABLE dbo.PopulationGroupType (
        PopulationGroupTypeID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code                  NVARCHAR(20)      NOT NULL,
        Name                  NVARCHAR(100)     NOT NULL,
        CreatedDateTime       DATETIME2(3)      NOT NULL CONSTRAINT DF_PopulationGroupType_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_PopulationGroupType_Code UNIQUE (Code)
    );
END
GO

-- ============================================================
-- PopulationGroup (FK -> City, FK -> PopulationGroupType)
-- One row per city per group type; Count is the aggregate headcount.
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'PopulationGroup')
BEGIN
    CREATE TABLE dbo.PopulationGroup (
        PopulationGroupID     INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        CityID                INT               NOT NULL,
        PopulationGroupTypeID INT               NOT NULL,
        Count                 INT               NOT NULL CONSTRAINT DF_PopulationGroup_Count DEFAULT 0,
        CreatedDateTime       DATETIME2(3)      NOT NULL CONSTRAINT DF_PopulationGroup_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_PopulationGroup_City FOREIGN KEY (CityID) REFERENCES dbo.City (CityID),
        CONSTRAINT FK_PopulationGroup_PopulationGroupType FOREIGN KEY (PopulationGroupTypeID) REFERENCES dbo.PopulationGroupType (PopulationGroupTypeID),
        CONSTRAINT UQ_PopulationGroup_City_Type UNIQUE (CityID, PopulationGroupTypeID),
        CONSTRAINT CK_PopulationGroup_Count_NonNegative CHECK (Count >= 0)
    );

    CREATE NONCLUSTERED INDEX IX_PopulationGroup_CityID ON dbo.PopulationGroup (CityID);
END
GO

-- ============================================================
-- ScenarioParameter (FK -> Scenario) - generic configurable key/value
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'ScenarioParameter')
BEGIN
    CREATE TABLE dbo.ScenarioParameter (
        ScenarioParameterID INT IDENTITY(1,1)   NOT NULL PRIMARY KEY,
        ScenarioID          INT                 NOT NULL,
        ParameterKey        NVARCHAR(100)       NOT NULL,
        ParameterValue      DECIMAL(18,6)       NOT NULL,
        CreatedDateTime     DATETIME2(3)        NOT NULL CONSTRAINT DF_ScenarioParameter_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_ScenarioParameter_Scenario FOREIGN KEY (ScenarioID) REFERENCES dbo.Scenario (ScenarioID),
        CONSTRAINT UQ_ScenarioParameter_ScenarioID_Key UNIQUE (ScenarioID, ParameterKey)
    );

    CREATE NONCLUSTERED INDEX IX_ScenarioParameter_ScenarioID ON dbo.ScenarioParameter (ScenarioID);
END
GO
