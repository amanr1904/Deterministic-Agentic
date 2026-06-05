---
description: Generate DAX measures, calculated columns, and What-If parameters for Power BI from Tableau calculated fields. Uses DAX best practices from MAQ Software and Microsoft guidance.
---

## User Input

```text
$ARGUMENTS
```

## Skill Reference

Read `.github/skills/dax-measures/SKILL.md` before proceeding.

## Steps

### 1. Read Context

- Read `.specify/memory/tableau-analysis-output.md` for source calculated fields
- Read `.specify/memory/constitution.md` for naming/DAX rules

### 2. Map Tableau Calculations to DAX

For each Tableau calculated field, generate the equivalent DAX:

**Simple aggregations** → DAX Measures:
- `COUNT([field])` → `COUNTROWS(Table)`
- `SUM([field])` → `SUM(Table[Column])`
- `AVG([field])` → `AVERAGE(Table[Column])`

**Conditional logic** → DAX Measures with IF/SWITCH:
- `IF [x] = "value" THEN 1 ELSE 0 END` → `IF(Table[x] = "value", 1, 0)`

**Table calculations** → DAX with window functions:
- `RANK(expr)` → `RANKX(ALL(Table), [Measure])`
- `LOOKUP(expr, offset)` → `OFFSET` / `INDEX` or VAR with EARLIER
- `WINDOW_MAX/MIN` → `MAXX/MINX(ALL(Table), [Measure])`

**Ratios** → DIVIDE():
- `a/b` → `DIVIDE([MeasureA], [MeasureB], 0)`

**Parameters** → What-If parameters:
- Create disconnected table + slicer measure

### 3. Apply DAX Best Practices

Ref: https://maqsoftware.com/insights/dax-best-practices

- Use `DIVIDE()` not `/` for division
- Use `COUNTROWS` not `COUNT`
- Use `SELECTEDVALUE()` not `VALUES()` for single-value retrieval
- Use `VAR/RETURN` to avoid repeated calculations
- Use `ISBLANK()` not `= Blank()`
- Use `COALESCE()` for null handling
- Use `KEEPFILTERS()` instead of `FILTER(T)` when maintaining context
- Use `FILTER(ALL(Column))` not `FILTER(VALUES())` for context-independent filters
- Use `TREATAS` for virtual relationships
- Fully qualify column refs: `Table[Column]`; unqualified measure refs: `[Measure]`
- Format with DAX Formatter conventions
- Add descriptions for every measure
- Organize measures into display folders
- Avoid IFERROR/ISERROR — use SEARCH/FIND with last parameter
- Avoid AddColumns() inside measure expressions
- Use `(a-b)/b` pattern with variables for ratios, not `a/b - 1`

### 4. Output Format

Save the DAX definitions to `.specify/memory/dax-measures-output.md`:

```markdown
# DAX Measures & Calculations

## Measures
| Measure Name | DAX Expression | Display Folder | Description | Source (Tableau) |
|---|---|---|---|---|

## Calculated Columns
| Column Name | Table | DAX Expression | Description | Source (Tableau) |
|---|---|---|---|---|

## What-If Parameters
| Parameter Name | Min | Max | Step | Default | DAX Measure |
|---|---|---|---|---|---|
```

### 5. Present Results

Show all generated DAX with clear mapping back to Tableau sources.

## Notes

- Generic — reads from analysis output, never hardcodes field names
- Every measure MUST have a description and display folder
- Prefer measures over calculated columns for aggregations
- Parameters use What-If pattern (disconnected table + measure)
