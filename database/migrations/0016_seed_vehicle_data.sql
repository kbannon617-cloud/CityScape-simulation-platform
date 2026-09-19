-- 0016_seed_vehicle_data.sql
-- Seeds the Vehicle Catalog, Logistics Mode Catalog, and per-building
-- vehicle requirements. No CityVehicle rows are seeded for CityScape:
-- per the "+Vehicle Assignments" sheet's own data, CityScape currently
-- owns 0 Trout Fisheries and 0 Teamster Depots (the only two building
-- types that require vehicles), so it genuinely has 0 vehicles - a
-- missing CityVehicle row means zero, per the sparse-seeding convention
-- already used for Building and CityInventory.

-- ============================================================
-- VehicleType
-- ============================================================
INSERT INTO dbo.VehicleType (Code, Type, Class, TimberRequiredPerVehicle, StoneRequiredPerVehicle, BaseMaintenancePerVehicle, MaximumPerBuilding, IncludedVehicleRule, Notes, Size)
SELECT v.Code, v.Type, v.Class, v.TimberRequiredPerVehicle, v.StoneRequiredPerVehicle, v.BaseMaintenancePerVehicle, v.MaximumPerBuilding, v.IncludedVehicleRule, v.Notes, v.Size
FROM (VALUES
    ('V-001', 'Boat', 'Watercraft',     50, 0, 20, 2, 'First Boat included with Trout Fishery building order.', 'Additional Boats ordered separately.',        'Small'),
    ('V-002', 'Cart', 'Ground Freight', 20, 0, 5,  5, 'Carts are assigned to Teamster Depots.',                 'Initial local freight transport mode.',        'Small')
) AS v(Code, Type, Class, TimberRequiredPerVehicle, StoneRequiredPerVehicle, BaseMaintenancePerVehicle, MaximumPerBuilding, IncludedVehicleRule, Notes, Size)
WHERE NOT EXISTS (SELECT 1 FROM dbo.VehicleType vt WHERE vt.Code = v.Code);
GO

-- ============================================================
-- TransportMode
-- ============================================================
DECLARE @CartVehicleTypeID INT;
SELECT @CartVehicleTypeID = VehicleTypeID FROM dbo.VehicleType WHERE Code = 'V-002';

IF NOT EXISTS (SELECT 1 FROM dbo.TransportMode WHERE Code = 'TM-001')
    INSERT INTO dbo.TransportMode (
        Code, ModeName, TransportFamily, VehicleTypeID, Size,
        GoodsCapacityPerVehiclePerMonth, TripsPerMonth, TeamstersPerVehicle,
        BaseMaintenancePerVehicle, GoodsCapacityPerTeamsterPerMonth,
        TimberRequiredPerVehicle, StoneRequiredPerVehicle,
        MaximumVehiclesPerDepot, InfrastructureRequired, Status, Notes
    )
    VALUES (
        'TM-001', 'Cart', 'Ground', @CartVehicleTypeID, 'Small',
        100, 1, 1,
        5, 100,
        20, 0,
        5, 'Dirt Road', 'Active', 'Initial Teamster freight mode.'
    );
GO

-- ============================================================
-- BuildingVehicleRequirement (Trout Fishery -> Boat, Teamster Depot -> Cart)
-- ============================================================
DECLARE @TroutFisheryTypeID INT, @TeamsterDepotTypeID INT;
DECLARE @BoatVehicleTypeID INT, @CartVehicleTypeID2 INT;

SELECT @TroutFisheryTypeID = BuildingTypeID FROM dbo.BuildingType WHERE Name = 'Trout Fishery';
SELECT @TeamsterDepotTypeID = BuildingTypeID FROM dbo.BuildingType WHERE Name = 'Teamster Depot';
SELECT @BoatVehicleTypeID = VehicleTypeID FROM dbo.VehicleType WHERE Code = 'V-001';
SELECT @CartVehicleTypeID2 = VehicleTypeID FROM dbo.VehicleType WHERE Code = 'V-002';

IF @TroutFisheryTypeID IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM dbo.BuildingVehicleRequirement
    WHERE BuildingTypeID = @TroutFisheryTypeID AND VehicleTypeID = @BoatVehicleTypeID
)
    INSERT INTO dbo.BuildingVehicleRequirement (BuildingTypeID, VehicleTypeID, CapacityPerBuilding, IncludedPerBuilding)
    VALUES (@TroutFisheryTypeID, @BoatVehicleTypeID, 2, 1);

IF @TeamsterDepotTypeID IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM dbo.BuildingVehicleRequirement
    WHERE BuildingTypeID = @TeamsterDepotTypeID AND VehicleTypeID = @CartVehicleTypeID2
)
    INSERT INTO dbo.BuildingVehicleRequirement (BuildingTypeID, VehicleTypeID, CapacityPerBuilding, IncludedPerBuilding)
    VALUES (@TeamsterDepotTypeID, @CartVehicleTypeID2, 100, 5);
GO
