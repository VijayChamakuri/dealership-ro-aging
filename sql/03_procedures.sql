/*
    03_procedures.sql
    usp_GetOpenROAging        Summary by branch and age bucket (called by the API).
    usp_GetOpenRODetail       Repair orders behind a summary cell.

    Example:
        EXEC dbo.usp_GetOpenROAging @Branch = 'Indianapolis', @AsOf = '2026-10-21';
*/
CREATE OR ALTER PROCEDURE dbo.usp_GetOpenROAging
    @Branch VARCHAR(50) = NULL,
    @AsOf   DATE        = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET @AsOf = ISNULL(@AsOf, CAST(GETDATE() AS DATE));

    SELECT o.branch,
           o.age_bucket,
           COUNT(*)                                                    AS ro_count,
           CAST(SUM(o.labor_amount + o.parts_amount) AS DECIMAL(12, 2)) AS open_dollars
    FROM dbo.fn_OpenRepairOrders(@AsOf) AS o
    WHERE @Branch IS NULL OR o.branch = @Branch
    GROUP BY o.branch, o.age_bucket, o.age_bucket_order
    ORDER BY o.branch, o.age_bucket_order;
END;
GO

CREATE OR ALTER PROCEDURE dbo.usp_GetOpenRODetail
    @Branch VARCHAR(50) = NULL,
    @Bucket VARCHAR(10) = NULL,
    @AsOf   DATE        = NULL
AS
BEGIN
    SET NOCOUNT ON;
    SET @AsOf = ISNULL(@AsOf, CAST(GETDATE() AS DATE));

    SELECT o.ro_number, o.branch, o.open_date, o.age_days, o.age_bucket,
           o.status, o.payer_type, o.unit, o.complaint, o.technician,
           CAST(o.labor_amount + o.parts_amount AS DECIMAL(12, 2)) AS open_dollars
    FROM dbo.fn_OpenRepairOrders(@AsOf) AS o
    WHERE (@Branch IS NULL OR o.branch = @Branch)
      AND (@Bucket IS NULL OR o.age_bucket = @Bucket)
    ORDER BY o.age_days DESC, o.ro_number;
END;
GO
