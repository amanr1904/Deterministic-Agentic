"""tmdl_blocks.py — reusable TMDL text builders.

Each function returns a TMDL fragment (tab-indented, as Power BI expects).
Indentation is semantic in TMDL: one tab per nesting level. These builders are
pure string formatting consumed by emit_tmdl.py — no parsing, no LLM.
"""
from __future__ import annotations

import csv as _csv
from typing import Dict, List, Optional, Tuple

TAB = "\t"

# IR dataType -> (TMDL dataType, summarizeBy, isDateTime)
TYPE_MAP = {
    "string": ("string", "none", False),
    "integer": ("int64", "sum", False),
    "real": ("double", "sum", False),
    "boolean": ("boolean", "none", False),
    "date": ("dateTime", "none", True),
    "datetime": ("dateTime", "none", True),
}


def quote(name: str) -> str:
    """Quote a TMDL identifier only when it needs it."""
    if name and (name[0].isdigit() or any(c in name for c in " '\"-./()&")):
        return f"'{name}'"
    return name


def lineage(seq: int) -> str:
    """Deterministic lineage tag from a sequence number."""
    return f"a1000000-0000-4000-9000-{seq:012x}"


def column_block(col: Dict, seq: int) -> str:
    """Build a TMDL column block from an IR column dict."""
    name = col["name"]
    tmdl_type, summarize, is_date = TYPE_MAP.get(col["dataType"], ("string", "none", False))
    if col["dataType"] in ("integer", "real") and summarize == "sum":
        summarize = "sum" if col.get("role") == "measure" else "none"
    lines = [f"{TAB}column {quote(name)}"]
    lines.append(f"{TAB}{TAB}dataType: {tmdl_type}")
    fmt = col.get("format") or ("m/d/yyyy" if is_date else None)
    if col["dataType"] == "integer":
        fmt = fmt or "#,0"
    lines.append(f"{TAB}{TAB}lineageTag: {lineage(seq)}")
    if fmt:
        lines.insert(2, f"{TAB}{TAB}formatString: {fmt}")
    lines.append(f"{TAB}{TAB}summarizeBy: {summarize}")
    lines.append(f"{TAB}{TAB}sourceColumn: {name}")
    lines.append("")
    lines.append(f"{TAB}{TAB}annotation SummarizationSetBy = Automatic")
    if is_date:
        lines.append("")
        lines.append(f"{TAB}{TAB}annotation UnderlyingDateTimeDataType = Date")
    return "\n".join(lines)


def calc_column_block(name: str, dax: str, data_type: str,
                      fmt: Optional[str], seq: int) -> str:
    """Build a TMDL calculated-column block (column Name = <DAX>)."""
    tmdl_type, _summ, is_date = TYPE_MAP.get(data_type, ("string", "none", False))
    fmt = fmt or ("m/d/yyyy" if is_date else None)
    lines = [f"{TAB}column {quote(name)} = {dax}"]
    lines.append(f"{TAB}{TAB}dataType: {tmdl_type}")
    if fmt:
        lines.append(f"{TAB}{TAB}formatString: {fmt}")
    lines.append(f"{TAB}{TAB}lineageTag: {lineage(seq)}")
    lines.append(f"{TAB}{TAB}summarizeBy: none")
    lines.append("")
    lines.append(f"{TAB}{TAB}annotation SummarizationSetBy = Automatic")
    if is_date:
        lines.append("")
        lines.append(f"{TAB}{TAB}annotation UnderlyingDateTimeDataType = Date")
    return "\n".join(lines)


def measure_block(m: Dict, seq: int) -> str:
    """Build a TMDL measure block from a decisions measure dict."""
    lines = []
    if m.get("description"):
        lines.append(f"{TAB}/// {m['description']}")
    dax = m["dax"].strip()
    if "\n" in dax:
        body = "\n".join(f"{TAB}{TAB}{TAB}{ln}" for ln in dax.splitlines())
        lines.append(f"{TAB}measure {quote(m['name'])} =")
        lines.append(body)
    else:
        lines.append(f"{TAB}measure {quote(m['name'])} = {dax}")
    if m.get("formatString"):
        lines.append(f"{TAB}{TAB}formatString: {m['formatString']}")
    if m.get("displayFolder"):
        lines.append(f"{TAB}{TAB}displayFolder: {m['displayFolder']}")
    lines.append(f"{TAB}{TAB}lineageTag: {lineage(seq)}")
    return "\n".join(lines)


def csv_partition(table: str, path: str, columns: List[Dict]) -> str:
    """Build an Import-mode CSV partition M block.

    The ``Columns=`` count and the typed-column list are anchored to the CSV's
    *physical* header (not the Tableau column metadata), so the read never gets
    truncated and no type step references a column the file does not contain.
    """
    delim = detect_delimiter(path)
    header = read_csv_header(path)
    header_set = set(header)
    phys_count = len(header) if header else len(columns)
    use_cols = [c for c in columns if not header_set or c["name"] in header_set]
    typed = ",\n".join(
        f'{TAB}{TAB}{TAB}{TAB}{{"{c["name"]}", {_m_type(c["dataType"])}}}'
        for c in use_cols
    )
    return (
        f"{TAB}partition {quote(table)} = m\n"
        f"{TAB}{TAB}mode: import\n"
        f"{TAB}{TAB}source =\n"
        f"{TAB}{TAB}{TAB}let\n"
        f'{TAB}{TAB}{TAB}{TAB}Source = Csv.Document(File.Contents("{path}"), '
        f'[Delimiter="{_m_delimiter(delim)}", Columns={phys_count}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),\n'
        f"{TAB}{TAB}{TAB}{TAB}Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),\n"
        f"{TAB}{TAB}{TAB}{TAB}Typed = Table.TransformColumnTypes(Promoted, {{\n{typed}\n"
        f'{TAB}{TAB}{TAB}{TAB}}}, "en-US")\n'
        f"{TAB}{TAB}{TAB}in\n"
        f"{TAB}{TAB}{TAB}{TAB}Typed\n"
    )


def detect_delimiter(path: str) -> str:
    """Sniff the field delimiter from a CSV's header line.

    Returns one of ',', ';', '\\t', '|'. Falls back to ',' when the file is
    unreadable or no candidate appears. Power BI's Csv.Document defaults to
    comma, so semicolon/tab/pipe files must be detected and emitted explicitly.
    """
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            line = fh.readline()
    except OSError:
        return ","
    candidates = [",", ";", "\t", "|"]
    best = max(candidates, key=line.count)
    return best if line.count(best) > 0 else ","


def _m_delimiter(delim: str) -> str:
    """Render a delimiter char for an M Csv.Document Delimiter property."""
    return {",": ",", ";": ";", "\t": "#(tab)", "|": "|"}.get(delim, ",")


def read_csv_header(path: str) -> List[str]:
    """Return the physical header names of a CSV, or [] if it cannot be read."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return next(_csv.reader(fh, delimiter=detect_delimiter(path)))
    except (OSError, StopIteration):
        return []


def read_csv_sample(path: str, max_rows: int = 100) -> Tuple[List[str], List[List[str]]]:
    """Return (header, sample-rows) from a CSV for light type inference."""
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = _csv.reader(fh, delimiter=detect_delimiter(path))
            header = next(reader)
            rows = []
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                rows.append(row)
            return header, rows
    except (OSError, StopIteration):
        return [], []


def infer_csv_type(rows: List[List[str]], idx: int) -> str:
    """Infer an IR dataType ('integer'/'real'/'string') for one CSV column."""
    vals = [r[idx].strip() for r in rows if idx < len(r) and r[idx].strip() != ""]
    if not vals:
        return "string"
    if all(_is_int(v) for v in vals):
        return "integer"
    if all(_is_float(v) for v in vals):
        return "real"
    return "string"


def _is_int(v: str) -> bool:
    v = v.replace(",", "").strip()
    if v[:1] in ("+", "-"):
        v = v[1:]
    return v.isdigit()


def _is_float(v: str) -> bool:
    try:
        float(v.replace(",", "").strip())
        return True
    except ValueError:
        return False



def datatable_partition(table: str, columns: List[Dict], rows: List[List]) -> str:
    """Build a disconnected DATATABLE partition (parameter selector table)."""
    coldef = ",\n".join(
        f'{TAB}{TAB}{TAB}{TAB}"{c["name"]}", {c["type"].upper()}' for c in columns
    )
    rowdef = ",\n".join(
        f"{TAB}{TAB}{TAB}{TAB}{TAB}{{ " + ", ".join(_lit(v) for v in row) + " }"
        for row in rows
    )
    return (
        f"{TAB}partition {quote(table)} = calculated\n"
        f"{TAB}{TAB}mode: import\n"
        f"{TAB}{TAB}source =\n"
        f"{TAB}{TAB}{TAB}DATATABLE (\n{coldef},\n"
        f"{TAB}{TAB}{TAB}{TAB}{{\n{rowdef}\n{TAB}{TAB}{TAB}{TAB}}}\n"
        f"{TAB}{TAB}{TAB})\n"
    )


def _lit(value) -> str:
    return f'"{value}"' if isinstance(value, str) else str(value)


def _m_type(data_type: str) -> str:
    return {
        "integer": "Int64.Type", "real": "type number", "date": "type date",
        "datetime": "type datetime", "boolean": "type logical",
    }.get(data_type, "type text")
