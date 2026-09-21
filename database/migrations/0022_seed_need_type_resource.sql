-- 0022_seed_need_type_resource.sql
-- Milestone 4, Step 4.4a. Initial need-to-resource mapping approved in
-- ADR-0010 Decision 2. Rows are guarded so the migration is safe to re-run.
--
--   FOOD    : Wheat (1), Trout (2), Eggs (3), Lentils (4)
--             Wheat then Trout follows the workbook's Population sheet.
--             Eggs and Lentils are appended after them (in resource-code
--             order); the order is data and can be changed when balancing.
--   HEATING : Timber (1)
--
-- BASIC_GOODS is deliberately NOT mapped: nothing in the current resource
-- catalog fits, and per the sparse-seeding convention a missing row means
-- "none". A need type with no mapping is skipped by the consumption step
-- (no consumption, no shortfall event); adding a mapping row later turns it
-- on without any code change.
--
-- Oats and Figs (PopulationFoodStatus = 'Future') are also not mapped.
--
-- The join is by code. If a code below did not exist, that row would simply
-- not be inserted; the integration tests check the seeded rows.

INSERT INTO dbo.NeedTypeResource (NeedTypeID, ResourceID, ConsumptionPriority)
SELECT nt.NeedTypeID, r.ResourceID, v.ConsumptionPriority
FROM (VALUES
    ('FOOD',    'R-001', 1),
    ('FOOD',    'R-002', 2),
    ('FOOD',    'R-009', 3),
    ('FOOD',    'R-010', 4),
    ('HEATING', 'R-004', 1)
) AS v(NeedTypeCode, ResourceCode, ConsumptionPriority)
JOIN dbo.NeedType nt ON nt.Code = v.NeedTypeCode
JOIN dbo.Resource r  ON r.Code  = v.ResourceCode
WHERE NOT EXISTS (
    SELECT 1 FROM dbo.NeedTypeResource ntr
    WHERE ntr.NeedTypeID = nt.NeedTypeID AND ntr.ResourceID = r.ResourceID
);
GO
