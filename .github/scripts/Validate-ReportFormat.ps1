<#
.SYNOPSIS
    Validates that the Power BI report uses the enhanced PBIR folder format.
.DESCRIPTION
    Modern Power BI Desktop requires the enhanced folder format:
    - {Name}.Report/definition/report.json (NO sections/visualContainers)
    - {Name}.Report/definition/pages/ folder with per-page subfolders
    - Each page has page.json + visuals/ folder with per-visual subfolders
    
    The legacy flat format (sections array in report.json) causes ThemeServiceBase crash.
.PARAMETER Path
    Path to the .Report folder.
#>
param(
    [string]$Path
)

if (-not $Path) {
    $Path = Get-ChildItem -Path (Get-Location) -Filter "*.Report" -Directory -Recurse | Select-Object -First 1 -ExpandProperty FullName
}

if (-not $Path) {
    Write-Error "No .Report folder found. Provide -Path parameter."
    return
}

$errors = @()

# Check definition.pbir exists
$pbir = Join-Path $Path "definition.pbir"
if (-not (Test-Path $pbir)) {
    $errors += [PSCustomObject]@{ Check = "definition.pbir"; Status = "MISSING"; Detail = "Required file not found" }
} else {
    $pbirContent = Get-Content $pbir -Raw | ConvertFrom-Json
    if (-not $pbirContent.datasetReference) {
        $errors += [PSCustomObject]@{ Check = "definition.pbir"; Status = "INVALID"; Detail = "Missing datasetReference" }
    }
}

# Check definition/report.json
$reportJson = Join-Path $Path "definition\report.json"
if (-not (Test-Path $reportJson)) {
    $errors += [PSCustomObject]@{ Check = "report.json"; Status = "MISSING"; Detail = "definition/report.json not found" }
} else {
    $reportContent = Get-Content $reportJson -Raw | ConvertFrom-Json
    if ($reportContent.sections) {
        $errors += [PSCustomObject]@{ Check = "report.json"; Status = "LEGACY FORMAT"; Detail = "Contains 'sections' array - must use enhanced folder format instead" }
    }
    if ($reportContent.themeCollection.baseTheme) {
        $errors += [PSCustomObject]@{ Check = "report.json"; Status = "THEME ERROR"; Detail = "themeCollection has baseTheme reference - must be empty {}" }
    }
}

# Check definition/version.json
$versionJson = Join-Path $Path "definition\version.json"
if (-not (Test-Path $versionJson)) {
    $errors += [PSCustomObject]@{ Check = "version.json"; Status = "MISSING"; Detail = "definition/version.json not found" }
}

# Check pages structure
$pagesDir = Join-Path $Path "definition\pages"
if (-not (Test-Path $pagesDir)) {
    $errors += [PSCustomObject]@{ Check = "pages/"; Status = "MISSING"; Detail = "definition/pages/ folder not found" }
} else {
    $pagesJson = Join-Path $pagesDir "pages.json"
    if (-not (Test-Path $pagesJson)) {
        $errors += [PSCustomObject]@{ Check = "pages.json"; Status = "MISSING"; Detail = "pages/pages.json not found" }
    } else {
        $pagesConfig = Get-Content $pagesJson -Raw | ConvertFrom-Json
        $pageOrder = $pagesConfig.pageOrder
        
        foreach ($pageName in $pageOrder) {
            $pageDir = Join-Path $pagesDir $pageName
            if (-not (Test-Path $pageDir)) {
                $errors += [PSCustomObject]@{ Check = "Page: $pageName"; Status = "MISSING"; Detail = "Page folder not found" }
                continue
            }

            $pageJson = Join-Path $pageDir "page.json"
            if (-not (Test-Path $pageJson)) {
                $errors += [PSCustomObject]@{ Check = "Page: $pageName"; Status = "NO page.json"; Detail = "page.json not found in page folder" }
            }

            $visualsDir = Join-Path $pageDir "visuals"
            if (-not (Test-Path $visualsDir)) {
                $errors += [PSCustomObject]@{ Check = "Page: $pageName"; Status = "NO visuals/"; Detail = "visuals/ folder not found" }
            } else {
                $visualFolders = Get-ChildItem -Path $visualsDir -Directory
                if ($visualFolders.Count -eq 0) {
                    $errors += [PSCustomObject]@{ Check = "Page: $pageName"; Status = "EMPTY"; Detail = "No visual folders in visuals/" }
                }
                foreach ($vf in $visualFolders) {
                    $visualJson = Join-Path $vf.FullName "visual.json"
                    if (-not (Test-Path $visualJson)) {
                        $errors += [PSCustomObject]@{ Check = "Visual: $($vf.Name)"; Status = "NO visual.json"; Detail = "visual.json not found in visual folder" }
                    }
                }
            }
        }

        Write-Host "Pages found: $($pageOrder.Count)" -ForegroundColor Cyan
    }
}

if ($errors.Count -eq 0) {
    Write-Host "PASS: Report uses correct enhanced PBIR folder format." -ForegroundColor Green
} else {
    Write-Host "FAIL: $($errors.Count) issue(s) found:" -ForegroundColor Red
    $errors | Format-Table -AutoSize
}

return $errors
