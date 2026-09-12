-- 0004_enforce_single_primary_active_city.sql
-- Enforces the MVP invariant (Document 4: "one primary active city") at the
-- database level via a filtered unique index, rather than relying solely on
-- application code. See ADR-0003 (accepted this as app-layer-only initially)
-- and ADR-0004 (the test-data-pollution bug that motivated revisiting it).
--
-- A filtered unique index on a column that only ever holds the value 1
-- (within the filter) guarantees at most one qualifying row: a second row
-- with IsPrimaryActive = 1 would be a duplicate value and is rejected.

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE name = 'UQ_City_OnePrimaryActive' AND object_id = OBJECT_ID('dbo.City')
)
BEGIN
    CREATE UNIQUE INDEX UQ_City_OnePrimaryActive
        ON dbo.City (IsPrimaryActive)
        WHERE IsPrimaryActive = 1;
END
GO
