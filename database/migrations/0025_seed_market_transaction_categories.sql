-- 0025_seed_market_transaction_categories.sql
-- Milestone 4, Step 4.6a. Seeds two TreasuryCategoryType rows for
-- MarketService (buy/sell execution): no category previously existed for
-- market transactions (only OPENING_BALANCE, RESIDENT_INCOME/EXPENSE,
-- BUILDING_MAINTENANCE, VEHICLE_MAINTENANCE, CONSTRUCTION_COST,
-- VEHICLE_ORDER_COST). Additive, matches the 0010/0024 seed pattern.

IF NOT EXISTS (SELECT 1 FROM dbo.TreasuryCategoryType WHERE Code = 'MARKET_PURCHASE')
    INSERT INTO dbo.TreasuryCategoryType (Code, Name) VALUES ('MARKET_PURCHASE', 'Market Purchase');

IF NOT EXISTS (SELECT 1 FROM dbo.TreasuryCategoryType WHERE Code = 'MARKET_SALE')
    INSERT INTO dbo.TreasuryCategoryType (Code, Name) VALUES ('MARKET_SALE', 'Market Sale');
GO
