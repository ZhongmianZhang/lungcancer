"""Regression checks for sampling, provenance, mechanism and bibliography errors."""
import copy
import csv
import datetime as dt
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from omniresist.engine import analyze
from omniresist.knowledge import load_knowledge
from omniresist.ranking import load_ranks, assess_reference, REQUIRED
from omniresist.render import write_case, write_catalog
from omniresist.schema import FUNCTION_FLAGS, validate_input


class MultiomicsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb = load_knowledge()

    def case(self, name='ret_fusion'):
        return json.loads((ROOT/'omniresist/examples'/f'{name}.json').read_text())

    def run_case(self, data, kb=None):
        return analyze(data, kb or self.kb)

    def rank_csv(self, directory, journal, issn='', rank=1, category='Oncology', **extra):
        if isinstance(issn, list):
            issn = ';'.join(issn)
        row = dict(journal=journal, issn=issn, rank=rank, category=category, jcr_edition=2025, jif_year=2024, ranking_metric='JIF', source='SYNTHETIC TEST FIXTURE, NOT REAL JCR DATA')
        row.update(extra)
        p = Path(directory)/'test-ranks.csv'
        with p.open('w', newline='') as h:
            writer = csv.DictWriter(h, fieldnames=sorted(REQUIRED)); writer.writeheader(); writer.writerow(row)
        return p

    def test_low_fraction_plasma_negative_is_not_exclusion(self):
        r = self.run_case(self.case('plasma_negative'))
        self.assertFalse(r['clinical_context_gate_passed'])
        self.assertFalse(r['research_directions'])
        self.assertEqual(r['assay_assessments'][0]['negative_interpretation'], 'not_interpretable_as_exclusion')
        codes = {x['code'] for x in r['unresolved_dimensions']}
        self.assertTrue({'TISSUE_AND_PATHOLOGY', 'RNA_FUSION_SPLICE', 'ANALYTICAL_OR_SAMPLING_LIMITS'} <= codes)

    def test_even_qualified_negative_only_addresses_declared_scope(self):
        d = self.case('plasma_negative'); a = d['assays'][0]; a['tumor_fraction'] = 0.1
        r = self.run_case(d)
        self.assertEqual(r['assay_assessments'][0]['status'], 'within_declared_scope_only')
        self.assertIn('never_all_resistance', r['assay_assessments'][0]['negative_interpretation'])
        self.assertTrue(r['unresolved_dimensions'])

    def test_qc_historical_or_unknown_version_does_not_support_action(self):
        for updates in ({'status':'failed'}, {'collection_timing':'before_progression'}, {'platform_version':'unknown'}):
            d = self.case(); d['assays'][0].update(updates)
            r = self.run_case(d)
            self.assertEqual(r['mechanism_hypotheses'][0]['status'], 'assay_or_time_unresolved')
            self.assertFalse(r['research_directions'])

    def test_wgs_cannot_claim_methylation_or_rna(self):
        for classes in (['methylation'], ['expression']):
            d = self.case('met_amp'); d['assays'][0]['validated_classes'] = classes
            with self.assertRaises(ValueError): self.run_case(d)

    def test_long_read_modification_needs_specific_validation(self):
        d = self.case('epigenetic_model'); a = d['assays'][0]
        a.update(modality='long_read_dna', validated_classes=['methylation'])
        d['findings'][0]['alteration_type'] = 'methylation'
        with self.assertRaises(ValueError): self.run_case(d)
        a['native_modification_validated'] = True
        self.assertTrue(self.run_case(d)['functional_assessments'])

    def test_chip_mark_and_atac_accessibility_not_interchangeable(self):
        d = self.case('epigenetic_model'); d['assays'][0]['modality'] = 'chip_seq'
        with self.assertRaises(ValueError): self.run_case(d)

    def test_invalid_fractions_booleans_and_dangling_links_rejected(self):
        for value in (True, -0.1, 5, math.nan, math.inf):
            d = self.case(); d['findings'][0]['vaf'] = value
            with self.assertRaises(ValueError): self.run_case(d)
        d = self.case(); d['findings'][0]['rna_confirmed'] = 'true'
        with self.assertRaises(ValueError): self.run_case(d)
        d = self.case(); d['findings'][0]['supporting_assay_ids'] = ['missing']
        with self.assertRaises(ValueError): self.run_case(d)

    def test_ch_or_germline_not_nsclc_somatic_resistance(self):
        for origin in ('hematopoietic', 'germline'):
            d = self.case('met_amp'); d['findings'][0]['tumor_origin'] = origin
            r = self.run_case(d)
            self.assertEqual(r['mechanism_hypotheses'][0]['status'], 'not_somatic_tumor_source')
            self.assertFalse(r['research_directions'])

    def test_snv_lod_does_not_become_copy_number_threshold(self):
        d = self.case('met_amp'); d['assays'][0]['lod_vaf'] = 0.05
        d['findings'][0]['vaf'] = 0.01
        self.assertTrue(self.run_case(d)['research_directions'])
        d['findings'][0].update(gene='EGFR', alteration_type='snv', variant='C797S', allele_phase='trans', phase_partner='SYNTHETIC T790M', phase_confirmed=True)
        r = self.run_case(d)
        self.assertEqual(r['mechanism_hypotheses'][0]['status'], 'below_assay_validated_lod')
        self.assertFalse(r['research_directions'])

    def test_paired_normal_presence_does_not_prove_finding_origin(self):
        d = self.case('met_amp'); d['assays'][0]['matched_normal_available'] = True
        d['findings'][0]['tumor_origin'] = 'unconfirmed'
        self.assertEqual(self.run_case(d)['mechanism_hypotheses'][0]['status'], 'origin_unresolved')

    def test_tumor_origin_does_not_prove_same_egfr_clone(self):
        for change in ({'egfr_clonal_link_confirmed':False}, {'egfr_clonal_link_evidence':''}):
            d = self.case(); d['findings'][0].update(change)
            r = self.run_case(d)
            self.assertEqual(r['mechanism_hypotheses'][0]['status'], 'clonal_relationship_unresolved')
            self.assertFalse(r['research_directions'])

    def test_contradictory_negative_and_positive_assay_is_held(self):
        d = self.case(); d['assays'][0]['negative_result'] = True
        self.assertEqual(self.run_case(d)['mechanism_hypotheses'][0]['status'], 'contradictory_negative_assay')

    def test_vus_not_upgraded_by_claimed_functional_flags(self):
        d = self.case('epigenetic_model'); f = d['findings'][0]
        d['assays'][0].update(modality='wgs', validated_classes=['noncoding'])
        f.update(alteration_type='noncoding', classification='vus')
        r = self.run_case(d)
        self.assertEqual(r['mechanism_hypotheses'][0]['status'], 'benign_or_vus_not_driver')
        self.assertFalse(r['research_directions'])

    def test_claimed_acquired_without_comparable_baseline_stays_unproven(self):
        d = self.case(); d['context']['baseline_available'] = False
        r = self.run_case(d)
        self.assertEqual(r['mechanism_hypotheses'][0]['acquisition_status'], 'claimed_acquired_not_proven')

    def test_met_copies_require_ploidy_and_focality(self):
        for flag in ('ploidy_reviewed', 'focal_amplification'):
            d = self.case('met_amp'); d['findings'][0][flag] = False
            r = self.run_case(d)
            self.assertEqual(r['mechanism_hypotheses'][0]['status'], 'event_specific_validation_needed')
            self.assertFalse(r['research_directions'])

    def test_fusion_needs_real_quality_rna_support_not_just_a_boolean(self):
        d = self.case('dna_fusion_only'); d['findings'][0]['rna_confirmed'] = True
        self.assertFalse(self.run_case(d)['research_directions'])
        rna = copy.deepcopy(self.case()['assays'][0]); rna['rna_quality_passed'] = False
        d['assays'].append(rna); d['findings'][0]['supporting_assay_ids'] = ['rna1']
        self.assertFalse(self.run_case(d)['research_directions'])
        rna['rna_quality_passed'] = True
        self.assertTrue(self.run_case(d)['research_directions'])

    def test_fusion_frame_and_domain_required(self):
        for flag in ('in_frame', 'kinase_domain_retained'):
            d = self.case(); d['findings'][0][flag] = False
            self.assertFalse(self.run_case(d)['research_directions'])

    def test_l718q_not_mislabelled_original_egfr_driver(self):
        d = self.case('met_amp'); f = d['findings'][0]
        f.update(gene='EGFR', alteration_type='snv', variant='p.L718Q')
        r = self.run_case(d)
        self.assertEqual(r['mechanism_hypotheses'][0]['mechanism'], 'EGFR_ALLELE_REVIEW')
        self.assertFalse(r['research_directions'])
        f.update(variant='p.L858R', original_egfr_driver=True)
        self.assertEqual(self.run_case(d)['mechanism_hypotheses'][0]['mechanism'], 'RETAINED_EGFR_NOT_RESISTANCE_PROOF')

    def test_c797s_phase_not_assumed_and_never_prescribes_first_third_combo(self):
        d = self.case('met_amp'); f = d['findings'][0]
        f.update(gene='EGFR', alteration_type='snv', variant='p.Cys797Ser')
        self.assertFalse(self.run_case(d)['research_directions'])
        f.update(allele_phase='trans', phase_partner='EGFR T790M, SYNTHETIC phase review', phase_confirmed=True)
        r = self.run_case(d)
        self.assertEqual(r['research_directions'][0]['mechanism'], 'EGFR_C797S')
        self.assertEqual(r['treatment_recommendations'], [])

    def test_tp53_rb1_risk_cannot_diagnose_transformation(self):
        d = self.case('met_amp'); d['findings'][0].update(gene='RB1', alteration_type='deletion')
        r = self.run_case(d)
        self.assertEqual(r['mechanism_hypotheses'][0]['status'], 'background_or_risk_not_mechanism')
        self.assertFalse(r['research_directions'])

    def test_epigenetic_readout_alone_not_drug_dependency(self):
        d = self.case('epigenetic_model'); d['functional_tests'] = []
        self.assertEqual(self.run_case(d)['mechanism_hypotheses'][0]['status'], 'hypothesis_requires_functional_validation')
        self.assertFalse(self.run_case(d)['research_directions'])

    def test_stromal_readout_retained_as_tme_clue_not_tumor_driver(self):
        d = self.case('epigenetic_model'); d['findings'][0].update(compartment='stromal', tumor_origin='unknown')
        r = self.run_case(d)
        self.assertEqual(r['mechanism_hypotheses'][0]['status'], 'nonmalignant_state_readout')
        self.assertFalse(r['research_directions'])

    def test_complete_model_is_still_not_clinical_validation(self):
        r = self.run_case(self.case('epigenetic_model'))
        self.assertEqual(r['mechanism_hypotheses'][0]['status'], 'model_hypothesis_not_clinical_validation')
        self.assertEqual(r['doses'], [])
        self.assertEqual(r['treatment_recommendations'], [])
        self.assertIsNone(r['response_probabilities'])

    def test_every_functional_causal_condition_is_required(self):
        for flag in FUNCTION_FLAGS:
            d = self.case('epigenetic_model'); d['functional_tests'][0][flag] = False
            self.assertFalse(self.run_case(d)['research_directions'], flag)

    def test_model_negative_not_global_exclusion(self):
        d = self.case('epigenetic_model'); d['functional_tests'][0]['result'] = 'does_not_support'
        r = self.run_case(d)
        self.assertEqual(r['functional_assessments'][0]['status'], 'supplied_test_not_supportive_not_global_exclusion')
        self.assertFalse(r['research_directions'])

    def test_treatment_time_histology_driver_gate(self):
        for updates in ({'egfr_driver_confirmed':False}, {'histology':'small_cell'}, {'histology':'squamous'}, {'histology_confirmed_at_progression':False}, {'collection_timing':'before_progression'}, {'concurrent_osi_chemo':False, 'progressed_after_combination':False}):
            d = self.case(); d['context'].update(updates)
            self.assertFalse(self.run_case(d)['research_directions'], updates)
        d = self.case(); d['context']['egfr_driver'] = 'EGFR wild-type'
        with self.assertRaises(ValueError): self.run_case(d)

    def test_cns_and_oligoprogression_not_ignored(self):
        for pattern, text in [('cns', 'CNS'), ('oligoprogression', '寡进展')]:
            d = self.case(); d['context']['progression_pattern'] = pattern
            self.assertTrue(any(text in a for a in self.run_case(d)['alerts']))

    def test_missing_jcr_table_does_not_claim_top80_or_strict_routes(self):
        r = self.run_case(self.case())
        self.assertEqual(r['journal_selection']['passed_unique_journal_records'], 0)
        self.assertFalse(r['strict_rank_screened_directions'])
        self.assertTrue(all(not e['ranking']['meets_journal_top80'] for e in self.kb['unique_evidence']))

    def test_exact_journal_and_issn_matching_cannot_override_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.rank_csv(tmp, 'SYNTHETIC JOURNAL', issn='1234-5678')
            rows, provenance = load_ranks(p)
            ref = {'journal':'SYNTHETIC JOURNAL','issn':'8765-4321','design':'original','verification':'metadata_abstract_checked'}
            self.assertFalse(assess_reference(ref, rows)['meets_journal_top80'])
            ref['issn'] = '1234-5678'
            self.assertTrue(assess_reference(ref, rows)['meets_journal_top80'])
            self.assertFalse(provenance['authenticated_by_program'])

    def test_rank81_edition_metric_and_duplicate_table_rejected_or_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self.rank_csv(tmp, 'SYNTHETIC JOURNAL', rank=81)
            rows, _ = load_ranks(p)
            ref = {'journal':'SYNTHETIC JOURNAL','design':'original','verification':'metadata_abstract_checked'}
            self.assertEqual(assess_reference(ref, rows)['status'], 'outside_top80')
            for change in ({'jif_year':2025}, {'jcr_edition':2024}, {'ranking_metric':'JCI'}, {'rank':0}):
                p = self.rank_csv(tmp, 'SYNTHETIC JOURNAL', **change)
                with self.assertRaises(ValueError): load_ranks(p)
            p = self.rank_csv(tmp, 'SYNTHETIC JOURNAL'); content = p.read_text(); p.write_text(content + content.splitlines()[-1] + '\n')
            with self.assertRaises(ValueError): load_ranks(p)

    def test_generic_guideline_rank_cannot_qualify_ret_treatment(self):
        # An actual guideline journal with synthetic rank only, never bundled as JCR data.
        generic = next(e for e in self.kb['evidence'] if 'AMP' in e.get('id','') or 'Standards and Guidelines for the Interpretation' in e['title'])
        with tempfile.TemporaryDirectory() as tmp:
            p = self.rank_csv(tmp, generic['journal'], issn=generic.get('issn',''))
            r = self.run_case(self.case(), load_knowledge(p))
            self.assertGreater(r['journal_selection']['passed_unique_journal_records'], 0)
            self.assertFalse(r['strict_rank_screened_directions'])

    def test_specific_primary_rank_can_filter_bibliography_but_not_validate_therapy(self):
        ret = next(e for e in self.kb['evidence'] if str(e.get('pmid')) == '36996322')
        with tempfile.TemporaryDirectory() as tmp:
            p = self.rank_csv(tmp, ret['journal'], issn=ret.get('issn',''))
            ranked = load_knowledge(p); r = self.run_case(self.case(), ranked)
            self.assertTrue(r['strict_rank_screened_directions'])
            refs = {e['id']:e for e in ranked['evidence']}
            for d in r['strict_rank_screened_directions']:
                self.assertTrue(all(refs[i]['ranking']['meets_journal_top80'] for i in d['evidence_ids']))
            self.assertEqual(r['treatment_recommendations'], [])

    def test_conference_metadata_not_abstract_results_or_jcr_pass(self):
        conference = [e for e in self.kb['evidence'] if e['design'] == 'conference_abstract']
        self.assertTrue(conference)
        self.assertTrue(any(e['verification'] == 'metadata_only' for e in conference))
        for e in conference:
            self.assertFalse(e['ranking']['meets_journal_top80'])
            if e['verification'] == 'metadata_only':
                self.assertFalse(e['ranking']['result_interpretation_allowed'])
        met = self.run_case(self.case('met_amp'))
        self.assertTrue(met['research_directions'][0]['conference_evidence_ids_separate'])
        self.assertFalse(met['strict_rank_screened_directions'])

    def test_offline_analysis_and_no_hidden_patient_network(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('Case input must stay offline')):
            r = self.run_case(self.case())
        self.assertFalse(r['patient_inputs_sent_to_network'])

    def test_knowledge_dates_aliases_and_escaped_case_html(self):
        self.assertEqual(self.kb['counts']['nodes'], 7)
        self.assertEqual(self.kb['window'], {'start':'2011-11-04','end':'2026-11-04'})
        self.assertTrue(all(e['full_text_reviewed'] is False for e in self.kb['evidence']))
        d = self.case(); d['findings'][0]['variant'] = '<img src=x onerror=alert(1)>'
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); write_case(self.run_case(d), self.kb, out); write_catalog(self.kb, out/'catalog')
            page = (out/'result.html').read_text()
            self.assertNotIn('<img src=x', page)
            self.assertIn('&lt;img', page)
            catalog = (out/'catalog/index.html').read_text()
            for e in self.kb['evidence']:
                self.assertEqual(catalog.count('id="ref-' + e['id'] + '"'), 1)

    def test_shared_search_uses_fifteen_year_window_and_truthful_fallback(self):
        from lineage.search import search
        with patch.dict('os.environ', {'FIRECRAWL_API_KEY':''}), patch('lineage.search.EuropePMCClient.request', return_value={'hitCount':0,'resultList':{'result':[]}}) as call:
            r = search('EGFR AND genome', start='2011-11-04', end='2026-11-04')
        self.assertIn('FIRST_PDATE:[2011-11-04 TO 2026-11-04]', call.call_args.args[0])
        self.assertEqual(r['attempts'][0]['kind'], 'missing_credential')
        self.assertEqual(r['actual_provider'], 'Europe PMC')


if __name__ == '__main__':
    unittest.main()
