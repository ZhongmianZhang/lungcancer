"""Regression tests for interpretations that can incorrectly upgrade evidence."""

import copy
import csv
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from alk_resistance.__main__ import main
from alk_resistance.adapters import allele_number, import_vcf
from alk_resistance.engine import assess, knowledge
from alk_resistance.input import InputError


PROJECT = Path(__file__).resolve().parents[1] / "alk_resistance"
EXAMPLES = PROJECT / "examples"


def load_case():
    return json.loads((EXAMPLES / "synthetic_case.json").read_text(encoding="utf-8"))


def finding(identifier, feature, *, gene="ALK", kind="variant", assay="WGS", attributes=None):
    return {
        "id": identifier, "assay_id": assay, "kind": kind, "gene": gene,
        "feature": feature, "status": "detected", "qc": "pass", "attributes": attributes or {},
    }


def cis_pair(left="p.Gly1202Arg", right="p.Leu1196Met"):
    phase = {"block": "molecule", "haplotype": "1", "method": "read_backed"}
    return [finding("a", left, attributes={"phase": dict(phase)}),
            finding("b", right, attributes={"phase": dict(phase)})]


def option(report, key):
    return next((item for item in report["clinical_options"] if item["id"] == key), None)


class EvidenceRulesTest(unittest.TestCase):
    def setUp(self):
        self.case = load_case()
        self.baseline, self.tissue, self.plasma = self.case["specimens"]

    def mechanisms(self):
        return {row["id"]: row for row in assess(self.case)["specimens"][0]["mechanisms"]}

    def test_reference_cis_pair_and_unknown_same_report(self):
        self.tissue["findings"] = cis_pair()
        self.assertEqual(self.mechanisms()["alk_g1202r_l1196m"]["level"], "supported")
        self.tissue["findings"][1]["attributes"].pop("phase")
        self.assertEqual(set(self.mechanisms()), {"alk_unresolved"})

    def test_trans_or_statistical_phase_is_insufficient(self):
        self.tissue["findings"] = cis_pair()
        self.tissue["findings"][1]["attributes"]["phase"]["haplotype"] = "2"
        self.assertEqual(set(self.mechanisms()), {"alk_unresolved"})
        self.tissue["findings"] = cis_pair()
        for row in self.tissue["findings"]:
            row["attributes"]["phase"]["method"] = "statistical"
        self.assertEqual(set(self.mechanisms()), {"alk_unresolved"})

    def test_phase_never_crosses_assays_or_lesions(self):
        self.tissue["findings"] = cis_pair()
        second_assay = {**self.tissue["assays"][0], "id": "secondary_wgs"}
        self.tissue["assays"].append(second_assay)
        self.tissue["findings"][1]["assay_id"] = "secondary_wgs"
        self.assertEqual(set(self.mechanisms()), {"alk_unresolved"})
        second_tissue = copy.deepcopy(self.tissue)
        second_tissue["id"] = "T2"
        second_tissue["site"] = "other_liver_lesion"
        self.tissue["findings"] = self.tissue["findings"][:1]
        second_tissue["findings"] = second_tissue["findings"][1:]
        self.case["specimens"].append(second_tissue)
        self.assertEqual(assess(self.case)["assessment"], "unresolved")

    def test_nonreference_HGVS_never_matches_known_pair(self):
        self.tissue["findings"] = cis_pair(left="NM_000001.1:p.Gly1202Arg")
        self.assertEqual(set(self.mechanisms()), {"alk_unresolved"})
        self.tissue["findings"][0]["attributes"]["transcript"] = "NM_004304.5"
        with self.assertRaises(InputError):
            self.mechanisms()

    def test_exact_case_report_option_excludes_a_third_alk_variant(self):
        self.tissue["findings"] = cis_pair("C1156Y", "p.Leu1198Phe")
        self.assertIsNotNone(option(assess(self.case), "crizotinib_case"))
        self.tissue["findings"].append(finding("extra", "G1202R"))
        self.assertIsNone(option(assess(self.case), "crizotinib_case"))

    def test_no_progression_sample_no_mechanism(self):
        self.case["specimens"] = [self.baseline]
        report = assess(self.case)
        self.assertEqual(report["assessment"], "unresolved")
        self.assertEqual(report["assay_gaps"][0]["status"], "no_progression_specimen")

    def test_focal_met_needs_comparable_explicit_baseline(self):
        met = finding("met1", "amplification", gene="MET", kind="copy_number", attributes={
            "focality": "focal", "validated_call": True, "criteria": "signed out for platform and locus",
        })
        self.tissue["findings"] = [met]
        report = assess(self.case)
        self.assertEqual(report["specimens"][0]["mechanisms"][0]["level"], "supported")
        self.assertIsNotNone(option(report, "alk_met_combination"))
        self.baseline["site"] = "different_lesion"
        self.assertEqual(self.mechanisms()["met_focal_amplification"]["level"], "candidate")
        self.assertIsNone(option(assess(self.case), "alk_met_combination"))
        self.baseline["site"] = self.tissue["site"]
        self.baseline["findings"][0]["status"] = "detected"
        self.assertEqual(self.mechanisms()["met_focal_amplification"]["evidence"][0]["acquisition"]["state"],
                         "detected_at_baseline")

    def test_broad_gain_is_not_focal_amplification(self):
        self.tissue["findings"] = [finding("met1", "amplification", gene="MET", kind="copy_number",
                                         attributes={"focality": "broad", "value": 12})]
        report = assess(self.case)
        self.assertEqual(set(self.mechanisms()), {"met_gain_unresolved"})
        self.assertIsNone(option(report, "alk_met_combination"))

    def test_st7_met_requires_concordant_rna_breakpoint(self):
        self.tissue["findings"] = [
            finding("cnv", "amplification", gene="MET", kind="copy_number",
                    attributes={"focality": "focal", "validated_call": True, "criteria": "lab review"}),
            finding("dna", "ST7::MET", gene="MET", kind="fusion", attributes={"event_link": "event1"}),
            finding("rna", "ST7::MET", gene="MET", kind="fusion", assay="RNA",
                    attributes={"event_link": "event1", "exon_junction": "ST7:1-MET:2"}),
        ]
        self.assertIn("st7_met", self.mechanisms())
        self.tissue["findings"][2]["attributes"]["event_link"] = "other_event"
        self.assertIn("st7_met_unresolved", self.mechanisms())

    def test_negative_liquid_and_locus_only_remain_unresolved(self):
        self.tissue["assays"][0]["coverage"][0]["feature"] = "G1202R"
        self.plasma["findings"] = [finding("p1", "G1202R", assay="ctDNA")]
        self.plasma["findings"][0]["status"] = "not_detected"
        report = assess(self.case)
        self.assertEqual(report["unresolved_specimens"], ["T1", "P1"])
        self.assertTrue(any(row["status"] == "locus_only" and row.get("adequate_features") == ["G1202R"]
                            for row in report["assay_gaps"]))
        self.assertTrue(any(row["status"] == "liquid_biopsy_sampling_limit" for row in report["assay_gaps"]))

    def test_methylation_not_implied_by_wgs(self):
        self.tissue["findings"] = [finding("epi", "promoter_hypomethylation", gene="CDA",
                                        kind="methylation")]
        with self.assertRaises(InputError):
            assess(self.case)
        self.tissue["findings"][0]["assay_id"] = "METH"
        report = assess(self.case)
        self.assertEqual(report["assessment"], "unresolved")
        self.assertEqual(self.mechanisms()["cda_epigenomics"]["level"], "candidate")
        self.assertIsNone(option(report, "small_cell_regimen"))

    def test_transformation_requires_tissue_pathology(self):
        call_metadata = {"classification": "pathogenic"}
        self.tissue["findings"] = [
            finding("var1", "R248W", gene="TP53", attributes=call_metadata),
            finding("var2", "R255*", gene="RB1", attributes=call_metadata),
        ]
        report = assess(self.case)
        self.assertIsNone(option(report, "small_cell_regimen"))
        self.assertEqual(self.mechanisms()["lineage_review"]["level"], "candidate")
        self.tissue["assays"].append({"id": "PATH", "modality": "pathology", "qc": "pass"})
        self.case["clinical"]["prior_advanced_platinum"] = True
        self.tissue["findings"].append(finding("smallcell", "SCLC", gene="HISTOLOGY", kind="histology",
            assay="PATH", attributes={"pathologist_confirmed": True, "morphology_and_ihc": True,
                                     "baseline_histology_compared": True}))
        report = assess(self.case)
        self.assertEqual(option(report, "small_cell_regimen")["sample_ids"], ["T1"])
        self.assertEqual(option(report, "neladalkib_us")["status"], "histology_review_required")

    def test_label_counts_active_lorlatinib_and_distinct_prior_drugs(self):
        clinical = self.case["clinical"]
        prior_scenarios = (
            (["lorlatinib"], True, "criteria_not_met"),
            (["lorlatinib", "lorbrena"], True, "criteria_not_met"),
            (["alectinib", "lorlatinib"], False, "criteria_not_met"),
            (["alectinib", "lorlatinib"], None, "insufficient_information"),
            (["alecensa", "lorlatinib"], True, "criteria_met"),
            (["lorlatinib", "unrelated"], True, "insufficient_information"),
            (["alectinib"], False, "insufficient_information"),
        )
        for drugs, platinum, expected in prior_scenarios:
            with self.subTest(drugs=drugs, platinum=platinum):
                clinical["prior_advanced_alk_tkis"] = drugs
                clinical["prior_advanced_platinum"] = platinum
                self.assertEqual(option(assess(self.case), "neladalkib_us")["status"], expected)
        self.case["progression"]["lorlatinib_setting"] = "other"
        clinical["prior_advanced_alk_tkis"] = ["alectinib"]
        self.assertEqual(option(assess(self.case), "neladalkib_us")["status"], "criteria_met")
        clinical["jurisdiction"] = "CN"
        self.assertEqual(option(assess(self.case), "neladalkib_us")["status"], "local_label_unverified")


class AdapterAndArtifactTest(unittest.TestCase):
    def test_ambiguous_alt_in_vep(self):
        self.assertIsNone(allele_number({"Allele": "AA"}, "A", ["AA", "AAA"]))
        self.assertEqual(allele_number({"Allele": "AA", "ALLELE_NUM": "2"}, "A", ["AA", "AAA"]), 2)

    def test_vcf_phasing_requires_explicit_trust_and_valid_alt_support(self):
        path = EXAMPLES / "synthetic_calls.vcf"
        document = load_case()
        import_vcf(document, "T1", "WGS", "TUMOR", path)
        self.assertEqual(assess(document)["assessment"], "unresolved")
        document = load_case()
        import_vcf(document, "T1", "WGS", "TUMOR", path, trust_phase=True)
        self.assertEqual(assess(document)["assessment"], "supported_hypothesis")
        test_data = path.read_text()
        for bad in (
            "1|1:1000:100:74,26", "1/0:1000:100:74,26", "0|1:.:100:74,26",
            "0|1:1000:0:100,0", "./.:1000:100:.",
        ):
            with self.subTest(genotype=bad), tempfile.TemporaryDirectory() as temp:
                imported = Path(temp) / "calls.vcf"
                imported.write_text(test_data.replace("0|1:1000:100:74,26", bad))
                document = load_case()
                import_vcf(document, "T1", "WGS", "TUMOR", imported, trust_phase=True)
                self.assertEqual(assess(document)["assessment"], "unresolved")

    def test_vcf_cross_contig_is_not_phased(self):
        example = (EXAMPLES / "synthetic_calls.vcf").read_text()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "calls.vcf"
            path.write_text(example.replace("chr2\t1018", "chr3\t1018"))
            document = load_case()
            import_vcf(document, "T1", "WGS", "TUMOR", path, trust_phase=True)
            self.assertEqual(assess(document)["assessment"], "unresolved")

    def test_clinical_demo_and_duplicate_vcf_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "result.json"
            vcfs = ["--vcf", "T1", "WGS", "TUMOR", str(EXAMPLES / "synthetic_calls.vcf")]
            args = ["--case", str(EXAMPLES / "synthetic_case.json"), "--output", str(report),
                    "--trust-vcf-read-phasing", "--findings-tsv", str(EXAMPLES / "synthetic_findings.tsv"), *vcfs]
            self.assertEqual(main(args), 0)
            previous = report.read_text()
            parsed = json.loads(previous)
            self.assertEqual(parsed["unresolved_specimens"], ["P1"])
            self.assertEqual([item["imported"] for item in parsed["imports"]], [3, 2])
            self.assertEqual(option(parsed, "neladalkib_us")["status"], "criteria_not_met")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(args + vcfs), 2)
            self.assertEqual(report.read_text(), previous)

    def test_literature_tables_preserve_lookup_and_denominators(self):
        ids = set()
        for filename in ("references.json", "variant_literature.json"):
            references = json.loads((PROJECT / filename).read_text(encoding="utf-8"))["references"]
            source_ids = {row["id"] for row in references}
            self.assertEqual(len(source_ids), len(references))
            ids.update(source_ids)
        self.assertTrue(set(knowledge()["sources"]) <= ids)
        with (PROJECT / "cohort_observations.tsv").open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle, delimiter="\t"):
                self.assertIn(row["reference_id"], ids)
                self.assertLessEqual(0, int(row["numerator"]))
                self.assertLessEqual(int(row["numerator"]), int(row["denominator"]))


if __name__ == "__main__":
    unittest.main()
