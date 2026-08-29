-- 0003_seed_cinis_reference_data.sql
-- Populates the Cinis MVP's fixed reference data per Document 4:
-- one operational currency, baseline units of measure, the predetermined
-- World -> Region -> City geography with one primary active city, and the
-- Cinis simulation with its approved "Cinis Baseline" scenario.
--
-- World/Region names are explicit placeholders pending real world-building
-- content. "CityScape" is the agreed placeholder name for the first city;
-- real city names will be selected later. "Cinis" and "Cinis Baseline" are
-- not placeholders - they are the names approved in Documents 1 and 4.

-- ============================================================
-- Currency (one operational currency per MVP scope)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM dbo.Currency WHERE Code = 'STD')
    INSERT INTO dbo.Currency (Code, Name) VALUES ('STD', 'Standard Currency');
GO

-- ============================================================
-- UnitOfMeasure (baseline units; tonnage-based pricing matches the
-- Production Chains / Town sheets in the design-concept workbook)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM dbo.UnitOfMeasure WHERE Code = 'KG')
    INSERT INTO dbo.UnitOfMeasure (Code, Name) VALUES ('KG', 'Kilogram');

IF NOT EXISTS (SELECT 1 FROM dbo.UnitOfMeasure WHERE Code = 'TON')
    INSERT INTO dbo.UnitOfMeasure (Code, Name) VALUES ('TON', 'Tonne');

IF NOT EXISTS (SELECT 1 FROM dbo.UnitOfMeasure WHERE Code = 'L')
    INSERT INTO dbo.UnitOfMeasure (Code, Name) VALUES ('L', 'Liter');

IF NOT EXISTS (SELECT 1 FROM dbo.UnitOfMeasure WHERE Code = 'EA')
    INSERT INTO dbo.UnitOfMeasure (Code, Name) VALUES ('EA', 'Each');
GO

-- ============================================================
-- Geography: World -> Region -> City (predetermined, authoritative;
-- placeholder names pending real world-building content)
-- ============================================================
DECLARE @WorldID INT;

IF NOT EXISTS (SELECT 1 FROM dbo.World WHERE Name = 'Primary World')
    INSERT INTO dbo.World (Name) VALUES ('Primary World');

SELECT @WorldID = WorldID FROM dbo.World WHERE Name = 'Primary World';

DECLARE @RegionID INT;

IF NOT EXISTS (SELECT 1 FROM dbo.Region WHERE WorldID = @WorldID AND Name = 'Primary Region')
    INSERT INTO dbo.Region (WorldID, Name) VALUES (@WorldID, 'Primary Region');

SELECT @RegionID = RegionID FROM dbo.Region WHERE WorldID = @WorldID AND Name = 'Primary Region';

IF NOT EXISTS (SELECT 1 FROM dbo.City WHERE RegionID = @RegionID AND Name = 'CityScape')
    INSERT INTO dbo.City (RegionID, Name, IsPrimaryActive) VALUES (@RegionID, 'CityScape', 1);
GO

-- ============================================================
-- Simulation & the approved Cinis Baseline scenario (Document 4)
-- ============================================================
DECLARE @SimulationID INT;

IF NOT EXISTS (SELECT 1 FROM dbo.Simulation WHERE Name = 'Cinis')
    INSERT INTO dbo.Simulation (Name, Description)
    VALUES ('Cinis', 'Permanent reference implementation of the CityScape Simulation Platform.');

SELECT @SimulationID = SimulationID FROM dbo.Simulation WHERE Name = 'Cinis';

IF NOT EXISTS (SELECT 1 FROM dbo.Scenario WHERE SimulationID = @SimulationID AND Name = 'Cinis Baseline')
    INSERT INTO dbo.Scenario (SimulationID, ParentScenarioID, Name, Description)
    VALUES (@SimulationID, NULL, 'Cinis Baseline', 'Baseline scenario for the Cinis MVP 100-day validation run.');
GO
