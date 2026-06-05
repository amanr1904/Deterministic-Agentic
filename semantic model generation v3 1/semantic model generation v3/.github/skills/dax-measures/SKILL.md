# DAX Measures & Calculations Skill

## Purpose

Generate DAX measures, calculated columns, and What-If parameters equivalent to Tableau calculated fields. Applies DAX best practices for Power BI semantic models.

## When to Use

- Converting Tableau calculated fields to DAX measures
- Creating What-If parameters from Tableau parameters
- Generating formatted DAX with proper naming and descriptions

## References

- https://maqsoftware.com/insights/dax-best-practices
- https://learn.microsoft.com/en-us/dax/best-practices/dax-variables
- https://learn.microsoft.com/en-us/dax/best-practices/dax-divide-function-operator

## Tableau → DAX Mapping Rules

### Aggregations
| Tableau | DAX |
|---------|-----|
| `SUM([field])` | `SUM(Table[Column])` |
| `COUNT([field])` | `COUNTROWS(Table)` |
| `AVG([field])` | `AVERAGE(Table[Column])` |
| `MIN/MAX([field])` | `MIN/MAX(Table[Column])` |
| `COUNTD([field])` | `DISTINCTCOUNT(Table[Column])` |

### Conditional Logic
| Tableau | DAX |
|---------|-----|
| `IF condition THEN x ELSE y END` | `IF(condition, x, y)` |
| `CASE WHEN` (nested IFs) | `SWITCH(TRUE(), ...)` |
| `IIF(cond, x, y)` | `IF(cond, x, y)` |
| `ZN(expr)` | `COALESCE(expr, 0)` |

### Table Calculations
| Tableau | DAX |
|---------|-----|
| `RANK(expr, 'desc')` | `RANKX(ALL(Table), [Measure], , DESC)` |
| `LOOKUP(expr, -1)` | `VAR prev = OFFSET(-1, ...) RETURN ...` |
| `WINDOW_MAX(expr)` | `MAXX(ALL(Table), [Measure])` |
| `INDEX()` | `RANKX(ALL(Table), [Measure])` |
| `RUNNING_SUM` | Visual calc or `SUMX(FILTER(...))` |

### LOD Expressions
| Tableau | DAX |
|---------|-----|
| `{FIXED [dim]: SUM([meas])}` | `CALCULATE(SUM(Table[Col]), REMOVEFILTERS(), VALUES(Table[Dim]))` |
| `{INCLUDE [dim]: ...}` | `CALCULATE(..., VALUES(Table[Dim]))` |
| `{EXCLUDE [dim]: ...}` | `CALCULATE(..., REMOVEFILTERS(Table[Dim]))` |

### String Functions
| Tableau | DAX |
|---------|-----|
| `CONTAINS(str, sub)` | `SEARCH(sub, str, 1, 0) > 0` |
| `LEFT/RIGHT/MID` | `LEFT/RIGHT/MID` |
| `UPPER/LOWER` | `UPPER/LOWER` |

### Parameters
- Tableau parameter with range → What-If parameter (disconnected table + measure)
- Tableau parameter with list → Field parameter or slicer table

### Sets
| Tableau | DAX |
|---------|-----|
| Fixed set (list of members) | Calculated column: `IF(Table[Col] IN {"A", "B", "C"}, "In Set", "Not In Set")` |
| Computed set (top N) | Measure: `IF(RANKX(ALL(Table[Col]), [Measure]) <= N, "In Set", "Not In Set")` |
| Combined sets (AND) | `IF([Set1] = "In Set" && [Set2] = "In Set", "In Set", "Not In Set")` |
| Combined sets (OR) | `IF([Set1] = "In Set" || [Set2] = "In Set", "In Set", "Not In Set")` |
| Set as filter | `CALCULATE([Measure], FILTER(ALL(Table), Table[Col] IN {"A", "B"}))` |

### Groups
| Tableau | DAX |
|---------|-----|
| Manual group (alias) | Calculated column: `SWITCH(TRUE(), Table[Col] = "A", "Group1", Table[Col] = "B", "Group1", Table[Col] = "C", "Group2", "Other")` |
| Group with "Other" | Same SWITCH pattern with default "Other" case |
| Grouping table (reusable) | Separate grouping table with LOOKUPVALUE relationship |

### Bins
| Tableau | DAX |
|---------|-----|
| Fixed bin size | Calculated column: `MROUND(Table[NumericCol], {bin_size})` or `FLOOR(Table[NumericCol], {bin_size})` |
| Custom bin ranges | `SWITCH(TRUE(), Table[Col] < 10, "0-9", Table[Col] < 20, "10-19", "20+")` |
| Bin table (reusable) | Create disconnected table with `GENERATESERIES(min, max, step)` + relationship |

### Advanced Table Calculations (Partitioned/Addressed)
| Tableau | DAX |
|---------|-----|
| `RUNNING_SUM(SUM([Sales]))` partitioned by [Region] | `CALCULATE(SUM(Table[Sales]), FILTER(ALL(Table), Table[Region] = EARLIER(Table[Region]) && Table[Date] <= EARLIER(Table[Date])))` or Visual Calculation |
| `WINDOW_AVG(SUM([Sales]), -2, 0)` | `AVERAGEX(WINDOW(-2, REL, 0, REL, ...), [Measure])` (visual calc) or use OFFSET pattern |
| `RANK_UNIQUE(SUM([Sales]))` | `RANKX(ALL(Table[Dim]), [Measure], , DESC, DENSE)` |
| `PREVIOUS_VALUE([Measure])` | `VAR PrevDate = OFFSET(-1, ...) RETURN CALCULATE([Measure], PrevDate)` |
| `PERCENT_OF_TOTAL` | `DIVIDE([Measure], CALCULATE([Measure], REMOVEFILTERS(Table[Dim])))` |
| `PERCENT_DIFFERENCE` | `VAR Current = [Measure] VAR Prev = CALCULATE([Measure], OFFSET(-1)) RETURN DIVIDE(Current - Prev, Prev)` |
| `PERCENTILE(expr, 0.5)` | `PERCENTILEX.INC(Table, Table[Col], 0.5)` |

### Date/Time Functions
| Tableau | DAX |
|---------|-----|
| `DATEPART('year', [date])` | `YEAR(Table[DateCol])` |
| `DATEPART('month', [date])` | `MONTH(Table[DateCol])` |
| `DATEDIFF('day', [start], [end])` | `DATEDIFF(Table[Start], Table[End], DAY)` |
| `DATEADD('month', 1, [date])` | `EDATE(Table[DateCol], 1)` |
| `DATETRUNC('month', [date])` | `EOMONTH(Table[DateCol], -1) + 1` or `DATE(YEAR(...), MONTH(...), 1)` |
| `TODAY()` | `TODAY()` |

## DAX Best Practices Checklist

1. Use `DIVIDE()` for all division operations
2. Use `COUNTROWS` instead of `COUNT`
3. Use `SELECTEDVALUE()` instead of `VALUES()` for single values
4. Use `VAR/RETURN` to store intermediate results
5. Fully qualify columns: `Table[Column]`, unqualify measures: `[Measure]`
6. Use `ISBLANK()` not `= BLANK()`
7. Use `COALESCE()` for null handling
8. Avoid `IFERROR`/`ISERROR` — use proper null-safe patterns
9. Use `KEEPFILTERS()` to maintain slicer context
10. Use `TREATAS` for virtual relationships
11. Add description to every measure
12. Organize into display folders by business domain
13. Format using DAX Formatter conventions
14. Use `(a-b)/b` with variables for growth ratios

## Output

Save to `.specify/memory/dax-measures-output.md` with tables for measures, calculated columns, and parameters.
