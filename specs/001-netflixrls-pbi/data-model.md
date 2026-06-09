# Phase 1 Data Model — Netflix RLS Migration

**Feature**: `001-netflixrls-pbi` | **Date**: 2026-06-08
**Source**: [star-schema-output.md](../../.specify/memory/NetflixRLS/star-schema-output.md), [dax-measures-output.md](../../.specify/memory/NetflixRLS/dax-measures-output.md)

Star schema: **6 tables**, **5 relationships**, **1 RLS role**, **2 measures**, **1 calculated column** (M-derived). Grain of `FactTitle` = one row per `show_id` (one Netflix title).

```
                 ┌──────────────┐
                 │  User_Access │  (RLS mapping — Username → Country)
                 └──────┬───────┘
                        │ R3 [Country]  (bi-dir: RLS propagation)
                        ▼
   DimGenre ──R5   ┌──────────┐   R2── DimCountry
        │          │ FactTitle│        │
        ▼          │ show_id  │        ▼
  BridgeGenre ─R4─►│  (grain) │◄─R1─ BridgeCountry
              (bi) └──────────┘ (bi)
```

---

## Tables

### FactTitle (fact)
- **Source**: `Data/Netflix RLS/netflix_titles.csv` (Import, loaded independently)
- **Grain**: one row per `show_id`
- **Key**: `show_id`

| Column | Type | Role | Notes |
|---|---|---|---|
| show_id | Int64 | Primary key / FK target for both bridges | Distinct-count grain |
| type | String | Degenerate dim | Movie / TV Show — donut & area legend |
| title | String | Attribute | Display |
| director | String | Attribute | Display |
| cast | String | Attribute | Display |
| country | String | Attribute (display only) | Original multi-valued string — **not** used in any relationship |
| Date Added | Date (nullable) | Attribute | Parsed in M from text `date_added` ("MMMM d, yyyy", en-US); null if unparseable |
| Year Added | Int64 (nullable) | Attribute | `Date.Year([Date Added])` (M, null-safe) — area-trend category axis |
| release_year | Int64 | Attribute | As-is |
| rating | String | Degenerate dim | Ratings bar chart |
| duration | String | Attribute | Duration listing |
| description | String | Attribute | Description table (TV-Show-filtered visual) |

### DimCountry (dimension — conformed)
- **Source**: union of split `netflix_titles.country` values AND `User_Access.Country` (one M query, `Distinct`)
- **Key**: `Country` (**Data Category = Country** for the filled map)

| Column | Type | Role |
|---|---|---|
| Country | String | Primary key (geo) |

### DimGenre (dimension)
- **Source**: distinct trimmed `listed_in` split values from `netflix_titles.csv`
- **Key**: `Genre`

| Column | Type | Role |
|---|---|---|
| Genre | String | Primary key |

### User_Access (dimension — security only)
- **Source**: `Data/Netflix RLS/User_Access.csv` (Import, loaded independently)
- **Key**: `Username` (RLS predicate column)
- **Visibility**: hidden from report use — never placed in a visual or slicer

| Column | Type | Role |
|---|---|---|
| Username | String | RLS predicate (`[Username] = USERPRINCIPALNAME()`) — email/UPN |
| Country | String | FK → `DimCountry[Country]` (entitled country) |

### BridgeCountry (bridge — multi-valued country)
- **Source**: `netflix_titles.csv` — split `country` by `,`, `Text.Trim`, one row per (`show_id`, `Country`), drop blanks

| Column | Type | Role |
|---|---|---|
| show_id | Int64 | FK → `FactTitle[show_id]` |
| Country | String | FK → `DimCountry[Country]` |

### BridgeGenre (bridge — multi-valued genre)
- **Source**: `netflix_titles.csv` — split `listed_in` by `,`, `Text.Trim`, one row per (`show_id`, `Genre`)

| Column | Type | Role |
|---|---|---|
| show_id | Int64 | FK → `FactTitle[show_id]` |
| Genre | String | FK → `DimGenre[Genre]` |

---

## Relationships

| # | From (one) | To (many) | Key | Cardinality | Cross-filter | Active | Purpose |
|---|---|---|---|---|---|---|---|
| R1 | FactTitle[show_id] | BridgeCountry[show_id] | show_id | 1 : * | **Both** | Yes | Country bridge — lets a country filter reach the fact (map + RLS). |
| R2 | DimCountry[Country] | BridgeCountry[Country] | Country | 1 : * | Single | Yes | Country dimension filters the bridge (map axis + RLS step). |
| R3 | DimCountry[Country] | User_Access[Country] | Country | 1 : * | **Both** | Yes | **RLS propagation** — role filters User_Access; bidir flows up to DimCountry. §4a exception. |
| R4 | FactTitle[show_id] | BridgeGenre[show_id] | show_id | 1 : * | **Both** | Yes | Genre bridge — genre filter reaches the fact (Genre / Top 10 Genre). |
| R5 | DimGenre[Genre] | BridgeGenre[Genre] | Genre | 1 : * | Single | Yes | Genre dimension filters the bridge. |

> Bidirectional only on R1, R4 (mandatory for many-to-many bridges) and R3 (mandatory for RLS). All other flows single-direction (constitution §4).

---

## RLS Propagation Path

**Role**: `Dynamic Country Access` — `modelPermission: read`; `tablePermission User_Access`: `User_Access[Username] = USERPRINCIPALNAME()`.

```
USERPRINCIPALNAME()
   │ filters
   ▼
User_Access (only signed-in user's rows → entitled Country values)
   │ R3  (cross-filter BOTH → many→one)
   ▼
DimCountry (restricted to entitled countries)
   │ R2  (single → DimCountry filters bridge)
   ▼
BridgeCountry (only entitled-country show_ids)
   │ R1  (cross-filter BOTH → many→one)
   ▼
FactTitle (only titles available in the entitled country)
   │ bridges + degenerate columns
   ▼
All visuals & measures
```

- **Deny by default (FR-013)**: unmapped user → zero `User_Access` rows → zero `DimCountry` → zero `BridgeCountry` → zero `FactTitle`.
- **Multi-valued match (FR-007)**: a title tagged "United States, India" is reachable by both a US-entitled and an India-entitled user (one bridge row each), counted once via `DISTINCTCOUNT(show_id)`.
- **Case-insensitivity (FR-012)**: default collation compares UPN to `Username` case-insensitively; fallback `LOWER(...) = LOWER(...)` if case-sensitive.
- **Constraint**: the role filter is a row-level boolean and MUST NOT reference any measure (constitution §4a).

---

## Measures

| Measure | DAX | Folder | Format |
|---|---|---|---|
| Total Titles | `DISTINCTCOUNT(FactTitle[show_id])` | Core Metrics | `#,##0` |
| % of Total Titles | `DIVIDE([Total Titles], CALCULATE([Total Titles], REMOVEFILTERS(FactTitle[type])))` | Core Metrics | `0.0%` |

```dax
Total Titles = DISTINCTCOUNT ( FactTitle[show_id] )
```

```dax
% of Total Titles =
VAR _TypeTitles = [Total Titles]
VAR _AllTypeTitles =
    CALCULATE ( [Total Titles], REMOVEFILTERS ( FactTitle[type] ) )
RETURN
    DIVIDE ( _TypeTitles, _AllTypeTitles )
```

---

## Calculated Column (M-derived)

| Column | Table | Source | Notes |
|---|---|---|---|
| Year Added | FactTitle | M: `Date.Year([Date Added])` (null-safe) | Area-trend axis. DAX fallback `YEAR(FactTitle[Date Added])` only if M parse skipped. |

---

## Validation Rules (from requirements)

- `Total Titles` author (no-role) view = distinct `show_id` count of the catalog (SC-006).
- RLS "View as role" → 100% of visuals show only the entitled country's titles (SC-002); unmapped user → zero (SC-003).
- Area trend ordered chronologically by `Year Added`; Top 10 Genre shows exactly 10 genres descending (SC-007).
- Every relationship many-to-one; bidirectional only on R1/R3/R4; no circular paths (constitution §10).
