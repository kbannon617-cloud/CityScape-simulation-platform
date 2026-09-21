-- 0021_create_need_type_resource.sql
-- Milestone 4, Step 4.4a. Implements ADR-0010 Decision 1: link each need
-- category (NeedType) to the resources that can satisfy it, with a
-- consumption priority. This resolves the "need-to-resource mapping" open
-- item from ADR-0009 (ADR-0005 modeled needs as categories only).
--
-- How it is used (Step 4.4b): for a need, the consumption step drains the
-- priority-1 resource first, then priority-2, and so on, until the need is
-- met or the mapped resources run out. This mirrors the design-concept
-- workbook's Population sheet (Wheat consumed first, then Trout for what
-- remains).
--
-- Design notes:
--   * ConsumptionPriority is unique within a need type, so the order is
--     total and deterministic (Document 1: determinism). Priority 1 is
--     consumed first.
--   * A resource can appear only once per need type.
--   * The mapping is global, like NeedConsumptionRate: it is not scoped to
--     a scenario or a city. Scenario-specific mappings are not needed yet.
--   * No unit column and no unit check. Need rates are currently seeded in
--     KG while every Resource is in EA; reconciling units is deferred to
--     ADR-0010 Decision 3.
--   * The two UNIQUE constraints create indexes led by NeedTypeID, which
--     also serve the lookup "all resources for a need type, in priority
--     order", so no extra index is added.
--
-- Seed rows are in 0022_seed_need_type_resource.sql.

IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'NeedTypeResource')
BEGIN
    CREATE TABLE dbo.NeedTypeResource (
        NeedTypeResourceID  INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        NeedTypeID          INT               NOT NULL,
        ResourceID          INT               NOT NULL,
        ConsumptionPriority INT               NOT NULL,
        CreatedDateTime     DATETIME2(3)      NOT NULL CONSTRAINT DF_NeedTypeResource_CreatedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_NeedTypeResource_NeedType FOREIGN KEY (NeedTypeID) REFERENCES dbo.NeedType (NeedTypeID),
        CONSTRAINT FK_NeedTypeResource_Resource FOREIGN KEY (ResourceID) REFERENCES dbo.Resource (ResourceID),
        CONSTRAINT UQ_NeedTypeResource_NeedType_Resource UNIQUE (NeedTypeID, ResourceID),
        CONSTRAINT UQ_NeedTypeResource_NeedType_Priority UNIQUE (NeedTypeID, ConsumptionPriority),
        CONSTRAINT CK_NeedTypeResource_ConsumptionPriority_Positive CHECK (ConsumptionPriority >= 1)
    );
END
GO
