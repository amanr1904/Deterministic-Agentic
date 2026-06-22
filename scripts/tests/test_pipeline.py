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
import twb_fields as F  # noqa: E402
import twb_visuals as V  # noqa: E402
import topn as TN  # noqa: E402
import date_levels as DL  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

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


class TestPassthroughResolution(unittest.TestCase):
    """A passthrough date calc (DATETIME([date_added])) must resolve to its base
    physical column so date-part binding works (Gap 1)."""

    def test_resolve_ref_maps_passthrough(self):
        passthrough = {"Year of Add": "date_added"}
        ref = "[federated.x].[none:Year of Add:nk]"
        self.assertEqual(F.resolve_ref(ref, {}, passthrough), "date_added")

    def test_resolve_ref_plain_passthrough(self):
        passthrough = {"AddedDate": "date_added"}
        self.assertEqual(F.resolve_ref("[AddedDate]", {}, passthrough), "date_added")

    def test_resolve_ref_without_map_unchanged(self):
        self.assertEqual(F.resolve_ref("[date_added]", {}, None), "date_added")

    def test_date_level_uses_passthrough(self):
        rows = ["[federated.1].[yr:AddedDate:ok]"]
        passthrough = {"AddedDate": "date_added"}
        self.assertEqual(F.date_level(rows, [], "date_added", passthrough), "year")

    def test_build_passthrough_map_skips_real_derivations(self):
        import twb_datasources as DS
        xml = """<workbook><datasource><column name='[Yr]' caption='Yr'>
        <calculation formula='YEAR([date_added])'/></column>
        <column name='[Cast]' caption='Cast'>
        <calculation formula='DATETIME([date_added])'/></column></datasource></workbook>"""
        root = ET.fromstring(xml)
        pmap = DS.build_passthrough_map(root)
        self.assertNotIn("Yr", pmap)        # YEAR(...) is a real derivation
        self.assertEqual(pmap.get("Cast"), "date_added")  # DATETIME(...) is a cast


class TestTopNExtraction(unittest.TestCase):
    """A Tableau Top-N groupfilter (count=N end=top) must be parsed into ws.topN
    and reproduced via a rank measure + filter (Gap 2)."""

    TWB = """<worksheet name='Top 10 Genre'><table><view>
      <filter class='categorical' column='[federated.1].[none:listed_in:nk]'>
        <groupfilter function='end' count='10' end='top'>
          <groupfilter function='order' direction='DESC'
                       expression='COUNTD([show_id])'>
            <groupfilter function='level-members'
                         level='[federated.1].[none:listed_in:nk]'/>
          </groupfilter>
        </groupfilter>
      </filter>
    </view></table></worksheet>"""

    def test_extract_topn(self):
        ws = ET.fromstring(self.TWB)
        tn = V._extract_topn(ws, {}, {})
        self.assertIsNotNone(tn)
        self.assertEqual(tn["field"], "listed_in")
        self.assertEqual(tn["count"], 10)
        self.assertEqual(tn["end"], "top")
        self.assertEqual(tn["direction"], "DESC")
        self.assertEqual(tn["byExpr"], "COUNTD([show_id])")

    def test_no_topn_returns_none(self):
        ws = ET.fromstring("<worksheet name='X'><table><view/></table></worksheet>")
        self.assertIsNone(V._extract_topn(ws, {}, {}))


class TestTopNHelper(unittest.TestCase):
    def test_measure_name(self):
        self.assertEqual(TN.measure_name("listed_in"), "listed_in (Rank)")

    def test_by_dax_translates_countd(self):
        self.assertEqual(TN.by_dax("COUNTD([show_id])", "Netflix"),
                         "DISTINCTCOUNT ( 'Netflix'[show_id] )")

    def test_by_dax_fallback_countrows(self):
        self.assertEqual(TN.by_dax("{FIXED [a]: SUM([b])}", "Netflix"),
                         "COUNTROWS('Netflix')")

    def test_rank_dax_desc_for_top(self):
        dax = TN.rank_dax("Netflix", "listed_in", "COUNTD([show_id])", ascending=False)
        self.assertEqual(
            dax,
            "RANKX(ALLSELECTED('Netflix'[listed_in]), "
            "DISTINCTCOUNT ( 'Netflix'[show_id] ), , DESC)")

    def test_spec_returns_name_dax_count(self):
        name, dax, count = TN.spec(
            {"field": "listed_in", "count": 10, "end": "top",
             "byExpr": "COUNTD([show_id])"}, "Netflix")
        self.assertEqual(name, "listed_in (Rank)")
        self.assertEqual(count, 10)
        self.assertIn("DESC", dax)


class TestDatePartBlankSafe(unittest.TestCase):
    def test_year_is_blank_guarded(self):
        dax = DL.part_dax("date_added", "Netflix", "year")
        self.assertEqual(
            dax, "IF(ISBLANK('Netflix'[date_added]), BLANK(), "
                 "YEAR('Netflix'[date_added]))")

    def test_is_part_column(self):
        self.assertTrue(DL.is_part_column("date_added (Year)"))
        self.assertTrue(DL.is_part_column("Census Date (Month)"))
        self.assertFalse(DL.is_part_column("date_added"))
        self.assertFalse(DL.is_part_column(None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
