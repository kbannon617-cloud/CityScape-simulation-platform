-- 0015_create_vehicle_tables.sql
-- Implements the Vehicles & Logistics piece of the Infrastructure &
-- Assets domain (named in Document 3 Amendment 1, assigned to Milestone 3
-- by ADR-0005 / Document 8 Amendment 1), from the design-concept
-- workbook's Vehicle Catalog, Logistics Mode Catalog, and Vehicle
-- Assignments sheets.
--
-- Scope boundary, matching the Production catalog-first pattern
-- (migrations 0011-0012 before execution in the ProductionService step):
-- this is the CATALOG and current CITY STATE (what vehicle types exist,
-- which building types need them, how many a city currently owns) - not
-- yet a running "order N vehicles" execution service that deducts
-- Timber/Stone/currency and increments CityVehicle. That is a deliberate
-- next step, mirroring how ProductionService followed the Production
-- catalog.
--
-- BuildingVehicleRequirement mirrors ProductionFlow's role for
-- BuildingType: it is the normalized source of which vehicle type a
-- building type requires, capacity per building, and how many are
-- included free vs. must be ordered separately - taken from the
-- "+Vehicle Assignments" sheet's per-building columns.

-- ============================================================
-- VehicleType (Infrastructure & Assets domain reference data)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'VehicleType')
BEGIN
    CREATE TABLE dbo.VehicleType (
        VehicleTypeID             INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code                      NVARCHAR(10)      NOT NULL,
        Type                      NVARCHAR(30)      NOT NULL,
        Class                     NVARCHAR(30)      NOT NULL,
        TimberRequiredPerVehicle  DECIMAL(18,4)     NOT NULL CONSTRAINT DF_VehicleType_TimberRequiredPerVehicle DEFAULT 0,
        StoneRequiredPerVehicle   DECIMAL(18,4)     NOT NULL CONSTRAINT DF_VehicleType_StoneRequiredPerVehicle DEFAULT 0,
        BaseMaintenancePerVehicle DECIMAL(18,4)     NOT NULL CONSTRAINT DF_VehicleType_BaseMaintenancePerVehicle DEFAULT 0,
        MaximumPerBuilding        INT               NULL,
        IncludedVehicleRule       NVARCHAR(200)     NULL,
        Notes                     NVARCHAR(500)     NULL,
        Size                      NVARCHAR(20)      NULL,
        RequiredTechCode          NVARCHAR(20)      NULL,
        CreatedDateTime           DATETIME2(3)      NOT NULL CONSTRAINT DF_VehicleType_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_VehicleType_Code UNIQUE (Code)
    );
END
GO

-- ============================================================
-- TransportMode (Infrastructure & Assets domain reference data)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'TransportMode')
BEGIN
    CREATE TABLE dbo.TransportMode (
        TransportModeID                    INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code                                NVARCHAR(10)      NOT NULL,
        ModeName                            NVARCHAR(30)      NOT NULL,
        TransportFamily                     NVARCHAR(30)      NOT NULL,
        VehicleTypeID                       INT               NOT NULL,
        Size                                NVARCHAR(20)      NULL,
        GoodsCapacityPerVehiclePerMonth      DECIMAL(18,4)     NOT NULL CONSTRAINT DF_TransportMode_GoodsCapacityPerVehiclePerMonth DEFAULT 0,
        TripsPerMonth                       INT               NOT NULL CONSTRAINT DF_TransportMode_TripsPerMonth DEFAULT 0,
        TeamstersPerVehicle                 INT               NOT NULL CONSTRAINT DF_TransportMode_TeamstersPerVehicle DEFAULT 0,
        BaseMaintenancePerVehicle           DECIMAL(18,4)     NOT NULL CONSTRAINT DF_TransportMode_BaseMaintenancePerVehicle DEFAULT 0,
        GoodsCapacityPerTeamsterPerMonth    DECIMAL(18,4)     NOT NULL CONSTRAINT DF_TransportMode_GoodsCapacityPerTeamsterPerMonth DEFAULT 0,
        TimberRequiredPerVehicle            DECIMAL(18,4)     NOT NULL CONSTRAINT DF_TransportMode_TimberRequiredPerVehicle DEFAULT 0,
        StoneRequiredPerVehicle             DECIMAL(18,4)     NOT NULL CONSTRAINT DF_TransportMode_StoneRequiredPerVehicle DEFAULT 0,
        MaximumVehiclesPerDepot             INT               NULL,
        -- Plain text, not a FK: refers to a required building type (e.g.
        -- "Dirt Road") conceptually, but no formal building-requires-
        -- building relationship table exists yet.
        InfrastructureRequired              NVARCHAR(50)      NULL,
        RequiredTechCode                    NVARCHAR(20)      NULL,
        Status                              NVARCHAR(20)      NOT NULL CONSTRAINT DF_TransportMode_Status DEFAULT 'Active',
        Notes                               NVARCHAR(500)     NULL,
        CreatedDateTime                     DATETIME2(3)      NOT NULL CONSTRAINT DF_TransportMode_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_TransportMode_Code UNIQUE (Code),
        CONSTRAINT FK_TransportMode_VehicleType FOREIGN KEY (VehicleTypeID) REFERENCES dbo.VehicleType (VehicleTypeID)
    );
END
GO

-- ============================================================
-- BuildingVehicleRequirement (which BuildingType needs which
-- VehicleType, and how many are included free vs. orderable)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'BuildingVehicleRequirement')
BEGIN
    CREATE TABLE dbo.BuildingVehicleRequirement (
        BuildingVehicleRequirementID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        BuildingTypeID                INT               NOT NULL,
        VehicleTypeID                 INT               NOT NULL,
        CapacityPerBuilding           INT               NOT NULL CONSTRAINT DF_BuildingVehicleRequirement_CapacityPerBuilding DEFAULT 0,
        IncludedPerBuilding           INT               NOT NULL CONSTRAINT DF_BuildingVehicleRequirement_IncludedPerBuilding DEFAULT 0,
        CreatedDateTime                DATETIME2(3)      NOT NULL CONSTRAINT DF_BuildingVehicleRequirement_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_BuildingVehicleRequirement_BuildingType FOREIGN KEY (BuildingTypeID) REFERENCES dbo.BuildingType (BuildingTypeID),
        CONSTRAINT FK_BuildingVehicleRequirement_VehicleType FOREIGN KEY (VehicleTypeID) REFERENCES dbo.VehicleType (VehicleTypeID),
        CONSTRAINT UQ_BuildingVehicleRequirement_BuildingType_VehicleType UNIQUE (BuildingTypeID, VehicleTypeID)
    );
END
GO

-- ============================================================
-- CityVehicle (per-city instance count; mirrors the Building pattern
-- from migration 0011 - one row per city per vehicle type)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'CityVehicle')
BEGIN
    CREATE TABLE dbo.CityVehicle (
        CityVehicleID   INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        CityID          INT               NOT NULL,
        VehicleTypeID   INT               NOT NULL,
        Count           INT               NOT NULL CONSTRAINT DF_CityVehicle_Count DEFAULT 0,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_CityVehicle_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_CityVehicle_City FOREIGN KEY (CityID) REFERENCES dbo.City (CityID),
        CONSTRAINT FK_CityVehicle_VehicleType FOREIGN KEY (VehicleTypeID) REFERENCES dbo.VehicleType (VehicleTypeID),
        CONSTRAINT UQ_CityVehicle_City_VehicleType UNIQUE (CityID, VehicleTypeID),
        CONSTRAINT CK_CityVehicle_Count_NonNegative CHECK (Count >= 0)
    );

    CREATE NONCLUSTERED INDEX IX_CityVehicle_CityID ON dbo.CityVehicle (CityID);
END
GO
