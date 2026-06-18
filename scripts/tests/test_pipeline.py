"""Regression tests for the deterministic migration engine.

Stdlib-only (unittest) so they run with `python -m unittest` and no extra deps.
Covers the pure logic-heavy functions plus golden-file regression of the
committed Midnight Census artifacts (the design doc's acceptance gate: the
deterministic path must reproduce the committed Output/ artifacts).

Run:
    python -m unittest discover -s scripts/tests -v
    python scripts/tests/test_pipeline.py
"""
from __future__ import annotations

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)
for sub in ("twb", "dax", "emit"):
    sys.path.insert(0, os.path.join(SCRIPTS, sub))

import twb_xml as X  # noqa: E402
import map_dax as M  # noqa: E402
import parse_twb as P  # noqa: E402

MIDNIGHT_TWB = os.path.join(ROOT, "Data", "Midnight Census", "Midnight Census Dashboard.twb")
MIDNIGHT_OUT = os.path.join(ROOT, "Output", "MidnightCensusDashboard")


def _load(path: str) -> dict:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


class TestPascalCase(unittest.TestCase):
    def test_spaces_and_punctuation(self):
        self.assertEqual(X.to_pascal_case("Midnight Census Dashboard"), "MidnightCensusDashboard")
        self.assertEqual(X.to_pascal_case("Sales & Customer Dashboards"), "SalesCustomerDashboards")
        self.assertEqual(X.to_pascal_case("(Active) 2021 Q3 Dealer"), "Active2021Q3Dealer")

    def test_empty_falls_back(self):
        self.assertEqual(X.to_pascal_case(""), "Model")
        self.assertEqual(X.to_pascal_case("___"), "Model")


class TestDecodeEntities(unittest.TestCase):
    def test_newline_sequences(self):
        self.assertEqual(X.decode_entities("a&#13;&#10;b"), "a\nb")
        self.assertEqual(X.decode_entities("a&#10;b"), "a\nb")

    def test_residual_xml_entities(self):
        self.assertEqual(X.decode_entities("&lt;x&gt; &amp; &quot;y&quot;"), '<x> & "y"')

    def test_none_is_empty(self):
        self.assertEqual(X.decode_entities(None), "")


class TestDaxTranslate(unittest.TestCase):
    def test_single_aggregations(self):
        self.assertEqual(M.translate("SUM([Sales])", "T"), ("SUM ( T[Sales] )", "#,0"))
        self.assertEqual(M.translate("AVG([Sales])", "T"), ("AVERAGE ( T[Sales] )", "#,0.00"))
        dax, fmt = M.translate("COUNTD([Id])", "T")
        self.assertEqual(dax, "DISTINCTCOUNT ( T[Id] )")
        self.assertEqual(fmt, "#,0")

    def test_population_stats(self):
        # longer keywords must win over their shorter prefixes
        self.assertEqual(M.translate("STDEVP([Sales])", "T"), ("STDEV.P ( T[Sales] )", None))
        self.assertEqual(M.translate("VARP([Sales])", "T"), ("VAR.P ( T[Sales] )", None))
        self.assertEqual(M.translate("STDEV([Sales])", "T"), ("STDEV.S ( T[Sales] )", None))
        self.assertEqual(M.translate("VAR([Sales])", "T"), ("VAR.S ( T[Sales] )", None))

    def test_attr_selectedvalue(self):
        cols = {"Region"}
        self.assertEqual(
            M.translate("ATTR([Region])", "T", cols),
            ("SELECTEDVALUE ( T[Region] )", None),
        )
        # references a non-base-column token -> bail to the agent
        self.assertIsNone(M.translate("ATTR([Calc_1])", "T", cols))

    def test_ratio(self):
        dax, fmt = M.translate("SUM([a]) / SUM([b])", "T")
        self.assertEqual(dax, "DIVIDE ( SUM ( T[a] ), SUM ( T[b] ) )")
        self.assertEqual(fmt, "#,0.00")

    def test_passthrough(self):
        self.assertEqual(M.translate("[Region]", "T"), ("T[Region]", None))

    def test_complex_returns_none(self):
        for f in ("{FIXED [a] : SUM([b])}", "WINDOW_SUM(SUM([x]))",
                  "RUNNING_SUM(SUM([x]))", "INDEX()", "DATEADD('day', -1, [d])",
                  "CASE [p] WHEN 'a' THEN 1 END"):
            self.assertIsNone(M.translate(f, "T"), msg=f)

    def test_ratio_general_gated(self):
        cols = {"Order ID", "Sales"}
        # any-aggregation ratio fires only when both fields are base columns
        dax, fmt = M.translate("COUNTD([Order ID]) / SUM([Sales])", "T", cols)
        self.assertEqual(dax, "DIVIDE ( DISTINCTCOUNT ( T[Order ID] ), SUM ( T[Sales] ) )")
        self.assertEqual(fmt, "#,0.00")
        # no column set -> not safe to translate
        self.assertIsNone(M.translate("COUNTD([Order ID]) / SUM([Sales])", "T"))
        # referenced field is not a base column (e.g. a calc-field token) -> bail
        self.assertIsNone(
            M.translate("COUNTD([CY (copy)_1]) / SUM([Sales])", "T", cols))

    def test_agg_arithmetic_gated(self):
        cols = {"Sales", "Profit"}
        self.assertEqual(
            M.translate("SUM([Sales]) - SUM([Profit])", "T", cols),
            ("SUM ( T[Sales] ) - SUM ( T[Profit] )", None),
        )
        # %-difference shape
        self.assertEqual(
            M.translate("(SUM([Sales]) - SUM([Profit])) / SUM([Profit])", "T", cols),
            ("(SUM ( T[Sales] ) - SUM ( T[Profit] )) / SUM ( T[Profit] )", "#,0.00"),
        )
        # constant scaling of a single aggregation
        self.assertEqual(
            M.translate("SUM([Sales]) * 100", "T", cols),
            ("SUM ( T[Sales] ) * 100", None),
        )
        # any non-base-column reference -> bail to the agent
        self.assertIsNone(
            M.translate("SUM([CY (copy)_1]) - SUM([Profit])", "T", cols))
        # stray logic / identifier in the residual -> not pure arithmetic -> bail
        self.assertIsNone(
            M.translate("SUM([Sales]) - [Profit]", "T", cols))


class TestDaxExpression(unittest.TestCase):
    COLS = {"Sales", "Profit", "Region", "Name", "Order Date", "Qty"}

    def t(self, formula):
        return M.translate(formula, "T", self.COLS)

    def test_if_simple(self):
        self.assertEqual(
            self.t("IF SUM([Sales]) > 0 THEN SUM([Profit]) ELSE 0 END"),
            ("IF ( ( SUM ( T[Sales] ) > 0 ), SUM ( T[Profit] ), 0 )", None),
        )

    def test_if_no_else(self):
        self.assertEqual(
            self.t("IF SUM([Qty]) > 0 THEN SUM([Sales]) END"),
            ("IF ( ( SUM ( T[Qty] ) > 0 ), SUM ( T[Sales] ) )", None),
        )

    def test_if_elseif_chain(self):
        dax, _ = self.t(
            "IF SUM([Qty]) > 10 THEN 'A' "
            "ELSEIF SUM([Qty]) > 5 THEN 'B' ELSE 'C' END")
        self.assertEqual(
            dax,
            'IF ( ( SUM ( T[Qty] ) > 10 ), "A", '
            'IF ( ( SUM ( T[Qty] ) > 5 ), "B", "C" ) )')

    def test_iif(self):
        dax, _ = self.t("IIF(SUM([Qty]) > 0, SUM([Sales]), 0)")
        self.assertEqual(dax, "IF ( ( SUM ( T[Qty] ) > 0 ), SUM ( T[Sales] ), 0 )")

    def test_case_to_switch(self):
        dax, _ = self.t(
            "CASE ATTR([Region]) WHEN 'N' THEN 1 WHEN 'S' THEN 2 ELSE 0 END")
        self.assertEqual(
            dax, 'SWITCH ( SELECTEDVALUE ( T[Region] ), "N", 1, "S", 2, 0 )')

    def test_logical_and_comparison(self):
        dax, _ = self.t(
            "IF SUM([Qty]) > 0 AND SUM([Sales]) > 100 THEN 1 ELSE 0 END")
        self.assertEqual(
            dax,
            "IF ( ( ( SUM ( T[Qty] ) > 0 ) && ( SUM ( T[Sales] ) > 100 ) ), 1, 0 )")

    def test_string_functions(self):
        self.assertEqual(
            self.t("LEFT(ATTR([Name]), 3)"),
            ("LEFT ( SELECTEDVALUE ( T[Name] ), 3 )", None))
        self.assertEqual(
            self.t("UPPER(ATTR([Name]))"),
            ("UPPER ( SELECTEDVALUE ( T[Name] ) )", None))

    def test_date_functions(self):
        self.assertEqual(
            self.t("YEAR(MAX([Order Date]))"),
            ("YEAR ( MAX ( T[Order Date] ) )", None))
        dax, _ = self.t("DATEDIFF('day', MIN([Order Date]), MAX([Order Date]))")
        self.assertEqual(
            dax, "DATEDIFF ( MIN ( T[Order Date] ), MAX ( T[Order Date] ), DAY )")

    def test_conversion_and_null(self):
        self.assertEqual(self.t("INT(SUM([Sales]))"), ("INT ( SUM ( T[Sales] ) )", None))
        self.assertEqual(
            self.t("ZN(SUM([Profit]))"), ("COALESCE ( SUM ( T[Profit] ), 0 )", None))
        self.assertEqual(
            self.t("ISNULL(SUM([Profit]))"), ("ISBLANK ( SUM ( T[Profit] ) )", None))

    def test_modulo(self):
        self.assertEqual(self.t("SUM([Qty]) % 2"), ("MOD ( SUM ( T[Qty] ), 2 )", None))

    def test_gating_parameter_ref_bails(self):
        # parameter-qualified refs are never base columns -> defer to agent
        self.assertIsNone(self.t(
            "CASE [Parameters].[P] WHEN 'a' THEN SUM([Sales]) END"))

    def test_gating_non_base_column_bails(self):
        self.assertIsNone(self.t("IF SUM([Calc_1]) > 0 THEN SUM([Sales]) END"))

    def test_gating_bare_column_bails(self):
        # a column outside an aggregation is invalid in a measure -> bail
        self.assertIsNone(self.t("IF [Qty] > 0 THEN [Sales] END"))
        self.assertIsNone(self.t("UPPER([Name])"))

    def test_gating_pure_constant_bails(self):
        # no base-column reference -> not translated (protects literal calcs)
        self.assertIsNone(M.translate('"(All)"', "T", self.COLS))
        self.assertIsNone(M.translate("TODAY() - 1", "T", self.COLS))

    def test_gating_string_concat_bails(self):
        # Tableau '+' on strings is ambiguous concat -> defer to agent
        self.assertIsNone(self.t("ATTR([Name]) + 'x'"))

    def test_gating_unknown_function_bails(self):
        self.assertIsNone(self.t("SPLIT(ATTR([Name]), ',', 1)"))

    def test_gating_no_columns_arg_bails(self):
        # without a column set the expression handler cannot run safely
        self.assertIsNone(M.translate("IF SUM([Qty]) > 0 THEN 1 ELSE 0 END", "T"))


class TestBuildMeasures(unittest.TestCase):
    def test_split_translated_vs_pending(self):
        ir = {
            "workbook": {"pascalName": "T"},
            "dataSources": [{"active": True}],
            "calculatedFields": [
                {"caption": "Total", "formula": "SUM([Amt])",
                 "complexity": "trivial", "suggestedDaxKind": "measure"},
                {"caption": "LOD", "formula": "{FIXED [k]: SUM([Amt])}",
                 "complexity": "complex", "suggestedDaxKind": "measure"},
            ],
        }
        out = M.build_measures(ir, "T")
        self.assertEqual(len(out["measures"]), 1)
        self.assertEqual(out["measures"][0]["name"], "Total")
        self.assertEqual(out["measures"][0]["source"], "template")
        self.assertEqual(len(out["pending"]), 1)
        self.assertEqual(out["pending"][0]["caption"], "LOD")


@unittest.skipUnless(os.path.isfile(MIDNIGHT_TWB), "Midnight Census workbook not present")
class TestGoldenMidnightCensus(unittest.TestCase):
    """The deterministic path must reproduce the committed Output/ artifacts."""

    def test_parse_matches_committed_analysis(self):
        produced = P.build_ir(MIDNIGHT_TWB)
        committed = _load(os.path.join(MIDNIGHT_OUT, "analysis.json"))
        # sourcePath is environment-specific (absolute vs committed relative); the
        # rest of the IR must match byte-for-byte.
        produced["workbook"]["sourcePath"] = committed["workbook"]["sourcePath"]
        self.maxDiff = None
        self.assertEqual(produced, committed)

    def test_map_dax_matches_committed_partial(self):
        ir = _load(os.path.join(MIDNIGHT_OUT, "analysis.json"))
        produced = M.build_measures(ir, M._default_table(ir))
        committed = _load(os.path.join(MIDNIGHT_OUT, "dax-partial.json"))
        self.assertEqual(produced, committed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
