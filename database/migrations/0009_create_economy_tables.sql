-- 0009_create_economy_tables.sql
-- Implements the Economy domain's Treasury per Document 3's domain
-- separation and the design-concept workbook's City Budget sheet.
--
-- Follows Document 5's CURRENT STATE + EVENTS + SNAPSHOTS pattern:
-- Treasury is current state (one row per City, 1:1), TreasuryLedgerEntry
-- is the append-only history that current state is derived from -
-- matching Document 7's "traceable history" invariant.
--
-- Cardinality note: Treasury is scoped to City only (no SimulationRunID),
-- consistent with the precedent already set by PopulationGroup in
-- Milestone 2. Per-run-scoped financial state would be a larger change
-- affecting Population too, and is not introduced here.
--
-- Amounts are stored SIGNED (income positive, expense negative) so
-- SUM(Amount) directly gives net cash flow, matching the workbook's own
-- "Monthly Net Cash Flow" concept.

-- ============================================================
-- TreasuryCategoryType (reference data, matches the City Budget sheet's
-- actual income/expense columns)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'TreasuryCategoryType')
BEGIN
    CREATE TABLE dbo.TreasuryCategoryType (
        TreasuryCategoryTypeID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        Code                   NVARCHAR(30)      NOT NULL,
        Name                   NVARCHAR(100)     NOT NULL,
        CreatedDateTime        DATETIME2(3)      NOT NULL CONSTRAINT DF_TreasuryCategoryType_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_TreasuryCategoryType_Code UNIQUE (Code)
    );
END
GO

-- ============================================================
-- Treasury (current state; FK -> City, unique = 1:1; FK -> Currency)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Treasury')
BEGIN
    CREATE TABLE dbo.Treasury (
        TreasuryID      INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        CityID          INT               NOT NULL,
        CurrencyID      INT               NOT NULL,
        Balance         DECIMAL(18,4)     NOT NULL CONSTRAINT DF_Treasury_Balance DEFAULT 0,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_Treasury_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Treasury_City FOREIGN KEY (CityID) REFERENCES dbo.City (CityID),
        CONSTRAINT FK_Treasury_Currency FOREIGN KEY (CurrencyID) REFERENCES dbo.Currency (CurrencyID),
        CONSTRAINT UQ_Treasury_CityID UNIQUE (CityID)
    );
END
GO

-- ============================================================
-- TreasuryLedgerEntry (append-only history; BIGINT PK since this is
-- Operational/Event-category data per the ID Precision Strategy, expected
-- to grow with every future tick/transaction once M4+ generates entries)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'TreasuryLedgerEntry')
BEGIN
    CREATE TABLE dbo.TreasuryLedgerEntry (
        TreasuryLedgerEntryID  BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        TreasuryID             INT                  NOT NULL,
        TreasuryCategoryTypeID INT                  NOT NULL,
        EntryDate              DATE                 NOT NULL,
        Amount                 DECIMAL(18,4)        NOT NULL,
        CreatedDateTime        DATETIME2(3)         NOT NULL CONSTRAINT DF_TreasuryLedgerEntry_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_TreasuryLedgerEntry_Treasury FOREIGN KEY (TreasuryID) REFERENCES dbo.Treasury (TreasuryID),
        CONSTRAINT FK_TreasuryLedgerEntry_TreasuryCategoryType FOREIGN KEY (TreasuryCategoryTypeID) REFERENCES dbo.TreasuryCategoryType (TreasuryCategoryTypeID)
    );

    CREATE NONCLUSTERED INDEX IX_TreasuryLedgerEntry_TreasuryID ON dbo.TreasuryLedgerEntry (TreasuryID);
    CREATE NONCLUSTERED INDEX IX_TreasuryLedgerEntry_EntryDate ON dbo.TreasuryLedgerEntry (EntryDate);
END
GO
