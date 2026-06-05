<#
.SYNOPSIS
    Validates that M/Power Query expressions properly quote field names with special characters.
.DESCRIPTION
    Field names containing hyphens, spaces, $, or parentheses MUST use #"..." quoting in M.
    Example: [Sub-Family] is INVALID → must be [#"Sub-Family"]
    Simple identifiers like [Date], [Family], [Gender] are fine without quoting.
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

# Characters that require #"..." quoting in M field references
$specialChars = '[- $()&@!#%^+={}|;:,<>?/~`]'

foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw
    $inMExpression = $false
    $lineNum = 0

    foreach ($line in ($content -split "`n")) {
        $lineNum++

        # Detect M expression blocks (inside partition mode = import / expression = ...)
        if ($line -match "expression\s*=") { $inMExpression = $true }
        if ($line -match "^\s*(column|measure|partition|table|hierarchy)\s+" -and $inMExpression -and $line -notmatch "expression") {
            $inMExpression = $false
        }

        if ($inMExpression) {
            # Find field references like [FieldName] that are NOT already quoted as [#"..."]
            $matches = [regex]::Matches($line, '\[(?!#")([^\]]+)\]')
            foreach ($m in $matches) {
                $fieldName = $m.Groups[1].Value
                if ($fieldName -match $specialChars) {
                    $errors += [PSCustomObject]@{
                        File      = $file.Name
                        Line      = $lineNum
                        Field     = $fieldName
                        Issue     = "Field name contains special chars but is not quoted with #`"...`""
                        Fix       = "Change [$fieldName] to [#`"$fieldName`"]"
                    }
                }
            }
        }
    }
}

if ($errors.Count -eq 0) {
    Write-Host "PASS: All M query field references are properly quoted." -ForegroundColor Green
} else {
    Write-Host "FAIL: $($errors.Count) unquoted field reference(s) found:" -ForegroundColor Red
    $errors | Format-Table -AutoSize
}

return $errors
