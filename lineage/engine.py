"""Keep reported phenotype, clonal origin, EGFR dependency and treatment separate.

This consumes expert annotations. It does not inspect slides, call variants,
validate functional experiments, establish clonality or prescribe treatment.
"""
from __future__ import annotations

import copy

from rasmapk.engine import validate_input as validate_context
from rasmapk.knowledge import citations
from .knowledge import load_knowledge

BASELINE_CATEGORIES = {'adenocarcinoma', 'adenosquamous', 'mixed', 'sclc', 'squamous', 'other', 'unknown'}
CATEGORIES = {'adenocarcinoma', 'sclc', 'squamous', 'lcnec', 'mixed', 'other', 'unknown'}
BASELINE_BOOLS = {'documented', 'components_reviewed'}
PATH_BOOLS = {'pathologist_reviewed', 'morphology_supports_category', 'integrated_diagnosis_confirmed', 'ihc_panel_reviewed', 'compared_with_baseline', 'ne_marker_positive', 'ki67_high', 'p40_positive'}
MOL_BOOLS = {'genomics_validated', 'matched_tissue_genomics', 'expert_clonality_reviewed', 'shared_private_or_structural_evidence', 'tp53_rb1_coaltered', 'rb_pathway_altered', 'dependency_experiment_validated', 'dependency_from_progression_sample', 'pdl1_high'}


def _boolean_fields(obj: dict, fields: set[str]) -> None:
    for field in fields:
        if field in obj and type(obj[field]) is not bool:
            raise ValueError(field + ' must be a JSON boolean')


def _enum(obj: dict, field: str, options: set[str], default='unknown') -> None:
    obj.setdefault(field, default)
    if obj[field] not in options:
        raise ValueError('Invalid ' + field)


def validate_input(document: dict) -> dict:
    fields = {'schema_version', 'case_label', 'context', 'baseline_pathology', 'progression_pathology', 'molecular'}
    if not isinstance(document, dict) or set(document) - fields:
        raise ValueError('Unknown top-level field')
    if document.get('schema_version') != '1.0':
        raise ValueError("schema_version must be '1.0'")
    for key in fields - {'schema_version', 'case_label'}:
        if not isinstance(document.get(key), dict):
            raise ValueError(key + ' must be an object')
    if 'case_label' in document and (not isinstance(document['case_label'], str) or len(document['case_label']) > 200):
        raise ValueError('case_label must be a short string')
    data = copy.deepcopy(document)
    if set(data['context']) & {'histology', 'histology_confirmed_at_progression'}:
        raise ValueError('Put histology in progression_pathology; avoid contradictory duplicate fields')
    data['context'] = validate_context({'schema_version':'1.0','context':data['context'],'findings':[]})['context']
    b, p, m = data['baseline_pathology'], data['progression_pathology'], data['molecular']
    if set(b) - (BASELINE_BOOLS | {'category'}):
        raise ValueError('Unknown baseline pathology field')
    if set(p) - (PATH_BOOLS | {'category', 'sample_type', 'adequacy', 'mixed_components'}):
        raise ValueError('Unknown progression pathology field')
    mol_fields = MOL_BOOLS | {'original_driver_retained','detection_source','additional_shared_somatic_events','egfr_protein_expression','functional_egfr_dependence','dependency_model_source','dll3_expression','research_liquid_signature'}
    if set(m) - mol_fields:
        raise ValueError('Unknown molecular field')
    _boolean_fields(b, BASELINE_BOOLS); _boolean_fields(p, PATH_BOOLS); _boolean_fields(m, MOL_BOOLS)
    _enum(b, 'category', BASELINE_CATEGORIES)
    _enum(p, 'category', CATEGORIES)
    _enum(p, 'sample_type', {'tissue','cytology','plasma','csf','unknown'})
    _enum(p, 'adequacy', {'adequate','limited','unknown'})
    p.setdefault('mixed_components', [])
    if not isinstance(p['mixed_components'], list) or any(x not in CATEGORIES - {'mixed','unknown'} for x in p['mixed_components']):
        raise ValueError('mixed_components must use supported phenotype names')
    if p['category'] == 'mixed' and len(set(p['mixed_components'])) < 2:
        raise ValueError('Mixed category requires at least two explicitly reported components')
    if p['category'] != 'mixed' and p['mixed_components']:
        raise ValueError('Report multiple components under the mixed category')
    _enum(m, 'original_driver_retained', {'yes','no','unknown'})
    _enum(m, 'detection_source', {'matched_progression_tissue','plasma','other_lesion','unknown'})
    _enum(m, 'egfr_protein_expression', {'high','low','absent','unknown'})
    _enum(m, 'functional_egfr_dependence', {'supported_in_model','not_supported_in_model','not_tested','unknown'}, 'not_tested')
    _enum(m, 'dependency_model_source', {'patient_matched','generic_cell_line','unknown'})
    _enum(m, 'dll3_expression', {'positive','negative','unknown'})
    _enum(m, 'research_liquid_signature', {'sclc_like','squamous_like','none','unknown'})
    m.setdefault('additional_shared_somatic_events', [])
    if not isinstance(m['additional_shared_somatic_events'], list) or any(not isinstance(v,str) or not v.strip() or len(v)>200 for v in m['additional_shared_somatic_events']):
        raise ValueError('additional_shared_somatic_events must be short curated strings')
    return data


def analyze(document: dict, kb: dict | None = None) -> dict:
    data = validate_input(document)
    kb = kb or load_knowledge()
    c, b, p, m = data['context'], data['baseline_pathology'], data['progression_pathology'], data['molecular']
    alerts, requirements = [], []
    target = all(c.get(k) is True for k in ('prior_osimertinib','prior_platinum_pemetrexed','concurrent_osi_chemo','progressed_after_combination'))
    at_progression = c['collection_timing'] == 'at_progression'
    if not target:
        alerts.append('未确认同期奥希替尼+铂类/培美曲塞后进展；不会贴上该场景的治疗讨论路线。')
    if not at_progression:
        alerts.append('没有明确进展期取样，不能用旧标本判定本次组织学变化。')
    morph_sample = p['sample_type'] in {'tissue','cytology'}
    if not morph_sample:
        requirements.append('需要来自进展病灶、可评估形态的组织或充分细胞学标本；常规血浆DNA面板不能确诊细胞类型。')
    if p['adequacy'] != 'adequate':
        requirements.append('标本充分性尚未确认，需病理评估或再次取样。')
    for field, label in [('pathologist_reviewed','病理医师复核'),('morphology_supports_category','形态学支持'),('integrated_diagnosis_confirmed','整合病理诊断'),('ihc_panel_reviewed','结合形态的IHC面板审查')]:
        if p.get(field) is not True:
            requirements.append('缺少'+label+'；不通过单一标志物或基因事件自动诊断。')
    recognized = p['category'] in CATEGORIES - {'unknown','other'}
    if not recognized:
        requirements.append('整合病理类别尚未明确，不由标志物或转录程序代填。')
    pathology_supported = morph_sample and p['adequacy']=='adequate' and not requirements and recognized
    if pathology_supported:
        pathology_state = 'supplied_integrated_pathology_supported'
    elif p['category'] == 'unknown' and (p.get('ne_marker_positive') or p.get('ki67_high') or p.get('p40_positive')):
        pathology_state = 'marker_only_not_diagnostic'
    else:
        pathology_state = 'requires_pathology_confirmation'
    if p.get('ne_marker_positive') or p.get('ki67_high') or p.get('p40_positive'):
        alerts.append('NE、Ki67或p40结果需与形态和完整面板整合；单阳性不能确诊SCLC或鳞癌，NE阴性也不自动排除SCLC。')
    baseline_pure = b.get('documented') is True and b['category']=='adenocarcinoma' and b.get('components_reviewed') is True
    lineage_category = p['category'] in {'sclc','squamous','lcnec','mixed'}
    if pathology_supported and lineage_category and baseline_pure and p.get('compared_with_baseline') is True and at_progression:
        shift = 'documented_phenotypic_change_origin_requires_integration'
    elif pathology_supported and lineage_category:
        shift = 'preexisting_component_or_new_primary_not_excluded'
        alerts.append('基线混合成分、漏采样或第二原发尚不能排除；临床新检出不等同于药物新产生了一个克隆。')
    elif pathology_supported and p['category']=='adenocarcinoma':
        shift = 'no_documented_lineage_shift_in_sampled_lesion'
    else:
        shift = 'transformation_not_established'
    shared = bool(m['additional_shared_somatic_events'])
    paired = at_progression and c.get('baseline_available') is True and m.get('genomics_validated') is True and m.get('matched_tissue_genomics') is True and m['detection_source']=='matched_progression_tissue'
    if m.get('genomics_validated') is not True:
        clonal = 'molecular_provenance_requires_validation'
        clonal_note = '遗传检测尚未验证，不能把保留EGFR或共享事件升级为同源性证据。'
    elif m['detection_source']=='matched_progression_tissue' and not at_progression:
        clonal = 'paired_sample_timing_requires_review'
        clonal_note = '匹配进展组织声明与取样时序不一致，不能支持本次进展来源。'
    elif m.get('matched_tissue_genomics') is True and c.get('baseline_available') is not True:
        clonal = 'paired_genomics_inconsistent_with_history'
        clonal_note = '配对基因组声明缺少可用基线历史，需先核实样本对应关系。'
    elif paired and shared:
        if not (m.get('expert_clonality_reviewed') is True and m.get('shared_private_or_structural_evidence') is True):
            clonal = 'shared_events_require_clonal_review'
            clonal_note = '列表非空或另一常见热点不等于有质量的同源证据；需要专家审查的私有主干/结构事件及样本对应，程序不建立系统发育。'
        elif m['original_driver_retained']=='no':
            clonal = 'shared_events_with_egfr_discordance_require_review'
            clonal_note = '共享事件与EGFR阴性不一致，优先检查取样、肿瘤含量、检测盲区和克隆差异；不能由阴性单独排除转化。'
        else:
            clonal = 'shared_origin_supported_by_supplied_paired_genomics'
            clonal_note = '输入的配对组织及专家审查的私有/结构事件支持同源，但程序不独立验证系统发育、污染或第二原发。'
    elif m['original_driver_retained']=='yes' and m['detection_source']=='plasma':
        clonal = 'liquid_driver_not_localized_to_transformed_lesion'
        clonal_note = '血浆EGFR可来自未转化病灶，不能定位到该转化成分，也不能单独建立同源性。'
    elif m['original_driver_retained']=='yes':
        clonal = 'retained_driver_is_ancestry_clue_only'
        clonal_note = '保留创始EGFR支持谱系线索，但一个常见热点不能独立证明同源；需配对组织及更多共享事件。'
    else:
        clonal = 'clonal_origin_indeterminate'
        clonal_note = '缺少足够配对证据，保留或丢失EGFR都不能单独决定来源。'
    dependency = 'not_determined_by_dna_or_expression'
    dependency_note = 'EGFR DNA保留、蛋白表达和药物依赖不是同一层次；不自动决定继续或停用EGFR-TKI。'
    model_valid = at_progression and m.get('dependency_experiment_validated') is True and m['dependency_model_source']=='patient_matched' and m.get('dependency_from_progression_sample') is True
    if m['functional_egfr_dependence'] in {'supported_in_model','not_supported_in_model'}:
        if model_valid:
            dependency = 'model_support_only_not_clinical_sensitivity' if m['functional_egfr_dependence']=='supported_in_model' else 'model_lack_of_dependency_not_global_exclusion'
            dependency_note = '患者匹配进展模型提供功能线索，仍不证明临床获益或所有病灶的统一药敏；需审查模型、靶点作用与异质性。'
        else:
            dependency = 'functional_claim_requires_model_validation'
            dependency_note = '功能声明缺少进展期患者匹配模型或实验验证，不能升级为个体依赖性证据。'
    if m.get('tp53_rb1_coaltered') or m.get('rb_pathway_altered'):
        alerts.append('TP53/RB1或Rb通路异常是风险/机制线索，不是转化诊断；Rb轴改变也可能参与鳞状转化。')
    if m['research_liquid_signature'] in {'sclc_like','squamous_like'}:
        alerts.append('研究性cfDNA表观组/甲基化分类器可提示谱系，但不等同于常规突变检测，也尚不替代此处的整合病理确认。')
    if m.get('pdl1_high'):
        alerts.append('PD-L1高不能单独选用免疫治疗；转化EGFR背景与de novo SCLC/SCC不同，正负研究需按人群解释。')
    if m['dll3_expression']=='positive':
        alerts.append('DLL3高不等于tarlatamab药敏或满足现行标签；已有高表达转化病例进展，需专门人群与试验资格核查。')
    if c['progression_pattern']=='cns':
        alerts.append('中枢进展及脑脊液结果需单独评估；血浆阴性不能排除，其他病灶病理不能自动代表中枢。')
    if c['progression_pattern']=='oligoprogression':
        alerts.append('寡进展应评估局部治疗与多病灶异质性，不能因单病灶转化自动认为全身完全同型。')
    if c.get('prior_additional_therapies'):
        alerts.append('额外既往ADC、抗体或其他药物可能改变入组与安全性，既有TKI后队列不能直接外推。')
    routes = []
    if target and at_progression and pathology_supported:
        if p['category']=='sclc':
            routes.append({'id':'SCLC_PATHOLOGY_LED_REVIEW','strategy':'按已报告SCLC病理讨论系统治疗框架，例如铂类/依托泊苷及后线选择；已用铂、治疗间隔、体能和毒性须逐项评估。','status':'cohort_informed_mtb_discussion_not_prescription','limitations':'转化人群多为回顾研究，不能机械重复既往含铂；来源仍需整合，病理框架不证明克隆起源。','evidence_ids':citations(kb,['node01','node05'])})
            if m['dll3_expression']=='positive':
                routes.append({'id':'DLL3_TRIAL_REVIEW_ONLY','strategy':'核查DLL3相关药物/试验是否明确纳入转化EGFR人群及既往治疗要求。','status':'investigational_eligibility_review_only','limitations':'不从DLL3表达推定药敏、审批适用或当前招募；病例组合信号不是标准。','evidence_ids':citations(kb,['node05','node08'])})
        elif p['category']=='squamous':
            routes.append({'id':'SCC_PATHOLOGY_LED_REVIEW','strategy':'按鳞状病理重新讨论系统治疗与试验，评估化疗组织学适用性及安全性，不机械延续原腺癌框架。','status':'case_limited_mtb_discussion_not_prescription','limitations':'一般鳞癌随机试验不等于EGFR转化鳞癌证据；PD-L1、保留EGFR或个别响应均不能决定通用方案。','evidence_ids':citations(kb,['node03','node06'])})
        elif p['category']=='mixed':
            routes.append({'id':'MIXED_COMPONENT_MTB','strategy':'复核各病理成分、不同病灶与配对分子结果，讨论残余腺癌及转化成分的联合处理。','status':'heterogeneity_review_only','limitations':'不能把全部病灶按一个成分处理；保留EGFR不自动为组合增加TKI。','evidence_ids':citations(kb,['node01','node06','node07'])})
        elif p['category']=='lcnec':
            routes.append({'id':'LCNEC_EXPERT_REVIEW','strategy':'由胸部病理与MTB按LCNEC进一步分型和评估研究。','status':'specialist_review_only','limitations':'不与SCLC混为一类，不自动套用SCLC治疗证据。','evidence_ids':citations(kb,['node02','node08'])})
    if not routes:
        alerts.append('当前条件不足以形成该联合序列的病理导向讨论路线；这不等于没有治疗选择，应先补齐病理/时序与适用背景。')
    return {'schema_version':'1.0','engine_version':'1.0.0','intended_use':'research_only_not_clinically_validated',
            'evidence_window':kb['window'],'target_sequence_confirmed_by_input':target,
            'pathology_assessment':{'status':pathology_state,'reported_category':p['category'],'scope':'sampled_lesion_only','requirements':requirements,'evidence_ids':citations(kb,['node02','node03'])},
            'transformation_assessment':{'status':shift,'evidence_ids':citations(kb,['node01','node03','node04','node07'])},
            'clonality_assessment':{'status':clonal,'explanation':clonal_note,'evidence_ids':citations(kb,['node01','node07'])},
            'egfr_dependency_assessment':{'status':dependency,'explanation':dependency_note,'egfr_tki_decision':'not_automatically_decided','evidence_ids':citations(kb,['node01','node04','node05'])},
            'treatment_discussion_routes':routes,'alerts':list(dict.fromkeys(alerts)),
            'treatment_recommendations':[],'doses':[],'response_probabilities':None,
            'next_steps':['进展病灶组织/充分细胞学与基线材料配对，胸部病理医师整合形态和IHC。','结合DNA/RNA与必要的共享体细胞事件审查来源；常规血浆面板不替代形态，多组学液体分类器需独立验证。','将遗传保留、表达与功能依赖分别记录；关注未转化残留成分、病灶差异和检测盲区。','核实既往铂类、治疗间隔、PS、毒性、当前地区标签及专门转化队列试验资格。']}
