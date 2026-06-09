# Quickstart — Building & Validating the Netflix RLS PBIP

**Feature**: `001-netflixrls-pbi` | **Date**: 2026-06-08

A step-by-step walkthrough to build and validate the Power BI Project. Read the format skills before authoring files:
- TMDL: `plugins/pbip/skills/tmdl/SKILL.md`
- PBIR: `plugins/pbip/skills/pbir-format/SKILL.md`
- PBIP structure: `plugins/pbip/skills/pbip/SKILL.md`

Target output: `Output/NetflixRLS/`. Source CSVs: `Data/Netflix RLS/netflix_titles.csv`, `Data/Netflix RLS/User_Access.csv`.

---

## Step 1 — Scaffold the PBIP project

Create the folder structure from [plan.md](plan.md) (Project Structure). Author:
- `NetflixRLS.pbip`, `.platform` files
- `NetflixRLS.SemanticModel/definition.pbism`, `diagramLayout.json`
- `NetflixRLS.Report/definition.pbir`, `definition/report.json`, `definition/version.json`

`report.json` MUST be the minimal PBIR schema (no `modelExtensions`, `publicCustomVisuals`, `sections`, or `baseTheme`).

## Step 2 — Author the semantic model (TMDL)

1. `database.tmdl` — compatibility level.
2. `model.tmdl` — culture `en-US`, `discourageImplicitMeasures`.
3. `tables/*.tmdl` — six tables with M partitions (Step 3) and columns per [data-model.md](data-model.md). Add measures to `FactTitle`.
4. `relationships.tmdl` — five relationships (R1–R5) with the cross-filter flags from data-model.
5. `roles/Dynamic Country Access.tmdl` — RLS role (Step 4).

## Step 3 — Power Query (M) partitions

Each table reads its CSV independently. Pattern:

```m
let
    Source = Csv.Document(
        File.Contents("C:\Users\...\Data\Netflix RLS\netflix_titles.csv"),
        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true])
    // ... per-table transforms
in
    Promoted
```

- **FactTitle**: cast types; parse `Date Added` (`try Date.From(DateTime.FromText([date_added], [Format="MMMM d, yyyy", Culture="en-US"])) otherwise null`); add `Year Added = Date.Year([Date Added])`.
- **BridgeCountry**: keep `show_id`+`country`; `Text.Split([country], ",")`; expand; `Text.Trim`; remove blanks.
- **BridgeGenre**: keep `show_id`+`listed_in`; split by `,`; expand; `Text.Trim`.
- **DimCountry**: read both CSVs in one query; combine split countries + `User_Access.Country`; `Text.Trim`; `Distinct`.
- **DimGenre**: distinct trimmed genres.
- **User_Access**: `Username`, `Country`; `Text.Trim`.

Rules: `QuoteStyle.Csv`; no cross-query references; no `Table.NestedJoin`; types after headers; null-safe parse.

## Step 4 — RLS role

```tmdl
role 'Dynamic Country Access'
	modelPermission: read

	tablePermission User_Access = User_Access[Username] = USERPRINCIPALNAME()
```

Set `crossFilteringBehavior: bothDirections` on R3 (and R1 as the country bridge) so the entitlement reaches `FactTitle`. The filter is boolean — no measure references.

## Step 5 — Report visuals

Create page `NetflixDashboard` (`displayName "Netflix"`) and the nine visuals per [plan.md](plan.md) Phase F. Apply the dark theme (`#000000` bg, white text, red accents) via `themeCollection`. Each visual: title shown, 1px border, alt text; tables use `active: true` projections; 25px edges, 20px gaps, no overlap.

## Step 6 — Validate

```powershell
# TMDL structural lint
& "plugins\pbip\hooks\bin\tmdl-validate-windows-x64.exe" "Output\NetflixRLS\NetflixRLS.SemanticModel\definition"

# Cross-cutting PBIP validator (0=clean, 1=warn, 2=error)
python "plugins\pbip\skills\pbip\scripts\validate_pbip.py" "Output\NetflixRLS"

# Report JSON syntax
Get-ChildItem "Output\NetflixRLS\NetflixRLS.Report" -Recurse -Include "*.json","*.pbir" |
  ForEach-Object { try { Get-Content $_.FullName -Raw | ConvertFrom-Json | Out-Null }
                   catch { Write-Error "Invalid JSON: $($_.FullName) — $_" } }
```

Fix any exit-code-2 errors before proceeding.

## Step 7 — Acceptance verification (Power BI Desktop)

1. Open `NetflixRLS.pbip` — confirm zero load errors (SC-001).
2. Author view: `Total Titles` = distinct `show_id` count of catalog (SC-006).
3. Modeling → **View as role** → "Dynamic Country Access" + a sample `User_Access.Username`:
   - All visuals filter to only that user's country (SC-002).
   - Try a username NOT in the table → all visuals show zero (SC-003, deny by default).
4. Confirm dark theme (SC-005), chronological year axis, exactly 10 genres descending (SC-007), all nine visuals present (SC-004).
