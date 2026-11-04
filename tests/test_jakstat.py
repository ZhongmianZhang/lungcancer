import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from jakstat.engine import analyze
from jakstat.knowledge import load_knowledge
from jakstat.render import write_case,write_catalog


class JAKSTATTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb=load_knowledge()
        cls.model=json.loads((ROOT/'jakstat/examples/patient_model.json').read_text())
        cls.readouts=json.loads((ROOT/'jakstat/examples/readouts_only.json').read_text())

    def case(self):return copy.deepcopy(self.model)
    def run_case(self,d):return analyze(d,self.kb)

    def test_readouts_and_serum_cytokine_do_not_match_drugs(self):
        r=self.run_case(copy.deepcopy(self.readouts))
        self.assertEqual(r['research_options'],[])
        states={x['id']:x['status'] for x in r['signals']}
        self.assertEqual(states['serum_IL6'],'systemic_or_microenvironment_signal')
        self.assertEqual(states['tumor_pSTAT3'],'signal_readout_not_dependency')
        self.assertEqual(states['blood_JAK2'],'molecular_origin_requires_validation')
        self.assertEqual(states['low_SOCS3'],'signal_readout_not_dependency')

    def test_stat3_sites_and_low_readout_never_standalone_dependency(self):
        for site in ('Y705','S727','unknown'):
            d=copy.deepcopy(self.readouts);d['observations']=[d['observations'][1]];d['observations'][0].update(site=site,level='low')
            r=self.run_case(d)
            self.assertEqual(r['signals'][0]['status'],'signal_readout_not_dependency')
            self.assertFalse(r['research_options'])

    def test_blood_cell_jak2_is_not_tumor_resistance(self):
        d=copy.deepcopy(self.readouts);d['observations']=[d['observations'][2]]
        d['observations'][0]['tumor_origin']='hematopoietic'
        self.assertEqual(self.run_case(d)['signals'][0]['status'],'not_tumor_resistance_source')

    def test_confirmed_tumor_dna_alone_still_not_dependency(self):
        d=copy.deepcopy(self.readouts);d['observations']=[d['observations'][2]]
        d['observations'][0].update(sample_type='tissue',tumor_origin='confirmed')
        r=self.run_case(d)
        self.assertEqual(r['signals'][0]['status'],'tumor_alteration_not_dependency')
        self.assertFalse(r['research_options'])

    def test_vus_or_hematopoietic_link_cannot_be_rescued_by_model_flags(self):
        for updates in ({'kind':'snv','variant':'p.V617F','classification':'vus'}, {'kind':'snv','variant':'p.V617F','classification':'pathogenic','tumor_origin':'hematopoietic'}):
            d=self.case();d['observations'][1].update(updates)
            r=self.run_case(d)
            self.assertEqual(r['dependency_assessments'][0]['status'],'requires_dependency_validation')
            self.assertFalse(r['research_options'])

    def test_qualified_model_produces_only_research_route(self):
        r=self.run_case(self.case())
        self.assertEqual(r['dependency_assessments'][0]['status'],'patient_model_hypothesis_not_clinical_validation')
        self.assertEqual(r['research_options'][0]['id'],'JAK_STAT_RESEARCH_REVIEW')
        self.assertEqual(r['treatment_recommendations'],[])
        self.assertEqual(r['doses'],[])
        self.assertIsNone(r['response_probabilities'])

    def test_each_causal_validation_flag_is_required(self):
        for flag in ('validated','compartment_resolved','selective_target_engagement','orthogonal_perturbation','rescue_or_reconstitution','resistance_phenotype_measured','downstream_axis_measured'):
            d=self.case();d['dependency_tests'][0][flag]=False
            self.assertFalse(self.run_case(d)['research_options'],flag)

    def test_generic_model_not_an_individual_dependency(self):
        d=self.case();d['dependency_tests'][0]['model_source']='generic_model'
        self.assertEqual(self.run_case(d)['dependency_assessments'][0]['status'],'requires_dependency_validation')

    def test_immune_only_model_has_no_tumor_anchor(self):
        d=self.case()
        for o in d['observations']:o.update(compartment='immune',tumor_origin='unknown')
        r=self.run_case(d)
        self.assertFalse(r['research_options'])
        self.assertTrue(any('缺少定位到肿瘤' in x for x in r['dependency_assessments'][0]['validation_needed']))

    def test_mixed_or_unresolved_compartment_blocks_upgrade(self):
        for change in ({'compartment':'mixed'},{'compartment_confirmed':False},{'assay_validated':False}):
            d=self.case();d['observations'][1].update(change)
            self.assertFalse(self.run_case(d)['research_options'])

    def test_jak_loss_not_activation_even_if_model_claimed_positive(self):
        d=self.case();d['observations'][1].update(kind='loss_of_function',classification='pathogenic')
        r=self.run_case(d)
        self.assertEqual(r['signals'][1]['status'],'loss_is_not_pathway_activation')
        self.assertFalse(r['research_options'])

    def test_src_bypass_requires_independence_test_and_never_selects_jak_route(self):
        d=json.loads((ROOT/'jakstat/examples/src_bypass.json').read_text())
        r=self.run_case(d);self.assertEqual(r['research_options'][0]['id'],'NON_JAK_SOURCE_REVIEW')
        d['dependency_tests'][0]['jak_independence_tested']=False
        self.assertFalse(self.run_case(d)['research_options'])

    def test_jak3_cannot_replace_gp130_canonical_kinases(self):
        d=self.case();d['observations'][1]['gene']='JAK3'
        self.assertFalse(self.run_case(d)['research_options'])

    def test_axis_name_without_linked_causal_chain_cannot_pass(self):
        d=self.case();d['dependency_tests'][0]['observation_ids']=['STAT3_Y705']
        self.assertFalse(self.run_case(d)['research_options'])

    def test_target_time_and_progression_pathology_gate(self):
        for changes in ({'concurrent_osi_chemo':False,'progressed_after_combination':False},{'collection_timing':'before_progression'},{'histology':'small_cell'},{'histology_confirmed_at_progression':False}):
            d=self.case();d['context'].update(changes)
            self.assertFalse(self.run_case(d)['research_options'])

    def test_missing_egfr_confirmation_does_not_get_egfr_routes(self):
        for changes in ({'egfr_driver_confirmed':False},{'egfr_driver_confirmed':False,'egfr_driver':'EGFR wild-type'}):
            d=self.case();d['context'].update(changes)
            r=self.run_case(d);self.assertFalse(r['clinical_context_gate_passed']);self.assertFalse(r['research_options'])
        d=self.case();del d['context']['egfr_driver_confirmed']
        self.assertFalse(self.run_case(d)['research_options'])

    def test_confirmed_driver_cannot_be_empty_or_wildtype(self):
        for value in ('','EGFR wild-type','unknown'):
            d=self.case();d['context']['egfr_driver']=value
            with self.assertRaises(ValueError):self.run_case(d)

    def test_negative_experiment_does_not_become_global_exclusion(self):
        d=self.case();d['dependency_tests'][0]['result']='does_not_support'
        r=self.run_case(d)
        self.assertEqual(r['dependency_assessments'][0]['status'],'supplied_experiment_not_supportive_not_global_exclusion')
        self.assertFalse(r['research_options'])

    def test_strict_schema_ids_and_booleans(self):
        d=self.case();d['dependency_tests'][0]['validated']='true'
        with self.assertRaises(ValueError):self.run_case(d)
        d=self.case();d['dependency_tests'][0]['observation_ids'].append('missing')
        with self.assertRaises(ValueError):self.run_case(d)
        d=self.case();d['observations'].append(copy.deepcopy(d['observations'][0]))
        with self.assertRaises(ValueError):self.run_case(d)
        d=self.case();d['observations'][0]['raw_IL6_cutoff']=5
        with self.assertRaises(ValueError):self.run_case(d)

    def test_loss_and_amplification_need_distinct_validation(self):
        d=copy.deepcopy(self.readouts);d['observations']=[d['observations'][3]]
        o=d['observations'][0];o.update(kind='loss_of_function',classification='pathogenic')
        self.assertEqual(self.run_case(d)['signals'][0]['status'],'feedback_loss_requires_validation')
        o['loss_effect_confirmed']=True
        self.assertEqual(self.run_case(d)['signals'][0]['status'],'feedback_change_not_drug_sensitivity')
        o.update(kind='amplification')
        self.assertEqual(self.run_case(d)['signals'][0]['status'],'amplification_requires_validation')

    def test_case_analysis_never_sends_network_requests(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('Case analysis must stay offline')):self.run_case(self.case())

    def test_seven_modules_and_real_conference_evidence(self):
        self.assertEqual(self.kb['agent_count'],7)
        self.assertEqual(self.kb['window'],{'start':'2016-11-04','end':'2026-11-04'})
        conf=[e for e in self.kb['evidence'] if e['design']=='conference_abstract']
        self.assertTrue(conf)
        self.assertTrue(all(e['scope']=='preclinical' for e in conf))
        self.assertTrue(all(not e['full_text_reviewed'] for e in self.kb['evidence']))

    def test_citations_aliases_offline_output_and_escaped_data(self):
        r=self.run_case(self.case());ids={e['id'] for e in self.kb['evidence']}
        for route in r['research_options']:self.assertTrue(set(route['evidence_ids'])<=ids)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);write_case(r,self.kb,p);write_catalog(self.kb,p/'catalog')
            self.assertTrue((p/'result.html').is_file())
            page=(p/'catalog/index.html').read_text()
            for e in self.kb['evidence']:self.assertEqual(page.count('id="ref-'+e['id']+'"'),1)
            self.assertNotIn('<script src=',page)

    def test_shared_search_uses_jakstat_own_date_window(self):
        from lineage.search import search
        with patch.dict('os.environ',{'FIRECRAWL_API_KEY':''}),patch('lineage.search.EuropePMCClient.request',return_value={'hitCount':0,'resultList':{'result':[]}}) as call:
            r=search('EGFR AND STAT3',start='2016-11-04',end='2026-11-04')
        self.assertIn('FIRST_PDATE:[2016-11-04 TO 2026-11-04]',call.call_args.args[0])
        self.assertEqual(r['actual_provider'],'Europe PMC')
        self.assertEqual(r['attempts'][0]['kind'],'missing_credential')


if __name__=='__main__':unittest.main()
