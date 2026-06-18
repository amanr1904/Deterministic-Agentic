# Deterministic DAX expression translation (IF / CASE / logical / string / date / conversion)

## Summary

Extends the Stage 6 deterministic DAX engine so that **safe, measure-grain Tableau
calculated fields are translated to DAX automatically** during the prepare phase,
instead of being deferred to the agent. A new fail-closed expression translator
adds support for conditional logic (`IF`, nested `IF`, `ELSEIF`), `CASE`/`WHEN`,
logical and comparison operators, modulo, and a whitelist of string, date,
conversion, and math functions — all wrapped around aggregations.

This reduces the number of calculated fields the LLM must author in
`decisions.json`, lowering token usage while keeping output correctness guaranteed
by a golden byte-match regression test.

## Motivation

`scripts/dax/map_dax.py` runs in the **prepare** phase, before any
`decisions.json`, star-schema, or date/parameter table names exist. Previously it
only handled single aggregations, ratios, and simple aggregate arithmetic;
everything with conditional or function logic fell through to `pending` and had to
be hand-written by the agent. Many of those calcs are mechanical and safe to
translate deterministically, so they were a good candidate for automation.

## Changes

| File | Type | Description |
|------|------|-------------|
| `scripts/dax/dax_expr.py` | **new** | Fail-closed recursive-descent translator converting a safe subset of Tableau expression syntax to DAX. Raises `Untranslatable` for anything outside the subset. |
| `scripts/dax/map_dax.py` | modified | Wires the new translator in as a column-gated `_h_expression` pattern handler; removes `CASE`/`ELSEIF` from the hard `COMPLEX_TOKENS` block so they reach the gated handler. (+194 / −22) |
| `scripts/tests/test_pipeline.py` | modified | Adds `TestDaxExpression` (18 cases) covering positive translations and every safety gate. (+151) |
| `scripts/emit/emit_tmdl.py` | modified | CSV path portability fix — resolves data sources against the repo root rather than an absolute path baked into `decisions.json`. (+36 / −4) |

### What is now auto-translated (measure-grain)

- `IF` / nested `IF` / `ELSEIF` conditionals → `IF(...)`
- `CASE` / `WHEN` → `SWITCH(...)`
- Logical `AND` / `OR` / `NOT` and comparison operators (`=`, `<>`, `<`, `>`, `<=`, `>=`)
- Modulo (`%` → `MOD`) and parenthesized arithmetic
- Aggregations: `SUM`, `AVG`→`AVERAGE`, `MIN`, `MAX`, `MEDIAN`, `COUNT`,
  `COUNTD`→`DISTINCTCOUNT`, `STDEV`/`STDEVP`, `VAR`/`VARP`, `ATTR`→`SELECTEDVALUE`
- Whitelisted functions: string (`UPPER`/`LOWER`/`TRIM`/`LEN`/`LEFT`/`RIGHT`/`MID`/
  `REPLACE`→`SUBSTITUTE`/`CONTAINS`/`STR`), date (`YEAR`/`MONTH`/`DAY`/`QUARTER`/
  `WEEK`/`HOUR`/`MINUTE`/`SECOND`/`TODAY`/`NOW`/`DATEDIFF`), conversion/null
  (`INT`/`ZN`/`ISNULL`→`ISBLANK`/`IFNULL`→`COALESCE`/`IIF`), and math
  (`ABS`/`ROUND`/`SQRT`/`SIGN`/`EXP`/`LN`/`POWER`)

### Measures added on the committed sample workbooks

Running the new translator against the committed `analysis.json` files, exactly one
previously-`pending` field now produces a deterministic measure; all other sample
workbooks are unchanged:

| Workbook | Measure | Generated DAX |
|----------|---------|---------------|
| `NetfixWorkbookRls` | **RLS** | `( ( SEARCH ( LOWER ( SELECTEDVALUE ( NetfixWorkbookRls[country] ) ), LOWER ( COALESCE ( SELECTEDVALUE ( NetfixWorkbookRls[country] ), "" ) ), 1, 0 ) > 0 ) && ( LOWER ( SELECTEDVALUE ( NetfixWorkbookRls[Username] ) ) = "user2@maq.com" ) )` |

- `MidnightCensusDashboard` — no change (golden byte-match preserved).
- `SalesCustomerDashboards`, `NetfixWorkbook` — no measure-kind calc fields fall
  into the safe subset; all remain `pending` for the agent.

> Note: `RLS` translates because it is classified `suggestedDaxKind: measure` in the
> IR. Its DAX is valid, but whether an RLS predicate belongs in a measure vs. a role
> definition is a *classification* concern handled downstream, not by this change.
> No committed `dax-partial.json` is regenerated in this PR, so this is a capability
> addition rather than an output diff.

Representative translations from the test suite (`TestDaxExpression`):

```text
IF SUM([Sales]) > 0 THEN SUM([Profit]) ELSE 0 END
  -> IF ( ( SUM ( T[Sales] ) > 0 ), SUM ( T[Profit] ), 0 )

CASE ATTR([Region]) WHEN 'N' THEN 1 WHEN 'S' THEN 2 ELSE 0 END
  -> SWITCH ( SELECTEDVALUE ( T[Region] ), "N", 1, "S", 2, 0 )

DATEDIFF('day', MIN([Order Date]), MAX([Order Date]))
  -> DATEDIFF ( MIN ( T[Order Date] ), MAX ( T[Order Date] ), DAY )

ZN(SUM([Profit]))   -> COALESCE ( SUM ( T[Profit] ), 0 )
SUM([Qty]) % 2      -> MOD ( SUM ( T[Qty] ), 2 )
```

## Safety design

The translator is **fail-closed**: any construct it does not explicitly understand
raises `Untranslatable`, and `map_dax` then leaves the field `pending` for the
agent. Three gates guarantee only valid DAX is emitted:

1. **Base-column only** — every `[token]` must resolve to a real source column.
   Parameter references (`[Parameters].[X]`), datasource-qualified refs (`[a].[b]`),
   and unknown calc-field tokens all bail.
2. **At least one column** — pure constant/literal formulas (e.g. `"(All)"`,
   `TODAY() - 1`) bail, protecting literal/parameter-style calcs.
3. **Measure-grain** — a column referenced outside an aggregation bails, because a
   bare column is invalid DAX inside a measure (e.g. `SUM([Sales]) - [Profit]`).

Additional guards: unknown functions, ambiguous string-concatenation `+`, mismatched
arity, and trailing tokens all raise `Untranslatable`.

### Deliberately left to the agent (out of scope)

These require context that does not exist in the prepare phase and remain
`pending` by design:

- Time-intelligence (needs the date-table name)
- LOD `FIXED` / `INCLUDE` / `EXCLUDE` (needs grain + relationships)
- Table calcs: `RUNNING_*` / `WINDOW_*` / `RANK` / `INDEX` / `LOOKUP` (need visual order/partition)
- Parameter references (need param-table names from `decisions.json`)
- Nested calculated-field references (need topological ordering)
- Row-level (column-kind) string/date/conversion calcs — surfaced as
  `pending: non-measure` since `map_dax` emits **measures** only; calculated
  columns are authored via the decisions/agent path.

## Testing

```powershell
python -m unittest discover -s scripts/tests -v
```

- **33 tests pass.**
- New `TestDaxExpression` covers each translation pattern plus all gating paths
  (parameter ref, non-base column, bare column, pure constant, string concat,
  unknown function, missing column set).
- The golden regression `TestGoldenMidnightCensus.test_map_dax_matches_committed_partial`
  still **byte-matches** the committed `Output/MidnightCensusDashboard/dax-partial.json`,
  confirming no existing pending field changed its translation or `reason`.

## Reviewer notes

- No public contract changes — `dax-partial.json` shape is unchanged; the new
  handler only converts some previously `pending` measures into translated ones.
- **Please exclude unrelated artifacts** that may appear in the working tree from
  a separate pipeline run and are not part of this change:
  - `Output/NetfixWorkbook/decisions.json`
  - `Output/NetfixWorkbook/constitution-cache.json`
  - `scripts/**/__pycache__/*.pyc`

## PR checklist

- [x] New code is UTF-8, no BOM
- [x] Full test suite green (33/33)
- [x] Golden byte-match preserved (Midnight Census)
- [x] No public schema/contract changes
- [ ] Unrelated `Output/NetfixWorkbook/*` and `__pycache__` artifacts excluded from the commit
