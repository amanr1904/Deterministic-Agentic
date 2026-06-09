# Navigation Buttons & Bookmarks Skill

## Purpose

Migrate Tableau navigation buttons (goto-sheet, toggle/show-hide) to Power BI `actionButton` visuals with page navigation and bookmark actions.

## Tableau Button Types

### 1. Page Navigation (`goto-sheet`)

**Tableau XML**: `<button action='tabdoc:goto-sheet window-id="..."'>`

**Detection**: Zone with `type-v2='dashboard-object'` containing `<button>` with `action` attribute matching `goto-sheet`.

**Power BI equivalent**: `actionButton` with `action.type = "PageNavigation"`

### 2. Toggle Visibility (`toggle-action`)

**Tableau XML**: `<button action=''><toggle-action>tabdoc:toggle-button-click-action ...</toggle-action></button>`

**Detection**: Zone with `<button>` containing a `<toggle-action>` child element. The `action` attribute is empty.

**Power BI equivalent**: `actionButton` with `action.type = "Bookmark"` (requires manual bookmark creation)

---

## Extraction (from TWB XML)

### PowerShell Extraction Script

```powershell
[xml]$twb = Get-Content "Data/{subfolder}/{workbook}.twb" -Raw

$twb.workbook.dashboards.dashboard | ForEach-Object {
    $dname = $_.name
    Write-Host "=== Buttons for: $dname ==="
    
    function Find-Buttons($zones) {
        foreach ($z in $zones) {
            if ($z.button) {
                $action = $z.button.action
                $tooltip = $z.button.'button-visual-state'.'tooltip-text'
                if ($tooltip -is [array]) { $tooltip = $tooltip[0] }
                $toggleAction = $z.button.'toggle-action'
                
                $actionType = if ($toggleAction) { "toggle" }
                              elseif ($action -match 'goto-sheet') { "goto-sheet" }
                              else { "unknown" }
                
                # For goto-sheet, extract window-id to resolve target dashboard
                $target = ""
                if ($action -match 'window-id="([^"]+)"') {
                    $windowId = $Matches[1]
                    $target = ($twb.workbook.windows.window | Where-Object { $_.id -eq $windowId }).name
                }
                
                Write-Host "  type=$actionType tooltip=$tooltip target=$target x=$($z.x) y=$($z.y) w=$($z.w) h=$($z.h)"
            }
            if ($z.zone) { Find-Buttons $z.zone }
        }
    }
    Find-Buttons $_.zones.zone
}
```

### Output Format (save to tableau-visuals-output.md)

```markdown
### Navigation Buttons: {dashboard_name}
| # | Action Type | Tooltip | Target | x | y | w | h |
|---|-------------|---------|--------|---|---|---|---|
| 1 | goto-sheet | Go to Sales Dashboard | SalesDashboard | 120 | 30 | 150 | 40 |
| 2 | goto-sheet | Go to Customer Dashboard | CustomerDashboard | 280 | 30 | 150 | 40 |
| 3 | toggle | Show Dashboard Filters | zones: [6, 7] | 450 | 30 | 40 | 40 |
```

---

## Generation Templates

### Page Navigation Button

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
      "title": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
      "background": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#072a35'"}}}}}
      }}],
      "border": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
    }
  }
}
```

### Bookmark Toggle Button

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
  "name": "toggle_{function}",
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
      "title": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
      "background": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "color": {"solid": {"color": {"expr": {"Literal": {"Value": "'#072a35'"}}}}}
      }}],
      "border": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
    }
  }
}
```

---

## Rules

### Navigation Buttons
- `action.page` MUST match the `name` field from the target page's `page.json`
- Button label (`text.text`) = Tableau tooltip text (e.g., "Go to Sales Dashboard")
- Use z-index 1000+ so buttons render above chart visuals
- Set `title.show = false` — buttons don't need container titles
- Style background/fill to match Tableau button bar color (extract from parent zone style)
- Group navigation buttons at the same y-position with consistent spacing
- Icon shape: `'Arrow'` for navigation

### Toggle/Bookmark Buttons
- `action.type` = `"'Bookmark'"` — requires manual bookmark creation in PBI Desktop
- Leave `action.bookmark` as empty string `"''"` — user assigns bookmarks after opening
- Icon shape: `'Filter'` for filter toggles, `'Blank'` for custom
- Note in the visual spec that bookmark pairs (show/hide states) must be created manually
- Tooltip text from Tableau should be recorded in spec for user reference

### Active State Indicator
- For "current page" button: use a distinct fill color or visible border to indicate active state
- Can use conditional formatting with `isCurrentPage` if supported

### Available Icon Shapes
- `'Arrow'` — navigation
- `'Filter'` — filter toggle
- `'Blank'` — no icon (text only)
- `'Back'` — back navigation
- `'Bookmark'` — bookmark action
- `'Reset'` — reset filters
- `'QnA'` — Q&A

---

## Validation Checklist

- [ ] Every Tableau `goto-sheet` button has a corresponding `actionButton` with `action.type = "PageNavigation"`
- [ ] Every Tableau `toggle` button has a corresponding `actionButton` with `action.type = "Bookmark"`
- [ ] `action.page` values match actual page `name` values in page.json files
- [ ] Button positions match extracted zone coordinates (scaled to PBI canvas)
- [ ] All navigation buttons have `title.show = false`
- [ ] Toggle buttons include a comment/note that bookmarks need manual setup
- [ ] Button count matches: if Tableau has N buttons per dashboard, PBI page has N button visuals
