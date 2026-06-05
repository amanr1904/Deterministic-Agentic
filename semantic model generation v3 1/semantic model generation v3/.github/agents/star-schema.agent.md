---
description: Design a star schema structure for Power BI from Tableau's flat/denormalized datasources. Creates fact tables, dimension tables, and defines relationships with proper cardinality and cross-filter direction.
---

## User Input

```text
$ARGUMENTS
```

## Skill Reference

Read `.github/skills/star-schema/SKILL.md` before proceeding.

## Steps

### 1. Read Context

- Read `.specify/memory/tableau-analysis-output.md` for source datasources and fields
- Read `.specify/memory/constitution.md` for star schema rules
- Read `.specify/memory/dax-measures-output.md` for measures that define fact table needs

### 2. Identify Fact and Dimension Tables

From the Tableau datasources (often flat/denormalized), decompose into:

**Fact Tables** — contain:
- Foreign keys to dimension tables
- Numeric measure columns (amounts, counts, rates)
- Transaction/event grain (one row per event)

**Dimension Tables** — contain:
- Natural key (unique text identifier — the distinct values from the source column)
- Descriptive attributes for filtering/grouping
- Slowly changing attributes if applicable

### 3. Design Relationships

For each relationship:
- **From** (dimension table, "one" side)
- **To** (fact table, "many" side)
- **Key columns** (join columns)
- **Cardinality**: one-to-many (always)
- **Cross-filter direction**: Single (dimension → fact)
- **Active**: Yes/No (only one active per pair)

Rules:
- No bidirectional unless justified (many-to-many bridging)
- Role-playing dimensions get separate copies (e.g., OrderDate, ShipDate)
- Many-to-many uses bridging/factless fact tables

**CRITICAL — Single-Source Key Strategy:**
If all tables come from ONE source (one CSV, one database table), use **NATURAL KEYS**:
- Dimension key = distinct text values from the source column
- Fact table keeps original columns — they ARE the FKs
- Example: `NetflixTitles.[type]` → `DimType.[TypeName]` (text relationship)
- Do NOT design surrogate integer keys that require cross-table M joins
- This prevents circular dependencies and "Load was cancelled" errors in Power BI

### 4. Define Hierarchies

For each dimension, identify natural hierarchies:
- Date: Year > Quarter > Month > Day
- Geography: Region > State > City
- Product: Category > Subcategory > Product

### 5. Output Format

Save to `.specify/memory/star-schema-output.md`:

```markdown
# Star Schema Design

## Fact Tables
### {FactTableName}
- **Grain**: one row per ...
- **Keys**: [list of FK columns]
- **Measures**: [numeric columns]

## Dimension Tables
### {DimTableName}
- **Key**: [PK column]
- **Attributes**: [list of columns]
- **Hierarchy**: [if applicable]

## Relationships
| From (Dimension) | To (Fact) | Key | Cardinality | Direction | Active |
|---|---|---|---|---|---|

## Decomposition Notes
- Original Tableau source → how it was split
```

### 6. Present Results

Show the star schema design with a clear table structure diagram description.

## Notes

- Generic — reads from analysis output, never hardcodes table or field names
- Tableau flat tables MUST be decomposed into proper fact/dimension split
- Every relationship: one-to-many, single direction, dimension → fact
- Date dimension is ALWAYS required if any date fields exist
- Ref: https://learn.microsoft.com/en-us/power-bi/guidance/star-schema
