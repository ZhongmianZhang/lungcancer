"""Assess specimen-level resistance evidence and enumerate clinical review options."""

import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from .input import PHYSICAL_PHASE, is_alk_reference, normalize_case


ADVANCED = {"unresectable_locally_advanced", "metastatic"}
COPY_GAIN = "amplification"
COVERAGE_TARGETS = (
    ("ALK", "variant"), ("ALK", "fusion"), ("MET", "copy_number"),
    ("MET", "fusion"), ("HISTOLOGY", "histology"), ("EMT", "expression"),
    ("EPIGENOME", "methylation"), ("EPIGENOME", "chromatin_accessibility"),
)
GAP_REVIEW = {
    ("ALK", "variant"): "核对激酶域和罕见 indel 的覆盖、低频检出限及复合位点定相",
    ("ALK", "fusion"): "核对 DNA 内含子及 RNA 表达融合的可评价范围",
    ("MET", "copy_number"): "复核局灶性、纯度和倍性，并核对组织或 FISH 结果",
    ("MET", "fusion"): "发现结构信号时用匹配 RNA 复核融合接头",
    ("HISTOLOGY", "histology"): "可行时结合进展组织、基线形态及 IHC 复核",
    ("EMT", "expression"): "研究中用配对多标志和肿瘤细胞定位复核",
    ("EPIGENOME", "methylation"): "研究中需独立、可比的甲基化测量",
    ("EPIGENOME", "chromatin_accessibility"): "研究中需独立、可比的染色质测量",
}


@lru_cache(maxsize=1)
def knowledge():
    data = json.loads(Path(__file__).with_name("knowledge.json").read_text(encoding="utf-8"))
    for group in ("mechanisms", "options"):
        for key, entry in data[group].items():
            if not entry["sources"] or set(entry["sources"]) - data["sources"].keys():
                raise ValueError(f"知识库引用无效 {group}/{key}")
    for mapping in ("alk_pairs", "exploratory_features", "exploratory_gene_events"):
        ids = data[mapping].keys() if mapping == "alk_pairs" else data[mapping].values()
        if set(ids) - data["mechanisms"].keys():
            raise ValueError(f"知识库机制引用无效 {mapping}")
    return data


def catalog_entry(group, key):
    return {"id": key, **knowledge()[group][key]}


def usable(specimen, finding):
    observed = finding["status"] == "not_detected" or finding["attributes"].get("vaf") != 0
    return (observed and specimen["qc"] == "pass" and specimen["tumor_fraction"] != 0 and finding["qc"] == "pass"
            and finding["attributes"].get("tumor_origin") not in ("germline", "hematopoietic")
            and specimen["assays"][finding["assay_id"]]["qc"] == "pass")


def covers_event(assay, finding):
    return any((row["gene"], row["kind"], row["feature"], row["status"]) == (
        finding["gene"], finding["kind"], finding["feature"], "adequate",
    ) for row in assay["coverage"])


def acquisition(case, specimen, finding):
    baseline = case["specimens"].get(specimen["baseline_sample_id"])
    if baseline is None:
        return {"state": "unresolved", "reason": "缺少指定的治疗前样本"}
    result = {"baseline_sample_id": baseline["id"]}
    expected = (finding["gene"], finding["kind"], finding["feature"])
    before = [row for row in baseline["findings"] if usable(baseline, row) and (
        row["gene"], row["kind"], row["feature"]) == expected]
    if finding["kind"] == "variant" and finding["gene"] == "ALK":
        before = [row for row in before if reference_variant(row)]
    if any(row["status"] == "detected" for row in before):
        return {**result, "state": "detected_at_baseline",
                "reason": "基线已检出同名事件，不推断同一克隆或同一相位"}
    linked_assay = specimen["comparable_baseline_assays"].get(finding["assay_id"])
    site_known = specimen["site"].casefold() != "unknown"
    same_matrix = baseline["material"] == specimen["material"] and specimen["material"] != "unknown"
    same_site = site_known and baseline["site"] == specimen["site"]
    build_known = (specimen["genome_build"] == baseline["genome_build"]
                   and specimen["genome_build"] != "unknown")
    # Negative liquid results have additional biological sampling limitations.
    if linked_assay and same_matrix and same_site and build_known and specimen["material"] == "tissue":
        negative = next((row for row in before if (
            row["assay_id"] == linked_assay and row["status"] == "not_detected"
            and covers_event(baseline["assays"][linked_assay], row)
        )), None)
        if negative is not None:
            return {**result, "state": "newly_detected_in_comparable_specimens",
                    "baseline_finding_id": negative["id"],
                    "reason": "同部位组织基线对该事件明确阴性且检测限可比，仍不能排除基线阈值下克隆"}
    return {**result, "state": "unresolved",
            "reason": "缺乏同部位组织的可比检测、同位点覆盖及明确基线阴性"}


def reference_variant(row):
    transcript = row["attributes"].get("transcript")
    return transcript is None or is_alk_reference(transcript)


def emit(case, specimen, matches, key, level, reasons, *findings):
    evidence = []
    for row in findings:
        baseline_evidence = acquisition(case, specimen, row)
        evidence.append({"finding_id": row["id"], "assay_id": row["assay_id"], "acquisition": baseline_evidence})
    matches.append({
        **catalog_entry("mechanisms", key), "sample_id": specimen["id"], "level": level,
        "reason": reasons, "evidence": evidence,
    })


def alk_rules(case, specimen, positive, matches):
    variants = [row for row in positive if row["gene"] == "ALK" and row["kind"] == "variant"]
    canonical = [row for row in variants if reference_variant(row)]
    phases = defaultdict(dict)
    for row in canonical:
        phase = row["attributes"].get("phase", {})
        if phase.get("method") in PHYSICAL_PHASE:
            key = (row["assay_id"], phase["method"], phase["block"], phase["haplotype"])
            phases[key].setdefault(row["feature"], row)
    supported_features = set()
    for group in phases.values():
        for rule, pair in knowledge()["alk_pairs"].items():
            if set(pair) != group.keys():
                continue
            rows = [group[feature] for feature in pair]
            supported_features.update(pair)
            emit(case, specimen, matches, rule, "supported",
                 "在同一进展样本、同一检测及同一物理单倍型上得到已报道的精确变异组合", *rows)
    for row in canonical:
        if row["feature"] == "K1150dup":
            emit(case, specimen, matches, "alk_k1150dup", "candidate",
                 "与一线洛拉替尼进展病例及功能实验一致，临床证据为单例", row)
            supported_features.add(row["feature"])
    if canonical and not {row["feature"] for row in canonical} <= supported_features:
        unresolved = [row for row in canonical if row["feature"] not in supported_features]
        emit(case, specimen, matches, "alk_unresolved", "insufficient",
             "单变异、未证实同一物理单倍型或缺少精确组合证据", *unresolved)
    for row in variants:
        if not reference_variant(row):
            emit(case, specimen, matches, "alk_unresolved", "insufficient",
                 "蛋白注释使用非参考 ALK 转录本", row)


def met_is_focal(row):
    attrs = row["attributes"]
    return (row["feature"] == COPY_GAIN and attrs.get("focality") == "focal"
            and attrs.get("validated_call") is True
            and isinstance(attrs.get("criteria"), str) and bool(attrs["criteria"].strip()))


def met_rules(case, specimen, positive, matches):
    cnvs = [row for row in positive if row["gene"] == "MET" and row["kind"] == "copy_number"]
    focal = [row for row in cnvs if met_is_focal(row)]
    provisional = [row for row in cnvs if not met_is_focal(row) and row["feature"] in {COPY_GAIN, "gain"}]
    for row in focal:
        baseline_status = acquisition(case, specimen, row)["state"]
        level = "supported" if baseline_status == "newly_detected_in_comparable_specimens" else "candidate"
        emit(case, specimen, matches, "met_focal_amplification", level,
             "检测报告以本平台标准确证局灶 MET 扩增，耐药解释取决于组织配对证据", row)
    for row in provisional:
        emit(case, specimen, matches, "met_gain_unresolved", "insufficient",
             "缺少经验证的局灶扩增判据，须区分倍体增加", row)
    # DNA and RNA must point to the same reported event in the same specimen.
    st7 = [row for row in positive if (
        row["gene"] == "MET" and row["kind"] == "fusion" and row["feature"] == "ST7::MET"
    )]
    if st7:
        by_link = defaultdict(list)
        for row in st7:
            link = row["attributes"].get("event_link")
            if isinstance(link, str) and link.strip():
                by_link[link].append(row)
        for rows in by_link.values():
            modalities = {specimen["assays"][row["assay_id"]]["modality"] for row in rows}
            supported_rna = any(
                specimen["assays"][row["assay_id"]]["modality"] == "rna"
                and row["attributes"].get("exon_junction") == "ST7:1-MET:2" for row in rows
            )
            if supported_rna and modalities & {"wgs", "targeted_dna", "wes", "long_read_dna"} and focal:
                emit(case, specimen, matches, "st7_met", "candidate",
                     "同一样本的局灶扩增及同一事件的 DNA/RNA 证据与已报道旁路病例一致",
                     *rows, *focal)
                break
        else:
            emit(case, specimen, matches, "st7_met_unresolved", "insufficient",
                 "须复核局灶扩增及同一融合事件的 DNA/RNA 配对", *st7)


def current_histology(specimen, rows):
    if specimen["material"] == "tissue":
        for row in rows:
            if row["kind"] == "histology" and row["feature"] in {"SCLC", "LCNEC", "SQUAMOUS"}:
                yield row


def pathology_confirmed(row):
    attrs = row["attributes"]
    return attrs.get("pathologist_confirmed") is True and attrs.get("morphology_and_ihc") is True


def histology_rules(case, specimen, positive, matches):
    for row in current_histology(specimen, positive):
        verified = pathology_confirmed(row) and row["attributes"].get("baseline_histology_compared") is True
        if (verified and case["clinical"]["baseline_histology"] == "adenocarcinoma"
                and acquisition(case, specimen, row)["state"] != "detected_at_baseline"):
            emit(case, specimen, matches, "lineage_transformation", "supported",
                 "进展组织的形态和 IHC 经病理医师确认，且已与基线腺癌对照", row)
        else:
            emit(case, specimen, matches, "lineage_review", "candidate",
                 "当前组织学或基线对照有待病理复核", row)


def exploratory_rules(case, specimen, positive, matches):
    for row in positive:
        gene, kind, feature = row["gene"], row["kind"], row["feature"]
        attrs = row["attributes"]
        key = knowledge()["exploratory_features"].get(f"{gene}|{kind}|{feature}")
        pathogenic = attrs.get("classification") in ("pathogenic", "likely_pathogenic")
        if key is None and pathogenic:
            key = knowledge()["exploratory_gene_events"].get(f"{gene}|{kind}")
        if key == "nf2_loss" and not (
            attrs.get("biallelic_inactivation_confirmed") is True
            and pathogenic
        ):
            key = None
        if key == "emt_partial" and not all(attrs.get(field) is True for field in (
            "tumor_cell_localized", "multiple_markers", "paired_reviewed",
        )):
            key = "emt_incomplete"
        if key:
            level = "insufficient" if key == "emt_incomplete" else "candidate"
            emit(case, specimen, matches, key, level,
                 "与文献机制线索相符，需结合纵向样本及路径活性独立验证", row)
    genes = {row["gene"] for row in positive if (
        row["kind"] == "variant"
        and row["attributes"].get("classification") in ("pathogenic", "likely_pathogenic")
    )}
    if {"TP53", "RB1"} <= genes and not any(row["id"] == "lineage_transformation" for row in matches):
        evidence = [row for row in positive if row["gene"] in ("TP53", "RB1")
                    and row["kind"] == "variant"
                    and row["attributes"].get("classification") in ("pathogenic", "likely_pathogenic")]
        emit(case, specimen, matches, "lineage_review", "candidate",
             "TP53 与 RB1 同时有致病级改变可触发组织复核，转化须依赖病理证据", *evidence)


def gaps_for(specimen):
    gaps = []
    assays = specimen["assays"]
    for gene, kind in COVERAGE_TARGETS:
        claims = [row for assay in assays.values() for row in assay["coverage"]
                  if row["gene"] == gene and row["kind"] == kind]
        usable_claims = {row["feature"] for assay in assays.values() if assay["qc"] == "pass"
                         for row in assay["coverage"] if row["gene"] == gene and row["kind"] == kind
                         and row["status"] == "adequate"}
        if specimen["qc"] != "pass" or specimen["tumor_fraction"] == 0:
            usable_claims.clear()
        if "*" not in usable_claims:
            status = "coverage_or_quality_limited" if claims else "coverage_undocumented"
            if usable_claims:
                status = "locus_only"
            gaps.append({
                "sample_id": specimen["id"], "gene": gene, "kind": kind,
                "status": status, "adequate_features": sorted(usable_claims), "review": GAP_REVIEW[(gene, kind)],
            })
    if specimen["material"] in {"plasma", "csf"}:
        gaps.append({
            "sample_id": specimen["id"], "status": "liquid_biopsy_sampling_limit",
            "reason": "液体阴性受脱落量、病灶部位、肿瘤分数及变异类别检出限影响",
            "tumor_fraction": specimen["tumor_fraction"],
            "review": "无信息量的液体结果可结合临床可行性复核进展组织",
        })
    return gaps


def neladalkib_label(clinical, progression, *, transformed=False):
    jurisdiction = clinical["jurisdiction"]
    if jurisdiction == "UNKNOWN":
        return "insufficient_information", "治疗地区待核实"
    if jurisdiction != "US":
        return "local_label_unverified", "请按当地监管适应证独立复核"
    if clinical["age_group"] == "pediatric" or clinical["setting"] == "other":
        return "criteria_not_met", "美国适应证要求成人局部晚期或转移性 ALK 阳性 NSCLC"
    if clinical["age_group"] != "adult" or clinical["setting"] not in ADVANCED:
        return "insufficient_information", "年龄或局部晚期/转移状态待核实"
    if not clinical["advanced_treatment_history_complete"]:
        return "insufficient_information", "相关治疗阶段的完整用药史待核实"
    prior = clinical["prior_advanced_alk_tkis"]
    if clinical["unrecognized_advanced_alk_tkis"]:
        return "insufficient_information", "有未识别的 ALK TKI 通用名，需核实并去重"
    if "lorlatinib" not in prior and progression["lorlatinib_setting"] != "other":
        return "insufficient_information", "需核对本次洛拉替尼用药是否计入相关治疗阶段"
    if transformed:
        return "histology_review_required", "进展组织具有神经内分泌表型，需复核标签对当前治疗目标的适用性"
    if prior == ["alectinib"]:
        return "criteria_met", "相关阶段仅有一种既往 ALK TKI，且为阿来替尼"
    if len(prior) >= 2:
        if clinical["prior_advanced_platinum"] is True:
            return "criteria_met", "相关阶段已用至少两种不同 ALK TKI 且已接受含铂化疗"
        if clinical["prior_advanced_platinum"] is None:
            return "insufficient_information", "相关阶段既往含铂化疗记录待核实"
    return "criteria_not_met", "记录中的既往治疗组合未达到美国标签条件"


def make_option(key, status="multidisciplinary_review", reason=None, samples=()):
    entry = {**catalog_entry("options", key), "status": status, "sample_ids": sorted(set(samples))}
    if reason:
        entry["reason"] = reason
    return entry


def clinical_options(case, per_sample):
    clinical = case["clinical"]
    pattern = case["progression"]["pattern"]
    all_mechanisms = [row for record in per_sample for row in record["mechanisms"]]
    changed_histology = set()
    neuroendocrine = set()
    sclc = set()
    for record in per_sample:
        sid = record["sample_id"]
        specimen = case["specimens"][sid]
        for row in current_histology(specimen, record["findings"]):
            if row["status"] == "detected" and usable(specimen, row) and pathology_confirmed(row):
                changed_histology.add(sid)
                if row["feature"] in {"SCLC", "LCNEC"}:
                    neuroendocrine.add(sid)
                if row["feature"] == "SCLC":
                    sclc.add(sid)
    label_status, reason = neladalkib_label(clinical, case["progression"], transformed=bool(neuroendocrine))
    options = [make_option("neladalkib_us", label_status, reason)]
    if sclc:
        options.append(make_option("small_cell_regimen", samples=sclc))
    if changed_histology:
        options.append(make_option("histology_review", samples=changed_histology))
    elif pattern == "systemic" and clinical["setting"] in ADVANCED:
        if clinical["baseline_histology"] in {"adenocarcinoma", "other_nonsquamous"}:
            prior_platinum = clinical["prior_advanced_platinum"]
            if prior_platinum is False:
                options.append(make_option("platinum_pemetrexed"))
            else:
                status = "insufficient_information" if prior_platinum is None else "prior_platinum_review"
                options.append(make_option("platinum_pemetrexed", status,
                                           "既往含铂方案、获益及进展时序需由肿瘤科复核"))
        else:
            options.append(make_option("systemic_histology_review"))
    elif pattern in {"oligoprogression", "isolated_cns"}:
        options.append(make_option("local_treatment"))
    elif pattern == "unknown":
        options.append(make_option("progression_review", "insufficient_information"))

    met_samples = set()
    rare_samples = set()
    shaw_samples = set()
    for row in all_mechanisms:
        key, sid = row["id"], row["sample_id"]
        if key == "met_focal_amplification" and row["level"] == "supported":
            met_samples.add(sid)
        if key == "alk_k1150dup" and row["level"] == "candidate":
            rare_samples.add(sid)
        if key == "alk_c1156y_l1198f" and row["level"] == "supported":
            extra = {finding["feature"] for finding in case["specimens"][sid]["findings"]
                     if finding["gene"] == "ALK" and finding["kind"] == "variant"
                     and finding["status"] == "detected" and finding["qc"] != "fail"}
            if extra == {"C1156Y", "L1198F"}:
                shaw_samples.add(sid)
    if met_samples:
        options.append(make_option("alk_met_combination", "investigational_review", samples=met_samples))
    if rare_samples:
        options.append(make_option("gilteritinib_trial", "trial_eligibility_review", samples=rare_samples))
    if shaw_samples:
        options.append(make_option("crizotinib_case", "case_report_context", samples=shaw_samples))
    if clinical["age_group"] == "adult" and clinical["setting"] in ADVANCED and not neuroendocrine:
        options.append(make_option("alkove_trial", "trial_eligibility_review"))
    return options


def assess(document):
    case = normalize_case(document)
    records, gaps = [], []
    for specimen in case["specimens"].values():
        if specimen["timepoint"] != "progression_on_lorlatinib":
            continue
        positive = [row for row in specimen["findings"] if (
            row["status"] == "detected" and usable(specimen, row)
        )]
        matches = []
        alk_rules(case, specimen, positive, matches)
        met_rules(case, specimen, positive, matches)
        histology_rules(case, specimen, positive, matches)
        exploratory_rules(case, specimen, positive, matches)
        indexed_ids = {item["finding_id"] for match in matches for item in match["evidence"]}
        supported = any(row["level"] == "supported" for row in matches)
        records.append({
            "sample_id": specimen["id"], "material": specimen["material"], "site": specimen["site"],
            "qc": specimen["qc"], "genome_build": specimen["genome_build"],
            "tumor_fraction": specimen["tumor_fraction"], "baseline_sample_id": specimen["baseline_sample_id"],
            "tumor_fraction_method": specimen["tumor_fraction_method"],
            "state": "supported_hypothesis" if supported else "unresolved",
            "mechanisms": matches, "assays": list(specimen["assays"].values()),
            "findings": specimen["findings"],
            "unmatched_findings": [row["id"] for row in specimen["findings"] if row["id"] not in indexed_ids],
        })
        gaps.extend(gaps_for(specimen))
    if not records:
        gaps.append({"status": "no_progression_specimen", "reason": "未输入洛拉替尼进展时样本"})
    state = "unresolved"
    if any(row["state"] == "supported_hypothesis" for row in records):
        state = "supported_hypothesis"
    options = clinical_options(case, records)
    sources = {sid for record in records for row in record["mechanisms"] for sid in row["sources"]}
    sources.update(sid for option in options for sid in option["sources"])
    sources.add("ESMO_ctDNA_2022")
    return {
        "schema_version": 1, "knowledge_version": knowledge()["version"],
        "case_id": case["case_id"], "progression": case["progression"],
        "clinical_context": case["clinical"],
        "assessment": state, "specimens": records, "assay_gaps": gaps,
        "unresolved_specimens": [row["sample_id"] for row in records if row["state"] == "unresolved"],
        "clinical_options": options,
        "sources": {sid: knowledge()["sources"][sid] for sid in sorted(sources)},
    }
