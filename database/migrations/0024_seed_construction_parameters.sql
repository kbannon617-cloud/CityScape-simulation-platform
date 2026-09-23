-- 0024_seed_construction_parameters.sql
-- Milestone 4, Step 4.5a. Seeds the three ScenarioParameter rows the
-- Construction Projects domain needs, for the Cinis Baseline scenario -
-- same pattern as the aging/labor rates in 0006/0008.
--
-- Values are the design-concept workbook's own defaults
-- ('+Default Statistics' B24/B25) and are explicit placeholders, not
-- balanced numbers - per the project owner's standing instruction, no
-- balancing pass happens until the M4 skeleton is complete.

DECLARE @CinisBaselineScenarioID INT;

SELECT @CinisBaselineScenarioID = sc.ScenarioID
FROM dbo.Scenario sc
JOIN dbo.Simulation s ON s.SimulationID = sc.SimulationID
WHERE s.Name = 'Cinis' AND sc.Name = 'Cinis Baseline';

-- Placeholder: $100 of construction cost converts to 1 base construction
-- month (workbook B24).
IF NOT EXISTS (
    SELECT 1 FROM dbo.ScenarioParameter
    WHERE ScenarioID = @CinisBaselineScenarioID AND ParameterKey = 'MonthlyConstructionBudget'
)
    INSERT INTO dbo.ScenarioParameter (ScenarioID, ParameterKey, ParameterValue)
    VALUES (@CinisBaselineScenarioID, 'MonthlyConstructionBudget', 100.0);

-- Placeholder: each completed Construction Crew building shortens future
-- projects' duration by 0.05%, uncapped (workbook B25).
IF NOT EXISTS (
    SELECT 1 FROM dbo.ScenarioParameter
    WHERE ScenarioID = @CinisBaselineScenarioID AND ParameterKey = 'ConstructionBonusPerCompletedCrew'
)
    INSERT INTO dbo.ScenarioParameter (ScenarioID, ParameterKey, ParameterValue)
    VALUES (@CinisBaselineScenarioID, 'ConstructionBonusPerCompletedCrew', 0.0005);

-- Not from the workbook (v1 there hard-codes exactly one active project
-- globally). Owner intends multiple concurrent projects later; this
-- parameter is the single point of change for that, per ADR-0011.
IF NOT EXISTS (
    SELECT 1 FROM dbo.ScenarioParameter
    WHERE ScenarioID = @CinisBaselineScenarioID AND ParameterKey = 'MaxActiveConstructionProjectsPerCity'
)
    INSERT INTO dbo.ScenarioParameter (ScenarioID, ParameterKey, ParameterValue)
    VALUES (@CinisBaselineScenarioID, 'MaxActiveConstructionProjectsPerCity', 1);
GO
