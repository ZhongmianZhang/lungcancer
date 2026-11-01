"""Deterministic research triage, never a diagnosis or automatic prescription.

No learned weights, invented response probabilities, doses or patient-network IO.
Input is explicitly annotated findings, not a replacement for variant annotation.
"""
from __future__ import annotations

import copy
import re

from .knowledge import load_knowledge, citations

AA = {"ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V", "TER": "*"}
CLASS2 = {"G469A", "G469V", "G469R", "K601E", "L597Q", "L597R", "L597S"}
CLASS3 = {"D594G", "D594N", "D594V", "G466V", "G466E"}
RTK = {"EGFR", "MET", "ERBB2", "FGFR1", "FGFR2", "FGFR3", "RET", "ALK", "ROS1", "AXL"}
ADAPTORS = {"PTPN11", "GRB2", "SOS1", "SOS2"}
CROSSTALK = {"PIK3CA", "AKT1", "AKT2", "MTOR", "PTEN", "YAP1", "SRC", "ILK"}
ENUMS = {
    "alteration_type": {"snv", "indel", "amplification", "fusion", "loss_of_function", "expression", "phosphoprotein", "unknown"},
    "classification": {"pathogenic", "likely_pathogenic", "vus", "benign", "likely_benign", "unknown"},
    "sample_type": {"tissue", "plasma", "csf", "unknown"},
    "tumor_origin": {"confirmed", "unconfirmed", "hematopoietic", "unknown"},
    "acquisition": {"acquired", "baseline", "unknown"},
}
CONTEXT_ENUMS = {
    "histology": {"adenocarcinoma", "small_cell", "squamous", "other", "unknown"},
    "progression_pattern": {"systemic", "oligoprogression", "cns", "unknown"},
    "collection_timing": {"at_progression", "before_progression", "unknown"},
}
BOOLEAN_CONTEXT = {"prior_osimertinib", "prior_platinum_pemetrexed", "concurrent_osi_chemo", "progressed_after_combination", "baseline_available", "histology_confirmed_at_progression"}
BOOLEAN_FINDING = {"assay_validated", "amplification_confirmed", "biallelic_loss", "rna_confirmed", "in_frame", "kinase_domain_retained", "functional_activation"}


def normalize_variant(value: str) -> str:
    value = re.sub(r"\s+", "", value).upper()
    value = re.sub(r"^P\.", "", value).strip("()")
    for old, new in AA.items():
        value = value.replace(old, new)
    return value


def validate_input(document: dict) -> dict:
    if not isinstance(document, dict) or set(document) - {"schema_version", "context", "findings", "case_label"}:
        raise ValueError("Only schema_version, context, findings and optional synthetic case_label are accepted")
    if document.get("schema_version") != "1.0":
        raise ValueError("schema_version must be '1.0'")
    if not isinstance(document.get("context"), dict) or not isinstance(document.get("findings"), list):
        raise ValueError("context must be an object; findings must be a list")
    if len(document["findings"]) > 200:
        raise ValueError("At most 200 curated findings are accepted")
    data = copy.deepcopy(document)
    if "case_label" in data and (not isinstance(data["case_label"], str) or len(data["case_label"]) > 200):
        raise ValueError("case_label must be a short string")
    ctx = data["context"]
    allowed_context = BOOLEAN_CONTEXT | set(CONTEXT_ENUMS) | {"egfr_driver", "prior_additional_therapies"}
    if set(ctx) - allowed_context:
        raise ValueError("Unknown context fields: " + ", ".join(sorted(set(ctx) - allowed_context)))
    for key in BOOLEAN_CONTEXT:
        if key in ctx and not isinstance(ctx[key], bool):
            raise ValueError(f"{key} must be a JSON boolean, not a string/number")
    for key, options in CONTEXT_ENUMS.items():
        ctx.setdefault(key, "unknown")
        if ctx[key] not in options:
            raise ValueError(f"Invalid {key}")
    for key in ("egfr_driver",):
        if key in ctx and not isinstance(ctx[key], str):
            raise ValueError(f"{key} must be a string")
    if "prior_additional_therapies" in ctx and (not isinstance(ctx["prior_additional_therapies"], list) or any(not isinstance(x, str) for x in ctx["prior_additional_therapies"])):
        raise ValueError("prior_additional_therapies must be a list of names")
    if ctx.get("progressed_after_combination") is True and any(ctx.get(k) is not True for k in ("prior_osimertinib", "prior_platinum_pemetrexed", "concurrent_osi_chemo")):
        raise ValueError("Progression after concurrent combination requires all three treatment-history fields to be true")
    allowed_finding = {"gene", "variant", "alteration_type", "classification", "sample_type", "tumor_origin", "tumor_origin_evidence", "acquisition", "assay", "notes"} | BOOLEAN_FINDING
    for f in data["findings"]:
        if not isinstance(f, dict) or set(f) - allowed_finding:
            raise ValueError("Finding has unknown fields; numeric copy-number/VAF alone is deliberately not an activation rule")
        if not isinstance(f.get("gene"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,30}", f["gene"]):
            raise ValueError("Each finding needs a valid gene symbol")
        f["gene"] = f["gene"].upper()
        for key, options in ENUMS.items():
            f.setdefault(key, "unknown")
            if f[key] not in options:
                raise ValueError(f"Invalid finding {key}: {f[key]}")
        for key in BOOLEAN_FINDING:
            if key in f and not isinstance(f[key], bool):
                raise ValueError(f"{key} must be a JSON boolean")
        for key in ("variant", "assay", "notes", "tumor_origin_evidence"):
            f.setdefault(key, "")
            if not isinstance(f[key], str) or len(f[key]) > 2000:
                raise ValueError(f"{key} must be a short string")
        f["normalized_variant"] = normalize_variant(f["variant"])
    return data


def identify(f: dict) -> tuple[str, list[str], str]:
    gene, kind, variant = f["gene"], f["alteration_type"], f["normalized_variant"]
    if kind in {"expression", "phosphoprotein"}:
        return "PATHWAY_READOUT_ONLY", ["node08", "node09"], "表达或磷酸化是状态读出，不能指认RAS/BRAF突变或自动预测抑制剂敏感性；低ERK也可能伴随持留反馈。"
    if gene == "EGFR":
        return "EGFR_ON_TARGET_REVIEW", ["node01", "node10"], "EGFR敏感驱动仍检出不等于耐药；继发靶内改变需具体等位变异及顺反式判读，不属于RAS旁路自动映射。"
    if gene == "BRAF":
        if kind == "fusion":
            return "BRAF_FUSION", ["node06"], "结构变异需确认表达、同框及激酶域；不能套用V600E单体抑制策略。"
        if variant == "V600E":
            return "BRAF_V600E_CLASS_I", ["node05"], "V600E支持class I机制候选；获得性旁路不同于de novo BRAF肺癌，临床组合证据有限且有阴性更新。"
        if variant in CLASS2:
            return "BRAF_CLASS_II", ["node05", "node06"], "该精确等位变异符合已知class II二聚体机制，不能沿用V600E治疗模板。"
        if variant in CLASS3:
            return "BRAF_CLASS_III", ["node05", "node02"], "该精确等位变异符合class III低活性/RAS依赖机制，需寻找上游驱动，不代表BRAF单药敏感。"
        return "BRAF_UNCLASSIFIED", ["node05"], "未在保守等位变异表中；V600K等不能冒称V600E证据，须功能分型和专业审校。"
    if gene == "KRAS":
        if kind == "amplification":
            return "KRAS_AMPLIFICATION", ["node03"], "须确认真实扩增而非仅表达/倍体变化；联合RAF/EGFR的依据主要是临床前。"
        return ("KRAS_G12C" if variant == "G12C" else "KRAS_NON_G12C"), ["node03"], "KRAS具体等位变异、来源与克隆关系必须分开。G12C或其他RAS药物在其他人群的证据不能直接迁移。"
    if gene in {"NRAS", "HRAS"}:
        return "NRAS_HRAS", ["node04"], "少见RAS激活可为旁路候选，仍需排除血细胞来源、独立克隆与其他驱动。"
    if gene in {"NF1", "RASA1"}:
        return "RAS_GAP_LOSS", ["node04", "node02"], "负调控缺失可能维持RAS-GTP；单个VUS或未经确认的单等位改变不足，NF1缺失也可能导致SHP2抑制抵抗。"
    if gene in {"RAF1", "ARAF"}:
        return "RAF_OTHER", ["node06"], "需依据结构/功能注释判读RAF二聚体；ARAF扩增伴转化线索应优先组织病理。"
    if gene in ADAPTORS:
        return "SHP2_SOS_ADAPTOR", ["node02"], "适配层改变并非表达即激活；PTPN11活化等位变异与变构SHP2药敏不可混同。"
    if gene in {"MAP2K1", "MAP2K2"}:
        return "MEK_ALLELE_SPECIFIC", ["node07"], "MEK变异存在等位特异性；部分RAF非依赖性变异不敏感，不能将基因名当作MEK药敏。"
    if gene in {"MAPK1", "MAPK3", "DUSP1", "DUSP6", "SPRY1", "SPRY2"}:
        return "ERK_FEEDBACK", ["node08"], "ERK/DUSP反馈具有方向和情境依赖性，不能使用‘ERK越低越好’的单调规则。"
    if gene in RTK:
        return "UPSTREAM_RTK", ["node01", "node02"], "RTK旁路可能同时驱动MAPK与PI3K；扩增、突变、融合、IHC和配体刺激必须分别确认。"
    if gene in CROSSTALK:
        return "PARALLEL_CROSSTALK", ["node09"], "并行存活与状态变化可共存，不自动证明RAS/BRAF是唯一耐药驱动。"
    return "OUTSIDE_CURATED_SCOPE", ["node10"], "不在当前节点规则范围，不能据此排除其他耐药机制。"


def research_routes(mechanism: str) -> list[dict]:
    policies = {
        "BRAF_V600E_CLASS_I": [("EGFR_BRAF_MEK", "EGFR+BRAF+MEK组合的分子肿瘤委员会／临床试验评估", "病例系列有选择偏倚，2026系列活性有限；不属于本治疗序列的已验证标准。")],
        "BRAF_CLASS_II": [("RAF_DIMER_TRIAL", "二聚体／pan-RAF或其他机制匹配的早期试验", "不沿用V600E单体模板，具体药物覆盖和资格须重新核验。")],
        "BRAF_CLASS_III": [("UPSTREAM_DEPENDENCY", "验证RAS／上游RTK依赖后讨论机制匹配研究", "不可仅凭class III选择BRAF单药。")],
        "BRAF_FUSION": [("RAF_FUSION_TRIAL", "结构确认后讨论EGFR/RAF二聚体相关研究", "患者模型和跨实体瘤结果不能证明奥希替尼+化疗后获益。")],
        "RAF_OTHER": [("RAF_STRUCTURE_TRIAL", "结构与病理复核后讨论早期研究", "RAF1/ARAF不套用BRAF V600E；有转化则优先转化分支。")],
        "KRAS_G12C": [("G12C_CONTEXT_REVIEW", "G12C相关策略的临床试验／适应证背景审查", "de novo KRAS G12C NSCLC证据不同于EGFR旁路；联合安全性及既往治疗入组要求必须核实。")],
        "KRAS_NON_G12C": [("RAS_VARIANT_TRIAL", "具体RAS等位变异／多选择性RAS试验研究", "2026患者源模型是临床前，不提供该序列临床应答概率。")],
        "KRAS_AMPLIFICATION": [("KRAS_AMP_RESEARCH", "扩增与克隆性功能验证及试验匹配", "不能用G12C获批信息支持扩增治疗。")],
        "NRAS_HRAS": [("RAS_CONTEXT_TRIAL", "功能确认与按背景分层的研究", "缺少该治疗序列的标准靶向治疗证据。")],
        "RAS_GAP_LOSS": [("GAP_LOSS_RESEARCH", "负调控缺失的功能研究与试验评估", "NF1篮式MEK研究有阴性结果；不能自动选择MEK或SHP2抑制。")],
        "SHP2_SOS_ADAPTOR": [("ADAPTOR_TRIAL", "适配层机制验证及早期试验评估", "SOS1/SHP2证据多为临床前或其他人群；2026 SOS1±MEK试验有严重毒性信号。")],
        "MEK_ALLELE_SPECIFIC": [("MEK_FUNCTIONAL_REVIEW", "MEK等位变异功能分类及机制匹配试验", "不能由MEK基因名推断曲美替尼等药敏。")],
        "ERK_FEEDBACK": [("ERK_FEEDBACK_RESEARCH", "动态ERK与反馈机制研究", "ERK跨癌篮式阴性试验和低ERK持留反例均需纳入。")],
        "UPSTREAM_RTK": [("RTK_MATCHED_REVIEW", "按真实RTK驱动讨论双通路研究", "例如MET扩增试验人群/阈值不能替代ERBB2表达或RET融合的人群定义。")],
        "PARALLEL_CROSSTALK": [("PARALLEL_DRIVER_REVIEW", "并行机制和细胞状态的功能验证", "不推荐将多个通路抑制剂经验性拼接。")],
    }
    return [{"id": code, "strategy": title, "status": "investigational_mtb_or_trial_only",
             "setting": "EGFR突变NSCLC奥希替尼+化疗后；此处均不是已验证自动治疗建议", "limitation": boundary}
            for code, title, boundary in policies.get(mechanism, [])]


def analyze(document: dict, kb: dict | None = None) -> dict:
    data = validate_input(document)
    kb = kb or load_knowledge()
    ctx = data["context"]
    alerts, missing, results = [], [], []
    for key in ("prior_osimertinib", "prior_platinum_pemetrexed", "concurrent_osi_chemo", "progressed_after_combination", "baseline_available"):
        if key not in ctx:
            missing.append(key)
    target = all(ctx.get(k) is True for k in ("prior_osimertinib", "prior_platinum_pemetrexed", "concurrent_osi_chemo", "progressed_after_combination"))
    if not target:
        alerts.append("输入尚未确认为奥希替尼与铂类/培美曲塞同期联合后进展；其他治疗背景不能混用证据。")
    if not ctx.get("egfr_driver"):
        missing.append("egfr_driver")
    if ctx["collection_timing"] != "at_progression":
        alerts.append("缺少明确进展时取样，不能证明检出事件为本次获得性耐药。")
    transformed = ctx["histology"] in {"small_cell", "squamous"} and ctx.get("histology_confirmed_at_progression") is True
    transformation_suspected = ctx["histology"] in {"small_cell", "squamous"} and not transformed
    if transformed:
        alerts.append("进展时组织已证实小细胞或鳞状转化：优先依据转化病理讨论治疗；MAPK事件不应自动覆盖该分支。")
    elif transformation_suspected:
        alerts.append("存在转化线索但未由进展期组织确认：先复核病理，不将分子事件自动映射为治疗。")
    if ctx["progression_pattern"] == "cns":
        alerts.append("中枢进展应独立评估药物暴露、影像/脑脊液及局部治疗；血浆阴性不能排除中枢机制。")
    elif ctx["progression_pattern"] == "oligoprogression":
        alerts.append("寡进展需讨论局部治疗与全身方案的持续价值，不能仅凭一个变异自动更换全部治疗。")
    if ctx.get("prior_additional_therapies"):
        alerts.append("既往额外药物/ADC/埃万妥单抗会改变入组条件和耐药背景；未自动外推现有研究。")
    for index, f in enumerate(data["findings"]):
        mechanism, nodes, rationale = identify(f)
        blockers, notes = [], []
        if f["classification"] in {"benign", "likely_benign"}:
            state = "not_supported_benign"
        elif f["tumor_origin"] == "hematopoietic":
            state = "not_tumor_resistance"
            notes.append("已标注血细胞来源，不纳入肿瘤耐药驱动或治疗匹配。")
        elif mechanism == "PATHWAY_READOUT_ONLY":
            state = "readout_only_not_driver"
            notes.append("仅能形成待验证的通路状态假说；不得映射为加MEK/ERK药。")
        elif mechanism in {"BRAF_UNCLASSIFIED", "OUTSIDE_CURATED_SCOPE", "EGFR_ON_TARGET_REVIEW"}:
            state = "unclassified_requires_expert_review"
        else:
            if f["classification"] not in {"pathogenic", "likely_pathogenic"}:
                blockers.append("VUS/未知功能改变不能按致病耐药驱动处理。")
            if f["alteration_type"] in {"snv", "indel"} and not f["variant"].strip():
                blockers.append("SNV/indel必须提供精确等位变异，不能只按基因名判读。")
            if f.get("assay_validated") is not True:
                blockers.append("尚缺经验证检测方法的确认。")
            if f["tumor_origin"] != "confirmed":
                blockers.append("尚未确认肿瘤来源；血浆RAS/PTPN11等需组织或必要的配对白细胞评估。")
            elif f["sample_type"] in {"plasma", "csf"} and not f["tumor_origin_evidence"].strip():
                blockers.append("液体样本的肿瘤来源确认缺少依据说明，VAF或与EGFR共检出不能代替。")
            if f["alteration_type"] == "amplification" and f.get("amplification_confirmed") is not True:
                blockers.append("需按平台、倍体和肿瘤含量确认扩增；不使用统一拷贝数阈值。")
            if f["alteration_type"] == "fusion" and any(f.get(k) is not True for k in ("rna_confirmed", "in_frame", "kinase_domain_retained")):
                blockers.append("融合尚缺RNA表达、同框或保留激酶域的确认。")
            if mechanism == "RAS_GAP_LOSS" and (f.get("biallelic_loss") is not True or f["alteration_type"] not in {"loss_of_function", "indel", "snv"}):
                blockers.append("RAS-GAP缺失需功能失活与双等位背景确认，单个改变不足。")
            if mechanism in {"SHP2_SOS_ADAPTOR", "MEK_ALLELE_SPECIFIC", "ERK_FEEDBACK", "PARALLEL_CROSSTALK"} and f.get("functional_activation") is not True:
                blockers.append("需要具体等位变异/功能和通路依赖性评估，不能只按基因名解释。")
            if mechanism == "SHP2_SOS_ADAPTOR" and f["alteration_type"] == "loss_of_function":
                blockers.append("正向适配因子失活不能按适配层激活解释；与激活注释矛盾时先专业复核。")
            if mechanism == "KRAS_G12C" and f["alteration_type"] != "snv":
                blockers.append("G12C变异与事件类型不一致。")
            if mechanism in {"BRAF_V600E_CLASS_I", "BRAF_CLASS_II", "BRAF_CLASS_III"} and f["alteration_type"] != "snv":
                blockers.append("BRAF点突变分型与事件类型不一致。")
            if f["gene"] in {"KRAS", "NRAS", "HRAS"} and f["alteration_type"] == "snv":
                hotspot = re.fullmatch(r"[A-Z](12|13|61|117|146)[A-Z]", f["normalized_variant"])
                if not hotspot and f.get("functional_activation") is not True:
                    blockers.append("非保守RAS热点表中的等位变异，需额外功能激活注释。")
            if f["gene"] in {"KRAS", "NRAS", "HRAS"}:
                if f["alteration_type"] not in {"snv", "indel", "amplification"}:
                    blockers.append("RAS非激活型事件不能仅凭致病分类推断通路激活。")
                if f["alteration_type"] == "indel" and f.get("functional_activation") is not True:
                    blockers.append("RAS indel需要额外功能激活依据。")
            if mechanism in {"UPSTREAM_RTK", "RAF_OTHER"} and f["alteration_type"] not in {"amplification", "fusion"} and f.get("functional_activation") is not True:
                blockers.append("受体/RAF的具体变异需激活功能依据，致病不自动等于本旁路激活。")
            if mechanism == "RAF_OTHER" and f["alteration_type"] == "amplification" and f.get("functional_activation") is not True:
                blockers.append("ARAF/RAF1扩增还需通路依赖与病理背景验证。")
            if f["alteration_type"] == "unknown":
                blockers.append("事件类型未知。")
            state = "requires_validation" if blockers else "supported_mechanistic_hypothesis"
        if f["acquisition"] == "acquired" and ctx.get("baseline_available") is not True:
            notes.append("声称获得性但缺少基线比较，不认定已证明获得性。")
        acquired = f["acquisition"] == "acquired" and ctx.get("baseline_available") is True and ctx["collection_timing"] == "at_progression"
        if not acquired:
            notes.append("未证明为治疗后新获得事件；可能为基线共变异或克隆选择。")
        if transformed:
            notes.append("存在已证实转化，任何基因相关干预先经病理与分子肿瘤委员会整合。")
        context_gate = target and ctx["collection_timing"] == "at_progression"
        routes = research_routes(mechanism) if state == "supported_mechanistic_hypothesis" and context_gate and not transformed and not transformation_suspected else []
        if not context_gate:
            notes.append("目标联合治疗序列或进展期取样未确认，暂不输出该场景的研究匹配。")
        ids = citations(kb, nodes)
        direct = [ref["id"] for ref in kb["evidence"] if ref["id"] in ids and ref["scope"] == "post_osimertinib_chemo" and ref["verification"] == "metadata_abstract_checked"]
        results.append({"index": index, "gene": f["gene"], "variant": f["variant"], "normalized_variant": f["normalized_variant"],
                        "alteration_type": f["alteration_type"], "mechanism": mechanism, "status": state,
                        "rationale": rationale, "validation_needed": blockers, "cautions": notes,
                        "acquired_supported_by_supplied_history": acquired, "node_ids": nodes, "evidence_ids": ids,
                        "target_setting_abstract_evidence_ids": direct, "research_options": routes,
                        "clinical_actionability": "not_established_for_this_sequence"})
    if len([f for f in data["findings"] if f["gene"] == "BRAF"]) > 1:
        alerts.append("检测到多个BRAF事件：逐等位保留分类，不将整个病例强行归为某一class；共检出不能证明顺反式或同一克隆。")
    if len(results) > 1:
        alerts.append("多个事件共检出不证明同一细胞/克隆，需结合组织、纵向VAF与必要的克隆研究；不自动拼接所有匹配药物。")
    if not results or not any(r["status"] == "supported_mechanistic_hypothesis" for r in results):
        alerts.append("未识别到足够支持的MAPK机制假说，不等于没有耐药机制；阴性血浆和检测盲区不能作为排除证据。")
    return {
        "schema_version": "1.0", "engine_version": "1.0.0", "intended_use": "research_only_not_clinically_validated",
        "evidence_window": kb["window"], "target_sequence_confirmed_by_input": target,
        "missing_context": missing, "alerts": list(dict.fromkeys(alerts)), "findings": results,
        "treatment_recommendations": [], "doses": [], "response_probabilities": None,
        "blocked_automatic_mappings": [
            "BRAF异常→奥希替尼+selumetinib：2026 ORCHARD队列不支持继续评估该组合。",
            "NF1失活→MEK或SHP2敏感：NF1篮式阴性和SHP2抵抗机制反对该推断。",
            "pERK高→ERK药、ERK越低越好：通路读出、反馈与持留使该规则不成立。",
            "BRAF非V600/融合→ulixertinib标准：2026跨癌种研究不能支持此映射。",
            "KRAS任意改变→G12C药：非G12C、扩增和血细胞来源不属于该模板。",
        ],
        "next_steps": [
            "整合进展期组织病理、DNA/RNA测序、拷贝数和必要的血浆/白细胞对照；血浆阴性不排除。",
            "与治疗前样本比较，核实遗传背景、获得性、克隆关系与并行耐药机制。",
            "按全身、寡进展或中枢进展分类，进入分子肿瘤委员会讨论。",
            "核实试验当前招募、地区标签、既往化疗/ADC入组限制和组合毒性；本工具不生成处方。",
        ],
    }
