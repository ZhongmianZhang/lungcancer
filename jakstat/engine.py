"""Deterministic research triage of curated observations and dependency assays.

No patient-network requests, slide/variant calling, clinical response prediction,
dosage generation or automatic drug prescribing. Input annotations are trusted
claims to review, not experiments independently verified by this program.
"""
from __future__ import annotations

import copy
import re

from rasmapk.engine import validate_input as validate_context
from rasmapk.knowledge import citations
from .knowledge import load_knowledge

LIGANDS={'IL6','IL6R','IL6ST','OSM','OSMR','LIF','LIFR','IL11','IL11RA'}
KINASES={'JAK1','JAK2','JAK3','TYK2'}
IMMUNE={'STAT1','STAT2','STAT5A','STAT5B','STAT6','IFNAR1','IFNAR2','IFNGR1','IFNGR2','IFNG','IL4','IL4R','IL13','IL13RA1','IL13RA2'}
NEGATIVE={'SOCS1','SOCS3','PIAS1','PIAS3','PTPN1','PTPN2','PTPN11'}
CROSS={'EGFR','MET','AXL','SRC','YAP1','MAPK1','MAPK3','KRAS','PIK3CA','AKT1','MTOR','BCL2L1','MCL1','BIRC5','MYC','LAMA5','PTK2','BCL2','TGFBR1'}
DNA={'snv','indel','amplification','loss_of_function'}
AXES={'IL6_JAK_STAT3','OSM_LIF_IL11_JAK_STAT3','JAK_STAT3','STAT3_JAK_INDEPENDENT','IFN_STAT1_2','STAT5_6','NEGATIVE_FEEDBACK','CROSSTALK','unknown'}
PROOF_FLAGS={'validated','compartment_resolved','selective_target_engagement','orthogonal_perturbation','rescue_or_reconstitution','resistance_phenotype_measured','downstream_axis_measured','jak_independence_tested'}
OBS_FLAGS={'assay_validated','compartment_confirmed','amplification_confirmed','loss_effect_confirmed'}
GENE_NODES=[(LIGANDS,'node01'),(KINASES,'node02'),({'STAT3'},'node03'),(IMMUNE,'node04'),(NEGATIVE,'node05'),(CROSS,'node06')]
AXIS_NODES={'IL6_JAK_STAT3':['node01','node02','node03'], 'OSM_LIF_IL11_JAK_STAT3':['node01','node02','node03'],
            'JAK_STAT3':['node02','node03'],'STAT3_JAK_INDEPENDENT':['node03','node06'],
            'IFN_STAT1_2':['node04'],'STAT5_6':['node04'],'NEGATIVE_FEEDBACK':['node05'],'CROSSTALK':['node06'],'unknown':['node07']}


def egfr_context_confirmed(c):
    label=re.sub(r'[\s_-]+','',str(c.get('egfr_driver','')).casefold())
    non_mutant={'','unknown','negative','none','wt','egfrwt','wildtype','egfrwildtype','notdetected','nottested','未检出','野生型','egfr野生型','无egfr突变'}
    return c.get('egfr_driver_confirmed') is True and label not in non_mutant


def validate_input(document):
    if not isinstance(document,dict) or set(document)-{'schema_version','case_label','context','observations','dependency_tests'}:
        raise ValueError('Unknown top-level field')
    if document.get('schema_version')!='1.0' or not isinstance(document.get('context'),dict):
        raise ValueError('schema_version 1.0 and context object are required')
    if not isinstance(document.get('observations'),list) or len(document['observations'])>200:
        raise ValueError('observations must be a list of at most 200 curated records')
    data=copy.deepcopy(document)
    ctx=copy.deepcopy(data['context']);confirmed=ctx.pop('egfr_driver_confirmed',False)
    if type(confirmed) is not bool:raise ValueError('egfr_driver_confirmed must be a JSON boolean')
    base={'schema_version':'1.0','context':ctx,'findings':[]}
    if 'case_label' in data:base['case_label']=data['case_label']
    data['context']=validate_context(base)['context']
    data['context']['egfr_driver_confirmed']=confirmed
    if confirmed and not egfr_context_confirmed(data['context']):raise ValueError('Confirmed EGFR driver contradicts missing/negative driver annotation')
    fields={'id','gene','kind','level','site','variant','sample_type','compartment','tumor_origin','tumor_origin_evidence','classification','acquisition'}|OBS_FLAGS
    enums={'kind':DNA|{'expression','phosphoprotein','cytokine','signature'},
           'level':{'high','low','normal','unknown'},'sample_type':{'tissue','plasma','blood_cells','csf','model','unknown'},
           'compartment':{'tumor','immune','stromal','serum','mixed','unknown'},
           'tumor_origin':{'confirmed','unconfirmed','hematopoietic','unknown'},
           'classification':{'pathogenic','likely_pathogenic','vus','benign','likely_benign','unknown'},
           'acquisition':{'acquired','baseline','unknown'}}
    seen=set()
    for o in data['observations']:
        if not isinstance(o,dict) or set(o)-fields:raise ValueError('Unknown observation field')
        if not isinstance(o.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',o['id']) or o['id'] in seen:raise ValueError('Observation IDs must be safe and unique')
        seen.add(o['id'])
        if not isinstance(o.get('gene'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,30}',o['gene']):raise ValueError('A gene symbol is required')
        o['gene']=o['gene'].upper()
        for key,values in enums.items():
            o.setdefault(key,'unknown')
            if o[key] not in values:raise ValueError('Invalid observation '+key)
        for key in OBS_FLAGS:
            if key in o and type(o[key]) is not bool:raise ValueError(key+' must be a JSON boolean')
        for key in ('site','variant','tumor_origin_evidence'):
            o.setdefault(key,'')
            if not isinstance(o[key],str) or len(o[key])>1000:raise ValueError(key+' must be a short string')
    data.setdefault('dependency_tests',[])
    if not isinstance(data['dependency_tests'],list) or len(data['dependency_tests'])>50:raise ValueError('dependency_tests must be a list of at most 50 records')
    dep_ids=set()
    for d in data['dependency_tests']:
        if not isinstance(d,dict) or set(d)-({'id','axis','observation_ids','model_source','result','description'}|PROOF_FLAGS):raise ValueError('Unknown dependency field')
        if not isinstance(d.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',d['id']) or d['id'] in dep_ids:raise ValueError('Dependency IDs must be safe and unique')
        dep_ids.add(d['id'])
        if d.get('axis') not in AXES:raise ValueError('Invalid dependency axis')
        if not isinstance(d.get('observation_ids'),list) or not d['observation_ids'] or any(not isinstance(x,str) or x not in seen for x in d['observation_ids']):raise ValueError('Dependency observation links must resolve')
        if len(d['observation_ids'])!=len(set(d['observation_ids'])):raise ValueError('Duplicate dependency observation link')
        if d.get('model_source') not in {'patient_matched_progression','generic_model','unknown'}:raise ValueError('Invalid model_source')
        if d.get('result') not in {'supports_dependency','does_not_support','unknown'}:raise ValueError('Invalid experiment result')
        for key in PROOF_FLAGS:
            if key in d and type(d[key]) is not bool:raise ValueError(key+' must be a JSON boolean')
        d.setdefault('description','')
        if not isinstance(d['description'],str) or len(d['description'])>2000:raise ValueError('description must be a short string')
    return data


def node_for(gene):
    return next((node for genes,node in GENE_NODES if gene in genes),'node07')


def observation_state(o):
    gene,kind=o['gene'],o['kind'];notes=[]
    node=node_for(gene)
    if node=='node07':return 'outside_curated_scope',notes
    if kind in DNA and (o['tumor_origin']=='hematopoietic' or o['sample_type']=='blood_cells'):
        return 'not_tumor_resistance_source',['血细胞克隆/CHIP/血液病来源不能当作NSCLC肿瘤耐药；需要临床定源。']
    if kind in DNA and o['classification'] in {'benign','likely_benign'}:return 'benign_not_dependency',notes
    if kind in DNA and o['classification'] not in {'pathogenic','likely_pathogenic'}:return 'unclassified_variant_not_driver',notes
    if o.get('assay_validated') is not True:return 'assay_requires_validation',notes
    if kind in DNA and (o['tumor_origin']!='confirmed' or (o['sample_type'] in {'plasma','csf'} and not o['tumor_origin_evidence'].strip())):
        return 'molecular_origin_requires_validation',['JAK2/STAT等血浆变异需组织或必要的配对白细胞等定源；VAF或与EGFR共检出不足。']
    if kind=='loss_of_function' and gene not in NEGATIVE:
        return 'loss_is_not_pathway_activation',['JAK/STAT正向成分失活不能按激活或JAK药敏解释；IFN免疫逃逸与EGFR耐药终点不同。']
    if o.get('compartment_confirmed') is not True or o['compartment'] in {'mixed','unknown'}:
        return 'cell_compartment_unresolved',['整体RNA/IHC不定位到肿瘤细胞；须分区审查免疫/基质/恶性细胞。']
    if o['compartment']!='tumor':
        return 'systemic_or_microenvironment_signal',['非肿瘤区室的信号可能参与TME，但需与肿瘤接收和耐药表型建立功能联系，不能简单忽略或当作肿瘤驱动。']
    if kind=='amplification' and o.get('amplification_confirmed') is not True:return 'amplification_requires_validation',notes
    if kind=='loss_of_function' and gene in NEGATIVE:
        if o.get('loss_effect_confirmed') is not True:return 'feedback_loss_requires_validation',notes
        return 'feedback_change_not_drug_sensitivity',['SOCS/PTP等失活的功能方向与区室有关；不自动等于JAK抑制药敏。']
    if kind in {'expression','phosphoprotein','cytokine','signature'}:
        if gene=='STAT3':notes.append('Y705/S727、核/线粒体/非磷酸化STAT3不可互换；pSTAT3不指认JAK来源，低STAT3也不排除其他耐药分叉。')
        return 'signal_readout_not_dependency',notes
    return 'tumor_alteration_not_dependency',['肿瘤来源及致病注释不等于该变异造成当前耐药，更不等于该序列的药敏。']


def axis_requirements(axis,genes):
    if axis=='IL6_JAK_STAT3':return bool(genes&{'IL6','IL6R','IL6ST'}) and 'STAT3' in genes and bool(genes&{'JAK1','JAK2','TYK2'})
    if axis=='OSM_LIF_IL11_JAK_STAT3':return bool(genes&{'OSM','OSMR','LIF','LIFR','IL11','IL11RA'}) and 'STAT3' in genes and bool(genes&{'JAK1','JAK2','TYK2'})
    if axis=='JAK_STAT3':return 'STAT3' in genes and bool(genes&KINASES)
    if axis=='STAT3_JAK_INDEPENDENT':return 'STAT3' in genes and bool(genes&{'SRC','EGFR','MET','AXL'})
    if axis=='IFN_STAT1_2':return bool(genes&{'STAT1','STAT2','IFNAR1','IFNAR2','IFNGR1','IFNGR2','IFNG'})
    if axis=='STAT5_6':return bool(genes&{'STAT5A','STAT5B','STAT6','IL4','IL4R','IL13'})
    if axis=='NEGATIVE_FEEDBACK':return bool(genes&NEGATIVE)
    if axis=='CROSSTALK':return bool(genes&CROSS)
    return False


def route_for(axis):
    if axis in {'IL6_JAK_STAT3','OSM_LIF_IL11_JAK_STAT3','JAK_STAT3'}:
        return 'JAK_STAT_RESEARCH_REVIEW','讨论受体/JAK/STAT3分层研究与EGFR背景的机制匹配试验；不把已获批血液病/炎症用途迁移为NSCLC标准。'
    if axis=='STAT3_JAK_INDEPENDENT':return 'NON_JAK_SOURCE_REVIEW','讨论SRC/RTK等来源的独立验证；此结果不能作为选择JAK抑制剂的依据。'
    if axis in {'IFN_STAT1_2','STAT5_6'}:return 'IMMUNE_DIRECTION_REVIEW','先审查宿主抗肿瘤保护与适应性持留的方向、区室及安全性，不按读出直接广谱抑制。'
    if axis=='NEGATIVE_FEEDBACK':return 'FEEDBACK_FUNCTION_REVIEW','审查负调控缺失的肿瘤/免疫双向效应，不按基因缺失自动选JAK药。'
    return 'PARALLEL_PATHWAY_REVIEW','验证FAK/SRC、MAPK/PI3K或抗凋亡等并行驱动；不经验性拼接全通路药物。'


def analyze(document,kb=None):
    data=validate_input(document);kb=kb or load_knowledge();c=data['context'];alerts=[]
    target=all(c.get(k) is True for k in ('prior_osimertinib','prior_platinum_pemetrexed','concurrent_osi_chemo','progressed_after_combination'))
    at_progression=c['collection_timing']=='at_progression'
    pathology=c['histology']=='adenocarcinoma' and c.get('histology_confirmed_at_progression') is True
    driver_confirmed=egfr_context_confirmed(c)
    gate=target and at_progression and pathology and driver_confirmed
    if not driver_confirmed:alerts.append('EGFR敏感驱动尚未明确专业确认，不将缺省/野生型注释放入EGFR驱动人群。')
    if not target:alerts.append('目标同期奥希替尼+铂/培美曲塞后进展未确认；既往TKI后或序贯化疗不能混作本场景。')
    if not at_progression:alerts.append('缺少进展期取样，不能把旧信号认作当前耐药。')
    if not pathology:alerts.append('需要确认进展期病理；小细胞/鳞状转化或病理未明时，先按谱系模块/病理MTB审查，不由JAK信号覆盖。')
    if c['progression_pattern']=='cns':alerts.append('中枢进展需独立取样/暴露评估；血浆阴性或血清细胞因子不能代表脑部机制。')
    if c['progression_pattern']=='oligoprogression':alerts.append('寡进展应评估局部处理与病灶异质性，不因单次JAK/STAT读出自动更换全身治疗。')
    if c.get('prior_additional_therapies'):alerts.append('额外既往ADC/抗体等会改变试验资格、免疫及骨髓风险，需独立核查。')
    signals=[];byid={}
    for o in data['observations']:
        state,notes=observation_state(o)
        if o['acquisition']=='acquired' and c.get('baseline_available') is not True:notes.append('声称获得性但缺少基线比较，不能证明新获得。')
        row={'id':o['id'],'gene':o['gene'],'kind':o['kind'],'level':o['level'],'site':o['site'],'compartment':o['compartment'],'status':state,'cautions':notes,'node_id':node_for(o['gene']),'evidence_ids':citations(kb,[node_for(o['gene'])])}
        signals.append(row);byid[o['id']]=(o,row)
    dependencies=[];routes=[]
    forbidden={'outside_curated_scope','not_tumor_resistance_source','benign_not_dependency','unclassified_variant_not_driver','assay_requires_validation','molecular_origin_requires_validation','loss_is_not_pathway_activation','cell_compartment_unresolved','amplification_requires_validation','feedback_loss_requires_validation'}
    for d in data['dependency_tests']:
        linked=[byid[i][0] for i in d['observation_ids']];states=[byid[i][1]['status'] for i in d['observation_ids']];needs=[]
        genes={o['gene'] for o in linked}
        if any(s in forbidden for s in states):needs.append('关联观察存在未定源、VUS、失活而非激活或检测/区室未确认，不能升级为依赖。')
        anchor=any(o['compartment']=='tumor' and o.get('compartment_confirmed') is True and o.get('assay_validated') is True and o['sample_type'] in {'tissue','model'} and (o['kind'] not in DNA or o['tumor_origin']=='confirmed') for o in linked)
        if not anchor:needs.append('缺少定位到肿瘤细胞的组织/模型观察；仅血清、血浆或免疫/基质读出不建立肿瘤依赖。')
        if not axis_requirements(d['axis'],genes):needs.append('关联基因/观察不覆盖声明的轴，不能从轴名自动补齐因果链。')
        for flag in PROOF_FLAGS-{'jak_independence_tested'}:
            if d.get(flag) is not True:needs.append('缺少实验审查条件：'+flag)
        if d['axis']=='STAT3_JAK_INDEPENDENT' and d.get('jak_independence_tested') is not True:needs.append('未直接检验JAK非依赖性，不能从pSTAT3或未检出JAK改变推断。')
        if d['model_source']!='patient_matched_progression':needs.append('不是进展期患者匹配模型，不能标为该个体的功能依赖。')
        if not at_progression:needs.append('实验声明与进展期取样时序未对齐。')
        if needs or d['result']=='unknown':state='requires_dependency_validation'
        elif d['result']=='does_not_support':state='supplied_experiment_not_supportive_not_global_exclusion'
        else:state='patient_model_hypothesis_not_clinical_validation'
        nodes=AXIS_NODES[d['axis']]
        ids=citations(kb,list(dict.fromkeys(nodes+['node07'])))
        dependencies.append({'id':d['id'],'axis':d['axis'],'status':state,'validation_needed':needs,'observation_ids':d['observation_ids'],'evidence_ids':ids,'clinical_actionability':'not_established_for_target_sequence'})
        if state=='patient_model_hypothesis_not_clinical_validation' and gate:
            code,strategy=route_for(d['axis'])
            routes.append({'id':code,'dependency_test':d['id'],'strategy':strategy,'status':'investigational_mtb_or_trial_review_only','limitations':'患者模型不能证明临床获益；需核对已用化疗/抗体、当前试验资格、现行地区标签以及感染/骨髓抑制等组合安全性。','evidence_ids':ids})
    if not dependencies:alerts.append('尚无可追溯功能依赖实验；读出与变异仅形成待验证线索，不等于没有耐药机制。')
    if not routes:alerts.append('当前不生成本场景的研究性干预匹配；先补齐病理、时序、来源和功能证据，仍需评估常规后线/局部治疗。')
    return {'schema_version':'1.0','engine_version':'1.0.0','intended_use':'research_only_not_clinically_validated','evidence_window':kb['window'],
            'target_sequence_confirmed_by_input':target,'egfr_driver_confirmed_by_input':driver_confirmed,'clinical_context_gate_passed':gate,'signals':signals,'dependency_assessments':dependencies,
            'research_options':routes,'alerts':alerts,'treatment_recommendations':[],'doses':[],'response_probabilities':None,
            'blocked_shortcuts':['IL6高→JAK/STAT依赖：IL6可走LAMA5/FAK或SRC/YAP。','pSTAT3高或STAT3表达高→JAK药敏：上游/区室/位点与功能需分别证明。','JAK2 V617F血浆阳性→NSCLC驱动：先定源血细胞克隆/血液病等。','JAK1/2失活或IFN高低→加JAK药：免疫终点和方向不等同于EGFR耐药。','SOCS/PTP失活或BCL2家族表达高→直接选药：反馈与BH3药敏不由基因名/表达量决定。'],
            'next_steps':['确认进展病理、治疗时序、病灶及基线；区分转化、寡进展/CNS与全身进展。','分区检查肿瘤/免疫/基质信号，明确pSTAT3位点、动态与下游；细胞因子需评估炎症/感染/激素及化疗混杂。','血液JAK/STAT变异按需要采用组织/配对白细胞等定源，不能靠VAF或与EGFR共检出。','用研究性患者匹配模型、选择性靶点作用、正交干预/救援及耐药表型检测区分JAK依赖与并行分叉。','由MTB核查专属人群临床证据、负面试验、现行标签与组合毒性；不从本工具生成处方。']}
