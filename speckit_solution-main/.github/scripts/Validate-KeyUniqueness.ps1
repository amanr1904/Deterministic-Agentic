<#
.SYNOPSIS
    Validates that dimension key columns are unique in the source CSV data.
.DESCRIPTION
    Relationships in Power BI require the "one" side to have unique values.
    This script reads CSV data files and checks that key columns (or composite keys)
    produce unique values - preventing relationship errors at load time.
.PARAMETER DataPath
    Path to the Data/ folder containing CSV files.
.PARAMETER KeyDefinitions
    Hashtable of table name → key column(s) to validate.
    Example: @{ "DimProduct" = @("Sub-Family", "Gender", "Collection"); "DimDate" = @("DateKey") }
.PARAMETER CsvFile
    Path to a specific CSV file to check.
.PARAMETER KeyColumns
    Array of column names that form the composite key.
#>
param(
    [string]$CsvFile,
    [string[]]$KeyColumns
)

if (-not $CsvFile -or -not $KeyColumns) {
    Write-Host "Usage: .\Validate-KeyUniqueness.ps1 -CsvFile 'path\to\file.csv' -KeyColumns @('Col1','Col2')" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Example:" -ForegroundColor Cyan
    Write-Host "  .\Validate-KeyUniqueness.ps1 -CsvFile '.\Data\Q3LaunchData 1.csv' -KeyColumns @('Sub-Family','Gender','Collection')" -ForegroundColor Cyan
    return
}

if (-not (Test-Path $CsvFile)) {
    Write-Error "CSV file not found: $CsvFile"
    return
}

Write-Host "Reading CSV: $CsvFile" -ForegroundColor Cyan
$data = Import-Csv -Path $CsvFile

$totalRows = $data.Count
Write-Host "Total rows: $totalRows" -ForegroundColor Cyan
Write-Host "Key columns: $($KeyColumns -join ' + ')" -ForegroundColor Cyan

# Build composite key for each row
$keys = $data | ForEach-Object {
    $row = $_
    ($KeyColumns | ForEach-Object { $row.$_ }) -join "|"
}

$uniqueKeys = $keys | Sort-Object -Unique
$uniqueCount = $uniqueKeys.Count

Write-Host "Unique key values: $uniqueCount" -ForegroundColor Cyan

if ($uniqueCount -eq $totalRows) {
    Write-Host "PASS: Key ($($KeyColumns -join ' + ')) is UNIQUE across all $totalRows rows." -ForegroundColor Green
} else {
    $duplicateCount = $totalRows - $uniqueCount
    Write-Host "FAIL: Key is NOT UNIQUE. $duplicateCount duplicate(s) found." -ForegroundColor Red

    # Show top duplicates
    $grouped = $keys | Group-Object | Where-Object { $_.Count -gt 1 } | Sort-Object Count -Descending | Select-Object -First 10
    Write-Host "`nTop duplicate keys:" -ForegroundColor Yellow
    $grouped | ForEach-Object {
        Write-Host "  '$($_.Name)' appears $($_.Count) times" -ForegroundColor Yellow
    }
}

return [PSCustomObject]@{
    CsvFile     = $CsvFile
    KeyColumns  = $KeyColumns -join " + "
    TotalRows   = $totalRows
    UniqueKeys  = $uniqueCount
    IsUnique    = ($uniqueCount -eq $totalRows)
    Duplicates  = ($totalRows - $uniqueCount)
}
