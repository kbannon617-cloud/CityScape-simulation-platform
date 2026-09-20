-- 0020_add_ledger_run_and_tick_columns.sql
-- Milestone 4, Step 4.1b. Implements ADR-0009 Decision 3: run and tick
-- traceability on the two ledger tables, so any ledger entry the tick
-- engine writes can be explained through run, tick and date (Document 7).
--
-- Additive only: two nullable columns on each of TreasuryLedgerEntry and
-- InventoryLedgerEntry. No existing column, row or constraint is changed,
-- and existing rows are not backfilled.
--
--   SimulationRunID  INT     NULL, FK -> SimulationRun
--   SimulationTickID BIGINT  NULL
--
-- Both are NULL for entries written before the engine existed (seed data,
-- tests) and for service calls made outside a tick. Entries written by the
-- engine carry both. SimulationTickID is a per-run counter (tick 5 exists
-- in every run), so it only identifies a tick together with
-- SimulationRunID; a CHECK enforces "both or neither".
--
-- City-scoped state is unchanged: Treasury, Population and Inventory stay
-- scoped to City, not run (migration 0009 note, ADR-0003).
--
-- No index is added. There is no access pattern yet (Document 5: index on
-- real access patterns). Intentional deferral; add one when tick-level
-- ledger queries exist.
--
-- Two batches: the CHECK constraints reference the new columns, which must
-- exist (batch 1 committed to the schema) before those constraints compile
-- (batch 2). Every step is guarded so the migration is safe to re-run.

-- ============================================================
-- Batch 1: columns (+ foreign key)
-- ============================================================
IF COL_LENGTH('dbo.InventoryLedgerEntry', 'SimulationRunID') IS NULL
    ALTER TABLE dbo.InventoryLedgerEntry ADD
        SimulationRunID  INT    NULL CONSTRAINT FK_InventoryLedgerEntry_SimulationRun REFERENCES dbo.SimulationRun (SimulationRunID),
        SimulationTickID BIGINT NULL;

IF COL_LENGTH('dbo.TreasuryLedgerEntry', 'SimulationRunID') IS NULL
    ALTER TABLE dbo.TreasuryLedgerEntry ADD
        SimulationRunID  INT    NULL CONSTRAINT FK_TreasuryLedgerEntry_SimulationRun REFERENCES dbo.SimulationRun (SimulationRunID),
        SimulationTickID BIGINT NULL;
GO

-- ============================================================
-- Batch 2: check constraints
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_InventoryLedgerEntry_Trace_BothOrNeither')
    ALTER TABLE dbo.InventoryLedgerEntry ADD CONSTRAINT CK_InventoryLedgerEntry_Trace_BothOrNeither
        CHECK ((SimulationRunID IS NULL AND SimulationTickID IS NULL) OR (SimulationRunID IS NOT NULL AND SimulationTickID IS NOT NULL));

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_InventoryLedgerEntry_SimulationTickID_Positive')
    ALTER TABLE dbo.InventoryLedgerEntry ADD CONSTRAINT CK_InventoryLedgerEntry_SimulationTickID_Positive
        CHECK (SimulationTickID IS NULL OR SimulationTickID >= 1);

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_TreasuryLedgerEntry_Trace_BothOrNeither')
    ALTER TABLE dbo.TreasuryLedgerEntry ADD CONSTRAINT CK_TreasuryLedgerEntry_Trace_BothOrNeither
        CHECK ((SimulationRunID IS NULL AND SimulationTickID IS NULL) OR (SimulationRunID IS NOT NULL AND SimulationTickID IS NOT NULL));

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = 'CK_TreasuryLedgerEntry_SimulationTickID_Positive')
    ALTER TABLE dbo.TreasuryLedgerEntry ADD CONSTRAINT CK_TreasuryLedgerEntry_SimulationTickID_Positive
        CHECK (SimulationTickID IS NULL OR SimulationTickID >= 1);
GO
