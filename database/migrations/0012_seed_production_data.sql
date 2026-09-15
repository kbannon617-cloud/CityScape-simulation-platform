-- 0012_seed_production_data.sql
-- Seeds Resource, BuildingType, Building, and ProductionFlow from the
-- design-concept workbook's Building Catalog and Building Production
-- Flows Catalog, with the Resource ID conflict corrected per the project
-- owner's decision (2026-09-13): Production Flows Catalog is authoritative.
-- Corrected mapping: R-008=Flax, R-009=Eggs, R-010=Lentils, R-011=Ore
-- (Ore moved from R-008, since nothing currently produces/consumes it -
-- it is marked "Reserved for future extraction" in the workbook).
-- The source workbook's Resource Catalog sheet should be corrected to
-- match; this seed data does not wait on that correction.
--
-- All figures below carry the same status as every other seeded number in
-- this project: real structure from the workbook, unvalidated/unbalanced
-- values, easily changed via data UPDATE.

-- ============================================================
-- Resource (corrected mapping)
-- ============================================================
DECLARE @EaUnitID INT;
SELECT @EaUnitID = UnitOfMeasureID FROM dbo.UnitOfMeasure WHERE Code = 'EA';

INSERT INTO dbo.Resource (Code, Name, ResourceClass, PopulationFoodStatus, TrackedInStorage, UnitOfMeasureID, Notes)
SELECT v.Code, v.Name, v.ResourceClass, v.PopulationFoodStatus, v.TrackedInStorage, @EaUnitID, v.Notes
FROM (VALUES
    ('R-001', 'Wheat',   'Agricultural Goods', 'Yes',    1, 'Primary cereal food resource.'),
    ('R-002', 'Trout',   'Fishing Goods',      'Yes',    1, 'Freshwater fish food resource.'),
    ('R-003', 'Stone',   'Minerals',           'No',     1, 'Construction material.'),
    ('R-004', 'Timber',  'Construction Goods', 'No',     1, 'Raw wood material and Saw Mill input.'),
    ('R-005', 'Lumber',  'Construction Goods', 'No',     1, 'Saw Mill output.'),
    ('R-006', 'Oats',    'Agricultural Goods', 'Future', 1, 'Oat Farm output; not yet included in population food consumption.'),
    ('R-007', 'Figs',    'Agricultural Goods', 'Future', 1, 'Fig Garden output; not yet included in population food consumption.'),
    ('R-008', 'Flax',    'Agricultural Goods', 'No',     1, 'Corrected from Resource Catalog conflict - Production Flows Catalog authoritative.'),
    ('R-009', 'Eggs',    'Agricultural Goods', 'Yes',    1, 'Corrected from Resource Catalog conflict - Production Flows Catalog authoritative.'),
    ('R-010', 'Lentils', 'Agricultural Goods', 'Yes',    1, NULL),
    ('R-011', 'Ore',     'Raw Material',       'No',     1, 'Reserved for future extraction. Moved from R-008 during ID conflict correction.')
) AS v(Code, Name, ResourceClass, PopulationFoodStatus, TrackedInStorage, Notes)
WHERE NOT EXISTS (SELECT 1 FROM dbo.Resource r WHERE r.Code = v.Code);
GO

-- ============================================================
-- BuildingType (15 buildings; Monthly Output / Output Resource columns
-- deliberately NOT carried over - see migration 0011 header)
-- ============================================================
INSERT INTO dbo.BuildingType (
    Code, Category, BuildingSubType, Subcategory, Name,
    HousingCapacity, WorkersPerBuilding, ConstructionCost, MonthlyMaintenance,
    VehicleTypeCode, VehicleCapacityPerBuilding, VehiclesAssignedPerBuilding,
    TimberRequiredPerBuilding, StoneRequiredPerBuilding, StorageCapacityShared,
    IsActive, Size, Notes
)
SELECT v.Code, v.Category, v.BuildingSubType, v.Subcategory, v.Name,
       v.HousingCapacity, v.WorkersPerBuilding, v.ConstructionCost, v.MonthlyMaintenance,
       v.VehicleTypeCode, v.VehicleCapacityPerBuilding, v.VehiclesAssignedPerBuilding,
       v.TimberRequiredPerBuilding, v.StoneRequiredPerBuilding, v.StorageCapacityShared,
       v.IsActive, v.Size, v.Notes
FROM (VALUES
    ('B-001', 'Housing',             'Low Density',  'Rural',               'Cottage',            20, 0,  500.00,  5.00, NULL,   0, 0, 100, 25,  NULL, 1, 'Small', 'Provides housing capacity.'),
    ('B-002', 'Agricultural',        'Food Crops',   'Cereals',             'Wheat Farm',          0, 5,  750.00, 20.00, NULL,   0, 0,  50, 25,  NULL, 1, 'Small', 'Produces Wheat each month.'),
    ('B-003', 'Resource Extraction', 'Minerals',     'Surface Mining',      'Stone Quarry',        0, 6,  900.00, 25.00, NULL,   0, 0, 200,  0,  NULL, 1, 'Small', 'Produces Stone each month.'),
    ('B-004', 'Fishing',             'Wild',         'Freshwater Fishing',  'Trout Fishery',       0, 4,  800.00, 20.00, 'Boat', 2, 1, 200, 25,  NULL, 1, 'Small', 'Produces Trout each month. First Boat included.'),
    ('B-005', 'Resource Extraction', 'Forestry',     'Soft Wood',           'Lumber Camp',         0, 4,  600.00, 15.00, NULL,   0, 0,  25,  0,  NULL, 1, 'Small', 'Produces Timber each month.'),
    ('B-006', 'Utility',             'Logistics',    'Road',                'Dirt Road',           0, 0,    0.00,  0.00, NULL,   0, 0,   0,  0,  NULL, 1, 'Small', 'No construction material cost. One Dirt Road required per non-road building built.'),
    ('B-007', 'Construction',        'Labor',        'Manpower',            'Construction Crew',   0, 0,    0.00,  0.00, NULL,   0, 0,  50, 50,  NULL, 1, 'Small', 'Construction labor building.'),
    ('B-008', 'Utility',             'Logistics',    'Storage',             'Small Warehouse',     0, 0,  500.00,200.00, NULL,   0, 0, 100,200,  100, 1, 'Small', 'Provides 100 units of shared storage capacity when completed.'),
    ('B-009', 'Processed Goods',     'Construction Goods', 'Structural Materials', 'Saw Mill',      0, 25,   0.00, 50.00, NULL,   0, 0, 100, 50,  NULL, 1, 'Small', 'Consumes 100 Timber per month to produce 50 Lumber. Monetary construction cost not yet specified.'),
    ('B-010', 'Agricultural',        'Food Crops',   'Cereals',             'Oat Farm',            0, 10, 100.00, 50.00, NULL,   0, 0,  25,  0,  NULL, 1, 'Small', 'Produces Oats each month.'),
    ('B-011', 'Agricultural',        'Food Crops',   'Fruits',              'Fig Garden',          0, 10, 150.00, 50.00, NULL,   0, 0,  25,  0,  NULL, 1, 'Small', 'Produces Figs each month.'),
    ('B-012', 'Utility',             'Logistics',    'Freight',             'Teamster Depot',      0, 10, 500.00, 25.00, 'Cart', 5, 5, 100, 50,  NULL, 1, 'Small', 'Provides Teamster labor and Cart-based freight capacity.'),
    ('B-013', 'Agricultural',        'Fiberous Crops','Fiberous Crops',     'Flax Farm',           0, 5,  750.00, 20.00, NULL,   0, 0, 100,  0,  NULL, 1, 'Small', NULL),
    ('B-014', 'Agricultural',        'Live Stock',   'Small Animals',       'Chicken Ranch',       0, 5, 1000.00, 45.00, NULL,   0, 0, 250,100,  NULL, 1, 'Small', NULL),
    ('B-015', 'Agricultural',        'Food Crops',   'Legumes',             'Lentil Farm',         0, 5,  750.00, 20.00, NULL,   0, 0, 100,  0,  NULL, 1, 'Small', NULL)
) AS v(Code, Category, BuildingSubType, Subcategory, Name,
       HousingCapacity, WorkersPerBuilding, ConstructionCost, MonthlyMaintenance,
       VehicleTypeCode, VehicleCapacityPerBuilding, VehiclesAssignedPerBuilding,
       TimberRequiredPerBuilding, StoneRequiredPerBuilding, StorageCapacityShared,
       IsActive, Size, Notes)
WHERE NOT EXISTS (SELECT 1 FROM dbo.BuildingType bt WHERE bt.Code = v.Code);
GO

-- ============================================================
-- Building (starting counts for CityScape - two building types have a
-- nonzero Starting Count in the workbook: Cottage (3) and Wheat Farm (1).
-- Every other building type starts at 0 and is expected to be
-- constructed later, once M4's Construction Projects queue exists).
-- ============================================================
DECLARE @CityScapeID INT;
DECLARE @CottageTypeID INT;
DECLARE @WheatFarmTypeID INT;

SELECT @CityScapeID = CityID FROM dbo.City WHERE Name = 'CityScape';
SELECT @CottageTypeID = BuildingTypeID FROM dbo.BuildingType WHERE Code = 'B-001';
SELECT @WheatFarmTypeID = BuildingTypeID FROM dbo.BuildingType WHERE Code = 'B-002';

IF NOT EXISTS (SELECT 1 FROM dbo.Building WHERE CityID = @CityScapeID AND BuildingTypeID = @CottageTypeID)
    INSERT INTO dbo.Building (CityID, BuildingTypeID, Count) VALUES (@CityScapeID, @CottageTypeID, 3);

IF NOT EXISTS (SELECT 1 FROM dbo.Building WHERE CityID = @CityScapeID AND BuildingTypeID = @WheatFarmTypeID)
    INSERT INTO dbo.Building (CityID, BuildingTypeID, Count) VALUES (@CityScapeID, @WheatFarmTypeID, 1);
GO

-- ============================================================
-- ProductionFlow (11 flows)
-- ============================================================
INSERT INTO dbo.ProductionFlow (Code, BuildingTypeID, FlowType, ResourceID, UnitsPerBuildingPerMonth, FlowRole, Notes)
SELECT v.Code, bt.BuildingTypeID, v.FlowType, r.ResourceID, v.Units, v.FlowRole, v.Notes
FROM (VALUES
    ('BF-001', 'B-002', 'Output', 'R-001', 100.0, 'Primary',        'Seeded from legacy output fields for Wheat Farm.'),
    ('BF-002', 'B-003', 'Output', 'R-003',  80.0, 'Primary',        'Seeded from legacy output fields for Stone Quarry.'),
    ('BF-003', 'B-004', 'Output', 'R-002',  60.0, 'Primary',        'Seeded from legacy output fields for Trout Fishery.'),
    ('BF-004', 'B-005', 'Output', 'R-004', 100.0, 'Primary',        'Seeded from legacy output fields for Lumber Camp.'),
    ('BF-005', 'B-009', 'Output', 'R-005',  50.0, 'Primary',        'Seeded from legacy output fields for Saw Mill.'),
    ('BF-006', 'B-010', 'Output', 'R-006',  80.0, 'Primary',        'Seeded from legacy output fields for Oat Farm.'),
    ('BF-007', 'B-011', 'Output', 'R-007',  40.0, 'Primary',        'Seeded from legacy output fields for Fig Garden.'),
    ('BF-008', 'B-009', 'Input',  'R-004', 100.0, 'Required Input', 'Seeded from current Saw Mill production-chain rule.'),
    ('BF-009', 'B-013', 'Output', 'R-008', 100.0, 'Primary',        NULL),
    ('BF-010', 'B-014', 'Output', 'R-009',  30.0, 'Primary',        NULL),
    ('BF-011', 'B-015', 'Output', 'R-010', 100.0, 'Primary',        NULL)
) AS v(Code, BuildingTypeCode, FlowType, ResourceCode, Units, FlowRole, Notes)
JOIN dbo.BuildingType bt ON bt.Code = v.BuildingTypeCode
JOIN dbo.Resource r ON r.Code = v.ResourceCode
WHERE NOT EXISTS (SELECT 1 FROM dbo.ProductionFlow pf WHERE pf.Code = v.Code);
GO
