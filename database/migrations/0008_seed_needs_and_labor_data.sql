-- 0008_seed_needs_and_labor_data.sql
-- Seeds the three essential need categories named explicitly in the
-- Master Prompt (food, heating, basic goods), placeholder per-person
-- consumption rates, and the labor participation rate as a
-- ScenarioParameter (configurable, not hardcoded, per ADR-0005).
--
-- All quantities below are explicit PLACEHOLDERS, same status as the
-- population counts and aging rate seeded in 0006 - easily changed via
-- data UPDATE, not validated/balanced numbers. Heating is modeled in KG
-- as a generic fuel-mass unit (specific fuel type e.g. coal vs. wood is
-- Economy/Resource Catalog scope, Milestone 3+).

IF NOT EXISTS (SELECT 1 FROM dbo.NeedType WHERE Code = 'FOOD')
    INSERT INTO dbo.NeedType (Code, Name) VALUES ('FOOD', 'Food');

IF NOT EXISTS (SELECT 1 FROM dbo.NeedType WHERE Code = 'HEATING')
    INSERT INTO dbo.NeedType (Code, Name) VALUES ('HEATING', 'Heating');

IF NOT EXISTS (SELECT 1 FROM dbo.NeedType WHERE Code = 'BASIC_GOODS')
    INSERT INTO dbo.NeedType (Code, Name) VALUES ('BASIC_GOODS', 'Basic Goods');
GO

DECLARE @AdultTypeID INT, @ChildTypeID INT;
DECLARE @FoodNeedID INT, @HeatingNeedID INT, @BasicGoodsNeedID INT;
DECLARE @KgUnitID INT, @EaUnitID INT;

SELECT @AdultTypeID = PopulationGroupTypeID FROM dbo.PopulationGroupType WHERE Code = 'ADULT';
SELECT @ChildTypeID = PopulationGroupTypeID FROM dbo.PopulationGroupType WHERE Code = 'CHILD';
SELECT @FoodNeedID = NeedTypeID FROM dbo.NeedType WHERE Code = 'FOOD';
SELECT @HeatingNeedID = NeedTypeID FROM dbo.NeedType WHERE Code = 'HEATING';
SELECT @BasicGoodsNeedID = NeedTypeID FROM dbo.NeedType WHERE Code = 'BASIC_GOODS';
SELECT @KgUnitID = UnitOfMeasureID FROM dbo.UnitOfMeasure WHERE Code = 'KG';
SELECT @EaUnitID = UnitOfMeasureID FROM dbo.UnitOfMeasure WHERE Code = 'EA';

-- Placeholder: Adult food = 1.0 KG/day, Child food = 0.5 KG/day.
IF NOT EXISTS (SELECT 1 FROM dbo.NeedConsumptionRate WHERE PopulationGroupTypeID = @AdultTypeID AND NeedTypeID = @FoodNeedID)
    INSERT INTO dbo.NeedConsumptionRate (PopulationGroupTypeID, NeedTypeID, QuantityPerPersonPerDay, UnitOfMeasureID)
    VALUES (@AdultTypeID, @FoodNeedID, 1.0, @KgUnitID);

IF NOT EXISTS (SELECT 1 FROM dbo.NeedConsumptionRate WHERE PopulationGroupTypeID = @ChildTypeID AND NeedTypeID = @FoodNeedID)
    INSERT INTO dbo.NeedConsumptionRate (PopulationGroupTypeID, NeedTypeID, QuantityPerPersonPerDay, UnitOfMeasureID)
    VALUES (@ChildTypeID, @FoodNeedID, 0.5, @KgUnitID);

-- Placeholder: Adult heating = 0.8 KG/day, Child heating = 0.4 KG/day.
IF NOT EXISTS (SELECT 1 FROM dbo.NeedConsumptionRate WHERE PopulationGroupTypeID = @AdultTypeID AND NeedTypeID = @HeatingNeedID)
    INSERT INTO dbo.NeedConsumptionRate (PopulationGroupTypeID, NeedTypeID, QuantityPerPersonPerDay, UnitOfMeasureID)
    VALUES (@AdultTypeID, @HeatingNeedID, 0.8, @KgUnitID);

IF NOT EXISTS (SELECT 1 FROM dbo.NeedConsumptionRate WHERE PopulationGroupTypeID = @ChildTypeID AND NeedTypeID = @HeatingNeedID)
    INSERT INTO dbo.NeedConsumptionRate (PopulationGroupTypeID, NeedTypeID, QuantityPerPersonPerDay, UnitOfMeasureID)
    VALUES (@ChildTypeID, @HeatingNeedID, 0.4, @KgUnitID);

-- Placeholder: Adult basic goods = 0.2 EA/day, Child basic goods = 0.1 EA/day.
IF NOT EXISTS (SELECT 1 FROM dbo.NeedConsumptionRate WHERE PopulationGroupTypeID = @AdultTypeID AND NeedTypeID = @BasicGoodsNeedID)
    INSERT INTO dbo.NeedConsumptionRate (PopulationGroupTypeID, NeedTypeID, QuantityPerPersonPerDay, UnitOfMeasureID)
    VALUES (@AdultTypeID, @BasicGoodsNeedID, 0.2, @EaUnitID);

IF NOT EXISTS (SELECT 1 FROM dbo.NeedConsumptionRate WHERE PopulationGroupTypeID = @ChildTypeID AND NeedTypeID = @BasicGoodsNeedID)
    INSERT INTO dbo.NeedConsumptionRate (PopulationGroupTypeID, NeedTypeID, QuantityPerPersonPerDay, UnitOfMeasureID)
    VALUES (@ChildTypeID, @BasicGoodsNeedID, 0.1, @EaUnitID);
GO

DECLARE @CinisBaselineScenarioID INT;

SELECT @CinisBaselineScenarioID = sc.ScenarioID
FROM dbo.Scenario sc
JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline';

-- Placeholder: 100% of adults are available labor (no participation
-- friction modeled yet - configurable so this can change without a
-- schema or code change).
IF NOT EXISTS (
    SELECT 1 FROM dbo.ScenarioParameter
    WHERE ScenarioID = @CinisBaselineScenarioID AND ParameterKey = 'AdultLaborParticipationRatePercent'
)
    INSERT INTO dbo.ScenarioParameter (ScenarioID, ParameterKey, ParameterValue)
    VALUES (@CinisBaselineScenarioID, 'AdultLaborParticipationRatePercent', 100.0);
GO
