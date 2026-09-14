-- 0010_seed_economy_data.sql
-- Seeds the six treasury categories from the design-concept workbook's
-- City Budget sheet, CityScape's Treasury (starting balance 10,000 STD -
-- an explicit PLACEHOLDER matching the workbook's own Month 1 beginning
-- balance, same unvalidated status as every other seeded number in this
-- project), and one opening-balance ledger entry so the balance is
-- traceable from day one rather than appearing from nowhere.

IF NOT EXISTS (SELECT 1 FROM dbo.TreasuryCategoryType WHERE Code = 'OPENING_BALANCE')
    INSERT INTO dbo.TreasuryCategoryType (Code, Name) VALUES ('OPENING_BALANCE', 'Opening Balance');

IF NOT EXISTS (SELECT 1 FROM dbo.TreasuryCategoryType WHERE Code = 'RESIDENT_INCOME')
    INSERT INTO dbo.TreasuryCategoryType (Code, Name) VALUES ('RESIDENT_INCOME', 'Resident Income');

IF NOT EXISTS (SELECT 1 FROM dbo.TreasuryCategoryType WHERE Code = 'RESIDENT_EXPENSE')
    INSERT INTO dbo.TreasuryCategoryType (Code, Name) VALUES ('RESIDENT_EXPENSE', 'Resident Expenses');

IF NOT EXISTS (SELECT 1 FROM dbo.TreasuryCategoryType WHERE Code = 'BUILDING_MAINTENANCE')
    INSERT INTO dbo.TreasuryCategoryType (Code, Name) VALUES ('BUILDING_MAINTENANCE', 'Building Maintenance');

IF NOT EXISTS (SELECT 1 FROM dbo.TreasuryCategoryType WHERE Code = 'VEHICLE_MAINTENANCE')
    INSERT INTO dbo.TreasuryCategoryType (Code, Name) VALUES ('VEHICLE_MAINTENANCE', 'Vehicle Maintenance');

IF NOT EXISTS (SELECT 1 FROM dbo.TreasuryCategoryType WHERE Code = 'CONSTRUCTION_COST')
    INSERT INTO dbo.TreasuryCategoryType (Code, Name) VALUES ('CONSTRUCTION_COST', 'Construction Costs');

IF NOT EXISTS (SELECT 1 FROM dbo.TreasuryCategoryType WHERE Code = 'VEHICLE_ORDER_COST')
    INSERT INTO dbo.TreasuryCategoryType (Code, Name) VALUES ('VEHICLE_ORDER_COST', 'Vehicle Order Costs');
GO

DECLARE @CityScapeID INT;
DECLARE @StdCurrencyID INT;

SELECT @CityScapeID = CityID FROM dbo.City WHERE Name = 'CityScape';
SELECT @StdCurrencyID = CurrencyID FROM dbo.Currency WHERE Code = 'STD';

IF NOT EXISTS (SELECT 1 FROM dbo.Treasury WHERE CityID = @CityScapeID)
    INSERT INTO dbo.Treasury (CityID, CurrencyID, Balance) VALUES (@CityScapeID, @StdCurrencyID, 10000.00);
GO

DECLARE @CityScapeTreasuryID INT;
DECLARE @OpeningBalanceCategoryID INT;

SELECT @CityScapeTreasuryID = t.TreasuryID
FROM dbo.Treasury t
JOIN dbo.City c ON c.CityID = t.CityID
WHERE c.Name = 'CityScape';

SELECT @OpeningBalanceCategoryID = TreasuryCategoryTypeID
FROM dbo.TreasuryCategoryType
WHERE Code = 'OPENING_BALANCE';

IF NOT EXISTS (
    SELECT 1 FROM dbo.TreasuryLedgerEntry
    WHERE TreasuryID = @CityScapeTreasuryID AND TreasuryCategoryTypeID = @OpeningBalanceCategoryID
)
    INSERT INTO dbo.TreasuryLedgerEntry (TreasuryID, TreasuryCategoryTypeID, EntryDate, Amount)
    VALUES (@CityScapeTreasuryID, @OpeningBalanceCategoryID, '2026-01-01', 10000.00);
GO
