# Tableau Visual Extraction Skill

## Purpose

Extract visualization-related metadata from a Tableau workbook (.twb) that has already been analyzed. This skill reads the worksheets, dashboards, and visual encodings to understand chart types, field placements, formatting, filters, colors, and layout positions needed to recreate equivalent visuals in Power BI.

## When to Use

- After `tableau-analysis` skill has run and `.specify/memory/tableau-analysis-output.md` exists
- User wants to migrate Tableau visuals/dashboards to Power BI report layer
- User needs to understand visual layout, chart types, and formatting before generating Power BI report visuals

## Instructions

### Step 1: Locate the TWB File and Analysis

1. Read `.specify/memory/tableau-analysis-output.md` to get worksheet/dashboard names
2. Locate the `.twb` file in the `Data/` folder via `file_search` with pattern `Data/**/*.twb`

### Step 2: Extract Worksheet Visual Configurations

For each `<worksheet name='...'>` element, extract:

#### 2.1 Mark Type (Chart Type)
- Look for `<mark class='...'>` inside `<panes><pane>`:
  - `Automatic`, `Bar`, `Line`, `Area`, `Circle`, `Square`, `Text`, `Map`, `Pie`, `Gantt`, `Polygon`, `Shape`
- **CRITICAL**: Use the EXACT visual type that matches the Tableau mark. Do NOT default to bar/column charts.

##### Primary Visual Type Mapping (use FIRST match):
  | Tableau Mark | Power BI Visual | When to Use |
  |---|---|---|
  | Text (single measure) | `card` | Single KPI number only |
  | Text (multiple rows/cols) | `tableEx` | Flat data table (no subtotals) |
  | Text (rows + cols as dimensions with measures) | `pivotTable` | Cross-tab / matrix with subtotals |
  | Bar (horizontal) | `clusteredBarChart` | Categorical comparison |
  | Bar (vertical / columns shelved) | `clusteredColumnChart` | Categorical comparison |
  | Line | `lineChart` | Trend over time (no fill) |
  | Line + color on dimension | `lineChart` with Legend | Trend with series/highlight |
  | Area | `areaChart` | Trend over time (filled) |
  | Circle / Shape | `scatterChart` | Two-measure comparison |
  | Pie | `pieChart` or `donutChart` | Proportions (few categories) |
  | Map | `map` or `filledMap` | Geographic data |
  | Gantt | `decompositionTree` | Approximate (no direct equivalent) |
  | Square (single dimension + size/color on measure) | `treemap` | Hierarchical proportions |
  | Square (dimensions on BOTH rows AND cols + color on measure) | `pivotTable` with conditional formatting | Heatmap / cross-tab comparison |
  | Polygon | `shape` | Custom shapes (approximate) |
  | Automatic | **Infer** (see rules below) | Context-dependent |

##### Automatic Mark Inference Rules (when mark class = "Automatic"):
  1. **Color + Size encodings on SAME measure + text/label on dimension** → `treemap` (proportional area display)
  2. **Date/time on columns + measure on rows** → `lineChart` or `areaChart`
  3. **Only dimensions on rows + measures on text** → `tableEx` (flat table)
  4. **Dimensions on BOTH rows AND columns + measures** → `pivotTable` (matrix/cross-tab)
  5. **Single measure, no dimensions** → `card`
  6. **Geographic field present** → `map`
  7. **Hierarchy on rows (multiple dimensions with `/`) + measure on columns** → `clusteredBarChart` with hierarchy drill-down (or `matrix` if text encoding also present)
  8. **Dimension on one axis + measure on other** → `clusteredBarChart` or `clusteredColumnChart`

> **CRITICAL Priority**: Rule 1 takes precedence — if a visual has BOTH color AND size encodings on a measure, it is a treemap regardless of other factors. The size encoding in Tableau almost always indicates a treemap/packed-bubble layout.

##### Square Mark Rules:
  - Square mark with **color encoding on a measure** and dimensions on BOTH rows AND cols → `matrix` with conditional formatting (heatmap style) — NOT a treemap
  - Square mark with **only rows** and size/color on measure → `treemap` (hierarchical proportions)
  - Square mark + single dimension + size → `treemap`

##### Text Mark → Table vs Matrix Decision:
  - If ONLY `<rows>` has dimensions and measures are on `<text>` encoding → `tableEx`
  - If BOTH `<rows>` AND `<cols>` have dimensions (cross-tabulation) → `pivotTable`
  - If a single aggregate value with no dimensions → `card`
  - **NEVER map a text table to a bar/column/line chart**

##### When No Direct Equivalent Exists:
  - **ASK THE USER** which Power BI visual to use via `vscode_askQuestions`
  - Present 2-3 closest alternatives with descriptions
  - Record the user's choice in the extraction output for the generation step
  - Example: Tableau packed bubbles → ask user: "treemap", "scatterChart", or "donutChart"?

##### ALL Dashboards Must Be Extracted:
  - **CRITICAL**: Extract visuals from EVERY dashboard in the workbook, not just the first one
  - Each dashboard becomes a separate Power BI report page
  - Maintain the same visual order and relative positioning per dashboard

#### 2.2 Field Placements (Shelves)
- `<rows>` → Y-axis fields (vertical)
- `<cols>` → X-axis fields (horizontal)
- `<encodings>`:
  - `<color column='...'>` → Legend / color encoding
  - `<size column='...'>` → Size encoding
  - `<text column='...'>` → Data labels / tooltip
  - `<detail column='...'>` → Detail (tooltip)
  - `<shape column='...'>` → Shape encoding
  - `<lod column='...'>` → Level of detail

#### 2.3 Aggregation & Derivation
- Parse column-instance references: `derivation` attribute (Sum, Avg, Count, Min, Max, None, User)
- Parse `type` attribute: quantitative, nominal, ordinal
- Example: `[sum:loan_amount:qk]` = SUM of loan_amount, quantitative

#### 2.4 Filters
- `<filter>` elements within worksheets
- Categorical filters: member inclusions/exclusions
- Range filters: min/max values
- Relative date filters

#### 2.5 Formatting
- `<format>` elements within `<style-rule>`:
  - `text-format` → number/percentage/currency format
  - `font-size` → font size
  - `text-align` → alignment
  - `width` / `height` → visual dimensions
- `<customized-label>` → custom label formatting
- Color palettes from `<encoding attr='color'>` elements

#### 2.6 Table Calculations Context
- If a field has `<table-calc>`:
  - `ordering-type` (Field, Rows, Columns)
  - `ordering-field` → compute direction
  - Note: These affect how the DAX equivalent should be visualized

#### 2.7 Dual-Axis & Combo Charts (MANDATORY — detect if present)
A dual-axis worksheet places two measures on the same axis with independent scales.
- Detect `<rows>` (or `<cols>`) containing TWO measure pills, OR a `<mark>` element whose pane has multiple `<encodings>` blocks, OR an axis with `<dual-axis>` / `mark-mapping` indicating two marks
- Identify the mark type of EACH measure (e.g. one `Bar` + one `Line`)
- Power BI mapping:
  - Bar/Column + Line → `lineClusteredColumnComboChart` (or `lineStackedColumnComboChart`)
  - Two lines on independent scales → `lineChart` with a secondary value axis
  - Two bars → `clusteredColumnChart` with both measures on the Y-axis (shared scale)
- Record both measures, both mark types, and which is primary vs secondary axis
- If NO dual-axis worksheet exists, write `None` — do not invent combo charts

#### 2.8 Reference / Trend / Constant Lines (MANDATORY — detect if present)
- Look for `<reference-line>`, `<reference-line-aggregation>`, or `<trend-lines>` elements within a worksheet's `<panes>`/`<axis>`
- Extract: line type (constant, average, median, total, min/max, trend), the value or aggregation, scope (per-cell / per-pane / per-table), and label
- Power BI mapping:
  - Constant / average / min / max → analytics-pane **constant line** / **min line** / **max line** / **average line** on the cartesian visual
  - Trend line → analytics-pane **trend line** (Power BI built-in) on a `lineChart` / `scatterChart`
- Record these as an "Analytics Lines" note on the affected visual
- If NO reference/trend lines exist, write `None` — do not invent lines

### Step 3: Extract Dashboard Layout

For each `<dashboard name='...'>` element:

#### 3.1 Dashboard Size
- `<size maxheight='...' maxwidth='...' minheight='...' minwidth='...'>`
- Default Tableau dashboard: 1000×800 or 1366×768

#### 3.2 Zone Layout (Visual Positions)
- Each `<zone>` element represents a container:
  - `type='text'` → Title/text box
  - `type='viz'` → Embedded worksheet
  - `type='filter'` → Filter control/slicer
  - `type='paramctrl'` → Parameter control
  - `type='bitmap'` → Image
  - `type-v2='dashboard-object'` with `<button>` child → Navigation/toggle button
- Extract from zones:
  - `h` (height), `w` (width) in pixels
  - `x`, `y` position coordinates
  - `name` → which worksheet is embedded
  - `param` → which parameter it controls

#### 3.3 Navigation Buttons (MANDATORY)

For each `<zone>` with `type-v2='dashboard-object'` that contains a `<button>` child element, extract:

1. **Button action type**:
   - `action='tabdoc:goto-sheet window-id="..."'` → Page navigation (navigates to another dashboard)
   - `<toggle-action>tabdoc:toggle-button-click-action ...</toggle-action>` → Toggle visibility (show/hide zones)
   - Empty `action=''` with `<toggle-action>` child → Toggle button

2. **Button visual states** (from `<button-visual-state>`):
   - `<tooltip-text>` → Button tooltip / accessible label
   - `<image-path>` → Icon image file path (for reference only)

3. **Button position**: `x`, `y`, `w`, `h` from the zone element

4. **Target resolution**:
   - For `goto-sheet`: Extract `window-id` from the action attribute, match against `<window class='dashboard' name='...'>` elements to determine target dashboard name
   - For toggle: Extract `zone-ids` from `<toggle-action>` to identify which zones are shown/hidden

5. **Button container**: Note the parent `<zone friendly-name='...'>` with `layout-strategy-id` — this defines button group layout (horizontal/vertical distribution)

Output navigation buttons as a separate section per dashboard:
```markdown
### Navigation Buttons: {dashboard_name}
| # | Action Type | Tooltip | Target | x | y | w | h |
|---|-------------|---------|--------|---|---|---|---|
| 1 | goto-sheet | Go to Sales Dashboard | Sales Dashboard | {x} | {y} | {w} | {h} |
| 2 | goto-sheet | Go to Customer Dashboard | Customer Dashboard | {x} | {y} | {w} | {h} |
| 3 | toggle | Show/Close Dashboard Filters | zones: [6] | {x} | {y} | {w} | {h} |
```

**Power BI equivalents** (inform report-visual-generation):
- `goto-sheet` → Power BI **actionButton** visual with `action.type = "PageNavigation"` and `action.pageTarget`
- `toggle` (show/hide) → Power BI **actionButton** visual with `action.type = "Bookmark"` (requires 2 bookmarks: show state + hide state)

#### 3.3 Layout Containers
- `<layout-component>` with type:
  - `layout-flow: tb` → Top-to-bottom (vertical stack)
  - `layout-flow: lr` → Left-to-right (horizontal stack)
  - `layout-basic` → Tiled/floating

#### 3.4 Title & Subtitle
- Dashboard `<formatted-text>` elements for title
- Font name, size, color, alignment

### Step 4: Output Format

Save extracted visualization metadata to `.specify/memory/tableau-visuals-output.md`:

```markdown
# Tableau Visual Extraction: {workbook_name}

## Dashboard Layout
- **Name**: {dashboard_name}
- **Size**: {width} × {height} px
- **Layout Type**: Tiled / Floating / Mixed

## Visual Inventory

### Visual 1: {worksheet_name}
- **Chart Type**: {Tableau mark} → {Power BI visual type}
- **Position**: x={x}, y={y}, w={w}, h={h}
- **X-Axis (Columns)**: {field_name} ({aggregation})
- **Y-Axis (Rows)**: {field_name} ({aggregation})
- **Color**: {field_name}
- **Size**: {field_name}
- **Labels**: {field_name}
- **Secondary Axis / Combo**: {second measure + mark type, or None}
- **Analytics Lines**: {constant/average/trend line details, or None}
- **Filters**: {filter_description}
- **Format**: {number_format}
- **Sort**: {sort_field} {direction}

### Visual 2: ...

## Filters / Slicers
| Filter Name | Type | Field | Position | Style |
|---|---|---|---|---|
| {name} | Dropdown / Slider / List | {field} | x,y,w,h | Single / Multi |

## Parameter Controls
| Parameter | Control Type | Position |
|---|---|---|
| {name} | Slider / Dropdown | x,y,w,h |

## Navigation Buttons
### {dashboard_name}
| # | Action Type | Tooltip | Target | x | y | w | h |
|---|-------------|---------|--------|---|---|---|---|
| 1 | goto-sheet | {tooltip} | {target_dashboard} | {x} | {y} | {w} | {h} |
| 2 | toggle | {tooltip} | show/hide zones: [{zone_ids}] | {x} | {y} | {w} | {h} |

## Color Palette
| Field Value | Color (Hex) |
|---|---|
| {value} | {color} |

## Formatting Summary
| Property | Value |
|---|---|
| Title Font | {font} {size} |
| Body Font | {font} {size} |
| Number Format | {format} |
| Date Format | {format} |
```

## Format String Translation (Tableau → Power BI)
Translate captured Tableau format strings to Power BI `formatString` values. Only include rows for formats actually found in the workbook; otherwise write `None`.

| Tableau Format | Power BI formatString | Notes |
|---|---|---|
| `$#,##0` / `$#,##0.00` | `\$#,##0` / `\$#,##0.00` | Currency (escape `$`) |
| `0%` / `0.0%` | `0%` / `0.0%` | Percentage |
| `#,##0` / `#,##0.00` | `#,##0` / `#,##0.00` | Thousands separator |
| `0.0"K"` / `0.0,"M"` | `#,0.0,"K"` / `#,0.0,,"M"` | Scaled abbreviations |
| `mmmm yyyy` | `mmmm yyyy` | Month-Year |
| `mm/dd/yyyy` | `mm/dd/yyyy` | Date |
| `[h]:mm:ss` | `h:mm:ss` | Duration (Power BI has no elapsed `[h]`) |
| (no format) | `Default` | Leave model default |

### Step 5: Validate Extraction Completeness (MANDATORY)

Before handing off, verify the output contains:
- [ ] **Mark type** for EVERY worksheet listed in `tableau-analysis-output.md`
- [ ] **Dashboard zone positions** (x, y, w, h) for ALL visuals in ALL dashboards
- [ ] **Color/Size/Text encodings** for worksheets that have them (crucial for treemap/legend detection)
- [ ] **Field shelf data** (rows, cols) to determine axis orientation
- [ ] **Navigation buttons** extracted for ALL dashboards that have `<button>` elements (goto-sheet, toggle actions)
- [ ] **Dual-axis / combo** detection recorded per worksheet (value or `None`)
- [ ] **Reference/trend lines** recorded per worksheet (value or `None`)

**If ANY worksheet is missing mark type or encoding data, re-parse the TWB XML before proceeding.**

**PowerShell reference for reliable extraction:**
```powershell
[xml]$twb = Get-Content "Data/{subfolder}/{workbook}.twb" -Raw

# Extract mark types and encodings
$twb.workbook.worksheets.worksheet | ForEach-Object {
    $name = $_.name
    $pane = $_.table.panes.pane
    if ($pane -is [array]) { $pane = $pane[0] }
    $mark = if ($pane.mark -is [array]) { $pane.mark[0].class } else { $pane.mark.class }
    $color = $pane.encodings.color.column
    $size = $pane.encodings.size.column
    $text = $pane.encodings.text.column
    $wedge = $pane.encodings.'wedge-size'.column
    $rows = $_.table.rows
    $cols = $_.table.cols
    Write-Host "$name | mark=$mark | rows=$rows | cols=$cols | color=$color | size=$size | text=$text | wedge=$wedge"
}

# Extract dashboard zones
$twb.workbook.dashboards.dashboard | ForEach-Object {
    $dname = $_.name
    $size = $_.size
    Write-Host "Dashboard: $dname (${($size.maxwidth)}x${($size.maxheight)})"
    $_.zones.zone | Where-Object { $_.type -in @('viz','filter','paramctrl') } | ForEach-Object {
        Write-Host "  zone: type=$($_.type) name=$($_.name) x=$($_.x) y=$($_.y) w=$($_.w) h=$($_.h)"
    }
}

# Extract navigation buttons (goto-sheet, toggle)
$twb.workbook.dashboards.dashboard | ForEach-Object {
    $dname = $_.name
    Write-Host "Navigation Buttons for: $dname"
    # Find zones with type-v2='dashboard-object' containing button elements
    function Find-Buttons($zones) {
        foreach ($z in $zones) {
            if ($z.button) {
                $action = $z.button.action
                $tooltip = $z.button.'button-visual-state'.'tooltip-text'
                if ($tooltip -is [array]) { $tooltip = $tooltip[0] }
                $toggleAction = $z.button.'toggle-action'
                $actionType = if ($toggleAction) { "toggle" } elseif ($action -match 'goto-sheet') { "goto-sheet" } else { "unknown" }
                Write-Host "  button: action=$actionType tooltip=$tooltip x=$($z.x) y=$($z.y) w=$($z.w) h=$($z.h)"
            }
            # Recurse into nested zones
            if ($z.zone) { Find-Buttons $z.zone }
        }
    }
    Find-Buttons $_.zones.zone
}
```

### Step 6: Hand Off

After saving, automatically invoke the `report-visual-constitution` agent which handles:
1. Report constitution (layout rules, theme, typography)
2. Specify (visual spec with Power BI JSON structure)
3. Clarify (chart type alternatives, layout adaptations)
4. Plan + Tasks
5. Implementation (generate report.json sections with visual containers)

## Notes

- Tableau pixel coordinates need scaling to Power BI's coordinate system (Power BI uses a 1280×720 base canvas)
- Tableau zones are absolute-positioned; Power BI visuals use x, y, width, height in the visualContainers array
- Mark class "Automatic" requires inference from shelf configuration:
  - Only measures on rows/cols → Bar chart
  - Date on cols + measure on rows → Line chart
  - Only text/dimensions on rows + measures on text encoding → Table (tableEx)
  - Dimensions on BOTH rows AND cols → Matrix (pivotTable)
  - Only a single measure → Card
  - Geographic field → Map
- Decode XML entities: `&amp;` → `&`, `&quot;` → `"`, `&#13;&#10;` → newline
- **IMPORTANT**: Text marks are the most common mark type in Tableau. They are used for tables/matrices, NOT for charts. Always map them to `tableEx` or `pivotTable`.
- **IMPORTANT**: Extract ALL dashboards in the workbook. Each becomes a Power BI page.
- **IMPORTANT**: When a Tableau visual type has no clear Power BI equivalent, use `vscode_askQuestions` to ask the user which visual to use, presenting 2-3 alternatives with descriptions.

## Anti-Hallucination Rules (MANDATORY)

1. **Recreate only what exists.** Every visual, field binding, position, color, combo measure, and reference line MUST come from a concrete element in the `.twb` XML. Never invent visuals or bindings.
2. **Use `None` for absent features.** If a worksheet has no dual-axis, no analytics lines, no filters, or no special format, write `None`. Do not fabricate plausible-looking values.
3. **One worksheet → assess once.** Map each worksheet to exactly one decision. Do not generate extra speculative visuals or duplicate pages.
4. **Ask, don't guess, on ambiguity.** When a mark type or format is unclear, use `vscode_askQuestions` rather than inventing a mapping. Mark unresolved items `UNVERIFIED`.
5. **Preserve real coordinates.** Use the actual zone `x/y/w/h` (scaled), not estimated layouts. Do not reposition visuals arbitrarily.
6. **No new measures or DAX here.** This skill describes visuals only; it never creates semantic-model fields or DAX.
