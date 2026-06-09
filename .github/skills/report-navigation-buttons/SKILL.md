# Report Navigation Buttons Skill

## Purpose

Generate Power BI `actionButton` visuals from Tableau navigation and toggle buttons. Single-responsibility companion to the report visual generation pipeline. Covers page-navigation buttons (`goto-sheet`) and bookmark toggle buttons.

## When to Use

- During report visual generation, for EVERY Tableau button extracted from a dashboard
- Whenever `visualType` is `actionButton`

## ⚠️ CRITICAL — Action Goes in `visualContainerObjects.visualLink`

Power BI wires button navigation through the **container-level `visualLink`** object — NOT `objects.action`.

- Set the action via `visualContainerObjects.visualLink` with `type` and `navigationSection` (the target page's `name`).
- Putting the action under `visual.objects.action` (or using a `page` key) makes the button **render but do nothing** — navigation silently fails.
- `type` values: `'PageNavigation'`, `'Bookmark'`, `'Back'`, `'Drillthrough'`, `'Url'`, `'WebUrl'`, `'QnA'`.

> This supersedes any older guidance that placed `action.type`/`action.page` inside `objects.action`. Always use `visualLink`.

## Page Navigation Button (Tableau `goto-sheet`)

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
  "name": "nav_button_{target_page}",
  "position": {"x": 25, "y": 25, "z": 1000, "height": 40, "width": 120, "tabOrder": 0},
  "visual": {
    "visualType": "actionButton",
    "objects": {
      "icon": [{"properties": {"shapeType": {"expr": {"Literal": {"Value": "'Arrow'"}}}}}],
      "outline": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
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

## Bookmark Toggle Button (Tableau `toggle-action`)

```json
{
  "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.4.0/schema.json",
  "name": "toggle_button_{function}",
  "position": {"x": 25, "y": 25, "z": 1000, "height": 40, "width": 40, "tabOrder": 0},
  "visual": {
    "visualType": "actionButton",
    "objects": {
      "icon": [{"properties": {"shapeType": {"expr": {"Literal": {"Value": "'Filter'"}}}}}],
      "outline": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}],
      "fill": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "fillColor": {"solid": {"color": {"expr": {"Literal": {"Value": "'#072a35'"}}}}}
      }}],
      "text": [{"properties": {"show": {"expr": {"Literal": {"Value": "false"}}}}}]
    },
    "visualContainerObjects": {
      "visualLink": [{"properties": {
        "show": {"expr": {"Literal": {"Value": "true"}}},
        "type": {"expr": {"Literal": {"Value": "'Bookmark'"}}},
        "bookmark": {"expr": {"Literal": {"Value": "''"}}}
      }}],
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

## Button Rules

- **No data query**: buttons only have `objects` + `visualContainerObjects` — no `query` property.
- **Position**: scale from Tableau zone coordinates using the same formula as charts (see `report-layout-gapping`).
- **Z-index**: 1000+ so buttons render above chart visuals.
- **Title**: ALWAYS `title.show = false`.
- **Label text**: use the extracted Tableau tooltip (e.g. "Go to Sales Dashboard").
- **Styling**: match the Tableau nav-bar background color (extract from the parent zone style).
- **Page target**: `visualLink.navigationSection` MUST match the target page's `name` from its `page.json`.
- **Bookmark toggle**: leave `visualLink.bookmark` empty — the user creates bookmark pairs (show/hide) manually in Power BI Desktop after opening. Note this in the spec.
- **Icon shapes**: `'Arrow'` for navigation, `'Filter'` for filter toggles, `'Blank'` for custom.
- **Active state**: distinct fill/border for the "current page" button.

## Anti-Hallucination

- Generate a button ONLY for Tableau zones that contain a `<button>` element.
- Resolve `goto-sheet` `window-id` to a real target dashboard; do not invent navigation targets.
