-- 0007_create_needs_tables.sql
-- Implements essential needs per Document 4 / Master Prompt Section 3
-- ("daily essential needs consumption, e.g. food, heating, basic goods").
--
-- Scope boundary (per ADR-0005): needs are modeled as CATEGORIES with a
-- per-person consumption rate, reusing the existing UnitOfMeasure table
-- from Milestone 1 (Economic Unit Isolation principle: quantity and unit
-- stay explicit and separate). This does NOT model specific Resource
-- Catalog items (Wheat, Coal, etc.) or deplete any city inventory - that
-- requires the Economy/Inventory domain, assigned to Milestone 3.

-- ============================================================
-- NeedType (reference data)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'NeedType')
BEGIN
    CREATE TABLE dbo.NeedType (
        NeedTypeID      INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code            NVARCHAR(20)      NOT NULL,
        Name            NVARCHAR(100)     NOT NULL,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_NeedType_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_NeedType_Code UNIQUE (Code)
    );
END
GO

-- ============================================================
-- NeedConsumptionRate (FK -> PopulationGroupType, NeedType, UnitOfMeasure)
-- One row per (group type, need type): how much of that need one person
-- in that group consumes per day.
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'NeedConsumptionRate')
BEGIN
    CREATE TABLE dbo.NeedConsumptionRate (
        NeedConsumptionRateID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        PopulationGroupTypeID INT               NOT NULL,
        NeedTypeID            INT               NOT NULL,
        QuantityPerPersonPerDay DECIMAL(10,4)   NOT NULL,
        UnitOfMeasureID       INT               NOT NULL,
        CreatedDateTime       DATETIME2(3)      NOT NULL CONSTRAINT DF_NeedConsumptionRate_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_NeedConsumptionRate_PopulationGroupType FOREIGN KEY (PopulationGroupTypeID) REFERENCES dbo.PopulationGroupType (PopulationGroupTypeID),
        CONSTRAINT FK_NeedConsumptionRate_NeedType FOREIGN KEY (NeedTypeID) REFERENCES dbo.NeedType (NeedTypeID),
        CONSTRAINT FK_NeedConsumptionRate_UnitOfMeasure FOREIGN KEY (UnitOfMeasureID) REFERENCES dbo.UnitOfMeasure (UnitOfMeasureID),
        CONSTRAINT UQ_NeedConsumptionRate_GroupType_NeedType UNIQUE (PopulationGroupTypeID, NeedTypeID),
        CONSTRAINT CK_NeedConsumptionRate_QuantityNonNegative CHECK (QuantityPerPersonPerDay >= 0)
    );

    CREATE NONCLUSTERED INDEX IX_NeedConsumptionRate_NeedTypeID ON dbo.NeedConsumptionRate (NeedTypeID);
END
GO
