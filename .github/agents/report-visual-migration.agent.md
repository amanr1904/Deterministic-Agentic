---
description: Extract Tableau visual metadata and generate Power BI report visuals with professional formatting. Runs the full visual migration pipeline — extraction → report constitution → specify → clarify → plan → tasks → implement (generate PBIR enhanced folder format with per-visual JSON files).
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Skill References

These skills are decomposed into focused, single-responsibility files so no rule is skipped. Read the router first, then the specific skill for each step.

**Routers (overview + which focused skill to read per task):**
- `.github/skills/tableau-visual-extraction/SKILL.md` — extraction router
- `.github/skills/report-visual-generation/SKILL.md` — generation router
- `.github/skills/report-visual-generation/report-constitution-template.md` — constitution defaults

**Focused extraction skills (read the one for your step):**
- `.github/skills/tableau-mark-mapping/SKILL.md` — Tableau mark → Power BI visualType (canonical, Automatic inference)
- `.github/skills/tableau-worksheet-extraction/SKILL.md` — per-worksheet encodings, combo, reference lines
- `.github/skills/tableau-dashboard-extraction/SKILL.md` — dashboard size, zones, navigation buttons
- `.github/skills/tableau-format-translation/SKILL.md` — format strings + extraction output document

**Focused generation skills (read the one for your step):**
- `.github/skills/report-theme-colors/SKILL.md` — copy Tableau theme OR standard fallback (color application)
- `.github/skills/report-layout-gapping/SKILL.md` — canvas, edge padding, 20px gaps, no-overlap, coordinate scaling
- `.github/skills/report-borders-titles/SKILL.md` — mandatory border on ALL visuals + title placement rules
- `.github/skills/report-slicers/SKILL.md` — slicer template + `title.show = false` rule
- `.github/skills/report-visual-json/SKILL.md` — visual.json structure, bindings, allowed top-level properties
- `.github/skills/report-navigation-buttons/SKILL.md` — nav/toggle buttons (action goes in `visualLink`)
- `.github/skills/report-pbir-folder-format/SKILL.md` — PBIR folder + report/version/pages/page entry files
- `.github/skills/report-load-failure-rules/SKILL.md` — final crash-prevention checklist

**Plugin references (validation + deeper format detail):**
- `plugins/pbip/skills/pbir-format/SKILL.md` — PBIR JSON structure, schema patterns, visual.json properties
- `plugins/reports/skills/create-pbi-report/SKILL.md` — report creation best practices
- `plugins/reports/skills/pbi-report-design/SKILL.md` — layout, spacing, visual hierarchy rules
- `plugins/reports/skills/tableau-theme-extraction/SKILL.md` — Extract theme colors from TWB files

## MANDATORY Visual Fidelity Rules

These rules MUST be followed for every migration. They ensure the Power BI report matches the original Tableau dashboard visually:

### Rule 1: Page Size MUST Match Dashboard Size
- Extract `maxwidth` and `maxheight` from Tableau `<size>` element in `<dashboard>`
- Set `width` and `height` in page.json to these exact pixel values
- Do NOT default to 1280×720 — use the actual Tableau dashboard size

### Rule 2: Titles MUST Match Tableau Worksheet Names Exactly
- Each visual's title text MUST be the Tableau worksheet name (as embedded in the dashboard)
- Do NOT paraphrase, abbreviate, or "improve" titles
- Example: If Tableau shows "Total Movies and TV Shows By Years", the PBI visual title MUST be exactly that

### Rule 3: Theme MUST Be Extracted and Applied
- Extract ALL style-rules from the TWB `<style>` element (background-color, mark color, font-color, title-color)
- Apply to every visual: page background, visual background, title font color, axis label colors, data point colors, legend text color
- Use `visualContainerObjects.background` and `visualContainerObjects.border` on EVERY visual
- Use `visual.objects.title[].properties.fontColor` for title colors
- Use `visual.objects.categoryAxis/valueAxis[].properties.labelColor` for axis text
- Use `visual.objects.legend[].properties.labelColor` for legend text

### Rule 4: Layout Must Use Exact Tableau Zone Positions
- Extract zone `x`, `y`, `w`, `h` from `<dashboard><zones>` (values are in 0–100000 coordinate space)
- Convert to pixel positions: `px = zone_value / 100000 * dashboard_dimension`
- Apply calculated positions directly to visual.json `position` object
- NEVER overlap visuals — maintain minimum 8px gaps

### Rule 5: Chart Type Mapping Must Preserve Orientation
- `clusteredColumnChart` = VERTICAL bars (categories on X-axis)
- `clusteredBarChart` = HORIZONTAL bars (categories on Y-axis)
- `areaChart` = stacked area (use Series field for legend/color split)
- `donutChart` = for Movie vs TV Show distribution (pie-like with center hole)
- `filledMap` = for geographic/country distribution
- Tableau "Bar" mark with dimension on rows → `clusteredBarChart` (horizontal)
- Tableau "Bar" mark with dimension on cols → `clusteredColumnChart` (vertical)

### Rule 6: Borders on ALL Visuals
- Every visual MUST have `visualContainerObjects.border` with `show: true`
- Use a subtle dark border (e.g., `#333333` for dark themes, `#E0E0E0` for light themes)

### Rule 8: Slicer Title MUST Be Disabled
- Slicers have a BUILT-IN header (`objects.header`) that already displays the field name
- NEVER set `visualContainerObjects.title.show = true` on slicers — this creates a DUPLICATE label (header + title)
- For slicers: always set `visualContainerObjects.title[].properties.show` to `false` (or omit title entirely)
- The slicer header color/font can be styled via `objects.header[].properties.fontColor`

### Rule 7: Data Color Consistency
- Extract mark colors from TWB style-rules (`style-rule element='mark'`)
- Apply to `visual.objects.dataPoint[].properties.fill`
- For charts with legend (multiple series), use TWB color palette entries
- Movie = `#d3293d`, TV Show = `#ffbeb2` (Netflix standard, or extract from TWB)

## Execution — Full Visual Migration Pipeline (ALL stages MANDATORY)

### Stage 1: Visual Extraction (MUST parse .twb XML directly)

**CRITICAL**: This stage MUST read and parse the actual `.twb` XML file — NOT just rely on the high-level analysis summary in `tableau-analysis-output.md`. The analysis file only contains metadata (datasources, columns, calculated fields). It does NOT contain mark types, field shelves, or dashboard zone positions needed to generate correct visuals.

**Step 1a: Locate the TWB file**
- Read `.specify/memory/{WorkbookName}/tableau-analysis-output.md` to get worksheet/dashboard names
- Use `file_search` with `Data/**/*.twb` to locate the actual workbook file

**Step 1b: Parse worksheet visual encodings from TWB XML**

For EACH `<worksheet>`, parse the `<table><panes><pane>` element to extract:

1. **Mark type**: `<mark class='...'>` — determines the Power BI visual type
   - Bar → clusteredBarChart or clusteredColumnChart (check rows/cols for orientation)
   - Line → lineChart
   - Pie → pieChart
   - Square (with color+size on measure) → treemap
   - Square (with dimensions on BOTH rows+cols) → pivotTable (matrix/heatmap)
   - Area → areaChart
   - Text (single measure) → card
   - Text (rows+cols) → pivotTable
   - Automatic → INFER from encodings (see rules in tableau-visual-extraction SKILL.md)

2. **Field shelves**:
   - `<rows>` → Y-axis fields (may contain hierarchy with `/` separators)
   - `<cols>` → X-axis fields

3. **Encodings** from `<pane><encodings>`:
   - `<color column='...'>` → Legend/color series field
   - `<size column='...'>` → Size encoding (treemap indicator)
   - `<text column='...'>` → Data labels
   - `<wedge-size column='...'>` → Pie chart measure

4. **Dual-axis / combo** (detect, do not assume): a worksheet with TWO measures on one axis or a `<dual-axis>` marker →
   - Bar/Column + Line → `lineClusteredColumnComboChart` / `lineStackedColumnComboChart`
   - Two lines, independent scales → `lineChart` with secondary value axis
   - Record both measures and which is the secondary axis. If none, treat as single-measure visual.

5. **Reference / trend lines** (`<reference-line>`, `<reference-line-aggregation>`, `<trend-lines>`) →
   - Constant/average/min/max → analytics-pane constant/average/min/max line
   - Trend → analytics-pane trend line
   - If none present, add no analytics lines (do not invent them).

**Step 1b-i: Field formatting**
- Apply the Tableau field format strings captured in `tableau-analysis-output.md` to the matching visual fields / measures (see the Format String Translation table in `tableau-visual-extraction/SKILL.md`). Where no format was captured, leave the model default — do not guess.

**Step 1c: Parse dashboard zone layout from TWB XML**

For EACH `<dashboard>`, extract:
- `<size maxwidth='...' maxheight='...'>` → dashboard pixel dimensions
- Each `<zone>` element → type (viz/filter/paramctrl), name (worksheet), x, y, w, h positions
- Each `<zone type-v2='dashboard-object'>` with `<button>` child → navigation/toggle buttons

**Step 1c-ii: Parse navigation buttons from TWB XML**

For EACH `<dashboard>`, find all zones with `type-v2='dashboard-object'` containing `<button>` elements:

1. **Page navigation buttons** (`action='tabdoc:goto-sheet window-id="..."'`):
   - Extract the `window-id` value from the action attribute
   - Resolve to target dashboard name by matching `<window class='dashboard' name='...'>` elements
   - Extract tooltip from `<button-visual-state><tooltip-text>`
   - Record zone position: x, y, w, h

2. **Toggle buttons** (empty `action=''` with `<toggle-action>` child):
   - Extract `zone-ids` from `<toggle-action>` text to identify target zones
   - Extract tooltip from `<button-visual-state><tooltip-text>` (may have multiple visual states)
   - Record zone position: x, y, w, h
   - Note: toggle buttons have `active-visual-state-index` indicating default state

3. **Button container layout**:
   - Note parent zone `friendly-name` (e.g., "Horizontal Cont. (Button)")
   - Note `layout-strategy-id` (e.g., "distribute-evenly") for positioning

**Power BI mapping for buttons** (canonical detail in `.github/skills/report-navigation-buttons/SKILL.md`):
- `goto-sheet` → `actionButton` visual with `visualContainerObjects.visualLink.type = "PageNavigation"` and `navigationSection` target page name (NOT `objects.action`)
- `toggle` (show/hide zones) → `actionButton` visual with `visualContainerObjects.visualLink.type = "Bookmark"` (note: requires bookmark pairs for show/hide states — generate a comment in output noting manual bookmark setup needed)

**Step 1d: Save comprehensive visual extraction output**

Save ALL extracted data to: `.specify/memory/{WorkbookName}/tableau-visuals-output.md`

**VALIDATION GATE**: Before proceeding to Stage 2, verify:
- [ ] Every worksheet from the analysis has a corresponding mark type extracted
- [ ] Dashboard zone positions have been extracted for ALL dashboards
- [ ] Navigation buttons have been extracted for ALL dashboards that contain `<button>` elements
- [ ] The output file `.specify/memory/{WorkbookName}/tableau-visuals-output.md` exists and contains the Visual Inventory table
- **If ANY of these checks fail, DO NOT proceed** — re-parse the TWB until extraction is complete

**Example PowerShell to extract mark types** (use as reference):
```powershell
[xml]$twb = Get-Content "Data/{subfolder}/{workbook}.twb" -Raw
$twb.workbook.worksheets.worksheet | ForEach-Object {
    $name = $_.name
    $pane = $_.table.panes.pane
    if ($pane -is [array]) { $pane = $pane[0] }
    $mark = if ($pane.mark -is [array]) { $pane.mark[0].class } else { $pane.mark.class }
    $rows = $_.table.rows
    $cols = $_.table.cols
    Write-Host "$name | mark=$mark | rows=$rows | cols=$cols"
}
```

### Stage 2: Read Universal Report Constitution

The report constitution at `.specify/memory/report-constitution.md` is a **universal rulebook** shared across ALL report visual migrations. It is NOT regenerated per workbook.

**Actions:**
1. Read `.specify/memory/report-constitution.md` — this contains universal layout rules (padding, gaps, typography, theme defaults, slicer standards, chart type mappings)
2. If the workbook has a distinctive theme (dark mode, brand colors), extract colors from TWB `<style>` and save as `.specify/memory/{WorkbookName}/theme-overrides.md` — do NOT modify the universal report constitution
3. Apply the universal rules from the constitution, with workbook-specific theme overrides layered on top

**NEVER overwrite or regenerate `.specify/memory/report-constitution.md`** — it is the shared authority for all report migrations in this workspace.

The following universal rules always apply (from the constitution):
- 25px edge padding from top and sides
- 20px gap between visuals (MANDATORY — visuals must NEVER overlap)
- **Minimum heights**: Slicers ≥ 55px, Cards ≥ 80px, Charts ≥ 130px
- **Layout validation**: For each row, ensure `previous_row_bottom + 20 ≤ current_row_y`. For adjacent visuals in the same row, ensure `left_visual_right + 20 ≤ right_visual_x`
- All visuals in the same row MUST have identical y and height values
- Font: Aptos, 10pt for data
- Professional background and theme (unless overridden by workbook theme)
- Table visuals: Numbers LEFT-aligned, Text RIGHT-aligned, Dates LEFT-aligned
- Data format preservation: same format as Tableau source

### Stage 3: Specify (Visual Specification)

Write a visual specification document at `specs/{feature-dir}/visual-spec.md`:

```markdown
# Visual Specification: {Workbook Name} Report

## Pages
### Page 1: {Dashboard Name}
- Canvas: 1280 × 720
- Layout: {description of visual arrangement}

## Visuals
### V1: {Worksheet Name}
- Type: {Power BI visual type}
- Position: x={x}, y={y}, w={w}, h={h}
- Category: {table.column}
- Values: {table.measure}
- Legend: {table.column} (if any)
- Title: "{title text}"
- Filters: {description}

### V2: ...

## Slicers
### S1: {Filter Name}
- Type: Dropdown / List / Slider
- Field: {table.column}
- Position: x={x}, y={y}, w={w}, h={h}
- **Title: DISABLED** (slicers use built-in header only, never title)

## Navigation Buttons
### B1: {Tooltip Text}
- Type: Page Navigation / Bookmark Toggle
- Target: {target_page_name}
- Position: x={x}, y={y}, w={w}, h={h}
- Tooltip: "{tooltip_text}"
- Icon: {description of button appearance}
```

### Stage 4: Clarify

Review the specification for ambiguities:
1. Are there Tableau mark types that don't have a direct Power BI equivalent?
   - **If YES**: Use `vscode_askQuestions` to present 2-3 Power BI alternatives with descriptions
   - Record the user's choice and update the spec accordingly
2. Are there table calculations that need special DAX + visual combination?
3. Does the layout overflow the 1280×720 canvas?
4. Are there interactive features (actions, highlights) that need bookmarks?
5. Are there dual-axis charts that need combo chart mapping?
6. Are there navigation buttons that target dashboards not in this workbook?
7. Are there toggle buttons — note that bookmark-based toggling requires manual bookmark creation in Power BI Desktop after opening?

**CRITICAL Visual Type Matching Rules:**
- Tableau Text mark with rows only → `tableEx` (flat table) — NEVER bar/column chart
- Tableau Text mark with rows AND cols → `pivotTable` (matrix/cross-tab)
- Tableau Area mark → `areaChart` — NEVER lineChart
- Tableau single KPI text → `card`
- Filter/parameter controls → `slicer`
- Tableau Square mark with single dimension + color/size on measure → `treemap`
- Tableau Square mark with dimensions on BOTH rows AND cols + color on measure → `pivotTable` with conditional formatting (heatmap)
- Tableau Automatic mark with color + size encodings on same measure + text/label on dimension → `treemap` (the size encoding is the key indicator)
- Tableau Line mark with color encoding on a dimension (e.g. highlight calc) → `lineChart` with Legend field
- Tableau Automatic mark with hierarchy on rows (fields joined by `/`) + measure on cols → `clusteredBarChart` with row hierarchy
- When unsure, ASK the user — do NOT silently default to bar/column charts

**CRITICAL — Faithfulness to Original**:
- Generate ONLY the visuals that exist in the original Tableau dashboard — do NOT invent new visuals
- If a Tableau dashboard has 4 worksheets embedded, the PBI page must have exactly 4 chart visuals (plus slicers for filter controls)
- Match the EXACT chart type from Tableau — a treemap must stay a treemap, a heatmap must become a matrix, a pie must stay a pie
- If the original has a color/legend encoding, the PBI visual MUST include a Legend field binding
- Preserve data labels if the original shows them (text encoding → data labels ON)

Encode clarifications back into the spec. Make reasonable professional choices where user input is not available.

### Stage 5: Plan

Write implementation plan at `specs/{feature-dir}/visual-plan.md`:

```markdown
# Implementation Plan: Visual Layer

## Approach
1. Generate page structure in report.json
2. Create visual containers with correct coordinates
3. Apply formatting/theme as per constitution
4. Wire up data bindings to semantic model tables/measures
5. Generate slicer visuals for filter controls
6. Validate JSON structure

## Technical Decisions
- Coordinate system: Scale from Tableau canvas to 1280×720
- Config format: Stringified JSON inside config property
- Query format: Semantic query model v2
```

### Stage 6: Tasks

Write task breakdown at `specs/{feature-dir}/visual-tasks.md`:

```markdown
# Tasks: Visual Generation

- [ ] Task 1: Create page definition (sections array entry)
- [ ] Task 2: Generate KPI card visuals (if any)
- [ ] Task 3: Generate chart visuals (bar, line, pie, etc.)
- [ ] Task 4: Generate table/matrix visuals
- [ ] Task 5: Generate slicer visuals
- [ ] Task 6: Generate navigation button visuals (page navigation + toggle)
- [ ] Task 7: Apply formatting (fonts, colors, alignment)
- [ ] Task 8: Wire up data queries (prototypeQuery, projections)
- [ ] Task 9: Write final report.json
- [ ] Task 10: Validate report opens in Power BI Desktop
```

### Stage 7: Implement — Generate Report Visuals (Enhanced PBIR Folder Format)

This is the critical implementation stage. Generate the actual report using the **Enhanced PBIR Folder Format**.

**CRITICAL**: Use the folder-based format (NOT the legacy flat report.json with `sections` array).
The legacy format causes ThemeServiceBase crashes in modern Power BI Desktop.

**Follow these rules strictly:**
1. Read the semantic model (TMDL files) to get exact table/column/measure names
2. Apply constitution padding/gap/font rules to every visual
3. Scale Tableau coordinates to Power BI canvas (1280×720)
4. Generate ALL pages for ALL Tableau dashboards (not just the first one)
5. Use correct visual types matching Tableau marks exactly

**Generate this folder structure inside the `Output/{WorkbookName}/` directory:**
```
Output/{WorkbookName}/{ProjectName}.Report/
├── definition.pbir              ← Points to semantic model
└── definition/
    ├── report.json              ← Report-level config (NO visuals here)
    ├── version.json             ← {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"}
    └── pages/
        ├── pages.json           ← Page ordering array
        ├── ReportSection1/
        │   ├── page.json        ← Page config (displayName, width, height)
        │   └── visuals/
        │       ├── {visual_name}/
        │       │   └── visual.json  ← Individual visual definition
        │       └── ...
        ├── ReportSection2/
        │   └── ...
        └── ...
```

**report.json (root level - NO visuals):**
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
  "themeCollection": {},
  "settings": {
    "useStylableVisualContainerHeader": true
  }
}
```

> **ALWAYS** include `"useStylableVisualContainerHeader": true` in `settings` to enable the modern visual header with updated styling options.

> **CRITICAL**: Schema MUST be `3.0.0`. NEVER use `1.0.0`. NEVER add `"datasetBinding"` or `"layoutOptimization"` — neither belongs in report.json. Dataset binding lives ONLY in `definition.pbir`.

> **CRITICAL**: If you include `baseTheme` in `themeCollection`, `reportVersionAtImport` MUST be an **object** (NOT a string). Use: `{"visual": "1.8.95", "report": "2.0.95", "page": "1.3.95"}`. A string value like `"5.50"` will cause a schema validation crash.

**pages.json (page ordering):**
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
  "pageOrder": ["ReportSection1"]
}
```

**page.json (per page):**
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
  "name": "ReportSection1",
  "displayName": "Dashboard Name",
  "displayOption": "FitToPage",
  "height": 720,
  "width": 1280
}
```

**visual.json (per visual):**
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
  "name": "unique_visual_name",
  "position": {
    "x": 25, "y": 25, "z": 0,
    "height": 300, "width": 400, "tabOrder": 0
  },
  "visual": {
    "visualType": "tableEx",
    "query": {
      "queryState": {
        "Values": {
          "projections": [{
            "field": {
              "Column": {
                "Expression": {"SourceRef": {"Entity": "TableName"}},
                "Property": "ColumnName"
              }
            },
            "queryRef": "TableName.ColumnName",
            "active": true
          }]
        }
      }
    },
    "objects": {},
    "visualContainerObjects": {
      "title": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "text": {"expr": {"Literal": {"Value": "'Visual Title'"}}}
      }}],
      "border": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#E0E0E0'"}}}}},
        "radius": {"expr": {"Literal": {"Value": "4D"}}}
      }}]
    }
  }
}
```

**SLICER-SPECIFIC TEMPLATE** — use this instead of the above template for ALL slicer visuals:
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
  "name": "slicer_{field_name}",
  "position": {
    "x": 25, "y": 25, "z": 0,
    "height": 55, "width": 300, "tabOrder": 0
  },
  "visual": {
    "visualType": "slicer",
    "query": {
      "queryState": {
        "Values": {
          "projections": [{
            "field": {
              "Column": {
                "Expression": {"SourceRef": {"Entity": "TableName"}},
                "Property": "ColumnName"
              }
            },
            "queryRef": "TableName.ColumnName",
            "active": true
          }]
        }
      }
    },
    "objects": {
      "data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}]
    },
    "visualContainerObjects": {
      "title": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}
      }}],
      "border": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#E0E0E0'"}}}}},
        "radius": {"expr": {"Literal": {"Value": "4D"}}}
      }}]
    }
  }
}
```

> **CRITICAL — NO FILTERS IN visual.json**: The `visualContainer/2.4.0` schema ONLY allows these top-level properties: `$schema`, `name`, `position`, `visual` (or `visualGroup`). **NEVER** add `filters`, `filterConfig`, or ANY other top-level property — Power BI Desktop rejects them with "Property has not been defined and the schema does not allow additional properties". For Top N / measure-based filtering, rely on DAX logic (e.g., `IF([Rank] <= SELECTEDVALUE(...), 1, 0)`) and let users add visual filters in Desktop UI. Page-level filters go in `page.json`, report-level filters go in `report.json`.
> **CRITICAL — Slicer Title Rule**: For `visualType: "slicer"`, ALWAYS use the SLICER-SPECIFIC template above — do NOT copy the generic visual template. The slicer has a BUILT-IN header that already shows the field name. Setting `title.show = true` on a slicer creates DUPLICATE labels (header + title stacked). This is the #1 most common mistake.
> **CRITICAL**: In page.json, `"displayOption"` MUST be a string (`"FitToPage"`, `"FitToWidth"`, or `"ActualSize"`), NEVER an integer.
> **CRITICAL**: In pages.json, the `$schema` URL must use `pagesMetadata` (NOT `pages`): `.../pagesMetadata/1.0.0/schema.json`

**NAVIGATION BUTTON TEMPLATE** — use this for page navigation buttons (Tableau `goto-sheet`):
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
  "name": "nav_button_{target_page}",
  "position": {
    "x": 25, "y": 25, "z": 1000,
    "height": 40, "width": 120, "tabOrder": 0
  },
  "visual": {
    "visualType": "actionButton",
    "objects": {
      "icon": [{"properties": {
        "shapeType": {"expr": {"Literal": {"Value": "'Arrow'"}}}
      }}],
      "outline": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}
      }}],
      "fill": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "fillColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#072a35'"}}}}}
      }}],
      "text": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "text": {"expr": {"Literal": {"Value": "'{button_label}'"}}},
        "fontColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#FFFFFF'"}}}}}
      }}]
    },
    "visualContainerObjects": {
      "visualLink": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "type": {"expr": {"Literal": {"Value": "'PageNavigation'"}}},
        "navigationSection": {"expr": {"Literal": {"Value": "'{target_page_name}'"}}}
      }}],
      "title": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}
      }}],
      "background": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#072a35'"}}}}}
      }}],
      "border": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}
      }}]
    }
  }
}
```

> **Navigation Button Rules** (canonical detail in `.github/skills/report-navigation-buttons/SKILL.md`):
> - **The action MUST be in `visualContainerObjects.visualLink`, NOT `objects.action`** — placing it under `objects.action` (or using a `page` key) makes the button render but do nothing (navigation silently fails).
> - `visualLink.type` = `'PageNavigation'` for goto-sheet buttons.
> - `visualLink.navigationSection` = the `name` field from the target page's `page.json` (e.g. `"'ReportSection2'"`).
> - Button label (`text.text`) should use the extracted tooltip text from Tableau (e.g. "Go to Sales Dashboard").
> - Use high z-index (1000+) so buttons render above other visuals.
> - Style the button background/fill to match the Tableau button bar color (e.g., `#072a35` for dark nav bars).
> - Set `title.show = false` — buttons don't need titles.
> - Group navigation buttons together at the same y-position with consistent spacing.

**BOOKMARK TOGGLE BUTTON TEMPLATE** — use for Tableau toggle (show/hide) buttons:
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
  "name": "toggle_button_{function}",
  "position": {
    "x": 25, "y": 25, "z": 1000,
    "height": 40, "width": 40, "tabOrder": 0
  },
  "visual": {
    "visualType": "actionButton",
    "objects": {
      "icon": [{"properties": {
        "shapeType": {"expr": {"Literal": {"Value": "'Filter'"}}}
      }}],
      "outline": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}
      }}],
      "fill": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "fillColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#072a35'"}}}}}
      }}],
      "text": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}
      }}]
    },
    "visualContainerObjects": {
      "visualLink": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "type": {"expr": {"Literal": {"Value": "'Bookmark'"}}},
        "bookmark": {"expr": {"Literal": {"Value": "''"}}}
      }}],
      "title": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}
      }}],
      "background": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#072a35'"}}}}}
      }}],
      "border": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "false"}}}
      }}]
    }
  }
}
```

> **Toggle Button Notes** (canonical detail in `.github/skills/report-navigation-buttons/SKILL.md`):
> - **The action MUST be in `visualContainerObjects.visualLink`, NOT `objects.action`.**
> - `visualLink.type` = `'Bookmark'` — requires bookmarks to be created manually in Power BI Desktop.
> - Leave `visualLink.bookmark` empty (`"''"`) — user must assign bookmarks after opening in Desktop.
> - Use `icon.shapeType = "'Filter'"` for filter toggle buttons (matches the filter icon concept).
> - Add a comment in the visual-spec noting that bookmark pairs (show/hide states) must be created manually.
> - Tooltip text from Tableau (e.g., "Show Dashboard Filters" / "Close Dashboard Filters") should be noted in spec for user reference.

**Write ALL files using UTF-8 without BOM.**

> **CRITICAL — PowerShell Encoding**: NEVER use `Set-Content -Encoding UTF8` in Windows PowerShell 5.1 — it writes UTF-8 WITH BOM which breaks Power BI. Use `[System.IO.File]::WriteAllText($path, $content, [System.Text.UTF8Encoding]::new($false))` instead, or use the `create_file` tool which writes without BOM.

### Stage 8: Validate

> Validation rules derived from `plugins/pbip/hooks/validate-pbir.sh` and `plugins/pbip/hooks/validate-report-binding.sh`.

After generating the report folder structure:

**JSON & Schema validation (from hooks):**
1. Verify all JSON files pass syntax check (valid JSON, no trailing commas)
2. Verify `$schema` URLs all start with `https://developer.microsoft.com/json-schemas/fabric/item/report/definition/`
3. Verify visual.json has required fields: `$schema`, `name`, `position`, and `visual` (or `visualGroup`)
4. Verify page.json has required fields: `$schema`, `name`, `displayName`, `displayOption`
5. Verify report.json has required fields: `$schema`, `themeCollection`
6. Verify definition.pbir has: `$schema`, `version`, `datasetReference`
7. Verify NO folder names contain spaces (pages/visuals won't render if they do)
8. Verify visual/page `name` values match `^[a-zA-Z0-9_][a-zA-Z0-9_-]*$` (non-compliant names are silently ignored)

**Data binding validation (from hooks):**
9. Verify all `queryRef` values match actual model tables/columns/measures from TMDL files
10. Verify definition.pbir `byPath` points to an existing SemanticModel folder

**Layout validation:**
11. **Verify no visual overlaps** — for EVERY pair of visuals, check:
    - Horizontal: if same row (y ranges overlap), then `left.x + left.width + 20 ≤ right.x`
    - Vertical: if same column (x ranges overlap), then `top.y + top.height + 20 ≤ bottom.y`
    - If ANY overlap exists, recalculate positions before writing files
12. Verify all positions respect edge padding (≥25px from edges)
13. Verify minimum heights: slicers ≥ 55px, cards ≥ 80px, charts ≥ 130px
14. Verify all visuals in the same logical row have identical y and height values
15. Verify all visuals fit within the 1280×720 canvas (x+width ≤ 1255, y+height ≤ 695)

**Visual fidelity validation:**
16. Verify visual types are valid Power BI `visualType` identifiers
17. Verify ALL Tableau dashboards have corresponding pages (check pages.json matches dashboard count)
18. Verify visual types match Tableau marks:
    - Text tables → `tableEx` or `pivotTable` (NOT bar charts)
    - Area marks → `areaChart` (NOT lineChart)
    - Square with color+size → `treemap` or `pivotTable` (NOT clusteredColumnChart)
19. Verify ALL visuals have `visualContainerObjects.border` with `show: true`
20. Verify ALL slicers have `visualContainerObjects.title.show = false`
21. Verify folder structure: each visual has its own subfolder with `visual.json`
22. Verify `themeCollection` is `{}` in report.json (no baseTheme references)
23. Verify ALL navigation buttons from Tableau are generated as `actionButton` visuals:
    - `goto-sheet` buttons → `actionButton` with `visualContainerObjects.visualLink.type = "PageNavigation"` and valid `navigationSection` target (NOT `objects.action`)
    - `toggle` buttons → `actionButton` with `visualContainerObjects.visualLink.type = "Bookmark"`
    - Button positions match extracted zone coordinates (scaled to PBI canvas)
    - Navigation buttons have `title.show = false`
24. Verify navigation button `visualLink.navigationSection` targets match actual page `name` values in page.json files
25. Verify dual-axis worksheets are mapped to a combo visual (`lineClusteredColumnComboChart` / `lineStackedColumnComboChart`) or a secondary-axis line — NOT split into two unrelated visuals
26. Verify reference/trend lines from Tableau are represented via the analytics pane only when they existed in the source (none invented)

Report success/failure and list all pages with their visuals (types and positions).

## Anti-Hallucination Guardrails

- **Generate only source-backed visuals.** Every page, visual, field binding, button, combo measure, and reference line MUST trace to a concrete element in the `.twb` XML or the analysis output. Never invent visuals, pages, or bindings to "fill" a layout.
- **Match counts exactly.** Pages = dashboards; visuals per page = that dashboard's zones. Do not add extra decorative visuals.
- **`None` means none.** If a worksheet has no dual-axis, no reference line, no filter, or no custom format, produce nothing for it — do not fabricate.
- **Bind only to real model fields.** Every `queryRef` must resolve to an actual TMDL table/column/measure. If a field is missing, stop and report it rather than guessing a name.
- **Ask on ambiguity.** Use `vscode_askQuestions` for unclear chart mappings instead of inventing one. Mark unresolved items in the spec as `UNVERIFIED`.
- **Stay in the report layer.** Do not create or modify semantic-model measures/tables here — that is the dax-measures / pbip-generator stage.
