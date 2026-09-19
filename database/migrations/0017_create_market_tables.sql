-- 0017_create_market_tables.sql
-- Implements Document 3's Markets and Transactions domains, completing
-- ADR-0005's Milestone 3 domain assignment. Unlike every other domain
-- built this milestone, the design-concept workbook has no Market or
-- pricing sheet at all - there is no source data to extract here.
--
-- Per the project owner's explicit decision (2026, M3 Vehicles/Markets
-- session): pricing starts as a FIXED reference price per resource,
-- scenario-scoped (same configurable-not-hardcoded pattern as the
-- aging/labor rates), not a supply/demand model. This can change later
-- without a schema change - only MarketResourcePrice's seeded VALUES
-- would need updating, or a new pricing mechanism added alongside it.
--
-- MarketTransaction realizes BOTH the Markets and Transactions domains:
-- MVP scope has no transaction type other than a market trade (no
-- peer-to-peer trade, no external trade), so a single ledger table
-- serves both. If a non-market transaction type is ever needed, it
-- would get its own table rather than forcing it into this one.
--
-- Scope boundary, matching the catalog-first pattern used for Production
-- and Vehicles: this is the schema and reference pricing, not yet a
-- running MarketService that actually executes buy/sell trades against
-- Treasury and CityInventory. That is a deliberate next step.

-- ============================================================
-- Market (current state; one row per City, mirrors Treasury's 1:1 shape)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'Market')
BEGIN
    CREATE TABLE dbo.Market (
        MarketID        INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        CityID          INT               NOT NULL,
        CreatedDateTime DATETIME2(3)      NOT NULL CONSTRAINT DF_Market_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Market_City FOREIGN KEY (CityID) REFERENCES dbo.City (CityID),
        CONSTRAINT UQ_Market_CityID UNIQUE (CityID)
    );
END
GO

-- ============================================================
-- MarketResourcePrice (scenario-scoped reference pricing)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'MarketResourcePrice')
BEGIN
    CREATE TABLE dbo.MarketResourcePrice (
        MarketResourcePriceID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ScenarioID             INT              NOT NULL,
        ResourceID              INT              NOT NULL,
        CurrencyID              INT              NOT NULL,
        UnitPrice                DECIMAL(18,4)   NOT NULL,
        CreatedDateTime          DATETIME2(3)    NOT NULL CONSTRAINT DF_MarketResourcePrice_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_MarketResourcePrice_Scenario FOREIGN KEY (ScenarioID) REFERENCES dbo.Scenario (ScenarioID),
        CONSTRAINT FK_MarketResourcePrice_Resource FOREIGN KEY (ResourceID) REFERENCES dbo.Resource (ResourceID),
        CONSTRAINT FK_MarketResourcePrice_Currency FOREIGN KEY (CurrencyID) REFERENCES dbo.Currency (CurrencyID),
        CONSTRAINT UQ_MarketResourcePrice_Scenario_Resource UNIQUE (ScenarioID, ResourceID),
        CONSTRAINT CK_MarketResourcePrice_UnitPrice_Positive CHECK (UnitPrice > 0)
    );
END
GO

-- ============================================================
-- MarketTransaction (append-only ledger; BIGINT-keyed growing data,
-- same precision choice as TreasuryLedgerEntry/InventoryLedgerEntry)
-- ============================================================
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'MarketTransaction')
BEGIN
    CREATE TABLE dbo.MarketTransaction (
        MarketTransactionID BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        MarketID             INT                 NOT NULL,
        ResourceID           INT                 NOT NULL,
        -- From the city's perspective: 'Sell' = city sells surplus
        -- (inventory decreases, treasury increases); 'Buy' = city buys a
        -- deficit (inventory increases, treasury decreases).
        TransactionType      NVARCHAR(10)        NOT NULL,
        Quantity              DECIMAL(18,4)      NOT NULL,
        UnitPrice              DECIMAL(18,4)      NOT NULL,
        -- Stored explicitly (not just derivable as Quantity * UnitPrice)
        -- for Document 7 traceability/explainability, same reasoning as
        -- TreasuryLedgerEntry storing signed Amount directly.
        TotalValue              DECIMAL(18,4)     NOT NULL,
        TransactionDate          DATE             NOT NULL,
        CreatedDateTime           DATETIME2(3)    NOT NULL CONSTRAINT DF_MarketTransaction_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_MarketTransaction_Market FOREIGN KEY (MarketID) REFERENCES dbo.Market (MarketID),
        CONSTRAINT FK_MarketTransaction_Resource FOREIGN KEY (ResourceID) REFERENCES dbo.Resource (ResourceID),
        CONSTRAINT CK_MarketTransaction_TransactionType CHECK (TransactionType IN ('Buy', 'Sell')),
        CONSTRAINT CK_MarketTransaction_Quantity_Positive CHECK (Quantity > 0),
        CONSTRAINT CK_MarketTransaction_UnitPrice_Positive CHECK (UnitPrice > 0)
    );

    CREATE NONCLUSTERED INDEX IX_MarketTransaction_MarketID ON dbo.MarketTransaction (MarketID);
    CREATE NONCLUSTERED INDEX IX_MarketTransaction_ResourceID ON dbo.MarketTransaction (ResourceID);
END
GO
