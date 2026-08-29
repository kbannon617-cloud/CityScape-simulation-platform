-- 0001_create_migration_history.sql
-- Bootstraps the MigrationHistory table used to track which migrations
-- have already been applied. This is the one migration the runner assumes
-- may not exist yet; every later migration can assume it does.

IF NOT EXISTS (
    SELECT 1 FROM sys.tables WHERE name = 'MigrationHistory'
)
BEGIN
    CREATE TABLE dbo.MigrationHistory (
        MigrationHistoryID INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        ScriptName          NVARCHAR(255)     NOT NULL,
        AppliedDateTime     DATETIME2(3)      NOT NULL CONSTRAINT DF_MigrationHistory_AppliedDateTime DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_MigrationHistory_ScriptName UNIQUE (ScriptName)
    );
END
GO
