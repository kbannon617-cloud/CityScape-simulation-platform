-- 0013_create_inventory_tables.sql
-- Implements the Inventory domain's core stockpile tracking per Document 3
-- / Master Prompt Section 3 ("Inventory authority resides at the city
-- level"). Mirrors the Treasury pattern from migration 0009: the ledger
-- is the append-only source of truth, CityInventory.Quantity is a
-- running total maintained by the single write path in the service layer
-- (InventoryService, next). CityInventory.Quantity also carries a hard
-- CHECK constraint, since "non-negative inventory" is one of Document 7's
-- explicitly named first-class invariants - the first table in this
-- project where that literal invariant applies.
--
-- Unlike TreasuryLedgerEntry, InventoryLedgerEntry has no category-type
-- reference table. Treasury's categories came from concrete budget
-- categories already enumerated in the workbook (Resident Income,
-- Building Maintenance, etc.); no equivalent enumerated list exists yet
-- for inventory transaction reasons (Production, Consumption, Market
-- trades are all real future writers, but none are built yet). A plain
-- Notes field is used instead; a category system can be added later, once
-- real consumers exist to inform what the categories should actually be.

-- ============================================================
-- CityInventory (current state; one row per City/Resource pair)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'CityInventory')
BEGIN
    CREATE TABLE dbo.CityInventory (
        CityInventoryID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        CityID          INT               NOT NULL,
        ResourceID      INT               NOT NULL,
        Quantity        DECIMAL(18,4)     NOT NULL CONSTRAINT DF_CityInventory_Quantity DEFAULT 0,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_CityInventory_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_CityInventory_City FOREIGN KEY (CityID) REFERENCES dbo.City (CityID),
        CONSTRAINT FK_CityInventory_Resource FOREIGN KEY (ResourceID) REFERENCES dbo.Resource (ResourceID),
        CONSTRAINT UQ_CityInventory_City_Resource UNIQUE (CityID, ResourceID),
        CONSTRAINT CK_CityInventory_Quantity_NonNegative CHECK (Quantity >= 0)
    );

    CREATE NONCLUSTERED INDEX IX_CityInventory_CityID ON dbo.CityInventory (CityID);
END
GO

-- ============================================================
-- InventoryLedgerEntry (append-only history; BIGINT-keyed growing data,
-- same precision choice as TreasuryLedgerEntry and for the same reason)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'InventoryLedgerEntry')
BEGIN
    CREATE TABLE dbo.InventoryLedgerEntry (
        InventoryLedgerEntryID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        CityInventoryID        INT                  NOT NULL,
        EntryDate               DATE                NOT NULL,
        -- Signed: positive = increase (e.g. production output, opening
        -- stock), negative = decrease (e.g. consumption). Mirrors
        -- TreasuryLedgerEntry.Amount.
        Amount                  DECIMAL(18,4)       NOT NULL,
        Notes                   NVARCHAR(500)       NULL,
        CreatedDateTime         DATETIME2(3)        NOT NULL CONSTRAINT DF_InventoryLedgerEntry_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_InventoryLedgerEntry_CityInventory FOREIGN KEY (CityInventoryID) REFERENCES dbo.CityInventory (CityInventoryID)
    );

    CREATE NONCLUSTERED INDEX IX_InventoryLedgerEntry_CityInventoryID ON dbo.InventoryLedgerEntry (CityInventoryID);
END
GO
