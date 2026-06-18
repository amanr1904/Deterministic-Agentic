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
