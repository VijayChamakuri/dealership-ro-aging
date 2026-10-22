/*
    01_staging.sql
    Landing table for the nightly DMS repair order export.
    Columns are loaded as delivered; typing and cleansing happen in views.
*/
IF OBJECT_ID(N'dbo.stg_RepairOrders', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.stg_RepairOrders (
        load_id       BIGINT IDENTITY(1, 1) NOT NULL PRIMARY KEY,
        ro_number     VARCHAR(20)    NOT NULL,
        branch        VARCHAR(50)    NOT NULL,
        open_date     VARCHAR(20)    NULL,
        status        VARCHAR(30)    NULL,
        payer_type    VARCHAR(20)    NULL,
        unit          VARCHAR(80)    NULL,
        complaint     VARCHAR(200)   NULL,
        technician    VARCHAR(50)    NULL,
        labor_hours   DECIMAL(6, 1)  NULL,
        labor_amount  DECIMAL(12, 2) NULL,
        parts_amount  DECIMAL(12, 2) NULL,
        loaded_at     DATETIME2(0)   NOT NULL
            CONSTRAINT DF_stg_RepairOrders_loaded_at DEFAULT SYSUTCDATETIME()
    );

    CREATE INDEX IX_stg_RepairOrders_ro_number
        ON dbo.stg_RepairOrders (ro_number, load_id DESC);
END;
GO
