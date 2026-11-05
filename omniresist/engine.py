"""Reproducible evidence-gap triage for annotated multi-omics reports.

No raw-read calling, independent experiment validation, learned response score,
network access or automatic treatment prescription occurs in case analysis.
"""
from __future__ import annotations

from jakstat.engine import egfr_context_confirmed
from rasmapk.engine import normalize_variant, CLASS2, CLASS3
from rasmapk.knowledge import citations
from .knowledge import load_knowledge
from .schema import validate_input, GENOMIC, READOUTS, FUNCTION_FLAGS

FUSION_KINASES = {'RET', 'ALK', 'ROS1', 'NTRK1', 'NTRK2', 'NTRK3', 'BRAF', 'FGFR1', 'FGFR2', 'FGFR3'}
EPIGENES = {'EZH2', 'EED', 'SUZ12', 'KDM5A', 'KDM5B', 'KDM1A', 'TET1', 'DNMT1', 'SMARCA4', 'ARID1A', 'YAP1', 'TEAD1'}
BLOCKED = {'assay_or_time_unresolved', 'event_not_validated_by_assay', 'not_somatic_tumor_source',
           'origin_unresolved', 'compartment_unresolved', 'coverage_or_confirmation_missing',
           'below_assay_validated_lod', 'benign_or_vus_not_driver', 'nonmalignant_state_readout',
           'clonal_relationship_unresolved', 'contradictory_negative_assay'}


def version_known(a):
    return a['platform_version'].strip().casefold() not in {'unknown', 'unspecified', '未知', '不明'}


def assess_assay(a):
    reasons = []
    if not version_known(a):
        reasons.append('检测版本未明，不能迁移其他版本的验证性能。')
    if a['status'] != 'passed':
        reasons.append('检测QC未完整通过。')
    if a['collection_timing'] != 'at_progression':
        reasons.append('不是明确的进展期标本。')
    if not a['validated_classes']:
        reasons.append('未声明经过验证的变异/读出类别。')
    if a.get('negative_result'):
        if not a['target_scope'].strip():
            reasons.append('未注明实际靶区/设计范围，不能扩大阴性解释范围。')
        if a.get('sensitivity_characterized') is not True:
            reasons.append('阴性结果缺少该版本及事件类别的灵敏度说明。')
        if a['modality'] in {'target_dna', 'wes', 'wgs', 'long_read_dna'} and a.get('genome_coverage_evaluated') is not True:
            reasons.append('阴性DNA检测缺少实际可检测区域/覆盖盲区评估；基因组广度不替代可检测性。')
        if a['sample_type'] in {'plasma', 'csf'} and ('tumor_fraction' not in a or 'validated_min_tumor_fraction' not in a):
            reasons.append('液体阴性缺少肿瘤分数及该实验室验证的解释条件。')
        if 'tumor_fraction' in a and 'validated_min_tumor_fraction' in a and a['tumor_fraction'] < a['validated_min_tumor_fraction']:
            reasons.append('肿瘤分数低于该实验室为该次解释提供的验证条件。')
        if a['modality'] in {'rna', 'scrna'} and a.get('rna_quality_passed') is not True:
            reasons.append('RNA质量未通过，不能把无融合信号当作排除。')
    return {'id': a['id'], 'platform_name': a['platform_name'], 'platform_version': a['platform_version'],
            'modality': a['modality'], 'sample_type': a['sample_type'],
            'target_scope': a['target_scope'], 'validated_classes': a['validated_classes'],
            'status': 'limitations_present' if reasons else 'within_declared_scope_only',
            'negative_interpretation': 'not_interpretable_as_exclusion' if reasons else 'only_within_declared_assay_scope_never_all_resistance',
            'limitations': reasons,
            'caution': '平台品牌/检测广度不自动证明该版本对每类事件的灵敏度；DNA阴性不能排除RNA、表观、病理或其他病灶机制。'}


def source_state(f, a):
    if a['status'] != 'passed' or a['collection_timing'] != 'at_progression' or not version_known(a):
        return 'assay_or_time_unresolved'
    if a.get('negative_result') is True:
        return 'contradictory_negative_assay'
    if f['alteration_type'] not in a['validated_classes']:
        return 'event_not_validated_by_assay'
    if f['tumor_origin'] in {'hematopoietic', 'germline'} or a['sample_type'] == 'blood_cells':
        return 'not_somatic_tumor_source'
    if f['alteration_type'] in GENOMIC and f['classification'] not in {'pathogenic', 'likely_pathogenic'}:
        return 'benign_or_vus_not_driver'
    if f['alteration_type'] in GENOMIC and (f['tumor_origin'] != 'confirmed' or (a['sample_type'] in {'plasma', 'csf'} and not f['tumor_origin_evidence'].strip())):
        return 'origin_unresolved'
    if f.get('compartment_confirmed') is not True or f['compartment'] in {'unknown', 'mixed'}:
        return 'compartment_unresolved'
    if f['compartment'] != 'malignant':
        return 'nonmalignant_state_readout'
    if f['tumor_origin'] != 'confirmed':
        return 'origin_unresolved'
    if f.get('egfr_clonal_link_confirmed') is not True or not f['egfr_clonal_link_evidence'].strip():
        return 'clonal_relationship_unresolved'
    if f.get('locus_coverage_confirmed') is not True or f.get('orthogonal_confirmed') is not True:
        return 'coverage_or_confirmation_missing'
    # This comparison concerns SNV/indel analytical validation, never a CNV threshold.
    if f['alteration_type'] in {'snv', 'indel'} and 'vaf' in f and 'lod_vaf' in a and f['vaf'] < a['lod_vaf']:
        return 'below_assay_validated_lod'
    return 'curated_observation_not_causality'


def rna_supported(f, assays):
    ids = [f['assay_id'], *f['supporting_assay_ids']]
    return f.get('rna_confirmed') is True and any(
        assays[i]['modality'] in {'rna', 'scrna'} and assays[i]['status'] == 'passed'
        and assays[i]['collection_timing'] == 'at_progression' and assays[i].get('rna_quality_passed') is True
        and version_known(assays[i]) and assays[i].get('negative_result') is not True
        and f['alteration_type'] in assays[i]['validated_classes'] for i in ids)


def identify(f, assays):
    gene, kind, variant = f['gene'], f['alteration_type'], normalize_variant(f['variant'])
    if kind in READOUTS:
        if kind in {'methylation', 'accessibility', 'histone_mark'} or gene in EPIGENES:
            return 'EPIGENETIC_STATE', ['node04', 'node05'], '表观状态可与持留/谱系变化相关；需验证细胞来源、因果方向及可逆性，不能据此选择EZH2/LSD1等药物。', []
        return 'CELL_STATE_OR_TME', ['node04', 'node05'], '表达、蛋白和多组学签名是状态线索；恶性细胞、CAF与免疫区室及方向须分开。', []
    if gene == 'EGFR':
        if kind in {'snv', 'indel'} and variant == 'C797S':
            needs = []
            if f.get('phase_confirmed') is not True or f['allele_phase'] not in {'cis', 'trans', 'not_applicable'} or not f['phase_partner'].strip():
                needs.append('C797S需说明相位对象及实测顺/反式，或经审查无相位对象；不能据此自动组合一/三代TKI。')
            return 'EGFR_C797S', ['node02', 'node07'], '精确C797S为靶内候选；EGFR敏感驱动保留、相位与并存旁路是不同问题。', needs
        if f.get('original_egfr_driver') is True:
            return 'RETAINED_EGFR_NOT_RESISTANCE_PROOF', ['node02', 'node07'], '已被专业注释为原EGFR驱动；仍检出不是新耐药机制或继续EGFR单药有效的证明。', []
        return 'EGFR_ALLELE_REVIEW', ['node02', 'node07'], '其他EGFR等位/结构事件不能一律归为原驱动；L718、G796等需精确等位、克隆与功能审查。', ['当前规则未完成该精确EGFR事件的因果与治疗证据分型，转入专业等位审查，不自动选药。']
    if gene == 'MET' and kind == 'amplification':
        needs = [] if all(f.get(k) is True for k in ('ploidy_reviewed', 'focal_amplification')) else ['需区分局灶MET扩增、染色体多体及纯度影响，不能用统一CN阈值或MET表达替代。']
        return 'MET_FOCAL_AMPLIFICATION', ['node01', 'node02', 'node07'], '经分型的MET扩增可为旁路候选；需核验克隆关系及专属序列临床证据。', needs
    if kind == 'fusion' and gene in FUSION_KINASES:
        needs = []
        if not rna_supported(f, assays) or f.get('in_frame') is not True or f.get('kinase_domain_retained') is not True:
            needs.append('需可追溯的进展期合格RNA支持、同框及激酶域保留；DNA断点或融合名称不能替代。')
        return 'KINASE_FUSION', ['node03', 'node07'], 'RNA与结构确认后的融合是旁路候选；de novo融合肺癌与EGFR获得性融合证据不能混用。', needs
    if gene == 'MET' and kind == 'splice':
        v = f['variant'].casefold().replace(' ', '').replace('_', '')
        needs = [] if v in {'exon14skipping', 'metexon14skipping'} and rna_supported(f, assays) else ['需RNA证实真实MET exon14跳跃，不从任意剪接区VUS推断。']
        return 'MET_EXON14_SPLICE', ['node03', 'node07'], '剪接事件与转录本需单独解释；METex14获批背景不自动覆盖EGFR联合耐药。', needs
    known_allele = ((gene == 'BRAF' and variant in ({'V600E'} | CLASS2 | CLASS3)) or
                    (gene in {'KRAS', 'NRAS', 'HRAS'} and variant in {'G12C', 'G12D', 'G12V', 'G13D', 'Q61H', 'Q61K', 'Q61R'}))
    if kind in {'snv', 'indel'} and known_allele:
        needs = [] if f['functional_direction'] == 'gain' else ['需明确具体等位变异的激活机制，不能只按致病注释选药。']
        if gene == 'BRAF' and variant in CLASS3:
            needs.append('BRAF class III需核查上游RAS/RTK依赖，不套用V600E模板。')
        return 'ALLELE_SPECIFIC_MAPK_BYPASS', ['node02', 'node07'], '旁路候选按精确等位分型；变异的肿瘤来源与耐药因果、临床药敏分开。', needs
    if gene in {'TP53', 'RB1'}:
        return 'TRANSFORMATION_RISK_NOT_DIAGNOSIS', ['node05', 'node07'], 'TP53/RB1异常可为风险线索；小细胞/鳞癌转化必须以进展组织病理确认。', []
    return 'NOVEL_GENOMIC_HYPOTHESIS', ['node02', 'node04'], '非编码、复杂SV、ecDNA或其他变异需独立注释、克隆归属及功能研究；WGS检出不等于可治疗驱动。', []


def strategy(mechanism):
    return {
        'EGFR_C797S': '经相位及伴随机制复核后，讨论第四代/其他机制匹配EGFR研究；不自动组合一代与三代TKI。',
        'MET_FOCAL_AMPLIFICATION': '讨论EGFR/MET双靶研究；核对savolitinib或tepotinib等研究的检测阈值、既往治疗与毒性，不能迁移为本序列标准。',
        'KINASE_FUSION': '讨论相应激酶与EGFR共同依赖的试验；RET的selpercatinib联合研究不等于所有融合或同期化疗后均有效。',
        'MET_EXON14_SPLICE': '按真实转录本与EGFR克隆关系审查MET相关研究；不能直接沿用de novo METex14适应证。',
        'ALLELE_SPECIFIC_MAPK_BYPASS': '转入RAS/MAPK等位分型模块及MTB；不把BRAF非V600或RAS扩增等同获批点突变背景。',
        'EPIGENETIC_STATE': '仅开展经模型验证的表观可塑性研究；EZH2等干预具有相反方向实例，不按表达/甲基化签名直接开药。',
        'CELL_STATE_OR_TME': '开展细胞区室和功能依赖研究，核查宿主保护作用与并行通路，避免经验性多靶叠加。',
        'NOVEL_GENOMIC_HYPOTHESIS': '先做结构/功能/克隆验证及独立变异重分类，再讨论机制匹配研究；不按VUS或网络相关性直接选药。',
    }[mechanism]


def bound_mechanism_evidence(row, kb):
    """Claim-specific primary sources; general interpretation guidelines never substitute.

    A screened citation still does not validate the target treatment sequence.
    Contextual node references remain available separately for critical reading.
    """
    mechanism, gene = row['mechanism'], row['gene']
    pmids = {
        'EGFR_C797S': {'25964297'},
        'MET_FOCAL_AMPLIFICATION': {'39793324', '40461383', '39089305'},
        'KINASE_FUSION': {'36996322', '30257958'} if gene == 'RET' else {'31761448'} if gene == 'NTRK1' else {'29883838'},
        'MET_EXON14_SPLICE': {'30639620'},
        # Exact MAPK drug evidence is in the linked rasmapk module, not supplied by WGS papers.
        'ALLELE_SPECIFIC_MAPK_BYPASS': set(),
        'EPIGENETIC_STATE': {
            'YAP1': {'31935369'}, 'TEAD1': {'31935369'}, 'TET1': {'27346347'},
            'KDM5A': {'27214401'}, 'KDM5B': {'27214401', '29934325'}, 'KDM1A': {'29934325'},
            'EZH2': {'32920200'}, 'EED': {'42611544'}, 'SMARCA4': {'37541244'}, 'ARID1A': {'37541244'},
        }.get(gene, set()),
        'CELL_STATE_OR_TME': {'32822576', '26828195', '26891683', '34381210'},
        'NOVEL_GENOMIC_HYPOTHESIS': {'32025007', '32025015', '32807987'},
    }.get(mechanism, set())
    dois = {'10.1200/jco.2025.43.17_suppl.lba8505'} if mechanism == 'MET_FOCAL_AMPLIFICATION' else set()
    return [r['id'] for r in kb['evidence'] if (str(r.get('pmid')) in pmids or str(r.get('doi', '')).casefold() in dois) and r['verification'] == 'metadata_abstract_checked']


def analyze(document, kb=None):
    data = validate_input(document); kb = kb or load_knowledge(); c = data['context']
    assays = {a['id']: a for a in data['assays']}
    assessments = [assess_assay(a) for a in data['assays']]
    target = egfr_context_confirmed(c) and all(c.get(k) is True for k in ('prior_osimertinib', 'prior_platinum_pemetrexed', 'concurrent_osi_chemo', 'progressed_after_combination'))
    current_adeno = c['histology'] == 'adenocarcinoma' and c.get('histology_confirmed_at_progression') is True
    gate = target and current_adeno and c['collection_timing'] == 'at_progression'
    alerts = []
    if not target:
        alerts.append('EGFR驱动及同期奥希替尼+铂/培美曲塞后进展未完整确认；其他治疗序列不可混同。')
    if not current_adeno:
        alerts.append('进展期组织病理未确认为腺癌；先核实小细胞/鳞状转化或其他病理，不由分子信号覆盖。')
    if c['collection_timing'] != 'at_progression':
        alerts.append('病例取样时序未确认在进展时，不把旧变化当作当前耐药。')
    if c['progression_pattern'] == 'cns':
        alerts.append('CNS进展需独立评估中枢暴露和合适病灶；血浆阴性不代表颅内阴性，CSF是否采集由临床决定。')
    if c['progression_pattern'] == 'oligoprogression':
        alerts.append('寡进展需病灶层面与局部治疗评估，单个分子线索不自动决定更换全身治疗。')
    if c.get('prior_additional_therapies'):
        alerts.append('既往抗体/ADC等需纳入具体试验资格、毒性及跨机制解释，不能只看EGFR注释。')
    rows, byid = [], {}
    for f in data['findings']:
        a = assays[f['assay_id']]; state = source_state(f, a)
        mechanism, nodes, explanation, needs = identify(f, assays)
        cautions = []
        if f['acquisition'] == 'acquired' and not (c.get('baseline_available') is True and f.get('baseline_comparison_confirmed') is True):
            cautions.append('获得性声明缺乏可比基线确认；不能证明它是治疗中新出现或唯一驱动。')
        if state in BLOCKED:
            status = state
        elif needs:
            status = 'event_specific_validation_needed'
        elif mechanism in {'RETAINED_EGFR_NOT_RESISTANCE_PROOF', 'TRANSFORMATION_RISK_NOT_DIAGNOSIS'}:
            status = 'background_or_risk_not_mechanism'
        elif mechanism in {'EPIGENETIC_STATE', 'CELL_STATE_OR_TME', 'NOVEL_GENOMIC_HYPOTHESIS'}:
            status = 'hypothesis_requires_functional_validation'
        else:
            status = 'curated_candidate_not_patient_causal_proof'
        row = {'id': f['id'], 'gene': f['gene'], 'variant': f['variant'], 'assay_id': f['assay_id'],
               'mechanism': mechanism, 'status': status, 'source_status': state, 'explanation': explanation,
               'validation_needed': needs, 'cautions': cautions, 'node_ids': nodes,
               'acquisition_status': 'claimed_acquired_not_proven' if cautions else f['acquisition'],
               'evidence_ids': citations(kb, nodes), 'clinical_predictive_validity': 'not_established_for_target_sequence'}
        rows.append(row); byid[f['id']] = row
    experiments = []
    for t in data['functional_tests']:
        linked = [byid[x] for x in t['finding_ids']]
        missing = [k for k in sorted(FUNCTION_FLAGS) if t.get(k) is not True]
        permitted = all(r['source_status'] not in BLOCKED and r['status'] == 'hypothesis_requires_functional_validation' for r in linked)
        qualified = not missing and permitted and c['collection_timing'] == 'at_progression'
        state = 'model_hypothesis_not_clinical_validation' if qualified and t['result'] == 'supports_dependency' else 'supplied_test_not_supportive_not_global_exclusion' if qualified and t['result'] == 'does_not_support' else 'requires_further_validation'
        experiments.append({'id': t['id'], 'finding_ids': t['finding_ids'], 'status': state, 'missing_experimental_conditions': missing})
        if state == 'model_hypothesis_not_clinical_validation':
            for r in linked:
                r['status'] = state
    directions = []
    allowed = {'curated_candidate_not_patient_causal_proof', 'model_hypothesis_not_clinical_validation'}
    refbyid = {r['id']: r for r in kb['evidence']}
    for r in rows:
        if r['status'] not in allowed or not gate:
            continue
        evidence_ids = list(dict.fromkeys(r['evidence_ids'] + citations(kb, ['node07'])))
        bound = bound_mechanism_evidence(r, kb)
        passed = [i for i in bound if refbyid[i]['ranking']['meets_journal_top80'] and refbyid[i]['verification'] == 'metadata_abstract_checked']
        conferences = [i for i in bound if refbyid[i]['design'] == 'conference_abstract' and refbyid[i]['verification'] == 'metadata_abstract_checked']
        # All journals are retained for transparent exploration; the strict set is separate.
        directions.append({'finding_id': r['id'], 'mechanism': r['mechanism'], 'strategy': strategy(r['mechanism']),
                           'status': 'investigational_review_only', 'evidence_ids': evidence_ids,
                           'mechanism_bound_evidence_ids': bound,
                           'conference_evidence_ids_separate': conferences,
                           'contextual_evidence_role': 'Node background and interpretation framework, not claim-specific clinical support.',
                           'rank_screened_evidence_ids': passed,
                           'jcr_requirement_status': 'has_screened_evidence_not_a_clinical_validation' if passed else 'unmet_pending_rank_table_or_eligible_source',
                           'limitations': '本序列临床增益及个体药敏未建立；原研究人群、检测阈值、当前标签/招募、既往抗体ADC及组合安全性必须独立核查。'})
    gaps = []
    good = [a for a in data['assays'] if a['status'] == 'passed' and a['collection_timing'] == 'at_progression' and version_known(a)]
    if not any(a['sample_type'] == 'tissue' for a in good):
        gaps.append({'code': 'TISSUE_AND_PATHOLOGY', 'reason': '缺少合格进展组织，液体活检无法判定组织学转化及全部低脱落病灶。', 'node_ids': ['node01', 'node05', 'node06']})
    if not any(a['modality'] in {'rna', 'scrna'} and a.get('rna_quality_passed') is True and {'fusion', 'splice'} <= set(a['validated_classes']) for a in good):
        gaps.append({'code': 'RNA_FUSION_SPLICE', 'reason': '未完整评估合格RNA融合/剪接；DNA panel或WGS不能替代真实转录本。', 'node_ids': ['node03']})
    if not any(a['modality'] in {'wgs', 'long_read_dna'} and a.get('genome_coverage_evaluated') is True and {'structural', 'noncoding'} <= set(a['validated_classes']) for a in good):
        gaps.append({'code': 'GENOME_STRUCTURE_NONCODING', 'reason': '复杂SV/非编码区域仍有范围或验证缺口；是否补WGS/长读应按临床价值评估，不能预设更敏感。', 'node_ids': ['node02']})
    if not any({'methylation', 'accessibility', 'histone_mark'} & set(a['validated_classes']) for a in good):
        gaps.append({'code': 'EPIGENOME_STATE', 'reason': '普通DNA测序未直接测量甲基化/染色质；相关研究检测没有自动用药价值。', 'node_ids': ['node04', 'node05']})
    if not any(a['modality'] in {'scrna', 'scatac', 'spatial'} and a.get('compartment_resolved') is True for a in good):
        gaps.append({'code': 'CELL_AND_SPATIAL_CONTEXT', 'reason': '肿瘤、免疫、CAF及病灶异质性未充分分区；不等于每人必须做单细胞/空间检测。', 'node_ids': ['node05']})
    if any(r['status'] == 'limitations_present' for r in assessments):
        gaps.append({'code': 'ANALYTICAL_OR_SAMPLING_LIMITS', 'reason': '至少一项检测存在QC、取样时序或阴性解释限制，先解决可解释性。', 'node_ids': ['node01', 'node06']})
    for g in gaps:
        g['evidence_ids'] = citations(kb, g['node_ids'])
    if not rows or not any(r['status'] in allowed for r in rows):
        alerts.append('当前仍属机制未明；需区分未检出、未测量、已检出未解释及非遗传状态，不等于没有可研究机制。')
    alerts.append('不能由“近一半未明”推算个体概率；检出率、可行动比例、实际用药比例与临床获益使用不同分母。')
    if kb['journal_selection']['table']['status'] == 'not_supplied':
        alerts.append('2025版JCR三学科前80筛选尚未完成：缺少可核验原表，当前文献为排名待核验研究集合。')
    return {'schema_version': '1.0', 'engine_version': '1.0.0', 'intended_use': 'research_not_clinically_validated',
            'evidence_window': kb['window'], 'journal_selection': kb['journal_selection'],
            'target_sequence_confirmed_by_input': target, 'clinical_context_gate_passed': gate,
            'assay_assessments': assessments, 'mechanism_hypotheses': rows, 'functional_assessments': experiments,
            'research_directions': directions,
            'strict_rank_screened_directions': [{**d, 'evidence_ids': d['rank_screened_evidence_ids']} for d in directions if d['rank_screened_evidence_ids']],
            'unresolved_dimensions': gaps, 'alerts': alerts,
            'coverage_caveat': '补检提示仅按所供检测声明生成；某维度没有提示不等于所有基因、区域、病灶或机制均已排除。',
            'treatment_recommendations': [], 'doses': [], 'response_probabilities': None,
            'patient_inputs_sent_to_network': False}
