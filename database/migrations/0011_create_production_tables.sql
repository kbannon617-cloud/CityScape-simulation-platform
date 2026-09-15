-- 0011_create_production_tables.sql
-- Implements the Production and Inventory-reference domains per Document 3,
-- from the design-concept workbook's Building Catalog and Building
-- Production Flows Catalog.
--
-- Design notes:
-- - Resource is Inventory-domain reference data (Milestone 3 scope per
--   ADR-0005), needed here because ProductionFlow references it. Full
--   city-level stockpile tracking (CityInventory) is a separate,
--   not-yet-built piece.
-- - Resource.UnitOfMeasureID is a required FK to Milestone 1's
--   UnitOfMeasure table, per the approved Economic Unit Isolation
--   principle (quantity and unit stay explicit and separate - a bare
--   ProductionFlow.UnitsPerBuildingPerMonth number with no attached unit
--   would violate this). All resources are seeded against 'EA' (Each) as
--   a known simplification: the workbook does not specify precise
--   physical units (kg vs. each) per resource.
-- - BuildingType deliberately does NOT store Monthly Output / Output
--   Resource, even though the workbook's Building Catalog sheet has those
--   columns - the workbook itself marks them "legacy", superseded by the
--   normalized Production Flows Catalog. ProductionFlow is the single
--   source of truth for what a building consumes/produces, avoiding two
--   representations of the same fact drifting out of sync.
-- - Building mirrors PopulationGroup's shape exactly: an aggregate Count
--   per (City, BuildingType) pair, not a per-instance row. Matches the
--   MVP's existing simplicity; per-instance building state is not in
--   scope yet.
-- - RequiredTechID is a plain nullable INT with NO foreign key, since the
--   Technology table does not exist yet (Milestone 8 per ADR-0005). The
--   FK will be added via a future migration once it does.
-- - Vehicle-related Building Catalog columns (Vehicle Type, Vehicle
--   Capacity/Building, Vehicles Assigned/Building) are stored as plain
--   descriptive columns for now, NOT a real FK to a Vehicle table -
--   Vehicles & Logistics is a separate, not-yet-built M3 piece.

-- ============================================================
-- Resource (Inventory-domain reference data)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Resource')
BEGIN
    CREATE TABLE dbo.Resource (
        ResourceID           INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code                 NVARCHAR(10)      NOT NULL,
        Name                 NVARCHAR(100)     NOT NULL,
        ResourceClass        NVARCHAR(50)      NOT NULL,
        -- Tri-state per the workbook: 'Yes', 'No', or 'Future' (produced
        -- but not yet wired into population food consumption).
        PopulationFoodStatus NVARCHAR(10)      NOT NULL CONSTRAINT DF_Resource_PopulationFoodStatus DEFAULT 'No',
        TrackedInStorage     BIT               NOT NULL CONSTRAINT DF_Resource_TrackedInStorage DEFAULT 1,
        UnitOfMeasureID      INT               NOT NULL,
        Notes                NVARCHAR(500)     NULL,
        CreatedDateTime      DATETIME2(3)      NOT NULL CONSTRAINT DF_Resource_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_Resource_Code UNIQUE (Code),
        CONSTRAINT FK_Resource_UnitOfMeasure FOREIGN KEY (UnitOfMeasureID) REFERENCES dbo.UnitOfMeasure (UnitOfMeasureID),
        CONSTRAINT CK_Resource_PopulationFoodStatus CHECK (PopulationFoodStatus IN ('Yes', 'No', 'Future'))
    );
END
GO

-- ============================================================
-- BuildingType (Production-domain reference/catalog data)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'BuildingType')
BEGIN
    CREATE TABLE dbo.BuildingType (
        BuildingTypeID              INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code                        NVARCHAR(10)      NOT NULL,
        Category                    NVARCHAR(50)      NOT NULL,
        BuildingSubType             NVARCHAR(50)      NOT NULL,
        Subcategory                 NVARCHAR(50)      NULL,
        Name                        NVARCHAR(100)     NOT NULL,
        HousingCapacity             INT               NOT NULL CONSTRAINT DF_BuildingType_HousingCapacity DEFAULT 0,
        WorkersPerBuilding          INT               NOT NULL CONSTRAINT DF_BuildingType_WorkersPerBuilding DEFAULT 0,
        ConstructionCost            DECIMAL(18,4)     NOT NULL CONSTRAINT DF_BuildingType_ConstructionCost DEFAULT 0,
        MonthlyMaintenance          DECIMAL(18,4)     NOT NULL CONSTRAINT DF_BuildingType_MonthlyMaintenance DEFAULT 0,
        VehicleTypeCode             NVARCHAR(20)      NULL,
        VehicleCapacityPerBuilding  INT               NOT NULL CONSTRAINT DF_BuildingType_VehicleCapacityPerBuilding DEFAULT 0,
        VehiclesAssignedPerBuilding INT               NOT NULL CONSTRAINT DF_BuildingType_VehiclesAssignedPerBuilding DEFAULT 0,
        TimberRequiredPerBuilding   DECIMAL(18,4)     NOT NULL CONSTRAINT DF_BuildingType_TimberRequiredPerBuilding DEFAULT 0,
        StoneRequiredPerBuilding    DECIMAL(18,4)     NOT NULL CONSTRAINT DF_BuildingType_StoneRequiredPerBuilding DEFAULT 0,
        StorageCapacityShared       INT               NULL,
        IsActive                    BIT               NOT NULL CONSTRAINT DF_BuildingType_IsActive DEFAULT 1,
        Size                        NVARCHAR(20)      NULL,
        RequiredTechID              INT               NULL,  -- no FK yet: Technology table does not exist (M8)
        Notes                       NVARCHAR(500)     NULL,
        CreatedDateTime             DATETIME2(3)      NOT NULL CONSTRAINT DF_BuildingType_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_BuildingType_Code UNIQUE (Code)
    );
END
GO

-- ============================================================
-- Building (aggregate count per City/BuildingType, mirrors PopulationGroup)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Building')
BEGIN
    CREATE TABLE dbo.Building (
        BuildingID      INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        CityID          INT               NOT NULL,
        BuildingTypeID  INT               NOT NULL,
        Count           INT               NOT NULL CONSTRAINT DF_Building_Count DEFAULT 0,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_Building_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Building_City FOREIGN KEY (CityID) REFERENCES dbo.City (CityID),
        CONSTRAINT FK_Building_BuildingType FOREIGN KEY (BuildingTypeID) REFERENCES dbo.BuildingType (BuildingTypeID),
        CONSTRAINT UQ_Building_City_Type UNIQUE (CityID, BuildingTypeID),
        CONSTRAINT CK_Building_Count_NonNegative CHECK (Count >= 0)
    );

    CREATE NONCLUSTERED INDEX IX_Building_CityID ON dbo.Building (CityID);
END
GO

-- ============================================================
-- ProductionFlow (single source of truth for building inputs/outputs)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'ProductionFlow')
BEGIN
    CREATE TABLE dbo.ProductionFlow (
        ProductionFlowID          INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code                      NVARCHAR(10)      NOT NULL,
        BuildingTypeID            INT               NOT NULL,
        FlowType                  NVARCHAR(10)      NOT NULL,
        ResourceID                INT               NOT NULL,
        UnitsPerBuildingPerMonth  DECIMAL(18,4)     NOT NULL,
        FlowRole                  NVARCHAR(30)      NULL,
        RequiredTechID            INT               NULL,  -- no FK yet: Technology table does not exist (M8)
        Notes                     NVARCHAR(500)     NULL,
        CreatedDateTime           DATETIME2(3)      NOT NULL CONSTRAINT DF_ProductionFlow_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_ProductionFlow_Code UNIQUE (Code),
        CONSTRAINT FK_ProductionFlow_BuildingType FOREIGN KEY (BuildingTypeID) REFERENCES dbo.BuildingType (BuildingTypeID),
        CONSTRAINT FK_ProductionFlow_Resource FOREIGN KEY (ResourceID) REFERENCES dbo.Resource (ResourceID),
        CONSTRAINT CK_ProductionFlow_FlowType CHECK (FlowType IN ('Input', 'Output')),
        CONSTRAINT CK_ProductionFlow_UnitsNonNegative CHECK (UnitsPerBuildingPerMonth >= 0)
    );

    CREATE NONCLUSTERED INDEX IX_ProductionFlow_BuildingTypeID ON dbo.ProductionFlow (BuildingTypeID);
    CREATE NONCLUSTERED INDEX IX_ProductionFlow_ResourceID ON dbo.ProductionFlow (ResourceID);
END
GO
