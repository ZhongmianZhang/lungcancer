"""Offline tests for errors that could otherwise overstate literature readiness."""

import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest import mock
import urllib.error


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "literature.py"
SPEC = importlib.util.spec_from_file_location("literature", MODULE_PATH)
literature = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(literature)


class LiteratureTests(unittest.TestCase):
    def test_access_denial_is_not_retried_or_hidden(self):
        for error in (urllib.error.HTTPError("https://example.org", 403, "Forbidden", {}, None),
                      urllib.error.URLError("Tunnel connection failed: 403 Forbidden")):
            with self.subTest(error=error), mock.patch.object(literature.urllib.request, "urlopen", side_effect=error) as fetch:
                with self.assertRaises(literature.LiteratureError) as caught:
                    literature.EuropePMCClient(retries=3).request("EGFR")
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(caught.exception.diagnostic["http_status"], 403)

    def test_similar_title_or_wrong_year_cannot_be_verified(self):
        seed = {"title": "EGFR resistance in lung cancer", "year": 2020, "doi": "10.1234/test"}
        record = {"title": "EGFR resistance in breast cancer", "pubYear": "2020", "doi": "10.1234/test"}
        self.assertIsNone(literature.matching_record(seed, [record]))
        record["title"], record["pubYear"] = seed["title"], "2021"
        self.assertIsNone(literature.matching_record(seed, [record]))
        record["pubYear"], record["doi"] = "2020", "10.1234/other"
        self.assertIsNone(literature.matching_record(seed, [record]))

    def test_exact_normalized_title_and_year_match_does_not_claim_fulltext(self):
        seed = {"title": "EGFR: resistance in lung cancer.", "year": 2020,
                "evidence_scope": "other_cancer", "finding_zh": "人工解释"}
        record = {"id": "123", "source": "MED", "title": "EGFR resistance in lung cancer",
                  "pubYear": "2020", "journalInfo": {"journal": {"title": "Cancer Research"}}}
        client = mock.Mock()
        client.request.return_value = {"resultList": {"result": [record]}}
        result = literature.verify_references(client, [seed])
        checked = result["references"][0]
        self.assertEqual(checked["verification"], "metadata_verified")
        self.assertEqual(checked["evidence_scope"], "other_cancer")
        self.assertEqual(checked["finding_zh"], "人工解释")
        self.assertFalse(checked["verification_details"]["full_text_reviewed"])
        self.assertNotIn("verification", seed)

    def test_network_block_stops_duplicate_verification_requests(self):
        client = mock.Mock()
        client.request.side_effect = literature.LiteratureError("blocked", diagnostic={"kind": "access_denied"})
        result = literature.verify_references(client, [
            {"title": "Paper one", "year": 2020}, {"title": "Paper two", "year": 2021}])
        self.assertEqual(client.request.call_count, 1)
        self.assertEqual(result["metadata_verification"]["status"], "blocked")
        self.assertEqual(result["references"][1]["verification"], "unverified_network_blocked")

    def test_dates_are_exact_and_invalid_window_rejected(self):
        query = literature.build_query("2011-10-21", "2026-10-21")
        self.assertIn("FIRST_PDATE:[2011-10-21 TO 2026-10-21]", query)
        with self.assertRaises(ValueError):
            literature.build_query("2026-10-21", "2011-10-21")

    def test_search_paginates_and_reports_truncation(self):
        client = mock.Mock()
        client.request.side_effect = [
            {"hitCount": 3, "nextCursorMark": "next", "resultList": {"result": [
                {"id": "1", "source": "MED", "title": "One", "pubYear": "2020"}]}},
            {"hitCount": 3, "nextCursorMark": "last", "resultList": {"result": [
                {"id": "2", "source": "MED", "title": "Two", "pubYear": "2021"}]}}]
        result = literature.search_literature(client, start="2011-10-21", end="2026-10-21", max_results=2)
        self.assertEqual(client.request.call_args_list[1].kwargs["cursor"], "next")
        self.assertEqual(len(result["references"]), 2)
        self.assertTrue(result["truncated"])
        self.assertEqual(result["references"][0]["evidence_scope"], "unscreened")

    def test_missing_ranking_is_unknown_not_failed_or_invented(self):
        refs = literature.annotate_journal_ranks([{"journal": "Nature"}], [])
        self.assertIsNone(refs[0]["journal_rank"])
        self.assertIsNone(refs[0]["rank_eligible"])
        self.assertEqual(refs[0]["rank_status"], "unranked")

    def test_ranking_respects_year_and_category_and_remains_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "ranks.csv"
            path.write_text("journal,issn,category,rank,jif_year,source\n"
                            "Example Journal,1234-567X,Oncology,80,2024,User export\n"
                            "Example Journal,1234-567X,Oncology,70,2025,User export\n"
                            "Example Journal,1234-567X,Immunology,10,2025,User export\n", encoding="utf-8")
            ranks = literature.load_journal_ranks(path)
        checked = literature.annotate_journal_ranks([{"journal": "EXAMPLE journal"}], ranks,
                    jif_year=2024, categories=["Oncology"])[0]
        self.assertEqual(checked["journal_rank"], 80)
        self.assertFalse(checked["rank_eligible"])
        self.assertEqual(checked["rank_status"], "user_supplied_unverified")
        with self.assertRaises(ValueError):
            literature.annotate_journal_ranks([], [], max_rank=0)

    def test_cli_writes_diagnostic_json_and_nonzero_exit_on_403(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "failure.json"
            with mock.patch.object(literature.urllib.request, "urlopen", side_effect=
                    urllib.error.URLError("Tunnel connection failed: 403 Forbidden")), mock.patch("sys.stdout", new=io.StringIO()):
                code = literature.main(["search", "--output", str(path), "--cache-dir", tmp])
            result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(code, 3)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["diagnostics"][0]["http_status"], 403)

    def test_latest_rank_year_is_common_across_all_journals(self):
        ranks = [
            {"journal": "Journal A", "issns": [], "category": "Oncology", "rank": 3,
             "jif_year": 2024, "source": "Supplied export"},
            {"journal": "Journal B", "issns": [], "category": "Oncology", "rank": 4,
             "jif_year": 2025, "source": "Supplied export"}]
        result = literature.apply_journal_ranks([{"journal": "Journal A"}, {"journal": "Journal B"}], ranks)
        self.assertEqual([x["rank_year"] for x in result], [2025, 2025])
        self.assertIsNone(result[0]["journal_rank"])
        self.assertEqual(result[1]["journal_rank"], 4)


if __name__ == "__main__":
    unittest.main()
