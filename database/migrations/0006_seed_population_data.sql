-- 0006_seed_population_data.sql
-- Seeds Milestone 2's initial population state. Starting counts below are
-- explicit, easily-changed PLACEHOLDERS (100 Adults, 20 Children) - the
-- design-concept workbook's own figures are unvalidated per the project
-- owner (2026-09-12) and are not treated as authoritative here. Changing
-- these later is a data UPDATE, not a schema or code change.
--
-- The aging rate is seeded as a ScenarioParameter on Cinis Baseline,
-- using the workbook's 1.5%/month figure as a starting default value -
-- explicitly configurable, not hardcoded, per ADR-0005.

IF NOT EXISTS (SELECT 1 FROM dbo.PopulationGroupType WHERE Code = 'ADULT')
    INSERT INTO dbo.PopulationGroupType (Code, Name) VALUES ('ADULT', 'Adult');

IF NOT EXISTS (SELECT 1 FROM dbo.PopulationGroupType WHERE Code = 'CHILD')
    INSERT INTO dbo.PopulationGroupType (Code, Name) VALUES ('CHILD', 'Child');
GO

DECLARE @CityScapeID INT;
DECLARE @AdultTypeID INT;
DECLARE @ChildTypeID INT;

SELECT @CityScapeID = CityID FROM dbo.City WHERE Name = 'CityScape';
SELECT @AdultTypeID = PopulationGroupTypeID FROM dbo.PopulationGroupType WHERE Code = 'ADULT';
SELECT @ChildTypeID = PopulationGroupTypeID FROM dbo.PopulationGroupType WHERE Code = 'CHILD';

-- Placeholder starting population: 100 Adults, 20 Children.
IF NOT EXISTS (SELECT 1 FROM dbo.PopulationGroup WHERE CityID = @CityScapeID AND PopulationGroupTypeID = @AdultTypeID)
    INSERT INTO dbo.PopulationGroup (CityID, PopulationGroupTypeID, Count) VALUES (@CityScapeID, @AdultTypeID, 100);

IF NOT EXISTS (SELECT 1 FROM dbo.PopulationGroup WHERE CityID = @CityScapeID AND PopulationGroupTypeID = @ChildTypeID)
    INSERT INTO dbo.PopulationGroup (CityID, PopulationGroupTypeID, Count) VALUES (@CityScapeID, @ChildTypeID, 20);
GO

DECLARE @CinisBaselineScenarioID INT;

SELECT @CinisBaselineScenarioID = sc.ScenarioID
FROM dbo.Scenario sc
JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline';

-- Placeholder default aging rate (Child -> Adult), from the design-concept
-- workbook, explicitly unvalidated. Stored as data so it can be tuned
-- without a schema or code change.
IF NOT EXISTS (
    SELECT 1 FROM dbo.ScenarioParameter
    WHERE ScenarioID = @CinisBaselineScenarioID AND ParameterKey = 'ChildToAdultMonthlyAgingRatePercent'
)
    INSERT INTO dbo.ScenarioParameter (ScenarioID, ParameterKey, ParameterValue)
    VALUES (@CinisBaselineScenarioID, 'ChildToAdultMonthlyAgingRatePercent', 1.5);
GO
