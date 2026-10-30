"""Transparent hypothesis generation. This is not a diagnostic or prescribing model."""
import json
import re
from importlib.resources import files


class InputError(ValueError):
    """Invalid or ambiguous structured input."""


SETTINGS = {
    'concurrent_osimertinib_platinum_pemetrexed',
    'sequential_osimertinib_then_platinum', 'osimertinib_monotherapy', 'unknown',
}
ALTERATIONS = {
    'activating_mutation', 'resistance_mutation', 'amplification', 'fusion', 'loss_of_function',
    'biallelic_loss', 'single_copy_loss', 'protein_loss', 'phosphorylation',
    'overexpression', 'no_alteration_detected',
}
ASSAYS = {'DNA_NGS', 'RNA_NGS', 'FISH', 'IHC', 'PHOSPHO_IHC', 'PROTEOMICS', 'RNA_EXPRESSION'}
GENOMIC = {'activating_mutation', 'resistance_mutation', 'amplification', 'fusion', 'loss_of_function', 'biallelic_loss', 'single_copy_loss'}
ALTERATION_ASSAYS = {
    'activating_mutation': {'DNA_NGS', 'RNA_NGS'},
    'resistance_mutation': {'DNA_NGS', 'RNA_NGS'},
    'loss_of_function': {'DNA_NGS', 'RNA_NGS'},
    'amplification': {'DNA_NGS', 'FISH'},
    'biallelic_loss': {'DNA_NGS'}, 'single_copy_loss': {'DNA_NGS', 'FISH'},
    'fusion': {'DNA_NGS', 'RNA_NGS', 'FISH'},
    'protein_loss': {'IHC', 'PROTEOMICS'},
    'phosphorylation': {'PHOSPHO_IHC', 'PROTEOMICS'},
    'overexpression': {'IHC', 'RNA_EXPRESSION', 'PROTEOMICS'},
    'no_alteration_detected': ASSAYS,
}
DISCLAIMER = ('研究性规则工具，未经临床诊断或治疗预测验证；不估计耐药概率、不作确定诊断、不提供处方或剂量。'
              '所有结果需结合原始检测、病理、既往治疗和多学科评估。检出改变不等于已证明耐药因果。')


def load_knowledge():
    return json.loads(files('resistance.data').joinpath('knowledge.json').read_text(encoding='utf-8'))


def _object(value, required, allowed, label):
    if not isinstance(value, dict):
        raise InputError(f'{label} must be an object')
    missing, extra = set(required) - value.keys(), value.keys() - set(allowed)
    if missing or extra:
        raise InputError(f'{label}: missing={sorted(missing)}, unknown={sorted(extra)}')


def _enum(value, choices, label):
    if not isinstance(value, str) or value not in choices:
        raise InputError(f'{label} must be one of {sorted(choices)}')


def _bool(value, label):
    if type(value) is not bool:
        raise InputError(f'{label} must be a boolean, not a string or number')


def _text(value, label, max_length=120):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise InputError(f'{label} must be a nonempty string of at most {max_length} characters')


def validate_case(case):
    """Fail closed on unknown fields, malformed booleans, dangling samples and ambiguity."""
    _object(case, {'schema_version', 'context', 'samples', 'findings'},
            {'schema_version', 'context', 'samples', 'findings'}, 'case')
    if case['schema_version'] != '1.0':
        raise InputError('schema_version must be "1.0"')
    context = case['context']
    keys = {'egfr_mutant_nsclc', 'progression_confirmed', 'treatment_setting', 'histology',
            'transformation_confirmed', 'progression_pattern'}
    _object(context, keys, keys | {'treatment_phase'}, 'context')
    if 'treatment_phase' in context:
        _enum(context['treatment_phase'], {'induction', 'maintenance', 'post_treatment', 'unknown'}, 'treatment_phase')
    for key in ('egfr_mutant_nsclc', 'progression_confirmed', 'transformation_confirmed'):
        _bool(context[key], f'context.{key}')
    _enum(context['treatment_setting'], SETTINGS, 'treatment_setting')
    _enum(context['histology'], {'adenocarcinoma', 'small_cell', 'squamous', 'other', 'unknown'}, 'histology')
    _enum(context['progression_pattern'], {'systemic', 'oligoprogression', 'cns_only', 'unknown'}, 'progression_pattern')
    if context['transformation_confirmed'] and context['histology'] not in {'small_cell', 'squamous', 'other'}:
        raise InputError('Confirmed transformation requires the transformed histology, not adenocarcinoma/unknown')
    if not isinstance(case['samples'], list) or not case['samples'] or len(case['samples']) > 100:
        raise InputError('samples must contain 1–100 objects')
    samples = {}
    for sample in case['samples']:
        required = {'id', 'material', 'timepoint', 'quality'}
        _object(sample, required, required | {'tumor_fraction', 'pathway_inhibitor_exposure'}, 'sample')
        _text(sample['id'], 'sample.id', 80)
        if sample['id'] in samples:
            raise InputError('Duplicate sample id')
        _enum(sample['material'], {'tissue', 'plasma'}, 'sample.material')
        _enum(sample['timepoint'], {'baseline', 'progression'}, 'sample.timepoint')
        _enum(sample['quality'], {'adequate', 'limited', 'unknown'}, 'sample.quality')
        if 'pathway_inhibitor_exposure' in sample:
            _enum(sample['pathway_inhibitor_exposure'], {'yes', 'no', 'unknown'}, 'pathway_inhibitor_exposure')
        fraction = sample.get('tumor_fraction')
        if 'tumor_fraction' in sample and (type(fraction) not in {int, float} or not 0 <= fraction <= 1):
            raise InputError('tumor_fraction must be a finite fraction from 0 to 1')
        samples[sample['id']] = sample
    if not isinstance(case['findings'], list) or len(case['findings']) > 10000:
        raise InputError('findings must be a list of at most 10000 objects')
    seen = set()
    for finding in case['findings']:
        required = {'id', 'sample_id', 'gene', 'alteration', 'assay', 'significance'}
        optional = {'variant', 'phosphosite', 'functional_confirmation', 'orthogonal_confirmation',
                    'internal_positive_control', 'baseline_status', 'baseline_sample_id', 'baseline_comparable',
                    'fusion_in_frame', 'kinase_domain_retained'}
        _object(finding, required, required | optional, 'finding')
        _text(finding['id'], 'finding.id', 80)
        if finding['id'] in seen:
            raise InputError('Duplicate finding id')
        seen.add(finding['id'])
        _text(finding['sample_id'], 'finding.sample_id', 80)
        if finding['sample_id'] not in samples:
            raise InputError('Unknown finding.sample_id')
        if not isinstance(finding['gene'], str) or not re.fullmatch(r'[A-Z][A-Z0-9]{0,15}', finding['gene']):
            raise InputError('gene must be an uppercase symbol (pan-AKT protein may use AKT)')
        _enum(finding['alteration'], ALTERATIONS, 'finding.alteration')
        _enum(finding['assay'], ASSAYS, 'finding.assay')
        _enum(finding['significance'], {'pathogenic', 'likely_pathogenic', 'vus', 'unknown'}, 'significance')
        for key in ('variant', 'phosphosite'):
            if key in finding:
                _text(finding[key], f'finding.{key}')
        for key in ('functional_confirmation', 'orthogonal_confirmation', 'internal_positive_control', 'baseline_comparable', 'fusion_in_frame', 'kinase_domain_retained'):
            if key in finding:
                _bool(finding[key], f'finding.{key}')
        if finding['alteration'] in {'activating_mutation', 'resistance_mutation', 'loss_of_function'} and 'variant' not in finding:
            raise InputError('Mutation requires an explicit protein variant')
        if finding['alteration'] == 'phosphorylation' and 'phosphosite' not in finding:
            raise InputError('phosphorylation requires phosphosite; total expression is not phosphorylation')
        if finding['assay'] not in ALTERATION_ASSAYS[finding['alteration']]:
            raise InputError(f'Assay {finding["assay"]} cannot establish {finding["alteration"]}')
        if 'baseline_status' in finding:
            _enum(finding['baseline_status'], {'present', 'absent', 'not_assessed'}, 'baseline_status')
        if 'baseline_sample_id' in finding:
            _text(finding['baseline_sample_id'], 'baseline_sample_id', 80)
            baseline = samples.get(finding['baseline_sample_id'])
            if not baseline or baseline['timepoint'] != 'baseline':
                raise InputError('baseline_sample_id must point to an actual baseline sample')
        if finding.get('baseline_comparable') and 'baseline_sample_id' not in finding:
            raise InputError('baseline_comparable requires baseline_sample_id')
    return samples


def _variant(finding):
    return finding.get('variant', '').removeprefix('p.')


def _matches(finding, rule):
    if finding['gene'] not in rule['genes'] or finding['alteration'] not in rule['alterations']:
        return False
    if finding['assay'] not in rule['assays']:
        return False
    if finding['alteration'] in GENOMIC and finding['significance'] == 'vus':
        return False
    if rule.get('pathogenic_required') and finding['significance'] not in {'pathogenic', 'likely_pathogenic'}:
        return False
    if 'variants' in rule and _variant(finding) not in rule['variants']:
        return False
    if 'phosphosites' in rule and finding.get('phosphosite') not in rule['phosphosites']:
        return False
    if 'phosphosites_by_gene' in rule and finding.get('phosphosite') not in rule['phosphosites_by_gene'].get(finding['gene'], []):
        return False
    if rule.get('functional_required') and not finding.get('functional_confirmation'):
        return False
    return True


def _temporal(finding, case, samples):
    def same(other):
        return (other['gene'], other['alteration'], _variant(other), other.get('phosphosite')) == (finding['gene'], finding['alteration'], _variant(finding), finding.get('phosphosite'))
    if finding.get('baseline_status') == 'present' or any(
        samples[other['sample_id']]['timepoint'] == 'baseline' and same(other) for other in case['findings']
    ):
        return 'preexisting_or_persistent' if finding['alteration'] in GENOMIC else 'baseline_signal_also_observed_not_clonal_identity'
    baseline = samples.get(finding.get('baseline_sample_id'))
    if (finding.get('baseline_status') == 'absent' and baseline and finding.get('baseline_comparable')
            and baseline['quality'] == 'adequate' and baseline.get('tumor_fraction') != 0
            and baseline['material'] == samples[finding['sample_id']]['material']):
        return ('newly_observed_activity_not_genetic_acquisition' if finding['alteration'] not in GENOMIC
                else 'newly_detected_candidate_not_proven_acquired')
    return 'unknown'


def assess(case, knowledge=None):
    samples = validate_case(case)
    kb = load_knowledge() if knowledge is None else knowledge
    context = case['context']
    report = {
        'schema_version': '1.0', 'tool_version': '0.1.0', 'research_only': True,
        'disclaimer_zh': DISCLAIMER, 'status': 'hypothesis_generation',
        'treatment_setting': context['treatment_setting'],
        'treatment_phase': context.get('treatment_phase', 'unknown'),
        'literature_window': kb['literature_window'],
        'evidence_verification': kb['verification'],
        'clinical_validation': 'not_performed', 'causal_diagnosis': 'not_established',
        'warnings_zh': [], 'priority_actions_zh': [], 'candidates': [], 'unmatched_findings': [],
    }
    warnings, actions = report['warnings_zh'], report['priority_actions_zh']
    warnings.append('多个规则/读数命中不代表多个独立耐药克隆；本工具不作分子分型概率或药物获益排序。')
    if any(s['verification_status'] != 'full_text_verified' for s in kb['sources'].values()):
        warnings.append('规则库含尚未完成全文核验的人工整理来源；不能把规则命中当作论文已证实或患者治疗建议。')
    if context['treatment_setting'] == 'concurrent_osimertinib_platinum_pemetrexed':
        warnings.append('当前规则库尚无已在线核验的同步奥希替尼＋铂/培美后进展节点匹配挽救证据；单药后研究仅为间接证据。')
    elif context['treatment_setting'] in {'unknown', 'sequential_osimertinib_then_platinum'}:
        warnings.append('分别确认同期联合与序贯暴露，不能从曾用过两类药物推断发生于同步联合方案之后。')
    progression_samples = [s for s in samples.values() if s['timepoint'] == 'progression']
    if not context['egfr_mutant_nsclc']:
        report['status'] = 'out_of_scope'
        actions.append('适用范围为已确诊 EGFR 突变 NSCLC；本工具不判定基础诊断。')
    elif not context['progression_confirmed']:
        report['status'] = 'progression_not_confirmed'
        actions.append('先核实临床/影像进展及治疗暴露；不在尚未确认进展时判定耐药机制。')
    elif not progression_samples:
        report['status'] = 'no_progression_sample'
        actions.append('仅有基线结果不能用于识别进展时耐药机制。')
    report['histology_review_required'] = context['transformation_confirmed'] or context['histology'] == 'small_cell'
    if report['histology_review_required']:
        if report['status'] == 'hypothesis_generation':
            report['status'] = 'histology_review_priority'
        actions.append('病理确认的组织转化/小细胞形态优先由 MDT 评估相应路径；不以通路联合替代组织学处理。')
    if context['progression_pattern'] in {'oligoprogression', 'cns_only'}:
        actions.append('先评估局限/CNS 进展、局部处理及药物暴露；不能把解剖学进展直接归因于全身 PI3K 通路耐药。')
    tissue = [s for s in progression_samples if s['material'] == 'tissue']
    if not tissue:
        actions.append('缺少进展组织：安全可行时组织病理＋DNA/RNA 互补检测；血浆阴性不排除扩增、融合、蛋白激活或组织转化。')
    for sample in progression_samples:
        if sample['quality'] != 'adequate' or sample.get('tumor_fraction') == 0:
            warnings.append(f'样本 {sample["id"]} 质量/肿瘤含量受限，阴性不可用于排除；阳性仍需技术复核。')
        if sample.get('pathway_inhibitor_exposure', 'unknown') != 'no':
            warnings.append(f'样本 {sample["id"]} 的 PI3K/AKT/mTOR 抑制剂暴露为 {sample.get("pathway_inhibitor_exposure", "unknown")}；pAKT/pERK 回升可有反馈/药效解释，需核实取样时用药与前处理。')
    suppressors = {f['gene'] for f in case['findings'] if samples[f['sample_id']]['timepoint'] == 'progression'
                   and f['gene'] in {'TP53', 'RB1'} and f['significance'] in {'pathogenic', 'likely_pathogenic'}
                   and f['alteration'] in {'loss_of_function', 'biallelic_loss'}}
    if suppressors == {'TP53', 'RB1'}:
        actions.append('TP53/RB1 并存仅提示转化风险；不同样本/克隆事件不能自动合并，必须以组织病理确认，不能诊断小细胞转化。')
    blocked = report['status'] != 'hypothesis_generation'
    for finding in case['findings']:
        sample = samples[finding['sample_id']]
        reason = None
        if sample['timepoint'] != 'progression':
            reason = 'baseline_only_not_a_progression_mechanism'
        elif blocked:
            reason = 'global_clinical_context_gate'
        elif sample.get('tumor_fraction') == 0:
            reason = 'no_measurable_tumor_requires_sample_review'
        elif finding['alteration'] == 'protein_loss' and not finding.get('internal_positive_control'):
            reason = 'protein_loss_uninterpretable_without_internal_control'
        else:
            matches = [r for r in kb['rules'] if _matches(finding, r)]
            if not matches:
                reason = 'no_supported_rule_or_insufficient_annotation'
            for rule in matches:
                confirmations = list(rule['confirmation_zh'])
                level = rule['signal_level']
                if sample['quality'] != 'adequate' or sample.get('tumor_fraction') == 0:
                    level = 'requires_confirmation'
                if finding['alteration'] in {'amplification', 'fusion'} and not finding.get('orthogonal_confirmation'):
                    level = 'requires_confirmation'
                if finding['alteration'] == 'fusion' and (
                    finding['assay'] != 'RNA_NGS' or not finding.get('fusion_in_frame') or not finding.get('kinase_domain_retained')
                ):
                    level = 'requires_fusion_structure_confirmation'
                if finding['alteration'] == 'protein_loss' and not finding.get('internal_positive_control'):
                    level = 'requires_confirmation'
                    confirmations.append('蛋白缺失必须核对同片内部阳性对照与肿瘤细胞来源。')
                temporal = _temporal(finding, case, samples)
                if temporal == 'preexisting_or_persistent':
                    confirmations.append('基线已存在/持续存在的改变不能仅凭检出称为新获得耐药；可为共存背景或选择后的克隆。')
                sources = [kb['sources'][key] | {'id': key, 'rule_support_role': rule['source_roles'][key]} for key in rule['source_ids']]
                report['candidates'].append({
                    'rule_id': rule['id'], 'node_zh': rule['node_zh'], 'finding_id': finding['id'],
                    'gene': finding['gene'], 'alteration': finding['alteration'],
                    'sample_id': finding['sample_id'], 'assay': finding['assay'],
                    'variant': finding.get('variant'), 'phosphosite': finding.get('phosphosite'),
                    'support_level': level, 'temporal_interpretation': temporal,
                    'mechanism_zh': rule['mechanism_zh'], 'causality': 'not_established',
                    'confirmation_needed_zh': confirmations,
                    'mechanism_evidence': rule['mechanism_evidence'],
                    'treatment_evidence': rule['treatment_evidence'],
                    'population_fit': 'not_directly_established_for_concurrent_combination_failure'
                        if context['treatment_setting'] == 'concurrent_osimertinib_platinum_pemetrexed'
                        else 'requires_study_level_population_review',
                    'research_options_zh': rule['research_options_zh'],
                    'treatment_recommendation': None, 'automatic_treatment_match': False,
                    'limitations_zh': rule['limitations_zh'], 'sources': sources,
                })
        if reason:
            report['unmatched_findings'].append({'finding_id': finding['id'], 'reason': reason})
    if not report['candidates'] and not blocked:
        actions.append('未命中不等于没有耐药机制或通路阴性；评估输入覆盖、样本与替代机制，不据此排除。')
    actions.append('并行评估 EGFR 靶内改变、组织转化和非 PI3K 机制；本工具不证明任何通路为主要耐药原因。')
    return report
