<#
.SYNOPSIS
    Runs all PBIP validation scripts and reports a summary.
.DESCRIPTION
    Master validation script that executes all individual validators:
    1. TMDL element order (columns before partitions)
    2. Column properties (sourceColumn, summarizeBy)
    3. M query field identifier quoting
    4. Report enhanced format structure
    5. Optionally: Key uniqueness against CSV data
.PARAMETER ProjectName
    The base name of the PBIP project (e.g., "Q3DealerBuyingEvent").
    If not specified, auto-detects from workspace.
#>
param(
    [string]$ProjectName
)

$scriptDir = $PSScriptRoot
$workDir = Split-Path $scriptDir -Parent | Split-Path -Parent

if (-not $ProjectName) {
    $pbipFile = Get-ChildItem -Path $workDir -Filter "*.pbip" | Select-Object -First 1
    if ($pbipFile) {
        $ProjectName = $pbipFile.BaseName
    } else {
        Write-Error "No .pbip file found. Provide -ProjectName parameter."
        return
    }
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " PBIP Validation Suite: $ProjectName" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$semanticModelPath = Join-Path $workDir "$ProjectName.SemanticModel"
$reportPath = Join-Path $workDir "$ProjectName.Report"
$allPassed = $true

# 1. TMDL Order
Write-Host "--- [1/4] TMDL Element Order ---" -ForegroundColor White
if (Test-Path $semanticModelPath) {
    $result = & "$scriptDir\Validate-TmdlOrder.ps1" -Path $semanticModelPath
    if ($result.Count -gt 0) { $allPassed = $false }
} else {
    Write-Host "SKIP: SemanticModel folder not found" -ForegroundColor Yellow
}
Write-Host ""

# 2. Column Properties
Write-Host "--- [2/4] Column Properties ---" -ForegroundColor White
if (Test-Path $semanticModelPath) {
    $result = & "$scriptDir\Validate-ColumnProperties.ps1" -Path $semanticModelPath
    if ($result.Count -gt 0) { $allPassed = $false }
} else {
    Write-Host "SKIP: SemanticModel folder not found" -ForegroundColor Yellow
}
Write-Host ""

# 3. M Query Identifiers
Write-Host "--- [3/4] M Query Field Quoting ---" -ForegroundColor White
if (Test-Path $semanticModelPath) {
    $result = & "$scriptDir\Validate-MQueryIdentifiers.ps1" -Path $semanticModelPath
    if ($result.Count -gt 0) { $allPassed = $false }
} else {
    Write-Host "SKIP: SemanticModel folder not found" -ForegroundColor Yellow
}
Write-Host ""

# 4. Report Format
Write-Host "--- [4/4] Report Enhanced Format ---" -ForegroundColor White
if (Test-Path $reportPath) {
    $result = & "$scriptDir\Validate-ReportFormat.ps1" -Path $reportPath
    if ($result.Count -gt 0) { $allPassed = $false }
} else {
    Write-Host "SKIP: Report folder not found" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
if ($allPassed) {
    Write-Host " ALL CHECKS PASSED" -ForegroundColor Green
} else {
    Write-Host " SOME CHECKS FAILED - Review above" -ForegroundColor Red
}
Write-Host "========================================" -ForegroundColor Cyan
