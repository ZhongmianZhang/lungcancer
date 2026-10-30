import copy
import unittest

from resistance.engine import InputError, assess, load_knowledge


def case():
    return {
        'schema_version': '1.0',
        'context': {'egfr_mutant_nsclc': True, 'progression_confirmed': True,
                    'treatment_setting': 'concurrent_osimertinib_platinum_pemetrexed',
                    'histology': 'adenocarcinoma', 'transformation_confirmed': False, 'progression_pattern': 'systemic'},
        'samples': [{'id': 'p', 'material': 'tissue', 'timepoint': 'progression', 'quality': 'adequate', 'pathway_inhibitor_exposure': 'no'}],
        'findings': [{'id': 'f', 'sample_id': 'p', 'gene': 'PIK3CA', 'alteration': 'activating_mutation',
                      'assay': 'DNA_NGS', 'significance': 'pathogenic', 'variant': 'H1047R'}],
    }


class ClinicalBoundaryTests(unittest.TestCase):
    def test_hotspot_is_candidate_not_diagnosis_or_prescription(self):
        report = assess(case())
        self.assertEqual([x['rule_id'] for x in report['candidates']], ['PIK3CA_HOTSPOT'])
        hit = report['candidates'][0]
        self.assertEqual(hit['causality'], 'not_established')
        self.assertIsNone(hit['treatment_recommendation'])
        self.assertFalse(hit['automatic_treatment_match'])
        self.assertIn('not_directly', hit['population_fit'])
        self.assertEqual(report['clinical_validation'], 'not_performed')

    def test_vus_never_becomes_hotspot_treatment_match(self):
        data = case()
        data['findings'][0]['significance'] = 'vus'
        self.assertEqual(assess(data)['candidates'], [])

    def test_arbitrary_variant_is_not_a_curated_hotspot(self):
        data = case()
        data['findings'][0]['variant'] = 'E999Q'
        self.assertEqual(assess(data)['candidates'], [])

    def test_gene_name_does_not_transfer_akt1_hotspot_to_akt2(self):
        data = case()
        data['findings'][0].update(gene='AKT2', variant='E17K')
        self.assertEqual(assess(data)['candidates'], [])

    def test_akt1_e17k_keeps_pan_tumor_population_boundary(self):
        data = case()
        data['findings'][0].update(gene='AKT1', variant='E17K')
        hit = assess(data)['candidates'][0]
        self.assertEqual(hit['rule_id'], 'AKT1_E17K')
        self.assertIn('indirect_pan_tumor', hit['treatment_evidence']['level'])

    def test_no_confirmed_progression_blocks_mechanism_inference(self):
        data = case()
        data['context']['progression_confirmed'] = False
        report = assess(data)
        self.assertEqual(report['status'], 'progression_not_confirmed')
        self.assertEqual(report['candidates'], [])

    def test_wrong_disease_is_out_of_scope_even_with_small_cell(self):
        data = case()
        data['context'].update(egfr_mutant_nsclc=False, histology='small_cell')
        report = assess(data)
        self.assertEqual(report['status'], 'out_of_scope')
        self.assertTrue(report['histology_review_required'])
        self.assertEqual(report['candidates'], [])

    def test_baseline_only_cannot_explain_acquired_resistance(self):
        data = case()
        data['samples'][0]['timepoint'] = 'baseline'
        report = assess(data)
        self.assertEqual(report['status'], 'no_progression_sample')
        self.assertEqual(report['candidates'], [])

    def test_preexisting_event_is_not_newly_acquired(self):
        data = case()
        data['samples'].append({'id': 'b', 'material': 'tissue', 'timepoint': 'baseline', 'quality': 'adequate'})
        baseline = data['findings'][0] | {'id': 'base', 'sample_id': 'b'}
        data['findings'].append(baseline)
        # Actual baseline finding overrides a contradictory absent label.
        data['findings'][0].update(baseline_status='absent', baseline_sample_id='b', baseline_comparable=True)
        self.assertEqual(assess(data)['candidates'][0]['temporal_interpretation'], 'preexisting_or_persistent')

    def test_baseline_absence_without_comparable_sample_stays_unknown(self):
        data = case()
        data['findings'][0]['baseline_status'] = 'absent'
        self.assertEqual(assess(data)['candidates'][0]['temporal_interpretation'], 'unknown')

    def test_valid_comparison_yields_newly_detected_not_proven_acquired(self):
        data = case()
        data['samples'].append({'id': 'b', 'material': 'tissue', 'timepoint': 'baseline', 'quality': 'adequate'})
        data['findings'][0].update(baseline_status='absent', baseline_sample_id='b', baseline_comparable=True)
        self.assertEqual(assess(data)['candidates'][0]['temporal_interpretation'], 'newly_detected_candidate_not_proven_acquired')

    def test_different_material_baseline_is_not_comparable_negative(self):
        data = case()
        data['samples'].append({'id': 'b', 'material': 'plasma', 'timepoint': 'baseline', 'quality': 'adequate'})
        data['findings'][0].update(baseline_status='absent', baseline_sample_id='b', baseline_comparable=True)
        self.assertEqual(assess(data)['candidates'][0]['temporal_interpretation'], 'unknown')

    def test_pten_single_copy_not_functional_loss_or_pi3ka_match(self):
        data = case()
        data['findings'][0].update(gene='PTEN', alteration='single_copy_loss')
        hit = assess(data)['candidates'][0]
        self.assertEqual(hit['support_level'], 'insufficient_for_functional_loss')
        self.assertEqual(hit['research_options_zh'], [])

    def test_pten_ihc_without_control_is_uninterpretable(self):
        data = case()
        data['findings'][0].update(gene='PTEN', alteration='protein_loss', assay='IHC')
        report = assess(data)
        self.assertEqual(report['candidates'], [])
        self.assertEqual(report['unmatched_findings'][0]['reason'], 'protein_loss_uninterpretable_without_internal_control')
        data['findings'][0]['internal_positive_control'] = True
        self.assertEqual(assess(data)['candidates'][0]['support_level'], 'functional_clue')

    def test_tsc_event_without_functional_annotation_does_not_match_everolimus(self):
        data = case()
        data['findings'][0].update(gene='TSC2', alteration='loss_of_function', variant='p.Q100*')
        self.assertEqual([x['rule_id'] for x in assess(data)['candidates']], ['TSC_SINGLE_EVENT'])
        self.assertEqual(assess(data)['candidates'][0]['research_options_zh'], [])
        data['findings'][0]['functional_confirmation'] = True
        hit = assess(data)['candidates'][0]
        self.assertIsNone(hit['treatment_recommendation'])
        self.assertEqual(hit['support_level'], 'requires_allelic_confirmation')
        self.assertEqual(hit['research_options_zh'], [])
        data['findings'][0]['alteration'] = 'biallelic_loss'
        self.assertIn('limited_activity', assess(data)['candidates'][0]['treatment_evidence']['level'])

    def test_fusion_requires_functional_annotation_and_orthogonal_review(self):
        data = case()
        data['findings'][0].update(gene='RET', alteration='fusion', assay='DNA_NGS')
        self.assertEqual(assess(data)['candidates'], [])
        data['findings'][0]['functional_confirmation'] = True
        self.assertEqual(assess(data)['candidates'][0]['support_level'], 'requires_fusion_structure_confirmation')
        data['findings'][0]['orthogonal_confirmation'] = True
        self.assertEqual(assess(data)['candidates'][0]['support_level'], 'requires_fusion_structure_confirmation')
        data['findings'][0].update(assay='RNA_NGS', fusion_in_frame=True, kinase_domain_retained=True)
        self.assertEqual(assess(data)['candidates'][0]['support_level'], 'molecular_candidate')

    def test_met_ihc_cannot_substitute_for_amplification(self):
        data = case()
        data['findings'][0].update(gene='MET', alteration='amplification', assay='IHC')
        with self.assertRaises(InputError):
            assess(data)

    def test_phosphorylation_cannot_infer_upstream_driver(self):
        data = case()
        data['findings'][0].update(gene='AKT', alteration='phosphorylation', phosphosite='S473', assay='PHOSPHO_IHC', significance='unknown')
        report = assess(data)
        self.assertEqual([hit['rule_id'] for hit in report['candidates']], ['AKT_PHOSPHORYLATION'])
        self.assertEqual(report['candidates'][0]['research_options_zh'], [])
        self.assertEqual(report['candidates'][0]['support_level'], 'pathway_activity_only')

    def test_phosphosites_do_not_merge_temporally(self):
        data = case()
        data['samples'].append({'id': 'b', 'material': 'tissue', 'timepoint': 'baseline', 'quality': 'adequate'})
        data['findings'][0].update(gene='AKT', alteration='phosphorylation', phosphosite='S473', assay='PHOSPHO_IHC', significance='unknown')
        data['findings'].append(data['findings'][0] | {'id': 'b_f', 'sample_id': 'b', 'phosphosite': 'T308'})
        self.assertEqual(assess(data)['candidates'][0]['temporal_interpretation'], 'unknown')

    def test_akt_inhibitor_exposure_retains_feedback_explanation(self):
        data = case()
        data['samples'][0]['pathway_inhibitor_exposure'] = 'yes'
        self.assertTrue(any('反馈' in x for x in assess(data)['warnings_zh']))

    def test_phosphorylation_without_site_rejected(self):
        data = case()
        data['findings'][0].update(alteration='phosphorylation', assay='PHOSPHO_IHC')
        with self.assertRaises(InputError):
            assess(data)

    def test_plasma_negative_is_not_a_negative_mechanism_diagnosis(self):
        data = case()
        data['samples'][0].update(material='plasma', quality='limited')
        data['findings'][0]['alteration'] = 'no_alteration_detected'
        report = assess(data)
        self.assertEqual(report['candidates'], [])
        self.assertTrue(any('阴性不排除' in x for x in report['priority_actions_zh']))

    def test_zero_tumor_fraction_cannot_generate_molecular_candidate(self):
        data = case()
        data['samples'][0]['tumor_fraction'] = 0
        self.assertEqual(assess(data)['candidates'], [])

    def test_pathology_transformation_has_priority_over_pathway(self):
        data = case()
        data['context'].update(histology='small_cell', transformation_confirmed=True)
        report = assess(data)
        self.assertEqual(report['status'], 'histology_review_priority')
        self.assertEqual(report['candidates'], [])

    def test_tp53_rb1_is_risk_not_transformation_diagnosis(self):
        data = case()
        for gene in ('TP53', 'RB1'):
            data['findings'].append({'id': gene, 'sample_id': 'p', 'gene': gene, 'alteration': 'loss_of_function', 'variant': 'p.Q100*', 'assay': 'DNA_NGS', 'significance': 'pathogenic'})
        report = assess(data)
        self.assertEqual(report['status'], 'hypothesis_generation')
        self.assertTrue(any('不能诊断小细胞' in x for x in report['priority_actions_zh']))

    def test_cns_only_progression_has_anatomical_review(self):
        data = case()
        data['context']['progression_pattern'] = 'cns_only'
        self.assertTrue(any('CNS' in x for x in assess(data)['priority_actions_zh']))

    def test_multiple_candidates_not_forced_into_single_driver(self):
        data = case()
        data['findings'].append({'id': 'met', 'sample_id': 'p', 'gene': 'MET', 'alteration': 'amplification', 'assay': 'FISH', 'significance': 'pathogenic', 'orthogonal_confirmation': True})
        report = assess(data)
        self.assertEqual(len(report['candidates']), 2)
        self.assertTrue(all(hit['causality'] == 'not_established' for hit in report['candidates']))

    def test_inputs_are_not_mutated(self):
        data = case()
        original = copy.deepcopy(data)
        assess(data)
        self.assertEqual(data, original)

    def test_inhibitory_irs_phosphorylation_is_direction_unknown_and_no_therapy(self):
        data = case()
        data['findings'][0].update(gene='IRS1', alteration='phosphorylation', phosphosite='S636/639', assay='PHOSPHO_IHC', significance='unknown')
        hit = assess(data)['candidates'][0]
        self.assertEqual(hit['support_level'], 'phospho_observation_direction_unknown')
        self.assertEqual(hit['research_options_zh'], [])

    def test_akt_and_s6_sites_are_isoform_and_gene_specific(self):
        for gene, wrong, right in [('AKT2','S473','S474'), ('RPS6KB1','S235/236','T389')]:
            data = case()
            data['findings'][0].update(gene=gene, alteration='phosphorylation', phosphosite=wrong, assay='PHOSPHO_IHC', significance='unknown')
            with self.subTest(gene=gene):
                self.assertEqual(assess(data)['candidates'], [])
                data['findings'][0]['phosphosite'] = right
                self.assertEqual(assess(data)['candidates'][0]['support_level'], 'pathway_activity_only')


class InputContractTests(unittest.TestCase):
    def test_missing_wrong_and_unknown_fields_rejected(self):
        for update in [{'context': None}, {'patient_name': 'not-permitted'}, {'schema_version': 1}]:
            with self.subTest(update=update):
                with self.assertRaises(InputError):
                    assess(case() | update)

    def test_boolean_strings_not_silently_truthy(self):
        data = case()
        data['context']['progression_confirmed'] = 'false'
        with self.assertRaises(InputError):
            assess(data)

    def test_invalid_fraction_rejected(self):
        for fraction in (-1, 1.1, float('nan'), float('inf'), True, '0.1'):
            data = case()
            data['samples'][0]['tumor_fraction'] = fraction
            with self.subTest(fraction=fraction), self.assertRaises(InputError):
                assess(data)

    def test_unknown_duplicate_sample_and_dangling_baseline(self):
        data = case()
        data['findings'][0]['sample_id'] = 'missing'
        with self.assertRaises(InputError):
            assess(data)
        data = case()
        data['samples'].append(copy.deepcopy(data['samples'][0]))
        with self.assertRaises(InputError):
            assess(data)
        data = case()
        data['findings'][0]['baseline_sample_id'] = 'p'
        with self.assertRaises(InputError):
            assess(data)

    def test_fish_cannot_call_snv_and_rna_cannot_call_biallelic_deletion(self):
        for alteration, assay in [('activating_mutation', 'FISH'), ('biallelic_loss', 'RNA_NGS')]:
            data = case()
            data['findings'][0].update(alteration=alteration, assay=assay)
            with self.subTest(assay=assay), self.assertRaises(InputError):
                assess(data)

    def test_loss_of_function_requires_variant_identity_for_comparison(self):
        data = case()
        data['findings'][0].update(gene='TSC2', alteration='loss_of_function')
        del data['findings'][0]['variant']
        with self.assertRaises(InputError):
            assess(data)


class KnowledgeIntegrityTests(unittest.TestCase):
    def test_all_sources_and_rules_have_auditable_status(self):
        kb = load_knowledge()
        self.assertEqual(len(kb['rules']), len({r['id'] for r in kb['rules']}))
        for rule in kb['rules']:
            self.assertTrue(rule['source_ids'])
            for key in rule['source_ids']:
                self.assertIn(key, kb['sources'])
                self.assertIn(key, rule['source_roles'])
            self.assertEqual(rule['treatment_evidence']['target_population_validation'], 'not_established')
        for source in kb['sources'].values():
            self.assertEqual(source['verification_status'], 'not_online_verified')
            self.assertTrue(source['url'].startswith('https://'))
        self.assertEqual(kb['sources']['RICTOR_2015_BACKGROUND']['period_status'], 'outside_window')
        self.assertFalse(kb['verification']['conference_search_completed'])


if __name__ == '__main__':
    unittest.main()
