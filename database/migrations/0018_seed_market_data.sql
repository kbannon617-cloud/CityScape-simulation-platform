-- 0018_seed_market_data.sql
-- Seeds one Market for CityScape and placeholder reference prices for all
-- 11 resources under the Cinis Baseline scenario, in the one operational
-- currency (STD). Prices below are explicit, arbitrary PLACEHOLDERS -
-- same status as every other seeded rate in this project (population
-- counts, aging rate, labor participation rate, need consumption rates):
-- there is no source data to draw from, so simple round numbers are used,
-- easily changed via data UPDATE, not a schema or code change.

IF NOT EXISTS (SELECT 1 FROM dbo.Market WHERE CityID = (SELECT CityID FROM dbo.City WHERE Name = 'CityScape'))
    INSERT INTO dbo.Market (CityID)
    SELECT CityID FROM dbo.City WHERE Name = 'CityScape';
GO

DECLARE @CinisBaselineScenarioID INT;
DECLARE @StdCurrencyID INT;

SELECT @CinisBaselineScenarioID = sc.ScenarioID
FROM dbo.Scenario sc
JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline';

SELECT @StdCurrencyID = CurrencyID FROM dbo.Currency WHERE Code = 'STD';

INSERT INTO dbo.MarketResourcePrice (ScenarioID, ResourceID, CurrencyID, UnitPrice)
SELECT @CinisBaselineScenarioID, r.ResourceID, @StdCurrencyID, v.UnitPrice
FROM (VALUES
    ('R-001', 2.00),  -- Wheat
    ('R-002', 3.00),  -- Trout
    ('R-003', 1.00),  -- Stone
    ('R-004', 1.50),  -- Timber
    ('R-005', 3.00),  -- Lumber
    ('R-006', 2.00),  -- Oats
    ('R-007', 2.50),  -- Figs
    ('R-008', 2.00),  -- Flax
    ('R-009', 1.50),  -- Eggs
    ('R-010', 2.00),  -- Lentils
    ('R-011', 4.00)   -- Ore
) AS v(ResourceCode, UnitPrice)
JOIN dbo.Resource r ON r.Code = v.ResourceCode
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.MarketResourcePrice mrp
    WHERE mrp.ScenarioID = @CinisBaselineScenarioID AND mrp.ResourceID = r.ResourceID
);
GO
