"""Check provenance, eligibility, and safe standalone report generation."""

import copy
import datetime as dt
import html.parser
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_report import (build_dataset, date_eligibility, merge_modules, safe_json,
                          validate_module, write_outputs, apply_verified_metadata)


class ReportTests(unittest.TestCase):
    def test_date_boundaries_do_not_invent_publication_day(self):
        start, end = dt.date(2011, 10, 21), dt.date(2026, 10, 21)
        self.assertEqual(date_eligibility({"year": 2011}, start, end)[0], None)
        self.assertFalse(date_eligibility({"year": 2011, "publication_date": "2011-03-23"}, start, end)[0])
        self.assertTrue(date_eligibility({"year": 2011, "publication_date": "2011-10-21"}, start, end)[0])
        self.assertIsNone(date_eligibility({"year": 2026}, start, end)[0])
        self.assertTrue(date_eligibility({"year": 2020}, start, end)[0])

    def test_dangling_citation_fails_instead_of_silent_omission(self):
        module = json.loads((ROOT / "data/stromal.json").read_text())
        module["mechanisms"][0]["references"].append("DOES_NOT_EXIST")
        with self.assertRaisesRegex(ValueError, "unresolved references"):
            merge_modules([module])

    def test_same_paper_is_deduplicated_and_citations_remapped(self):
        module = json.loads((ROOT / "data/stromal.json").read_text())
        ref = copy.deepcopy(module["references"][0])
        ref["id"] = "duplicate"
        duplicate = {"references": [ref], "mechanisms": []}
        refs, mechanisms, notes = merge_modules([module, duplicate])
        self.assertEqual(len(refs), len(module["references"]))
        self.assertIn("duplicate", refs[0]["source_ids"])
        self.assertTrue(mechanisms)

    def test_strict_ranking_refuses_missing_official_input(self):
        with self.assertRaisesRegex(ValueError, "requires an explicit ranking CSV"):
            build_dataset(ROOT / "data", start="2011-10-21", end="2026-10-21", strict_ranking=True)

    def test_metadata_verification_does_not_become_fulltext_review(self):
        refs = [{"id": "A", "title": "Paper A", "year": 2020}]
        document = {"references": [{"id": "A", "title": "Paper A", "year": 2020,
                    "verification": "metadata_verified", "full_text_reviewed": True}]}
        apply_verified_metadata(refs, document)
        self.assertEqual(refs[0]["verification"], "metadata_verified")
        self.assertFalse(refs[0]["full_text_reviewed"])
        document["references"][0]["verified_metadata"] = {"title": "Paper A", "year": 2020, "journal": "Canonical Journal"}
        apply_verified_metadata(refs, document)
        self.assertEqual(refs[0]["journal"], "Canonical Journal")
        self.assertFalse(refs[0]["full_text_reviewed"])
        document["references"][0]["title"] = "Wrong paper"
        with self.assertRaisesRegex(ValueError, "identity"):
            apply_verified_metadata(refs, document)

    def test_graph_rejects_nonexistent_node(self):
        module = json.loads((ROOT / "data/stromal.json").read_text())
        module["mechanisms"][0]["edges"][0]["target"] = "nonexistent"
        with self.assertRaisesRegex(ValueError, "unknown node"):
            validate_module(module, "test")

    def test_standalone_html_has_no_external_assets_and_preserves_data(self):
        data = build_dataset(ROOT / "data", start="2011-10-21", end="2026-10-21")
        data["mechanisms"][0]["summary"] = '</script><script>alert("x")</script>'
        self.assertNotIn("</script>", safe_json(data))
        with tempfile.TemporaryDirectory() as tmp:
            result = write_outputs(data, pathlib.Path(tmp), ROOT / "templates")
            page = pathlib.Path(result["html"]).read_text()
            class AuditHTML(html.parser.HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.assets = []
                    self.data = ""
                    self.in_data = False
                def handle_starttag(self, tag, attrs):
                    attrs = dict(attrs)
                    if tag in {"script", "img", "iframe", "link"} and any(attrs.get(k) for k in ("src", "href")):
                        self.assets.append((tag, attrs))
                    self.in_data = tag == "script" and attrs.get("id") == "report-data" or self.in_data
                def handle_data(self, chunk):
                    if self.in_data: self.data += chunk
                def handle_endtag(self, tag):
                    if tag == "script": self.in_data = False
            parsed = AuditHTML()
            parsed.feed(page)
            self.assertEqual(parsed.assets, [])
            self.assertEqual(json.loads(parsed.data)["mechanisms"][0]["summary"], data["mechanisms"][0]["summary"])
            self.assertIn('id="static-report"', page)
            self.assertIn("IF前79名", page)
            self.assertEqual(data["audit"]["counts"]["metadata_verified"], 0)
            self.assertEqual(data["audit"]["counts"]["rank_eligible"], 0)


if __name__ == "__main__":
    unittest.main()
