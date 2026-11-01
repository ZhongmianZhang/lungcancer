import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rasmapk.engine import analyze, normalize_variant
from rasmapk.knowledge import load_knowledge, date_in_window, plain
from rasmapk.render import write_case, write_catalog


class RASMAPKTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = load_knowledge()
        cls.template = json.loads((ROOT / "rasmapk/examples/braf_v600e.json").read_text())

    def case(self, **changes):
        data = copy.deepcopy(self.template)
        data["findings"] = [data["findings"][0]]
        data["findings"][0].update(changes)
        return data

    def result(self, data):
        return analyze(data, self.kb)["findings"][0]

    def test_vus_even_at_known_hotspot_never_selects_drugs(self):
        r = self.result(self.case(classification="vus"))
        self.assertEqual(r["status"], "requires_validation")
        self.assertEqual(r["research_options"], [])

    def test_plasma_kras_unconfirmed_or_hematopoietic_not_tumor_driver(self):
        for origin, expected in [("unconfirmed", "requires_validation"), ("hematopoietic", "not_tumor_resistance")]:
            r = self.result(self.case(gene="KRAS", variant="p.G12C", sample_type="plasma", tumor_origin=origin))
            self.assertEqual(r["status"], expected)
            self.assertFalse(r["research_options"])

    def test_claimed_liquid_tumor_origin_requires_explanation(self):
        d = self.case(gene="KRAS", variant="p.G12C", sample_type="plasma")
        self.assertEqual(self.result(d)["status"], "requires_validation")
        d["findings"][0]["tumor_origin_evidence"] = "Synthetic tissue confirmation plus matched blood-cell assessment"
        self.assertEqual(self.result(d)["status"], "supported_mechanistic_hypothesis")

    def test_braf_exact_alleles_and_unclassified_are_separate(self):
        for v, mechanism in [("p.Val600Glu", "BRAF_V600E_CLASS_I"), ("p.G469A", "BRAF_CLASS_II"), ("p.D594N", "BRAF_CLASS_III"), ("p.V600K", "BRAF_UNCLASSIFIED")]:
            self.assertEqual(self.result(self.case(variant=v))["mechanism"], mechanism)
        self.assertEqual(normalize_variant("p.(Gly12Cys)"), "G12C")
        d = self.case()
        d["findings"].append({**d["findings"][0], "variant": "p.D594N"})
        r = analyze(d, self.kb)
        self.assertEqual([x["mechanism"] for x in r["findings"]], ["BRAF_V600E_CLASS_I", "BRAF_CLASS_III"])
        self.assertTrue(any("多个BRAF" in a for a in r["alerts"]))

    def test_fusion_requires_all_three_structural_confirmations(self):
        d = self.case(variant="AGK::BRAF", alteration_type="fusion", rna_confirmed=False, in_frame=True, kinase_domain_retained=True)
        self.assertEqual(self.result(d)["status"], "requires_validation")
        d["findings"][0]["rna_confirmed"] = True
        self.assertEqual(self.result(d)["mechanism"], "BRAF_FUSION")
        self.assertEqual(self.result(d)["status"], "supported_mechanistic_hypothesis")

    def test_copy_number_without_confirmation_does_not_establish_amplification(self):
        d = self.case(gene="MET", variant="", alteration_type="amplification", amplification_confirmed=False)
        self.assertEqual(self.result(d)["status"], "requires_validation")
        d["findings"][0]["amplification_confirmed"] = True
        self.assertEqual(self.result(d)["status"], "supported_mechanistic_hypothesis")

    def test_nf1_single_loss_and_double_loss_do_not_imply_mek_sensitivity(self):
        d = self.case(gene="NF1", variant="LOF", alteration_type="loss_of_function", biallelic_loss=False)
        self.assertEqual(self.result(d)["status"], "requires_validation")
        d["findings"][0]["biallelic_loss"] = True
        r = self.result(d)
        self.assertEqual(r["status"], "supported_mechanistic_hypothesis")
        self.assertIn("不能自动选择MEK或SHP2", r["research_options"][0]["limitation"])

    def test_phospho_and_expression_never_turn_into_actionable_drivers(self):
        for gene in ("MAPK1", "BRAF", "PTPN11", "AXL"):
            for kind in ("expression", "phosphoprotein"):
                r = self.result(self.case(gene=gene, variant="", alteration_type=kind))
                self.assertEqual(r["status"], "readout_only_not_driver")
                self.assertFalse(r["research_options"])

    def test_mek_mutation_without_functional_class_is_not_drug_sensitivity(self):
        d = self.case(gene="MAP2K1", variant="p.K57N")
        self.assertEqual(self.result(d)["status"], "requires_validation")
        d["findings"][0]["functional_activation"] = True
        self.assertEqual(self.result(d)["clinical_actionability"], "not_established_for_this_sequence")

    def test_confirmed_histology_transformation_suppresses_gene_based_routes(self):
        d = self.case()
        d["context"].update(histology="small_cell", histology_confirmed_at_progression=True)
        r = analyze(d, self.kb)
        self.assertEqual(r["findings"][0]["research_options"], [])
        self.assertTrue(any("转化" in a for a in r["alerts"]))

    def test_acquisition_without_baseline_is_not_confirmed(self):
        d = self.case()
        d["context"]["baseline_available"] = False
        r = self.result(d)
        self.assertFalse(r["acquired_supported_by_supplied_history"])
        self.assertTrue(any("缺少基线" in a for a in r["cautions"]))

    def test_negative_cns_sample_does_not_exclude_resistance(self):
        d = self.case()
        d["findings"] = []
        d["context"]["progression_pattern"] = "cns"
        r = analyze(d, self.kb)
        self.assertTrue(any("不能排除中枢" in a for a in r["alerts"]))
        self.assertTrue(any("不等于没有" in a for a in r["alerts"]))

    def test_invalid_boolean_typo_and_inconsistent_history_rejected(self):
        d = self.case(); d["context"]["baseline_available"] = "false"
        with self.assertRaises(ValueError): analyze(d, self.kb)
        d = self.case(); d["findings"][0]["clasification"] = "pathogenic"
        with self.assertRaises(ValueError): analyze(d, self.kb)
        d = self.case(); d["context"]["concurrent_osi_chemo"] = False
        with self.assertRaises(ValueError): analyze(d, self.kb)

    def test_founder_egfr_not_a_ras_resistance_drug_mapping(self):
        r = self.result(self.case(gene="EGFR", variant="p.L858R", acquisition="baseline"))
        self.assertEqual(r["mechanism"], "EGFR_ON_TARGET_REVIEW")
        self.assertFalse(r["research_options"])

    def test_outside_target_sequence_or_before_progression_never_gets_target_routes(self):
        for updates in ({"progressed_after_combination": False, "concurrent_osi_chemo": False}, {"collection_timing": "before_progression"}, {"collection_timing": "unknown"}):
            d = self.case(); d["context"].update(updates)
            r = self.result(d)
            self.assertEqual(r["status"], "supported_mechanistic_hypothesis")
            self.assertEqual(r["research_options"], [])
            self.assertTrue(any("研究匹配" in n for n in r["cautions"]))

    def test_adaptor_loss_does_not_become_activation_even_with_inconsistent_flag(self):
        r = self.result(self.case(gene="PTPN11", variant="LOF", alteration_type="loss_of_function", functional_activation=True))
        self.assertEqual(r["status"], "requires_validation")
        self.assertEqual(r["research_options"], [])

    def test_gene_only_ras_and_inconsistent_variant_type_blocked(self):
        for f in ({"gene": "KRAS", "variant": ""}, {"gene": "BRAF", "alteration_type": "amplification"}, {"gene": "NRAS", "alteration_type": "loss_of_function"}, {"gene": "MET", "variant": "p.M1250T"}, {"gene": "ARAF", "alteration_type": "amplification", "amplification_confirmed": True}):
            self.assertEqual(self.result(self.case(**f))["status"], "requires_validation")

    def test_no_prescriptions_probabilities_or_unresolved_citations(self):
        r = analyze(self.template, self.kb)
        self.assertEqual(r["treatment_recommendations"], [])
        self.assertEqual(r["doses"], [])
        self.assertIsNone(r["response_probabilities"])
        ids = {e["id"] for e in self.kb["evidence"]}
        for f in r["findings"]:
            self.assertTrue(set(f["evidence_ids"]) <= ids)
            self.assertFalse(f["target_setting_abstract_evidence_ids"])
        self.assertIn("N05_E04", r["findings"][0]["evidence_ids"])

    def test_conference_metadata_never_treated_as_results(self):
        self.assertEqual(plain('Drug activity in &lt;i&gt;EGFR&lt;/i&gt;-mutant cancer.'), 'Drug activity in EGFR-mutant cancer.')
        conferences = [e for e in self.kb["evidence"] if e["design"] == "conference_abstract"]
        self.assertEqual(len(conferences), 2)
        self.assertTrue(all(e["verification"] == "metadata_only" and e["result_interpretation_allowed"] is False for e in conferences))
        self.assertTrue(date_in_window("2026-10"))
        self.assertIsNone(date_in_window("2016"))
        self.assertFalse(date_in_window("2015-01-01"))

    def test_offline_outputs_have_unique_citation_aliases_and_escape_input(self):
        d = self.case(variant='<img src=x onerror=alert(1)>')
        result = analyze(d, self.kb)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            write_case(result, self.kb, path)
            page = (path / "result.html").read_text()
            self.assertNotIn('<img src=x', page)
            self.assertIn('&lt;img', page)
            write_catalog(self.kb, path / "catalog")
            page = (path / "catalog/index.html").read_text()
            for e in self.kb["evidence"]:
                self.assertEqual(page.count('id="ref-' + e["id"] + '"'), 1)
            self.assertNotIn('<script src=', page)


if __name__ == "__main__":
    unittest.main()
