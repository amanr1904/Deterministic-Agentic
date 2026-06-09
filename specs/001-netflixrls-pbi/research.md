# Phase 0 Research — Netflix RLS Migration

**Feature**: `001-netflixrls-pbi` | **Date**: 2026-06-08

All open questions from the spec were already resolved in the Clarifications session (2026-06-08). This document consolidates the decisions, rationale, and alternatives considered. **No NEEDS CLARIFICATION items remain.**

---

## R1 — Dynamic RLS identity & role configuration

- **Decision**: Single dynamic role **"Dynamic Country Access"** with `tablePermission` on `User_Access`: `[Username] = USERPRINCIPALNAME()`. Case-insensitive under default model collation (fallback `LOWER(...) = LOWER(...)` if collation is case-sensitive).
- **Rationale**: The Tableau `RLS` calc hardcodes `LOWER(ATTR([Username])) = "user2@maq.com"` — a single-user test predicate. `USERPRINCIPALNAME()` returns the signed-in UPN/email matching `User_Access.Username`, achieving true per-user filtering (constitution §4a dynamic-RLS pattern).
- **Alternatives considered**: (a) Static role per country — rejected: doesn't scale, doesn't match the mapping-table intent. (b) `USERNAME()` (DOMAIN\\user) — rejected: source stores emails, UPN is the correct match.

## R2 — Multi-valued `country` vs single-country entitlement

- **Decision**: Normalize via **BridgeCountry** (split `country` by comma, `Text.Trim`, one row per `show_id`+`Country`). Retain the original `country` string on `FactTitle` for display only.
- **Rationale**: A direct equality join on the full multi-country string ("United States, India") would never match a single entitlement value, hiding multi-country titles. The bridge realizes a CONTAINS-style match per individual country; `DISTINCTCOUNT(show_id)` still counts each title once.
- **Alternatives considered**: Direct equality relationship `netflix_titles.country = User_Access.Country` — rejected (spec edge case): mis-filters multi-country titles. DAX `PATHCONTAINS`/`CONTAINSSTRING` RLS predicate — rejected: cannot reference fact in a `User_Access` table predicate and hurts performance.

## R3 — Primary measure definition & name

- **Decision**: `Total Titles = DISTINCTCOUNT(FactTitle[show_id])`, format `#,##0`, folder `Core Metrics`.
- **Rationale**: Direct equivalent of Tableau `COUNTD([show_id])`, the only aggregation used across all nine worksheets. Distinct count keeps multi-country/multi-genre titles counted once after bridge expansion.
- **Alternatives considered**: `COUNTROWS(FactTitle)` — rejected: counts rows not distinct titles (would over-count if grain ever changed).

## R4 — `% of Total Titles` (donut proportional label)

- **Decision**: `DIVIDE([Total Titles], CALCULATE([Total Titles], REMOVEFILTERS(FactTitle[type])))`, format `0.0%`.
- **Rationale**: `REMOVEFILTERS(type)` clears only the type slice so the denominator is Movies+TV Shows while still honoring RLS and other filters — equivalent to Tableau percent-of-total within the type partition. `DIVIDE` is safe against zero.
- **Alternatives considered**: `ALLSELECTED(FactTitle)` denominator — rejected: would also strip RLS-relevant and cross-filter context beyond `type`.

## R5 — `date_added` parsing & year derivation

- **Decision**: Parse in **Power Query** — `try Date.From(DateTime.FromText([date_added], [Format="MMMM d, yyyy", Culture="en-US"])) otherwise null`; derive `Year Added = Date.Year([Date Added])` (Int64, null-safe).
- **Rationale**: Tableau `Year = DATETIME([date_added])` then `YEAR([Year])`. Pushing the transform to M (constitution §6) keeps the model lean and excludes unparseable rows gracefully (null → dropped from the trend).
- **Alternatives considered**: DAX calculated column `YEAR(FactTitle[Date Added])` — kept only as a fallback if the M parse is skipped.

## R6 — `listed_in` (genre) normalization

- **Decision**: Split `listed_in` by comma → **BridgeGenre** + **DimGenre** (distinct trimmed genres).
- **Rationale**: "Top 10 Genre" must rank individual genres; keeping the raw composite string would mis-rank "Dramas, International Movies" as one genre. Bridge + distinct count gives correct per-genre ranking, titles counted once.

## R7 — DimCountry sourcing

- **Decision**: Build `DimCountry` from the **union** of split `netflix_titles.country` values AND `User_Access.Country` (both read directly inside one M query, `Distinct`).
- **Rationale**: Guarantees every entitled country exists as a key so RLS never silently drops a valid entitlement; unmatched values still fall back to deny-by-default. Avoids cross-query references (constitution §5).

## R8 — Date dimension

- **Decision**: **No DimDate**; `Year Added` is a degenerate column on `FactTitle`.
- **Rationale**: Only Year granularity is consumed (the by-Years area trend) and there are zero time-intelligence measures (no YTD/MTD/YoY). A full DimDate would be over-engineering (constitution §0 spirit). Deferred as a future enhancement if time-intelligence is later needed.

## R9 — Degenerate dimensions (type, rating)

- **Decision**: Keep `type` and `rating` as columns on `FactTitle` (no DimType/DimRating).
- **Rationale**: Low cardinality, no conformed reuse, used as legend/axis only. Separate dimensions would add joins without benefit.

## R10 — Report theme

- **Decision**: Dark Netflix theme — `#000000` background, white text, red accents (`#aa0000`/`#ff0000`), applied via report `themeCollection`.
- **Rationale**: Matches the source Tableau dashboard (fixed 1700×800, `#000000`). This is a domain-justified override of the constitution §9 default "professional" light theme (spec FR-019).

## R11 — Tableau `Year` parameter

- **Decision**: **Not migrated** (no What-If table, no slicer).
- **Rationale**: The parameter (date, default `2024-03-26`) has no detected binding to any worksheet filter (spec FR-022 / Assumptions). Migrating it would create an orphan disconnected table. Documented for fidelity; its absence must not break any visual.

## R12 — Donut vs packed bubble

- **Decision**: Render "Movies and TV Shows distribution" as a **donut** sliced by `type`, sized by `[Total Titles]`, labeled with `[% of Total Titles]`.
- **Rationale**: Power BI has no native packed-bubble; a donut conveys the same Movie-vs-TV-Show proportional split with a percent-of-total label (spec clarification + FR-015).

---

## Tableau → Power BI source-type mapping

| Aspect | Tableau source | Power BI target |
|---|---|---|
| Connection | `textscan` (CSV) under a federated datasource | `Csv.Document(File.Contents(...))`, `QuoteStyle.Csv`, Import |
| Logical join | `netflix_titles.country = User_Access.Country` | Replaced by bridge-normalized relationships (R1–R3) |
| `COUNTD([show_id])` | distinct count | `DISTINCTCOUNT(FactTitle[show_id])` |
| `RLS` calc (hardcoded user) | boolean context filter | dynamic role `[Username] = USERPRINCIPALNAME()` |
| `Year = DATETIME([date_added])` | datetime calc | M `Date.From(DateTime.FromText(...))` → `Year Added` |
| % of total (pcto) | table calc | `DIVIDE([Total Titles], CALCULATE([Total Titles], REMOVEFILTERS([type])))` |
| Geographic role `[Country].[ISO3166_2]` | country geo-role | `DimCountry[Country]` Data Category = Country (filled map) |

**Outcome**: All unknowns resolved; ready for Phase 1 design (data-model.md).
