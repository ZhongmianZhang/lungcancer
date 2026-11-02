import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lineage.engine import analyze
from lineage.knowledge import load_knowledge
from lineage.render import write_case,write_catalog
from lineage.search import FirecrawlClient,FirecrawlError,search
from rasmapk.knowledge import load_knowledge as load_ras


class LineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kb=load_knowledge()
        cls.template=json.loads((ROOT/'lineage/examples/sclc_retained_egfr.json').read_text())

    def case(self):return copy.deepcopy(self.template)
    def run_case(self,d):return analyze(d,self.kb)

    def test_egfr_retained_and_protein_high_do_not_prove_dependency(self):
        r=self.run_case(self.case())
        self.assertEqual(r['pathology_assessment']['status'],'supplied_integrated_pathology_supported')
        self.assertEqual(r['egfr_dependency_assessment']['status'],'not_determined_by_dna_or_expression')
        self.assertEqual(r['egfr_dependency_assessment']['egfr_tki_decision'],'not_automatically_decided')

    def test_shared_common_events_need_expert_private_or_structural_review(self):
        d=self.case()
        d['molecular']['additional_shared_somatic_events']=['TP53:p.R273H']
        self.assertEqual(self.run_case(d)['clonality_assessment']['status'],'shared_events_require_clonal_review')
        d['molecular'].update(expert_clonality_reviewed=True,shared_private_or_structural_evidence=True)
        d['molecular']['additional_shared_somatic_events'].append('synthetic expert-confirmed private structural breakpoint')
        self.assertEqual(self.run_case(d)['clonality_assessment']['status'],'shared_origin_supported_by_supplied_paired_genomics')

    def test_single_egfr_hotspot_is_only_ancestry_clue(self):
        d=self.case();d['molecular']['additional_shared_somatic_events']=[]
        self.assertEqual(self.run_case(d)['clonality_assessment']['status'],'retained_driver_is_ancestry_clue_only')

    def test_plasma_egfr_does_not_localize_to_transformed_lesion(self):
        d=self.case();d['molecular'].update(detection_source='plasma',matched_tissue_genomics=False)
        self.assertEqual(self.run_case(d)['clonality_assessment']['status'],'liquid_driver_not_localized_to_transformed_lesion')

    def test_liquid_panel_or_risk_genes_cannot_diagnose_sclc(self):
        d=json.loads((ROOT/'lineage/examples/liquid_only_risk.json').read_text())
        r=self.run_case(d)
        self.assertNotEqual(r['pathology_assessment']['status'],'supplied_integrated_pathology_supported')
        self.assertEqual(r['transformation_assessment']['status'],'transformation_not_established')
        self.assertEqual(r['treatment_discussion_routes'],[])
        self.assertTrue(any('研究性cfDNA' in a for a in r['alerts']))

    def test_marker_or_ki67_alone_is_not_diagnostic(self):
        d=self.case();d['progression_pathology'].update(category='unknown',morphology_supports_category=False,integrated_diagnosis_confirmed=False)
        r=self.run_case(d)
        self.assertEqual(r['pathology_assessment']['status'],'marker_only_not_diagnostic')
        self.assertFalse(r['treatment_discussion_routes'])

    def test_ne_negative_or_rb_wildtype_does_not_override_integrated_pathology(self):
        d=self.case();d['progression_pathology']['ne_marker_positive']=False
        d['molecular']['tp53_rb1_coaltered']=False
        r=self.run_case(d)
        self.assertEqual(r['pathology_assessment']['status'],'supplied_integrated_pathology_supported')
        self.assertEqual(r['treatment_discussion_routes'][0]['id'],'SCLC_PATHOLOGY_LED_REVIEW')

    def test_limited_sample_and_missing_review_prevent_target_routes(self):
        for field,value in [('adequacy','limited'),('pathologist_reviewed',False),('morphology_supports_category',False),('ihc_panel_reviewed',False)]:
            d=self.case();d['progression_pathology'][field]=value
            self.assertFalse(self.run_case(d)['treatment_discussion_routes'])

    def test_adequate_cytology_is_allowed(self):
        d=self.case();d['progression_pathology']['sample_type']='cytology'
        self.assertEqual(self.run_case(d)['pathology_assessment']['status'],'supplied_integrated_pathology_supported')

    def test_baseline_mixed_or_unreviewed_not_definite_new_transformation(self):
        for updates in ({'category':'adenosquamous'},{'documented':False},{'components_reviewed':False}):
            d=self.case();d['baseline_pathology'].update(updates)
            self.assertEqual(self.run_case(d)['transformation_assessment']['status'],'preexisting_component_or_new_primary_not_excluded')

    def test_timing_and_target_context_gate(self):
        for updates in ({'collection_timing':'before_progression'},{'collection_timing':'unknown'},{'concurrent_osi_chemo':False,'progressed_after_combination':False}):
            d=self.case();d['context'].update(updates)
            self.assertFalse(self.run_case(d)['treatment_discussion_routes'])
        d=self.case();d['context']['collection_timing']='before_progression'
        self.assertEqual(self.run_case(d)['clonality_assessment']['status'],'paired_sample_timing_requires_review')

    def test_matched_genomics_without_baseline_or_validation_is_not_upgraded(self):
        d=self.case();d['context']['baseline_available']=False
        self.assertEqual(self.run_case(d)['clonality_assessment']['status'],'paired_genomics_inconsistent_with_history')
        d=self.case();d['molecular']['genomics_validated']=False
        self.assertEqual(self.run_case(d)['clonality_assessment']['status'],'molecular_provenance_requires_validation')

    def test_egfr_negative_does_not_automatically_exclude_common_origin(self):
        d=self.case();d['molecular'].update(original_driver_retained='no',expert_clonality_reviewed=True,shared_private_or_structural_evidence=True)
        self.assertEqual(self.run_case(d)['clonality_assessment']['status'],'shared_events_with_egfr_discordance_require_review')
        self.assertNotEqual(self.run_case(d)['transformation_assessment']['status'],'transformation_not_established')

    def test_model_dependency_is_not_clinical_sensitivity_and_requires_progression_match(self):
        d=self.case();d['molecular']['functional_egfr_dependence']='supported_in_model'
        self.assertEqual(self.run_case(d)['egfr_dependency_assessment']['status'],'functional_claim_requires_model_validation')
        d['molecular'].update(dependency_experiment_validated=True,dependency_model_source='patient_matched',dependency_from_progression_sample=True)
        r=self.run_case(d)
        self.assertEqual(r['egfr_dependency_assessment']['status'],'model_support_only_not_clinical_sensitivity')
        self.assertEqual(r['egfr_dependency_assessment']['egfr_tki_decision'],'not_automatically_decided')
        d['molecular']['functional_egfr_dependence']='not_supported_in_model'
        self.assertEqual(self.run_case(d)['egfr_dependency_assessment']['status'],'model_lack_of_dependency_not_global_exclusion')

    def test_squamous_lcnec_and_mixed_do_not_become_sclc(self):
        for category,route in [('squamous','SCC_PATHOLOGY_LED_REVIEW'),('lcnec','LCNEC_EXPERT_REVIEW'),('mixed','MIXED_COMPONENT_MTB')]:
            d=self.case();d['progression_pathology']['category']=category
            if category=='mixed':d['progression_pathology']['mixed_components']=['adenocarcinoma','sclc']
            r=self.run_case(d)
            self.assertEqual(r['treatment_discussion_routes'][0]['id'],route)
            self.assertNotIn('SCLC_PATHOLOGY_LED_REVIEW',[s['id'] for s in r['treatment_discussion_routes']])

    def test_pd_l1_and_dll3_are_not_drug_sensitivity(self):
        r=self.run_case(self.case())
        self.assertTrue(any('PD-L1' in x for x in r['alerts']))
        self.assertTrue(any('DLL3高不等于' in x for x in r['alerts']))
        self.assertEqual(r['treatment_recommendations'],[])
        self.assertEqual(r['doses'],[])
        self.assertIsNone(r['response_probabilities'])
        self.assertNotIn('IMMUNOTHERAPY',[s['id'] for s in r['treatment_discussion_routes']])

    def test_strict_schema_and_boolean_types(self):
        d=self.case();d['molecular']['genomics_validated']='true'
        with self.assertRaises(ValueError):self.run_case(d)
        d=self.case();d['progression_pathology']['ki_67_score']=95
        with self.assertRaises(ValueError):self.run_case(d)
        d=self.case();d['context']['concurrent_osi_chemo']=False
        with self.assertRaises(ValueError):self.run_case(d)
        d=self.case();d['progression_pathology']['category']='mixed'
        with self.assertRaises(ValueError):self.run_case(d)

    def test_analysis_never_calls_network(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('Unexpected case-network request')):
            self.run_case(self.case())

    def test_evidence_window_conference_status_and_ras_backwards_compatibility(self):
        self.assertEqual(self.kb['agent_count'],8)
        self.assertEqual(self.kb['window']['start'],'2016-11-02')
        conferences=[e for e in self.kb['evidence'] if e['design']=='conference_abstract']
        self.assertTrue(conferences)
        self.assertTrue(any(e['verification']=='metadata_abstract_checked' for e in conferences))
        self.assertTrue(all(not e['result_interpretation_allowed'] for e in self.kb['evidence'] if e['verification']=='metadata_only'))
        old=load_ras();self.assertEqual(old['agent_count'],10);self.assertEqual(old['window']['end'],'2026-11-01')

    def test_citations_resolve_and_offline_outputs_include_all_aliases(self):
        r=self.run_case(self.case());ids={e['id'] for e in self.kb['evidence']}
        for route in r['treatment_discussion_routes']:self.assertTrue(set(route['evidence_ids'])<=ids)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);write_case(r,self.kb,p);write_catalog(self.kb,p/'catalog')
            self.assertEqual(json.loads((p/'result.json').read_text())['doses'],[])
            page=(p/'catalog/index.html').read_text()
            for e in self.kb['evidence']:self.assertEqual(page.count('id="ref-'+e['id']+'"'),1)
            self.assertNotIn('<script src=',page)


class FirecrawlTests(unittest.TestCase):
    def test_auto_prefers_firecrawl_without_scholarly_request_when_successful(self):
        with patch('lineage.search.FirecrawlClient.search',return_value=[{'title':'paper','url':'https://pubmed.ncbi.nlm.nih.gov/123/'}]),patch('lineage.search.EuropePMCClient.request',side_effect=AssertionError('Unexpected fallback')):
            r=search('EGFR transformation')
        self.assertEqual(r['actual_provider'],'Firecrawl')
        self.assertEqual(r['attempts'][0]['status'],'executed')

    def test_missing_credential_records_honest_auto_fallback(self):
        with patch.dict(os.environ,{'FIRECRAWL_API_KEY':''}),patch('lineage.search.EuropePMCClient.request',return_value={'hitCount':0,'resultList':{'result':[]}}):
            r=search('EGFR transformation')
        self.assertEqual(r['actual_provider'],'Europe PMC')
        self.assertEqual(r['attempts'][0]['kind'],'missing_credential')
        self.assertFalse(r['case_analysis_inputs_accessed'])

    def test_forced_firecrawl_missing_key_is_blocked_not_successful_zero_hits(self):
        with patch.dict(os.environ,{'FIRECRAWL_API_KEY':''}),patch('lineage.search.EuropePMCClient.request',side_effect=AssertionError('Forced mode must not fallback')):
            r=search('EGFR transformation',provider='firecrawl')
        self.assertEqual(r['status'],'blocked')
        self.assertIsNone(r['actual_provider'])

    def test_firecrawl_protocol_and_safe_field_projection(self):
        body={'success':True,'data':{'web':[{'title':'paper','url':'https://example.org/paper','description':'abstract lead','secret_field':'unit-test-only-key'}]}}
        with patch.dict(os.environ,{'FIRECRAWL_API_KEY':'unit-test-only-key'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())) as call:
            result=FirecrawlClient().search('EGFR transformation',3)
        request=call.call_args.args[0]
        self.assertEqual(request.full_url,'https://api.firecrawl.dev/v2/search')
        self.assertEqual(json.loads(request.data)['limit'],3)
        self.assertNotIn('unit-test-only-key',json.dumps(result))
        self.assertNotIn('secret_field',result[0])

    def test_firecrawl_http_error_redacts_body_and_falls_back(self):
        error=urllib.error.HTTPError('https://api.firecrawl.dev/v2/search',401,'unauthorized',{},io.BytesIO(b'unit-test-only-key'))
        with patch.dict(os.environ,{'FIRECRAWL_API_KEY':'unit-test-only-key'}),patch('urllib.request.urlopen',side_effect=error),patch('lineage.search.EuropePMCClient.request',return_value={'hitCount':0,'resultList':{'result':[]}}):
            result=search('EGFR transformation')
        self.assertEqual(result['actual_provider'],'Europe PMC')
        self.assertNotIn('unit-test-only-key',json.dumps(result))
        self.assertEqual(result['attempts'][0]['http_status'],401)


if __name__=='__main__':unittest.main()
