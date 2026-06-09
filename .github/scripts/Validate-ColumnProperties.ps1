<#
.SYNOPSIS
    Validates that all TMDL columns have required properties (sourceColumn, summarizeBy).
.DESCRIPTION
    Every non-calculated column in TMDL must have:
    - sourceColumn property (maps to data source field)
    - summarizeBy property (aggregation behavior)
    Missing these causes "column not found" errors in Power BI.
.PARAMETER Path
    Path to the SemanticModel folder.
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
    $content = Get-Content $file.FullName
    $currentColumn = $null
    $hasSourceColumn = $false
    $hasSummarizeBy = $false
    $inColumn = $false
    $columnIndent = 0

    for ($i = 0; $i -lt $content.Count; $i++) {
        $line = $content[$i]

        # Detect column start
        if ($line -match "^(\s*)column\s+'?(.+?)'?\s*$") {
            # Save previous column check
            if ($inColumn -and $currentColumn) {
                if (-not $hasSourceColumn -and $currentColumn -notmatch "calculated") {
                    $errors += [PSCustomObject]@{
                        File   = $file.Name
                        Column = $currentColumn
                        Issue  = "Missing sourceColumn property"
                    }
                }
                if (-not $hasSummarizeBy) {
                    $errors += [PSCustomObject]@{
                        File   = $file.Name
                        Column = $currentColumn
                        Issue  = "Missing summarizeBy property"
                    }
                }
            }

            $currentColumn = $Matches[2]
            $columnIndent = $Matches[1].Length
            $inColumn = $true
            $hasSourceColumn = $false
            $hasSummarizeBy = $false
        }
        elseif ($inColumn) {
            # Check if we're still in the column block (indented more than column declaration)
            if ($line -match "^\s*$" -or ($line -match "^(\s*)" -and $Matches[1].Length -le $columnIndent -and $line.Trim().Length -gt 0 -and $line -notmatch "^\s+")) {
                # End of column block - check previous
                if ($currentColumn) {
                    if (-not $hasSourceColumn -and $content[$i - 1] -notmatch "expression\s*=") {
                        $errors += [PSCustomObject]@{
                            File   = $file.Name
                            Column = $currentColumn
                            Issue  = "Missing sourceColumn property"
                        }
                    }
                    if (-not $hasSummarizeBy) {
                        $errors += [PSCustomObject]@{
                            File   = $file.Name
                            Column = $currentColumn
                            Issue  = "Missing summarizeBy property"
                        }
                    }
                }
                $inColumn = $false
                $currentColumn = $null
            }
            else {
                if ($line -match "sourceColumn") { $hasSourceColumn = $true }
                if ($line -match "summarizeBy") { $hasSummarizeBy = $true }
            }
        }
    }
}

if ($errors.Count -eq 0) {
    Write-Host "PASS: All columns have required properties." -ForegroundColor Green
} else {
    Write-Host "FAIL: $($errors.Count) column property issue(s) found:" -ForegroundColor Red
    $errors | Format-Table -AutoSize
}

return $errors
