<#
.SYNOPSIS
    Validates that TMDL files have columns defined BEFORE partitions.
.DESCRIPTION
    Power BI Desktop throws "Invalid column ID" errors when partition definitions
    appear before column definitions in a TMDL table file.
    This script checks all .tmdl files in the SemanticModel/definition/tables/ folder.
.PARAMETER Path
    Path to the SemanticModel folder. Defaults to searching the workspace.
#>
param(
    [string]$Path
)

if (-not $Path) {
    $Path = Get-ChildItem -Path (Get-Location) -Filter "*.SemanticModel" -Directory -Recurse | Select-Object -First 1 -ExpandProperty FullName
}

if (-not $Path) {
    Write-Error "No .SemanticModel folder found. Provide -Path parameter."
    return
}

$tablesPath = Join-Path $Path "definition\tables"
if (-not (Test-Path $tablesPath)) {
    Write-Error "Tables folder not found at: $tablesPath"
    return
}

$errors = @()
$files = Get-ChildItem -Path $tablesPath -Filter "*.tmdl"

foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw
    $lines = $content -split "`n"

    $firstPartitionLine = -1
    $lastColumnLine = -1

    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i].Trim()
        if ($line -match "^\s*partition\s+" -and $firstPartitionLine -eq -1) {
            $firstPartitionLine = $i
        }
        if ($line -match "^\s*column\s+") {
            $lastColumnLine = $i
        }
    }

    if ($firstPartitionLine -ge 0 -and $lastColumnLine -ge 0 -and $lastColumnLine -gt $firstPartitionLine) {
        $errors += [PSCustomObject]@{
            File    = $file.Name
            Issue   = "Column definition at line $($lastColumnLine + 1) appears AFTER partition at line $($firstPartitionLine + 1)"
            Fix     = "Move all column definitions above the partition block"
        }
    }
}

if ($errors.Count -eq 0) {
    Write-Host "PASS: All TMDL files have columns before partitions." -ForegroundColor Green
} else {
    Write-Host "FAIL: $($errors.Count) file(s) have incorrect element order:" -ForegroundColor Red
    $errors | Format-Table -AutoSize
}

return $errors
