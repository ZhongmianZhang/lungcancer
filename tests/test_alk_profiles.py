"""Regression tests for drug-specific ALK resistance and molecular profiles."""

import copy
import json
import unittest
from pathlib import Path

from alk_resistance.engine import assess
from alk_resistance.input import InputError


EXAMPLES = Path(__file__).resolve().parents[1] / "alk_resistance" / "examples"


def load_example(filename):
    return json.loads((EXAMPLES / filename).read_text(encoding="utf-8"))


def mechanisms(report):
    return [row for sample in report["specimens"] for row in sample["mechanisms"]]


def option(report, ident):
    return next((row for row in report["clinical_options"] if row["id"] == ident), None)


class ALKProfilesTest(unittest.TestCase):
    def setUp(self):
        self.case = load_example("synthetic_alectinib_profile.json")
        self.baseline, self.post = self.case["specimens"]
        self.fusion, self.tp53, self.cdkn2a, self.alk_baseline = self.baseline["findings"]

    def test_transcript_and_coalterations_are_separate_from_progression(self):
        report = assess(self.case)
        baseline, post = report["molecular_profiles"]
        self.assertEqual(baseline["stage"], "before_tki")
        self.assertEqual(baseline["fusions"][0]["transcript_family"], "v3")
        self.assertEqual(baseline["joint_associations"][0]["type"], "prognosis")
        self.assertEqual({row["id"] for row in baseline["coalterations"]},
                         {"tp53_prognosis", "cdkn2ab_prognosis"})
        self.assertEqual(post["experimental_associations"][0]["id"], "atlas_model_clinical_discordance")
        self.assertEqual({row["id"] for row in mechanisms(report)}, {"alectinib_alk_variant"})
        evidence = mechanisms(report)[0]["evidence"][0]
        self.assertEqual(evidence["acquisition"]["state"], "newly_detected_in_comparable_specimens")
        self.assertEqual(option(report, "lorlatinib_after_alectinib")["status"], "multidisciplinary_review")
        self.assertEqual(option(report, "neladalkib_us")["status"], "criteria_met")
        self.post["findings"].clear()
        unresolved = assess(self.case)
        self.assertEqual(unresolved["assessment"], "unresolved")
        self.assertEqual(unresolved["clinical_options"], report["clinical_options"])

    def test_exon_grouping_and_discordance(self):
        for exon, family in ((13, "v1"), ("20", "v2"), ("6b", "v3"), (2, "other_eml4")):
            with self.subTest(exon=exon):
                self.fusion["attributes"]["partner_exon"] = exon
                self.fusion["attributes"].pop("reported_variant", None)
                self.assertEqual(assess(self.case)["molecular_profiles"][0]["fusions"][0]["transcript_family"],
                                 family)
        self.fusion["attributes"]["partner_exon"] = "6b"
        self.fusion["attributes"]["reported_variant"] = "V1"
        baseline = assess(self.case)["molecular_profiles"][0]
        self.assertTrue(baseline["discordant_junction"])
        self.assertEqual(baseline["fusions"][0]["status"], "discordant_junction")
        self.assertFalse(baseline["joint_associations"])

    def test_dna_annotated_v3_and_unvalidated_rna_keep_subtype_unresolved(self):
        self.fusion["assay_id"] = "DNA"
        baseline = assess(self.case)["molecular_profiles"][0]
        self.assertEqual(baseline["fusions"][0]["status"], "junction_prediction_only")
        self.assertIsNone(baseline["fusions"][0]["transcript_family"])
        self.assertFalse(baseline["joint_associations"])
        self.fusion["assay_id"] = "RNA"
        self.fusion["attributes"]["kinase_domain_retained"] = False
        self.assertIsNone(assess(self.case)["molecular_profiles"][0]["fusions"][0]["transcript_family"])

    def test_rare_and_multiple_orthogonal_transcripts(self):
        rare = copy.deepcopy(self.fusion)
        rare.update(id="rare", feature="KIF5B::ALK")
        rare["attributes"].pop("reported_variant")
        self.baseline["findings"].append(rare)
        baseline = assess(self.case)["molecular_profiles"][0]
        self.assertTrue(baseline["multiple_verified_families"])
        self.assertEqual(baseline["fusions"][1]["transcript_family"], "non_eml4")
        self.assertFalse(baseline["joint_associations"])

    def test_different_tkis_require_distinct_biopsy_timepoints(self):
        history = self.case["clinical"]
        history["prior_advanced_alk_tkis"].append("lorlatinib")
        self.case["progression"].update(failed_tki="lorlatinib", tki_line=2)
        report = assess(self.case)
        self.assertFalse(mechanisms(report))
        self.assertEqual(report["assessment"], "unresolved")
        self.assertIsNone(option(report, "lorlatinib_after_alectinib"))
        self.post["timepoint"] = "progression_on_lorlatinib"
        with self.assertRaises(InputError):
            assess(self.case)
        self.baseline["timepoint"] = "pre_lorlatinib"
        report = assess(self.case)
        self.assertEqual({row["id"] for row in mechanisms(report)}, {"alk_unresolved"})
        self.assertEqual(report["molecular_profiles"][-1]["experimental_associations"][0]["variant"], "G1202R")

    def test_alectinib_samples_require_explicit_drug_selection(self):
        self.case["progression"].pop("failed_tki")
        with self.assertRaises(InputError):
            assess(self.case)

    def test_multiple_alk_variants_remain_candidates_after_alectinib(self):
        later = {**self.post["findings"][0], "id": "other-alk", "feature": "p.Ile1171Asn"}
        self.post["findings"].append(later)
        report = assess(self.case)
        self.assertEqual([row["level"] for row in mechanisms(report)], ["candidate", "candidate"])
        self.assertEqual(report["assessment"], "unresolved")
        self.assertIsNotNone(option(report, "lorlatinib_after_alectinib"))

    def test_liquid_tp53_requires_tumor_origin(self):
        self.baseline["material"] = "plasma"
        baseline = assess(self.case)["molecular_profiles"][0]
        self.assertIn("circulating_origin", {row["id"] for row in baseline["coalterations"]})
        self.assertFalse(baseline["joint_associations"])
        self.tp53["attributes"]["tumor_origin"] = "hematopoietic"
        baseline = assess(self.case)["molecular_profiles"][0]
        self.assertNotIn("TP53", {row["gene"] for row in baseline["coalterations"]})
        self.tp53["attributes"]["tumor_origin"] = "confirmed"
        baseline = assess(self.case)["molecular_profiles"][0]
        self.assertEqual(baseline["joint_associations"][0]["id"], "v3_tp53")

    def test_early_nf2_only_in_documented_early_primary_progression(self):
        self.baseline["findings"].append({**self.tp53, "id": "nf2", "gene": "NF2", "feature": "E202*",
                                         "attributes": {"classification": "pathogenic", "loss_of_function": True}})
        self.post["findings"] = []
        self.case["progression"].update(best_response="PD", months_to_progression=2.5)
        report = assess(self.case)
        self.assertIn("alectinib_early_nf2", {row["id"] for row in report["molecular_profiles"][0]["joint_associations"]})
        self.assertEqual(report["assessment"], "unresolved")
        self.case["progression"].update(best_response="PR", months_to_progression=2.5)
        report = assess(self.case)
        self.assertNotIn("alectinib_early_nf2", {row["id"] for row in report["molecular_profiles"][0]["joint_associations"]})

    def test_vus_or_unverified_copy_loss_does_not_create_prognosis_entry(self):
        self.tp53["attributes"]["classification"] = "vus"
        self.cdkn2a["attributes"]["validated_call"] = False
        baseline = assess(self.case)["molecular_profiles"][0]
        self.assertFalse(baseline["coalterations"])
        self.assertFalse(baseline["joint_associations"])

    def test_prior_lorlatinib_oligoprogression_and_jurisdiction(self):
        self.case["clinical"]["prior_advanced_alk_tkis"].append("lorlatinib")
        report = assess(self.case)
        self.assertEqual(option(report, "lorlatinib_after_alectinib")["status"], "prior_lorlatinib_review")
        self.assertEqual(option(report, "neladalkib_us")["status"], "criteria_not_met")
        self.case["clinical"]["jurisdiction"] = "CN"
        self.case["progression"]["pattern"] = "isolated_cns"
        report = assess(self.case)
        self.assertIsNone(option(report, "lorlatinib_after_alectinib"))
        self.assertIsNotNone(option(report, "local_treatment_alectinib"))
        self.assertEqual(option(report, "neladalkib_us")["status"], "local_label_unverified")

    def test_model_only_variant_does_not_create_a_supported_patient_mechanism(self):
        self.post["findings"][0]["feature"] = "M1199L"
        report = assess(self.case)
        self.assertEqual(report["assessment"], "unresolved")
        self.assertEqual(report["molecular_profiles"][-1]["experimental_associations"][0]["id"],
                         "atlas_alectinib_model")

    def test_mtap_trial_signal_requires_direct_observation(self):
        case = load_example("synthetic_case.json")
        tissue = case["specimens"][1]
        finding = {**self.cdkn2a, "assay_id": "WGS"}
        tissue["findings"] = [finding]
        self.assertIsNone(option(assess(case), "tap_alk_trial"))
        finding["gene"] = "MTAP"
        report = assess(case)
        self.assertEqual(report["assessment"], "unresolved")
        self.assertEqual(option(report, "tap_alk_trial")["status"], "registered_not_yet_recruiting")
        finding["attributes"] = {"validated_call": False}
        self.assertIsNone(option(assess(case), "tap_alk_trial"))


if __name__ == "__main__":
    unittest.main()
