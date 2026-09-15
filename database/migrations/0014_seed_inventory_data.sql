-- 0014_seed_inventory_data.sql
-- Seeds CityScape's opening inventory per the Storage Capacity sheet's own
-- note: "Starting stock is assumed to be zero except for Wheat and Timber
-- listed in Default Statistics." All other resources start at zero and
-- simply have no CityInventory row yet (a missing row means zero stock,
-- same sparse-seeding convention used for Building in migration 0012).
--
-- Recorded through the ledger (opening-stock entries), consistent with
-- Treasury's opening-balance pattern in migration 0010, dated the same
-- simulation start date ('2026-01-01').

DECLARE @CityScapeID INT;
DECLARE @WheatResourceID INT;
DECLARE @TimberResourceID INT;

SELECT @CityScapeID = CityID FROM dbo.City WHERE Name = 'CityScape';
SELECT @WheatResourceID = ResourceID FROM dbo.Resource WHERE Code = 'R-001';
SELECT @TimberResourceID = ResourceID FROM dbo.Resource WHERE Code = 'R-004';

IF NOT EXISTS (SELECT 1 FROM dbo.CityInventory WHERE CityID = @CityScapeID AND ResourceID = @WheatResourceID)
    INSERT INTO dbo.CityInventory (CityID, ResourceID, Quantity) VALUES (@CityScapeID, @WheatResourceID, 100.00);

IF NOT EXISTS (SELECT 1 FROM dbo.CityInventory WHERE CityID = @CityScapeID AND ResourceID = @TimberResourceID)
    INSERT INTO dbo.CityInventory (CityID, ResourceID, Quantity) VALUES (@CityScapeID, @TimberResourceID, 100.00);
GO

DECLARE @CityScapeWheatInventoryID INT;
DECLARE @CityScapeTimberInventoryID INT;

SELECT @CityScapeWheatInventoryID = ci.CityInventoryID
FROM dbo.CityInventory ci
JOIN dbo.City c ON c.CityID = ci.CityID
JOIN dbo.Resource r ON r.ResourceID = ci.ResourceID
WHERE c.Name = 'CityScape' AND r.Code = 'R-001';

SELECT @CityScapeTimberInventoryID = ci.CityInventoryID
FROM dbo.CityInventory ci
JOIN dbo.City c ON c.CityID = ci.CityID
JOIN dbo.Resource r ON r.ResourceID = ci.ResourceID
WHERE c.Name = 'CityScape' AND r.Code = 'R-004';

IF NOT EXISTS (SELECT 1 FROM dbo.InventoryLedgerEntry WHERE CityInventoryID = @CityScapeWheatInventoryID)
    INSERT INTO dbo.InventoryLedgerEntry (CityInventoryID, EntryDate, Amount, Notes)
    VALUES (@CityScapeWheatInventoryID, '2026-01-01', 100.00, 'Opening stock.');

IF NOT EXISTS (SELECT 1 FROM dbo.InventoryLedgerEntry WHERE CityInventoryID = @CityScapeTimberInventoryID)
    INSERT INTO dbo.InventoryLedgerEntry (CityInventoryID, EntryDate, Amount, Notes)
    VALUES (@CityScapeTimberInventoryID, '2026-01-01', 100.00, 'Opening stock.');
GO
