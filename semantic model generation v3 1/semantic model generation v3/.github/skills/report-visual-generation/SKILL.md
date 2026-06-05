# Report Visual Generation Skill

## Purpose

Generate Power BI report visuals (report.json sections/visualContainers) from the extracted Tableau visual metadata and report constitution rules. Produces the complete report layer that opens in Power BI Desktop with pre-built visuals.

## When to Use

- After `tableau-visual-extraction` skill has produced `.specify/memory/tableau-visuals-output.md`
- After `report-constitution.md` has been written with layout/formatting rules
- User wants to generate actual Power BI report visuals from the migration pipeline

## Instructions

### Step 1: Read Context

1. Read `.specify/memory/tableau-visuals-output.md` — visual inventory, positions, chart types
2. Read `.specify/memory/report-constitution.md` — layout rules, theme, typography, alignment
3. Read the TMDL files from `Output/{WorkbookName}/{ModelName}.SemanticModel/definition/` to get exact table/column/measure names available

### Step 2: Apply Report Constitution

The report constitution defines strict formatting rules. Apply these to every visual:

#### Layout Rules
- **Canvas**: 1280 × 720 px (Power BI default 16:9)
- **Edge padding**: As defined (e.g., 25px from top/sides)
- **Inter-visual gap**: As defined (e.g., 20px between visuals)
- **Alignment**: Grid-aligned, consistent heights per row

#### Typography
- **Font family**: As defined (e.g., "Aptos")
- **Font size**: As defined (e.g., 10pt for data, 12pt for titles)
- **Title**: Bold, slightly larger than body text

#### Theme & Colors
- **Background**: Professional (white canvas, light gray visual backgrounds, or as specified)
- **Color palette**: Use the mapped palette from Tableau extraction or constitution default
- **Border**: Subtle (1px light gray) or as specified

#### Table/Matrix Visual Alignment
- **Numbers**: Left-aligned (or as specified)
- **Text**: Right-aligned (or as specified)
- **Dates**: Left-aligned (or as specified)

#### Number Formatting
- Preserve source format from Tableau (currency, percentage, decimal places)
- Apply locale-specific formatting (₹ for INR, $ for USD)

### Step 3: Map Visuals to Power BI JSON

For each visual from the inventory, generate a visual.json file in its own folder:

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
  "name": "{unique_visual_name}",
  "position": {
    "x": {calculated_x},
    "y": {calculated_y},
    "z": {z_index},
    "height": {calculated_height},
    "width": {calculated_width},
    "tabOrder": {order}
  },
  "visual": { ... }
}
```

> **CRITICAL — ALLOWED TOP-LEVEL PROPERTIES ONLY**: The `visualContainer/2.4.0` schema permits ONLY: `$schema`, `name`, `position`, `visual` (or `visualGroup`). **NEVER** add `filters`, `filterConfig`, `config`, or ANY other property at the root of visual.json. Power BI Desktop will reject the file with "Property has not been defined and the schema does not allow additional properties". For measure-based filtering (Top N, conditional visibility), rely on DAX logic and let users add visual filters in the Desktop UI.

#### Visual Config Structure (inside `visual` property of visual.json):
```json
{
  "visualType": "{powerbi_visual_type}",
  "query": {
    "queryState": {
      "Category": {
        "projections": [
          {
            "field": {
              "Column": {
                "Expression": {"SourceRef": {"Entity": "{TableName}"}},
                "Property": "{ColumnName}"
              }
            },
            "queryRef": "{TableName}.{ColumnName}",
            "active": true
          }
        ]
      },
      "Y": {
        "projections": [
          {
            "field": {
              "Measure": {
                "Expression": {"SourceRef": {"Entity": "{TableName}"}},
                "Property": "{MeasureName}"
              }
            },
            "queryRef": "{TableName}.{MeasureName}",
            "active": true
          }
        ]
      }
    }
  },
  "objects": {
    "dataPoint": [{"properties": {"fill": {"solid": {"color": {"expr": {"Literal": {"Value": "'#4e79a7'"}}}}}}}]
  },
  "visualContainerObjects": {
    "title": [{"properties": {
      "show": {"expr": {"Literal": {"Value": "true"}}},
      "text": {"expr": {"Literal": {"Value": "'{title}'"}}}
    }}],
    "border": [{"properties": {
      "show": {"expr": {"Literal": {"Value": "true"}}},
      "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#E0E0E0'"}}}}},
      "radius": {"expr": {"Literal": {"Value": "4D"}}}
    }}]
  }
}
```

> **IMPORTANT `objects` vs `visualContainerObjects` distinction**:
> - `objects` = visual-type-specific formatting (data colors, axis, labels). Keys vary by visual type.
> - `visualContainerObjects` = container-level formatting (title, background, border). Same keys for ALL visual types.
> - NEVER put `title`, `background`, or `border` inside `objects` — those belong ONLY in `visualContainerObjects`.
> - NEVER put `"general"` with `title` inside `objects` — this is invalid and causes crashes.
> - ALL visuals MUST include `visualContainerObjects.border` with `show: true`, color `#E0E0E0`, radius `4D`.
> - SLICERS: Set `visualContainerObjects.title.show = false` — slicers use their built-in header as label.

### Step 4: Visual Type Mapping Reference

| Power BI visualType | Usage |
|---|---|
| `clusteredBarChart` | Horizontal bars |
| `clusteredColumnChart` | Vertical bars |
| `stackedBarChart` | Stacked horizontal |
| `stackedColumnChart` | Stacked vertical |
| `lineChart` | Time series / trends |
| `areaChart` | Filled area |
| `lineClusteredColumnComboChart` | Combo chart |
| `pieChart` | Proportions (few categories) |
| `donutChart` | Proportions (with center value) |
| `card` | Single KPI value |
| `multiRowCard` | Multiple KPIs |
| `tableEx` | Table visual |
| `pivotTable` | Matrix visual |
| `map` | Bubble map |
| `filledMap` | Choropleth map |
| `treemap` | Hierarchical proportions |
| `slicer` | Filter control |
| `textbox` | Text/title |
| `shape` | Background shape |
| `kpi` | KPI with trend |
| `waterfallChart` | Waterfall |
| `funnel` | Funnel chart |
| `scatterChart` | Scatter / bubble |
| `gauge` | Gauge/radial |
| `actionButton` | Navigation button / bookmark toggle |

### Step 4b: Navigation Button Generation

For each navigation button extracted from the Tableau workbook, generate an `actionButton` visual:

#### Page Navigation Buttons (Tableau `goto-sheet`)

Map Tableau `goto-sheet` buttons to Power BI `actionButton` with page navigation:

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
      }}],
      "action": [{"properties": {
        "type": {"expr": {"Literal": {"Value": "'PageNavigation'"}}},
        "page": {"expr": {"Literal": {"Value": "'{target_page_name}'"}}}
      }}]
    },
    "visualContainerObjects": {
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

#### Bookmark Toggle Buttons (Tableau `toggle-action`)

Toggle buttons require bookmarks (must be created manually in PBI Desktop after opening):

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
      }}],
      "action": [{"properties": {
        "type": {"expr": {"Literal": {"Value": "'Bookmark'"}}},
        "bookmark": {"expr": {"Literal": {"Value": "''"}}}
      }}]
    },
    "visualContainerObjects": {
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

#### Navigation Button Rules:
- **Position**: Scale from Tableau zone coordinates using same formula as chart visuals
- **Z-index**: Use 1000+ so buttons render above chart visuals
- **Title**: ALWAYS `title.show = false` — buttons don't need container titles
- **Label text**: Use Tableau tooltip (e.g., "Go to Sales Dashboard")
- **Styling**: Match Tableau nav bar `background-color` (extract from parent zone style)
- **Page target**: `action.page` must match the `name` from the target page's `page.json`
- **Bookmark toggle**: Leave `action.bookmark` empty — user creates bookmark pairs manually
- **Icon shapes**: `'Arrow'` for navigation, `'Filter'` for filter toggles, `'Blank'` for custom
- **Active state**: Use distinct fill color or border for the "current page" button

### Step 5: Generate Report (Enhanced PBIR Folder Format)

Generate the enhanced folder-based report format that modern Power BI Desktop requires.

> **CRITICAL**: Use the **PBIR Enhanced Folder Format** (NOT the legacy flat `report.json` with `sections` array).
> Power BI Desktop with enhanced report format crashes with "ThemeServiceBase" errors when using the legacy format.
> **OUTPUT LOCATION**: All report files MUST be generated inside the `Output/{WorkbookName}/` folder (e.g., `Output/Netflix/{ProjectName}.Report/`).

#### Folder Structure:
```
Output/{WorkbookName}/{ProjectName}.Report/
├── definition.pbir              ← Points to semantic model
└── definition/
    ├── report.json              ← Report-level config (no visuals here)
    ├── version.json             ← Schema version
    └── pages/
        ├── pages.json           ← Page ordering array
        ├── ReportSection1/
        │   ├── page.json        ← Page config (displayName, width, height)
        │   └── visuals/
        │       ├── {visual_name}/
        │       │   └── visual.json  ← Individual visual definition
        │       └── ...
        ├── ReportSection2/
        │   ├── page.json
        │   └── visuals/
        │       └── ...
        └── ...
```

#### report.json (root - NO visuals here):
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json",
  "themeCollection": {}
}
```

> **CRITICAL**: Schema MUST be version `3.0.0`. NEVER use `1.0.0` (requires `layoutOptimization` with complex anyOf format). NEVER add `"datasetBinding"` or `"layoutOptimization"` — neither is allowed in `3.0.0`. Dataset binding lives ONLY in `definition.pbir`. — it's NOT allowed in the PBIR enhanced schema (causes "additional properties" error). The dataset reference lives ONLY in `definition.pbir`. The `"layoutOptimization": 0` property is REQUIRED by the schema.

#### version.json:
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
  "version": "2.0.0"
}
```

> **CRITICAL**: `$schema` is MANDATORY in version.json. Without it, PBI Desktop throws "Can't find '$schema' property in 'version.json'" and refuses to open.

#### pages.json (ordering):
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
  "pageOrder": ["ReportSection1", "ReportSection2", "ReportSection3"]
}
```

#### page.json (per-page):
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json",
  "name": "ReportSection1",
  "displayName": "Launch Report Dashboard",
  "displayOption": "FitToPage",
  "height": 720,
  "width": 1280
}
```

#### visual.json (per-visual):
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
  "name": "unique_visual_name",
  "position": {
    "x": 25,
    "y": 25,
    "z": 0,
    "height": 300,
    "width": 400,
    "tabOrder": 0
  },
  "visual": {
    "visualType": "tableEx",
    "query": {
      "queryState": {
        "Values": {
          "projections": [
            {
              "field": {
                "Column": {
                  "Expression": { "SourceRef": { "Entity": "TableName" } },
                  "Property": "ColumnName"
                }
              },
              "queryRef": "TableName.ColumnName",
              "active": true
            }
          ]
        }
      }
    },
    "objects": {},
    "visualContainerObjects": {
      "title": [{
        "properties": {
          "show": { "expr": { "Literal": { "Value": "true" } } },
          "text": { "expr": { "Literal": { "Value": "'Visual Title'" } } }
        }
      }],
      "border": [{
        "properties": {
          "show": { "expr": { "Literal": { "Value": "true" } } },
          "color": { "solid": { "color": { "expr": { "Literal": { "Value": "'#E0E0E0'" } } } } },
          "radius": { "expr": { "Literal": { "Value": "4D" } } }
        }
      }]
    }
  }
}
```

> **CRITICAL — NO FILTERS IN visual.json**: The `visualContainer/2.4.0` schema ONLY allows these top-level properties: `$schema`, `name`, `position`, `visual` (or `visualGroup`). **NEVER** add `filters`, `filterConfig`, or ANY other top-level property — Power BI Desktop will reject the file with "Property has not been defined and the schema does not allow additional properties". Visual-level filters can only be added through PBI Desktop's UI after opening. For Top N scenarios, rely on the DAX measure logic (e.g., `Top N Filter = IF([State Rank] <= SELECTEDVALUE(...), 1, 0)`) and let users apply the filter manually, or use page-level filters in `page.json` instead.
> **CRITICAL**: In page.json, `"displayOption"` MUST be a string (`"FitToPage"`, `"FitToWidth"`, or `"ActualSize"`), NEVER an integer.
> **CRITICAL**: In pages.json, the `$schema` URL must use `pagesMetadata` (NOT `pages`): `https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json`
> **IMPORTANT**: Every visual MUST have `border.show = true` in `visualContainerObjects`. Use color `#E0E0E0` and radius `4D` (4px rounded corners).
> **IMPORTANT**: For slicers, set `title.show = false` — slicers use their built-in header instead.
> **IMPORTANT**: Each visual in its own folder under `visuals/`. Visual folder name = visual name (no spaces).
> **IMPORTANT**: Create pages for ALL dashboards in Tableau, not just the first one.
> **IMPORTANT**: Use correct `visualType` from the extraction step — especially `tableEx` for text tables, `pivotTable` for cross-tabs, `areaChart` for area marks.

### Step 6: Coordinate Calculation

Scale Tableau dashboard coordinates to Power BI 1280×720 canvas:

```
scale_x = 1280 / tableau_dashboard_width
scale_y = 720 / tableau_dashboard_height

pbi_x = (tableau_x * scale_x) + edge_padding
pbi_y = (tableau_y * scale_y) + edge_padding
pbi_width = (tableau_w * scale_x) - inter_visual_gap
pbi_height = (tableau_h * scale_y) - inter_visual_gap
```

> **CRITICAL — NO OVERLAP RULE**: After calculating all positions, validate that NO visuals overlap:
> - Horizontal: `visual_A.x + visual_A.width + 20 <= visual_B.x` (for horizontally adjacent visuals)
> - Vertical: `visual_A.y + visual_A.height + 20 <= visual_B.y` (for vertically adjacent visuals)
> - If any overlap is detected, shrink the width/height by the gap amount (20px) to create space
> - Edge constraint: `visual.x + visual.width <= 1280 - 25` (right edge padding)
> - Edge constraint: `visual.y + visual.height <= 720 - 25` (bottom edge padding)
>
> **Gap enforcement formula**: Subtract the full inter-visual gap (20px) from the calculated width/height. This guarantees minimum 20px spacing between all visuals regardless of Tableau source coordinates.

Apply constitution padding/gap rules after scaling.

### Step 7: Slicer Generation

For each Tableau filter/parameter control, use this **SLICER-SPECIFIC template** (NOT the generic visual template):

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
                "Expression": {"SourceRef": {"Entity": "{TableName}"}},
                "Property": "{ColumnName}"
              }
            },
            "queryRef": "{TableName}.{ColumnName}",
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

> **⚠️ CRITICAL SLICER RULE — title.show MUST be "false"**: 
> - Slicers have a BUILT-IN **header** that automatically displays the field name
> - Setting `title.show = true` creates a DUPLICATE label (header text + title text stacked)
> - This rule overrides the generic visual template — DO NOT copy `title.show = true` from other visual templates when generating slicers
> - **WRONG**: `"show": {"expr": {"Literal": {"Value": "true"}}}` ← creates duplicate label
> - **CORRECT**: `"show": {"expr": {"Literal": {"Value": "false"}}}` ← only header shows

Slicer modes: `'Basic'` (list), `'Dropdown'` (compact), `'Slider'` (range)

## Notes

- In enhanced format, `queryRef` format: `{TableName}.{ColumnOrMeasureName}` (e.g., `FactLoan.Total Loan Amount`)
- Visual folder names must be unique, no spaces (use underscores or camelCase)
- Power BI Desktop will auto-correct minor layout issues on first save
- If a Tableau visual has no direct PBI equivalent, ASK THE USER via `vscode_askQuestions` — never silently default
- Generate visuals for ALL dashboards (each = one page), not just the first dashboard
- Use `tableEx` for flat tables, `pivotTable` for cross-tabs/matrices, `card` for single KPIs
- Use `areaChart` for area marks, NOT `lineChart`
- Generate `actionButton` visuals for ALL Tableau navigation buttons (goto-sheet → PageNavigation, toggle → Bookmark)
- Navigation buttons do NOT have data queries — they only have `objects` (no `query` property needed)
- Toggle/bookmark buttons require manual bookmark setup in Power BI Desktop after file generation

## Critical Rules — Report Load Failures Prevention

These rules MUST be followed or Power BI Desktop will crash with "Failed to load the report":

### 1. themeCollection MUST be empty `{}`

```json
// CORRECT — always works (in definition/report.json)
"themeCollection": {}

// WRONG — causes TypeError: Cannot read properties of undefined (reading 'visual')
"themeCollection": {"baseTheme": {"name": "CY24SU06", "type": 2}}
```

**Why**: `ThemeServiceBase.getInheritParentColors` looks up visual styles in the referenced theme. If the theme definition can't be fully resolved, the lookup returns `undefined` and accessing `.visual` crashes.

### 2. Use Enhanced Folder Format (PBIR), NOT Legacy Flat Format

```
// CORRECT — Enhanced format with per-visual folders
{ProjectName}.Report/definition/pages/ReportSection1/visuals/{name}/visual.json

// WRONG — Legacy flat format with sections array causes ThemeServiceBase crash
report.json with "sections": [{ "visualContainers": [...] }]
```

### 3. Visual Type Must Match Tableau Source Exactly

| Tableau Feature | CORRECT Power BI Visual | WRONG (Never Use) |
|---|---|---|
| Text table (rows only) | `tableEx` | clusteredBarChart |
| Cross-tab (rows + cols) | `pivotTable` | clusteredColumnChart |
| Area mark | `areaChart` | lineChart |
| Single KPI number | `card` | multiRowCard |
| Filter control | `slicer` | — |

### 4. ALL Dashboards → ALL Pages

- Extract and generate visuals for EVERY dashboard in the Tableau workbook
- Each Tableau dashboard = one Power BI report page
- Do NOT skip any dashboards or generate only the first page

### 5. Ask User for Ambiguous Visual Types

When a Tableau visual has no clear Power BI equivalent:
- Use `vscode_askQuestions` to present 2-3 options with descriptions
- Record the user's choice and proceed with that visual type
- NEVER silently default to a bar/column chart

### 6. Enhanced Format Visual Rules (objects vs visualContainerObjects)

In the enhanced folder format, visuals use `objects` and `visualContainerObjects` (NOT `vcObjects`):

| Property | Scope | Valid keys (examples) |
|----------|-------|----------------------|
| `visual.objects` | Visual-type-specific formatting | `data`, `dataPoint`, `labels`, `categoryAxis`, `valueAxis`, `legend`, `lineStyles` |
| `visual.visualContainerObjects` | Container formatting (same for ALL types) | `title`, `background`, `border`, `padding`, `visualHeader` |

**NEVER put `title`, `background`, or `general` inside `visual.objects`.**

### 7. Slicer `objects` — only `data` is valid; title MUST be disabled

For slicers, the only valid key in `visual.objects` is `data` (for mode/orientation). **Title MUST be disabled** — slicers use their built-in header (field name label) instead:

```json
"objects": { "data": [{"properties": {"mode": {"expr": {"Literal": {"Value": "'Dropdown'"}}}}}] },
"visualContainerObjects": { "title": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}] }
```

> **NEVER set title show to true for slicers.** The slicer header (built-in field label) is always visible and serves as the slicer label. Having both title AND header creates a redundant double-label.

### 8. File encoding — UTF-8 WITHOUT BOM

Power BI Desktop rejects any file with a UTF-8 BOM (byte order mark). When writing any .pbip/.pbir/.tmdl/.json file from code:

```powershell
# CORRECT — .NET method, no BOM
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $content, $utf8NoBom)

# WRONG — PowerShell 5.1 always adds BOM with -Encoding UTF8
Set-Content -Path $path -Value $content -Encoding UTF8
```

### 8. PBIP project file schemas — MANDATORY format

The `.pbip`, `definition.pbir`, and `definition.pbism` files MUST follow these exact schemas. Using incorrect versions, missing `$schema`, or adding invalid properties (e.g., `"dataset"`) causes PBI Desktop to reject the file entirely.

#### `.pbip` file — ONLY references the report (NOT the dataset/semantic model)
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
  "version": "1.0",
  "artifacts": [
    {
      "report": {
        "path": "{Name}.Report"
      }
    }
  ],
  "settings": {
    "enableAutoRecovery": true
  }
}
```

**NEVER add a `"dataset"` artifact entry** — the semantic model is referenced from `definition.pbir`, not from `.pbip`.

#### `definition.pbir` — report points to semantic model
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
  "version": "4.0",
  "datasetReference": {
    "byPath": {
      "path": "../{Name}.SemanticModel"
    }
  }
}
```

**NEVER use `"version": "1.0"` or include `"byConnection": null`** — causes schema validation failure.

#### `definition.pbism` — semantic model manifest
```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
  "version": "4.2",
  "settings": {}
}
```

**NEVER use `"version": "1.0"` or include `"datasetReference"`** — the `.pbism` is a self-contained manifest, not a reference pointer.
