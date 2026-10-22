Attribute VB_Name = "RO_Aging_Report"
' ----------------------------------------------------------------------------
'  RO_Aging_Report
'  Builds the "Aging" sheet: open repair order counts and dollars by branch
'  and days open. Run from the Refresh button on the Aging sheet.
'
'  Retained for reference only. Replaced by the ro_aging service.
'  See docs/legacy-analysis.md for the behavior review.
' ----------------------------------------------------------------------------
Option Explicit

Sub BuildROAging()
    On Error Resume Next

    Dim cn As Object, rs As Object
    Set cn = CreateObject("ADODB.Connection")
    cn.Open "Provider=SQLOLEDB;Data Source=DMS-SQL01;Initial Catalog=DMS;" & _
            "User ID=report_user;Password=Spring2019!"

    Set rs = CreateObject("ADODB.Recordset")
    rs.Open "SELECT ro_number, branch, open_date, status, labor_amount, parts_amount " & _
            "FROM dbo.RepairOrders", cn

    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets("Aging")
    ws.Range("A2:Z500").ClearContents

    Dim asOf As Date: asOf = Date
    Dim age As Long, bucket As String, key As String
    Dim counts As Object: Set counts = CreateObject("Scripting.Dictionary")
    Dim dollars As Object: Set dollars = CreateObject("Scripting.Dictionary")

    Do While Not rs.EOF
        If rs!status <> "Closed" And rs!status <> "Invoiced" And rs!status <> "Void" Then
            age = DateDiff("d", CDate(rs!open_date), asOf)

            If age <= 7 Then
                bucket = "0-7"
            ElseIf age <= 15 Then
                bucket = "8-15"
            ElseIf age <= 30 Then
                bucket = "16-30"
            ElseIf age <= 60 Then
                bucket = "31-60"
            ElseIf age <= 90 Then
                bucket = "61-90"
            Else
                bucket = "90+"
            End If

            key = rs!branch & "|" & bucket
            counts(key) = counts(key) + 1
            dollars(key) = dollars(key) + rs!labor_amount + rs!parts_amount
        End If
        rs.MoveNext
    Loop

    Dim r As Long: r = 2
    Dim k As Variant
    For Each k In counts.Keys
        ws.Cells(r, 1) = Split(k, "|")(0)
        ws.Cells(r, 2) = Split(k, "|")(1)
        ws.Cells(r, 3) = counts(k)
        ws.Cells(r, 4) = dollars(k)
        r = r + 1
    Next k

    rs.Close: cn.Close
End Sub
