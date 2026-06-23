"""emit_tmdl.py — Stage 10 deterministic TMDL semantic-model generator.

Consumes analysis.json (IR) + decisions.json and writes a complete
{Model}.SemanticModel/ folder plus the {Model}.pbip root and .platform file. All
TMDL boilerplate is emitted here; the LLM only supplies measure DAX via decisions.
"""
from __future__ import annotations

import argparse
import csv as _csv
import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tmdl_blocks as B  # noqa: E402
import date_levels as D  # noqa: E402
import field_param as FP  # noqa: E402
import topn as T  # noqa: E402

_TWB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "twb")
sys.path.insert(0, os.path.normpath(_TWB_DIR))
import csv_probe as CP  # noqa: E402

PBISM = {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "version": "4.2", "settings": {},
}
PLATFORM_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json"


def platform_file(item_type: str, name: str, seed: str) -> str:
    """Build a Fabric .platform file (deterministic GUID-shaped logicalId)."""
    import hashlib
    h = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    lid = f"{h[:8]}-{h[8:12]}-4{h[13:16]}-9{h[17:20]}-{h[20:32]}"
    return json.dumps({
        "$schema": PLATFORM_SCHEMA,
        "metadata": {"type": item_type, "displayName": name},
        "config": {"version": "2.0", "logicalId": lid},
    }, indent=2)


def pbip_root(model_name: str) -> str:
    """Build the {Model}.pbip root file (report artifact only)."""
    return json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{model_name}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }, indent=2)

def load_json(path: str) -> Dict:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def model_dir(analysis_path: str, model_name: str) -> str:
    base = os.path.dirname(os.path.abspath(analysis_path))
    path = os.path.join(base, f"{model_name}.SemanticModel")
    os.makedirs(os.path.join(path, "definition", "tables"), exist_ok=True)
    return path


def write(path: str, text: str) -> None:
    # Always write UTF-8 WITHOUT BOM — Power BI Desktop rejects BOM in TMDL/PBIR files.
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def build_table_file(table: Dict, ir: Dict, decisions: Dict, seq: int) -> str:
    """Assemble one table TMDL file: header, measures, columns, partition."""
    name = table["name"]
    lines = [f"table {B.quote(name)}", f"{B.TAB}lineageTag: {B.lineage(seq)}"]
    if table.get("role") == "date":
        lines.append(f"{B.TAB}dataCategory: Time")
    lines.append("")
    measures = [m for m in decisions.get("measures", []) if m["table"] == name]
    # Names already claimed on this table (explicit measures + auto-injected
    # ones). The SAME rank/last-order measure is commonly referenced by many
    # visual tableColumns; without this guard each occurrence would emit a
    # duplicate `measure 'X'` block and Power BI Desktop rejects the model
    # ("TMDL objects cannot be merged because both declare the same property:
    # expression"). One declaration per name is all the model needs.
    _seen_measure = {m["name"].lower() for m in measures}
    # Auto-inject rankMeasure declared on visual tableColumns in decisions.json.
    # "rankMeasure": {"by": "CY Profit", "over": "DimCustomer", "overCol": "Customer Name"}
    # Generates: RANKX(ALLSELECTED(DimCustomer[Customer Name]), [CY Profit], , DESC, Dense)
    _rank_specs = [
        tc for vd in decisions.get("visualDecisions", []) if vd
        for tc in (vd.get("tableColumns") or [])
        if tc.get("isMeasure") and tc.get("rankMeasure") and tc["table"] == name
    ]
    for rs in _rank_specs:
        if rs["prop"].lower() in _seen_measure:
            continue
        _seen_measure.add(rs["prop"].lower())
        rm = rs["rankMeasure"]
        by_m, over_t, over_c = rm["by"], rm["over"], rm["overCol"]
        measures.append({
            "name": rs["prop"],
            "table": name,
            "dax": (
                f"VAR _v = [{by_m}] "
                f"RETURN IF(ISBLANK(_v), BLANK(), "
                f"RANKX(ALLSELECTED({over_t}[{over_c}]), [{by_m}], , DESC, Dense))"
            ),
            "formatString": "#,0",
            "displayFolder": "Customers",
        })
    # Auto-inject lastOrderMeasure declared on visual tableColumns in decisions.json.
    # "lastOrderMeasure": {"dateColumn": "Order Date"} -> MAX(TableName[dateColumn])
    _last_specs = [
        tc for vd in decisions.get("visualDecisions", []) if vd
        for tc in (vd.get("tableColumns") or [])
        if tc.get("isMeasure") and tc.get("lastOrderMeasure") and tc["table"] == name
    ]
    for ls in _last_specs:
        if ls["prop"].lower() in _seen_measure:
            continue
        _seen_measure.add(ls["prop"].lower())
        lm = ls["lastOrderMeasure"]
        date_col = lm["dateColumn"]
        measures.append({
            "name": ls["prop"],
            "table": name,
            "dax": f"MAX({name}[{date_col}])",
            "formatString": "dd-mm-yyyy",
            "displayFolder": "Customers",
        })
    # Auto-inject Top-N rank measures from the IR (Tableau groupfilter count=N).
    # The category column lives on the fact table, so rank measures land here.
    if table.get("role") == "fact":
        _seen_rank = _seen_measure
        for ws in ir.get("worksheets", []):
            tn = ws.get("topN")
            if not tn or not tn.get("field"):
                continue
            rname, rdax, _count = T.spec(tn, name)
            if rname.lower() in _seen_rank:
                continue
            _seen_rank.add(rname.lower())
            measures.append({
                "name": rname,
                "table": name,
                "dax": rdax,
                "formatString": "#,0",
                "displayFolder": "Helper",
                "description": (f"Rank of {tn['field']} for the Top-{_count} "
                                f"filter (mirrors the Tableau Top-N groupfilter)."),
            })
    cols = _columns_for(table, ir, decisions)
    col_names = {c["name"].lower() for c in cols}
    # Agent-authored calculated columns also share the table namespace with
    # measures — fold them in so a name collision is caught here, not in Desktop.
    cc_names = {c["name"].lower() for c in decisions.get("calculatedColumns", [])
                if c.get("table") == name}
    clash = sorted(m["name"] for m in measures
                   if m["name"].lower() in col_names or m["name"].lower() in cc_names)
    if clash:
        raise ValueError(f"table '{name}': measure name(s) collide with columns: {clash}")
    for i, m in enumerate(measures):
        lines += [B.measure_block(m, seq * 100 + i + 1), ""]
    for i, col in enumerate(cols):
        lines += [B.column_block(col, seq * 1000 + i + 1), ""]
    # Calendar date table: Date key column + date intelligence calculated columns
    if table.get("role") == "date" and table.get("sourceType") == "calendar":
        lines += [B.date_key_column_block(seq * 1000 + 1), ""]
        for j, (col_name, dax, dtype, fmt) in enumerate(_CALENDAR_CALC_COLS):
            lines += [B.calc_column_block(col_name, dax, dtype, fmt, seq * 1000 + 10 + j), ""]
    for j, part in enumerate(_date_part_columns(table, cols, ir)):
        dax = D.part_dax(part["baseColumn"], name, part["level"])
        lines += [B.calc_column_block(part["name"], dax, part["dataType"],
                                      part["format"], seq * 1000 + 500 + j), ""]
    # Agent-authored calculated columns from decisions.json (e.g. Tableau FIXED
    # LOD buckets that must be materialized as a column). Hosted on table.name.
    cc_cols = [c for c in decisions.get("calculatedColumns", [])
               if c.get("table") == name]
    for j, cc in enumerate(cc_cols):
        lines += [B.calc_column_block(cc["name"], cc["dax"],
                                      cc.get("dataType") or "string",
                                      cc.get("formatString"), seq * 1000 + 700 + j), ""]
    lines.append(_partition_for(table, ir, cols, decisions))
    return "\n".join(lines)


def _date_part_columns(table: Dict, cols: List[Dict], ir: Dict) -> List[Dict]:
    """Date-part derived columns this table must expose (month/year/etc.)."""
    if table.get("role") != "fact":
        return []
    date_cols = {c["name"] for c in cols if c["dataType"] in ("date", "datetime")}
    if not date_cols:
        return []
    return D.needed_parts(ir.get("worksheets", []), date_cols)


# Calculated columns added to every CALENDAR() date dimension table.
_CALENDAR_CALC_COLS = [
    ("Year",         "YEAR([Date])",                        "integer", "0"),
    ("Month Number", "MONTH([Date])",                       "integer", "0"),
    ("Month",        'FORMAT([Date], "MMMM")',               "string",  None),
    ("Quarter",      '"Q" & FORMAT(QUARTER([Date]), "0")',   "string",  None),
    ("Year-Month",   'FORMAT([Date], "YYYY-MM")',            "string",  None),
]


def _dim_source_column(table_name: str, key_col: str, decisions: Dict) -> str:
    """Find the fact-side column that maps to this dim's key via relationships."""
    for rel in decisions.get("relationships", []):
        to_t, to_c = rel["toColumn"].split(".", 1)
        if to_t == table_name and to_c == key_col:
            _, from_c = rel["fromColumn"].split(".", 1)
            return from_c
    return key_col  # fallback: same name as key


def _date_source_column(table_name: str, decisions: Dict, ir: Dict = None):
    """Return (fact_table, date_col) for a DimDate calendar table via relationships."""
    for rel in decisions.get("relationships", []):
        to_t, _to_c = rel["toColumn"].split(".", 1)
        if to_t == table_name:
            from_t, from_c = rel["fromColumn"].split(".", 1)
            return from_t, from_c
    tables = decisions.get("tables", [])
    fact = next((t["name"] for t in tables if t.get("role") == "fact"), "Table")
    # No relationship to resolve the source date: fall back to the first
    # date/datetime column in the IR (generic, not a workbook-specific name).
    date_col = next((c["name"] for c in (ir or {}).get("columns", [])
                     if c.get("dataType") in ("date", "datetime")), "Date")
    return fact, date_col


def _columns_for(table: Dict, ir: Dict, decisions: Dict) -> List[Dict]:
    role = table.get("role")
    # Dim with dedupKey: load ALL CSV columns so attributes are available.
    # Fall back to key-only when CSV cannot be probed.
    if role == "dim" and table.get("dedupKey"):
        key = (table.get("keyColumns") or [table["dedupKey"]])[0]
        probe = _probe_for_table(table, ir)
        if probe and probe["columns"]:
            return probe["columns"]
        return [{"name": key, "dataType": "string", "role": "dimension", "format": None}]
    # Calendar date table: no regular columns (Date key + calc columns added separately)
    if role == "date" and table.get("sourceType") == "calendar":
        return []
    if role == "param" and table.get("datatable"):
        return [{"name": c["name"], "dataType": c.get("dataType", "string"),
                 "role": "dimension", "format": None}
                for c in table["datatable"]["columns"]]
    ds = table.get("sourceDatasource")
    cols = [c for c in ir["columns"] if ds is None or c["datasource"] == ds]
    cols = cols or ir["columns"]
    cols = _dedupe_columns(cols, ir)
    cols = [c for c in cols if not _is_pseudo_column(c.get("name", ""))]
    # The MODEL columns must reflect what the M partition actually loads. When the
    # table is backed by a probeable CSV whose header set DIFFERS from the IR (e.g.
    # the workbook's datasource was an Excel export but the supplied data file is a
    # differently-shaped CSV), trust the CSV: declaring an IR-only column whose
    # sourceColumn is absent from the file fails to load ("column 'X' wasn't found"),
    # and CSV-only columns the visuals/measures need would otherwise be missing.
    probe = _probe_for_table(table, ir)
    if probe and probe["columns"]:
        ir_norm = {_normalize_name(c["name"]) for c in cols}
        csv_norm = {_normalize_name(c["name"]) for c in probe["columns"]}
        if ir_norm != csv_norm:
            return [c for c in probe["columns"] if not _is_pseudo_column(c.get("name", ""))]
    return cols


def _is_pseudo_column(name: str) -> bool:
    """True for Tableau synthetic shelf fields that have no backing CSV column."""
    n = (name or "").strip()
    if n.startswith(":"):
        return True
    return n.lower() in {"measure names", "measure values",
                         "number of records", "multiple values"}


def _dedupe_columns(cols: List[Dict], ir: Dict) -> List[Dict]:
    """Collapse duplicate column names (Power BI rejects a table that declares the
    same column twice — "TMDL objects cannot be merged ... same property: dataType").
    Duplicates arise when several datasources (e.g. an inactive Hyper extract plus the
    active CSV) each expose a same-named field and they flatten into one table.
    Keep the first occurrence per normalized name, but prefer a column sourced from an
    ACTIVE datasource over an inactive one. Insertion order is preserved.
    """
    active_ds = {d.get("name") for d in ir.get("dataSources", []) if d.get("active")}
    seen: "dict[str, Dict]" = {}
    for c in cols:
        key = _normalize_name(c.get("name", ""))
        if key not in seen:
            seen[key] = c
        elif c.get("datasource") in active_ds and seen[key].get("datasource") not in active_ds:
            seen[key] = c  # replace inactive-source duplicate with the active-source one
    return list(seen.values())


def _partition_for(table: Dict, ir: Dict, cols: List[Dict], decisions: Dict) -> str:
    role = table.get("role")
    # Dim with dedupKey: full M partition — load all CSV columns, rename, dedup.
    if role == "dim" and table.get("dedupKey"):
        key = (table.get("keyColumns") or [table["dedupKey"]])[0]
        path = _abs_csv(ir, table.get("sourceFile") or _first_csv(ir))
        probe = _probe_for_table(table, ir)
        if probe and probe["columns"]:
            return B.dim_partition(table["name"], path, probe["delimiter"],
                                   key, probe["columns"])
        # Fallback: key-only slim partition when CSV cannot be probed
        src_col = _dim_source_column(table["name"], key, decisions)
        all_cols = [{"name": key, "csv_name": src_col, "dataType": "string"}]
        return B.dim_partition(table["name"], path, ",", key, all_cols)
    # Calendar date table: DAX CALENDAR calculated partition
    if role == "date" and table.get("sourceType") == "calendar":
        fact_tbl, date_col = _date_source_column(table["name"], decisions, ir)
        return B.calendar_partition(table["name"], fact_tbl, date_col)
    if role == "param" and table.get("datatable"):
        dt = table["datatable"]
        return B.datatable_partition(table["name"], dt["columns"], dt["rows"])
    if table.get("mExpression"):
        return B.raw_partition(table["name"], table["mExpression"])
    # Fact / other: probe CSV for delimiter; use robust parsing for European CSVs.
    path = table.get("sourceFile") or _first_csv(ir)
    abs_path = _abs_csv(ir, path)
    probe = _probe_for_table(table, ir)
    delimiter = probe["delimiter"] if probe else ","
    if probe and probe["columns"]:
        csv_names_norm = {_normalize_name(c["csv_name"]) for c in probe["columns"]}
        cols = [c for c in cols if _normalize_name(c["name"]) in csv_names_norm]
    if delimiter != ",":
        date_cs = [c["name"] for c in cols if c.get("dataType") in ("date", "datetime")]
        decimal_cs = [c["name"] for c in cols if c.get("dataType") == "real"]
        return B.robust_csv_partition(table["name"], abs_path, cols, delimiter,
                                      date_cs, decimal_cs)
    return B.csv_partition(table["name"], abs_path, cols, delimiter)


def _abs_csv(ir: Dict, path: str) -> str:
    """Resolve a CSV filename to an absolute path (File.Contents needs it)."""
    if os.path.isabs(path):
        return path
    data_dir = os.path.dirname(ir.get("workbook", {}).get("sourcePath", ""))
    return os.path.abspath(os.path.join(data_dir, os.path.basename(path)))


def _first_csv(ir: Dict) -> str:
    for ds in ir.get("dataSources", []):
        csvs = [f for f in ds.get("files", []) if ds.get("active") and f.lower().endswith(".csv")]
        if csvs:
            return csvs[0]
    return "PATH_TO_DATA.csv"


def _normalize_name(s: str) -> str:
    """Normalize a column name for fuzzy matching: underscores/slashes/hyphens/spaces
    all collapse to a single space, then lowercase.  Handles CSV underscore headers
    (Customer_ID) matching logical names (Customer ID) and slash variants (Country/Region).
    """
    return re.sub(r"[_/\-\s]+", " ", s).strip().lower()


def _build_csv_columns(csv_headers: List[str], ir_columns: List[Dict],
                       inferred: Dict[str, str] | None = None) -> List[Dict]:
    """Match each CSV header to an IR logical column using normalized comparison.
    Returns a list of {name, csv_name, dataType} dicts ordered by CSV column order.
    Unmatched headers keep their raw name; their dataType comes from value-sniffing
    (``inferred``) so CSV-only numeric columns (e.g. measures materialized into the
    export that the original Tableau datasource never declared) are typed correctly.
    """
    inferred = inferred or {}
    ir_by_norm = {_normalize_name(c["name"]): c for c in ir_columns}
    result = []
    for h in csv_headers:
        n = _normalize_name(h)
        if n in ir_by_norm:
            col = ir_by_norm[n]
            result.append({"name": col["name"], "csv_name": h,
                           "dataType": col.get("dataType", "string")})
        else:
            result.append({"name": h, "csv_name": h,
                           "dataType": inferred.get(h, "string")})
    return result


def _infer_csv_types(path: str, delimiter: str, headers: List[str],
                     sample: int = 200) -> Dict[str, str]:
    """Sniff each CSV column's dataType from up to ``sample`` data rows."""
    buckets: "dict[str, list]" = {h: [] for h in headers}
    try:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
            reader = _csv.reader(fh, delimiter=delimiter)
            next(reader, None)  # skip header
            for i, row in enumerate(reader):
                if i >= sample:
                    break
                for h, v in zip(headers, row):
                    if v is not None and v.strip() != "":
                        buckets[h].append(v.strip())
    except OSError:
        return {}
    return {h: _infer_one_type(vals) for h, vals in buckets.items()}


def _infer_one_type(vals: List[str]) -> str:
    if not vals:
        return "string"

    def _is_int(v: str) -> bool:
        try:
            int(v)
            return True
        except ValueError:
            return False

    def _is_float(v: str) -> bool:
        try:
            float(v)
            return True
        except ValueError:
            return False

    if all(_is_int(v) for v in vals):
        return "integer"
    if all(_is_float(v) for v in vals):
        return "real"
    _fmts = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S")

    def _is_date(v: str) -> bool:
        for f in _fmts:
            try:
                datetime.strptime(v, f)
                return True
            except ValueError:
                continue
        return False

    if all(_is_date(v) for v in vals):
        return "date"
    return "string"


def _probe_for_table(table: Dict, ir: Dict) -> Dict | None:
    """Probe the CSV backing a table.  Returns {delimiter, columns} or None."""
    raw_path = table.get("sourceFile") or _first_csv(ir)
    path = _abs_csv(ir, raw_path)
    result = CP.probe(path)
    if result is None:
        return None
    ir_cols = ir.get("columns", [])
    inferred = _infer_csv_types(path, result["delimiter"], result["headers"])
    return {
        "delimiter": result["delimiter"],
        "columns": _build_csv_columns(result["headers"], ir_cols, inferred),
    }


def build_model_file(decisions: Dict) -> str:
    tables = [t["name"] for t in decisions.get("tables", [])]
    tables += [fp["name"] for fp in decisions.get("fieldParameters", [])]
    refs = "\n".join(f"ref table {B.quote(t)}" for t in tables)
    return ("model Model\n\tculture: en-US\n\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tdiscourageImplicitMeasures\n\tsourceQueryCulture: en-US\n\tdataAccessOptions\n"
        "\t\tlegacyRedirects\n\t\treturnErrorValuesAsNull\n\n"
        f"annotation PBI_QueryOrder = {json.dumps(tables)}\n\n"
        "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
        "annotation PBI_ProTooling = [\"DevMode\"]\n\n"
        f"{refs}\n")


def build_relationships_file(decisions: Dict) -> str:
    blocks = []
    for i, rel in enumerate(decisions.get("relationships", [])):
        from_t, from_c = rel["fromColumn"].split(".", 1)
        to_t, to_c = rel["toColumn"].split(".", 1)
        block = (f"relationship {B.lineage(0xf000 + i)}\n"
                 f"\tfromColumn: {B.quote(from_t)}.{B.quote(from_c)}\n"
                 f"\ttoColumn: {B.quote(to_t)}.{B.quote(to_c)}\n")
        block += "\tcrossFilteringBehavior: bothDirections\n" if rel.get("crossFilter") == "both" else ""
        block += "\tisActive: false\n" if rel.get("active") is False else ""
        blocks.append(block)
    return "\n".join(blocks) + ("\n" if blocks else "")


def _build_calculated_table_tmdl(ct: Dict, lineage_base: int) -> str:
    """Build TMDL text for a DAX calculated table (no circular-ref risk).

    ct = {"name": "...", "dax": "...", "columns": [{"name", "dataType", "formatString", "summarizeBy"}]}
    Calculated tables are safe alternatives to calculated columns that reference
    other tables — they don't participate in the relationship-based processing cycle.
    """
    t = ct["name"]
    tag = f"a1000000-0000-4000-9000-{lineage_base:012x}"
    lines = [f"table {t!r}" if " " in t or not t[0].isalpha() else f"table {t}",
             f"\tlineageTag: {tag}",
             ""]
    for i, col in enumerate(ct.get("columns", []), start=1):
        ctag = f"a1000000-0000-4000-9000-{lineage_base + i:012x}"
        lines += [
            f"\tcolumn {col['name']!r}" if (" " in col["name"] or not col["name"][0].isalpha())
            else f"\tcolumn {col['name']}",
            f"\t\tdataType: {col.get('dataType', 'string')}",
        ]
        if col.get("formatString"):
            lines.append(f"\t\tformatString: {col['formatString']}")
        lines += [
            f"\t\tlineageTag: {ctag}",
            f"\t\tsummarizeBy: {col.get('summarizeBy', 'none')}",
            f"\t\tsourceColumn: [{col['name']}]",
            "",
            "\t\tannotation SummarizationSetBy = Automatic",
            "",
        ]
    dax = ct["dax"].strip()
    lines += [
        f"\tpartition {t} = calculated",
        "\t\tmode: import",
        "\t\tsource =",
        f"\t\t\t\t{dax}",
    ]
    return "\n".join(lines) + "\n"


def emit(ir: Dict, decisions: Dict, analysis_path: str) -> str:
    model_name = decisions.get("modelName") or ir["workbook"]["pascalName"]
    root = model_dir(analysis_path, model_name)
    defin = os.path.join(root, "definition")
    write(os.path.join(defin, "database.tmdl"), "database\n\tcompatibilityLevel: 1600\n")
    write(os.path.join(defin, "model.tmdl"), build_model_file(decisions))
    write(os.path.join(defin, "relationships.tmdl"), build_relationships_file(decisions))
    for i, table in enumerate(decisions.get("tables", []), start=1):
        fname = re.sub(r"[\\/:*?\"<>|]+", "_", table["name"])
        write(os.path.join(defin, "tables", f"{fname}.tmdl"),
              build_table_file(table, ir, decisions, i))
    for j, fp in enumerate(decisions.get("fieldParameters", []), start=1):
        fname = re.sub(r"[\\/:*?\"<>|]+", "_", fp["name"])
        write(os.path.join(defin, "tables", f"{fname}.tmdl"),
              FP.table_tmdl(fp, 0x7000 + j))
    # Calculated tables from decisions (avoids circular-reference issues with
    # calculated columns on dim tables that reference other tables via relationships)
    for k, ct in enumerate(decisions.get("calculatedTables", []), start=1):
        fname = re.sub(r"[\\/:*?\"<>|]+", "_", ct["name"])
        write(os.path.join(defin, "tables", f"{fname}.tmdl"),
              _build_calculated_table_tmdl(ct, 0xA000 + k))
    write(os.path.join(root, "definition.pbism"), json.dumps(PBISM, indent=2))
    write(os.path.join(root, "diagramLayout.json"), json.dumps({"version": "1.1.0", "diagrams": []}))
    write(os.path.join(root, ".platform"), platform_file("SemanticModel", model_name, model_name + ".sm"))
    write(os.path.join(os.path.dirname(root), f"{model_name}.pbip"), pbip_root(model_name))
    return root


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Emit TMDL semantic model from IR + decisions.")
    parser.add_argument("analysis", help="path to analysis.json")
    parser.add_argument("--decisions", required=True, help="path to decisions.json")
    args = parser.parse_args(argv)
    for p in (args.analysis, args.decisions):
        if not os.path.isfile(p):
            print(f"ERROR: file not found: {p}", file=sys.stderr); return 2
    ir, decisions = load_json(args.analysis), load_json(args.decisions)
    root = emit(ir, decisions, args.analysis)
    print(f"Wrote semantic model: {root}\n  tables: {len(decisions.get('tables', []))}  "
          f"measures: {len(decisions.get('measures', []))}  "
          f"relationships: {len(decisions.get('relationships', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
