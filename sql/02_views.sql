/*
    02_views.sql
    vw_RepairOrders_Clean   One row per repair order with normalized status and typed dates.
    fn_OpenRepairOrders     Open repair orders aged against a given date.
    vw_RO_DataExceptions    Records that cannot be aged until corrected in the DMS.
*/
CREATE OR ALTER VIEW dbo.vw_RepairOrders_Clean
AS
WITH ranked AS (
    SELECT s.*,
           ROW_NUMBER() OVER (PARTITION BY s.ro_number ORDER BY s.load_id DESC) AS rn
    FROM dbo.stg_RepairOrders AS s
)
SELECT ro_number,
       branch,
       TRY_CONVERT(DATE, NULLIF(LTRIM(RTRIM(open_date)), '')) AS open_date,
       UPPER(LTRIM(RTRIM(status)))                              AS status,
       payer_type,
       unit,
       complaint,
       NULLIF(LTRIM(RTRIM(technician)), '')                     AS technician,
       labor_hours,
       ISNULL(labor_amount, 0)                                  AS labor_amount,
       ISNULL(parts_amount, 0)                                  AS parts_amount
FROM ranked
WHERE rn = 1;
GO

CREATE OR ALTER FUNCTION dbo.fn_OpenRepairOrders (@AsOf DATE)
RETURNS TABLE
AS
RETURN
(
    SELECT c.*,
           a.age_days,
           CASE
               WHEN a.age_days <= 7  THEN '0-7'
               WHEN a.age_days <= 15 THEN '8-15'
               WHEN a.age_days <= 30 THEN '16-30'
               WHEN a.age_days <= 60 THEN '31-60'
               WHEN a.age_days <= 90 THEN '61-90'
               ELSE '90+'
           END AS age_bucket,
           CASE
               WHEN a.age_days <= 7  THEN 1
               WHEN a.age_days <= 15 THEN 2
               WHEN a.age_days <= 30 THEN 3
               WHEN a.age_days <= 60 THEN 4
               WHEN a.age_days <= 90 THEN 5
               ELSE 6
           END AS age_bucket_order
    FROM dbo.vw_RepairOrders_Clean AS c
    CROSS APPLY (SELECT DATEDIFF(DAY, c.open_date, @AsOf) AS age_days) AS a
    WHERE c.status NOT IN ('CLOSED', 'INVOICED', 'VOID')
      AND c.open_date IS NOT NULL
);
GO

CREATE OR ALTER VIEW dbo.vw_RO_DataExceptions
AS
SELECT ro_number, branch, status, 'Missing or invalid open date' AS issue
FROM dbo.vw_RepairOrders_Clean
WHERE open_date IS NULL
  AND status NOT IN ('CLOSED', 'INVOICED', 'VOID')
UNION ALL
SELECT ro_number, MIN(branch), MIN(status), 'Duplicate export row (counted once)'
FROM dbo.stg_RepairOrders
GROUP BY ro_number
HAVING COUNT(*) > 1;
GO
