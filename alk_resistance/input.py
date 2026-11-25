"""Validate reported observations and normalize protein notation."""

import math
import re
from urllib.parse import unquote


class InputError(ValueError):
    """An input document cannot be interpreted without changing its meaning."""


TKI_TIMES = {
    "alectinib": ("pre_alectinib", "progression_on_alectinib"),
    "lorlatinib": ("pre_lorlatinib", "progression_on_lorlatinib"),
}
PRE_FOR_PROGRESSION = {post: pre for pre, post in TKI_TIMES.values()}
TIMES = {timepoint for pair in TKI_TIMES.values() for timepoint in pair} | {"other", "unknown"}
MATERIALS = {"tissue", "plasma", "csf", "other", "unknown"}
QUALITY = {"pass", "limited", "fail", "unknown"}
COVERAGE = {"adequate", "limited", "not_assayed", "unknown"}
MODALITIES = {
    "targeted_dna", "wgs", "wes", "shallow_wgs", "rna", "fish",
    "pathology", "methylation", "atac", "chip", "long_read_dna",
    "single_cell_rna", "single_cell_atac", "spatial", "other",
}
KIND_MODALITIES = {
    "variant": {"targeted_dna", "wgs", "wes", "rna", "long_read_dna", "other"},
    "copy_number": {"targeted_dna", "wgs", "wes", "shallow_wgs", "fish", "long_read_dna", "other"},
    "fusion": {"targeted_dna", "wgs", "wes", "rna", "fish", "long_read_dna", "single_cell_rna", "other"},
    "structural_variant": {"wgs", "long_read_dna", "targeted_dna", "other"},
    "noncoding_variant": {"wgs", "long_read_dna", "targeted_dna", "other"},
    "histology": {"pathology"},
    "expression": {"rna", "single_cell_rna", "spatial", "pathology", "other"},
    "methylation": {"methylation"},
    "chromatin_accessibility": {"atac", "single_cell_atac"},
    "histone_mark": {"chip", "other"},
}
PHASE_METHODS = {
    "read_backed", "long_read", "molecular_linkage", "statistical", "unknown",
}
PHYSICAL_PHASE = {"read_backed", "long_read", "molecular_linkage"}
ALK_REFERENCE = {"NM_004304", "ENST00000389048", "NP_004295"}
ALK_TKI_NAMES = {
    "alectinib": "alectinib", "alecensa": "alectinib",
    "brigatinib": "brigatinib", "alunbrig": "brigatinib",
    "ceritinib": "ceritinib", "zykadia": "ceritinib",
    "crizotinib": "crizotinib", "xalkori": "crizotinib",
    "ensartinib": "ensartinib", "ensacove": "ensartinib",
    "lorlatinib": "lorlatinib", "lorbrena": "lorlatinib", "lorviqua": "lorlatinib",
    "neladalkib": "neladalkib", "nelkarmi": "neladalkib", "nvl-655": "neladalkib",
    "iruplinalkib": "iruplinalkib", "envonalkib": "envonalkib",
}
AMINO = dict(zip(
    "Ala Arg Asn Asp Cys Gln Glu Gly His Ile Leu Lys Met Phe Pro Ser Thr Trp Tyr Val Ter".split(),
    "ARNDCQEGHILKMFPSTWYV*",
))
SUBSTITUTION = re.compile(r"^([A-Z][a-z]{2}|[A-Z])([1-9][0-9]*)([A-Z][a-z]{2}|[A-Z*]|=|dup)$")


def protein_key(value):
    """Convert simple HGVS substitutions, stops and single-residue duplications."""
    notation = unquote(value.strip()).rsplit(":", 1)[-1].removeprefix("p.")
    if notation.startswith("(") and notation.endswith(")"):
        notation = notation[1:-1]
    match = SUBSTITUTION.fullmatch(notation)
    if match is None:
        return notation
    ref, position, alt = match.groups()
    return f"{AMINO.get(ref, ref)}{position}{AMINO.get(alt, alt)}"


def is_alk_reference(transcript):
    return transcript.split(".", 1)[0] in ALK_REFERENCE


def object_value(value, where):
    if not isinstance(value, dict):
        raise InputError(f"{where} 必须是对象")
    return value


def list_value(value, where):
    if not isinstance(value, list):
        raise InputError(f"{where} 必须是数组")
    return value


def string_value(value, where, *, allow_empty=False):
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise InputError(f"{where} 必须是字符串" if allow_empty else f"{where} 必须是非空字符串")
    return value.strip()


def choice(value, choices, where):
    if not isinstance(value, str) or value not in choices:
        raise InputError(f"{where} 的允许值为 {', '.join(sorted(choices))}")
    return value


def unique_ids(items, where):
    identifiers = set()
    for index, item in enumerate(items, 1):
        item = object_value(item, f"{where}[{index}]")
        ident = string_value(item.get("id"), f"{where}[{index}].id")
        if ident in identifiers:
            raise InputError(f"{where} 中的 id 重复 {ident}")
        identifiers.add(ident)


def normalize_finding(item, assays, where):
    assay = string_value(item.get("assay_id"), f"{where}.assay_id")
    if assay not in assays:
        raise InputError(f"{where} 引用了未知 assay_id {assay}")
    kind = choice(item.get("kind"), KIND_MODALITIES, f"{where}.kind")
    if assays[assay]["modality"] not in KIND_MODALITIES[kind]:
        raise InputError(f"{where} 的检测模态不支持 {kind} 类型")
    feature = string_value(item.get("feature"), f"{where}.feature")
    gene = string_value(item.get("gene", ""), f"{where}.gene", allow_empty=kind == "histology")
    status = choice(item.get("status", "detected"), {"detected", "not_detected"}, f"{where}.status")
    qc = choice(item.get("qc", "unknown"), QUALITY, f"{where}.qc")
    attrs = dict(object_value(item.get("attributes", {}), f"{where}.attributes"))
    if kind == "variant":
        notation = unquote(feature)
        reference, separator, _ = notation.rpartition(":")
        if gene.upper() == "ALK" and separator:
            explicit = attrs.get("transcript")
            if isinstance(explicit, str) and is_alk_reference(reference) != is_alk_reference(explicit):
                raise InputError(f"{where} 的 ALK 蛋白注释前缀与 transcript 矛盾")
            attrs["transcript"] = reference
        feature = protein_key(feature)
    if "phase" in attrs:
        phase = dict(object_value(attrs["phase"], f"{where}.attributes.phase"))
        if kind != "variant":
            raise InputError(f"{where} 只有序列变异支持 phase 字段")
        phase["method"] = choice(phase.get("method", "unknown"), PHASE_METHODS, f"{where}.phase.method")
        for key in ("block", "haplotype"):
            phase[key] = string_value(phase.get(key), f"{where}.phase.{key}")
        attrs["phase"] = phase
    if "transcript" in attrs:
        attrs["transcript"] = string_value(attrs["transcript"], f"{where}.attributes.transcript")
    if "vaf" in attrs and attrs["vaf"] is not None:
        validate_fraction(attrs["vaf"], f"{where}.attributes.vaf")
    return {
        "id": item["id"].strip(), "assay_id": assay, "kind": kind, "gene": gene.upper(),
        "feature": feature, "status": status, "qc": qc, "attributes": attrs,
    }


def validate_fraction(value, where):
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise InputError(f"{where} 必须是 0 到 1 之间的小数")


def usable(specimen, finding):
    attrs = finding["attributes"]
    observed = finding["status"] == "not_detected" or attrs.get("vaf") != 0
    return (observed and specimen["qc"] == "pass" and specimen["tumor_fraction"] != 0
            and finding["qc"] == "pass"
            and attrs.get("tumor_origin") not in ("germline", "hematopoietic")
            and specimen["assays"][finding["assay_id"]]["qc"] == "pass")


def normalize_assays(items, where):
    assays = {}
    unique_ids(items, where)
    for item in items:
        ident = item["id"].strip()
        tag = f"{where}/{ident}"
        modality = choice(item.get("modality"), MODALITIES, f"{tag}.modality")
        coverage = []
        for target in list_value(item.get("coverage", []), f"{tag}.coverage"):
            target = object_value(target, f"{tag}.coverage")
            kind = choice(target.get("kind"), KIND_MODALITIES, f"{tag}.coverage.kind")
            if modality not in KIND_MODALITIES[kind]:
                raise InputError(f"{tag} 的检测模态不支持覆盖声明 {kind}")
            gene = string_value(target.get("gene"), f"{tag}.coverage.gene").upper()
            status = choice(target.get("status"), COVERAGE, f"{tag}.coverage.status")
            feature = string_value(target.get("feature", "*"), f"{tag}.coverage.feature")
            coverage.append({
                "kind": kind, "gene": gene, "status": status,
                "feature": protein_key(feature) if kind == "variant" else feature,
                "details": string_value(target.get("details", ""), f"{tag}.coverage.details", allow_empty=True),
            })
        keys = {(row["kind"], row["gene"], row["feature"]) for row in coverage}
        if len(keys) != len(coverage):
            raise InputError(f"{tag}.coverage 对同一基因、类型和位点有重复声明")
        assays[ident] = {
            "id": ident, "modality": modality, "coverage": coverage,
            "platform": string_value(item.get("platform", "unspecified"), f"{tag}.platform"),
            "platform_version": string_value(item.get("platform_version", "unknown"), f"{tag}.platform_version"),
            "qc": choice(item.get("qc", "unknown"), QUALITY, f"{tag}.qc"),
        }
    return assays


def normalize_clinical(item):
    where = "clinical"
    item = object_value(item, where)
    age = choice(item.get("age_group", "unknown"), {"adult", "pediatric", "unknown"}, "clinical.age_group")
    setting = choice(item.get("setting", "unknown"), {
        "unresectable_locally_advanced", "metastatic", "other", "unknown",
    }, "clinical.setting")
    histology = choice(item.get("baseline_histology", "unknown"), {
        "adenocarcinoma", "other_nonsquamous", "squamous", "unknown",
    }, "clinical.baseline_histology")
    jurisdiction = string_value(item.get("jurisdiction", "unknown"), "clinical.jurisdiction").upper()
    drugs = list_value(item.get("prior_advanced_alk_tkis", []), "clinical.prior_advanced_alk_tkis")
    drugs = [string_value(drug, "clinical.prior_advanced_alk_tkis").casefold() for drug in drugs]
    if any(re.fullmatch(r"[a-z][a-z0-9-]*", drug) is None for drug in drugs):
        raise InputError("clinical.prior_advanced_alk_tkis 使用英文通用名")
    complete = item.get("advanced_treatment_history_complete", False)
    platinum = item.get("prior_advanced_platinum")
    if type(complete) is not bool or (platinum is not None and type(platinum) is not bool):
        raise InputError("既往治疗完整性和含铂治疗字段必须使用布尔值，铂治疗可为 null")
    return {
        "age_group": age, "setting": setting, "baseline_histology": histology,
        "jurisdiction": jurisdiction,
        "prior_advanced_alk_tkis": sorted({ALK_TKI_NAMES[drug] for drug in drugs if drug in ALK_TKI_NAMES}),
        "unrecognized_advanced_alk_tkis": sorted({drug for drug in drugs if drug not in ALK_TKI_NAMES}),
        "advanced_treatment_history_complete": complete, "prior_advanced_platinum": platinum,
    }


def normalize_progression(raw):
    item = object_value(raw, "progression")
    failed_tki = choice(item.get("failed_tki", "lorlatinib"), TKI_TIMES, "progression.failed_tki")
    pattern = choice(item.get("pattern", "unknown"), {
        "systemic", "oligoprogression", "isolated_cns", "unknown",
    }, "progression.pattern")
    if failed_tki != "lorlatinib" and {"lorlatinib_line", "lorlatinib_setting"} & item.keys():
        raise InputError("阿来替尼进展请使用 tki_line 和 tki_setting")
    for new, legacy in (("tki_line", "lorlatinib_line"), ("tki_setting", "lorlatinib_setting")):
        if new in item and legacy in item and item[new] != item[legacy]:
            raise InputError(f"progression.{new} 与旧字段 {legacy} 矛盾")
    line = item.get("tki_line", item.get("lorlatinib_line"))
    if line is not None and (type(line) is not int or line < 1):
        raise InputError("progression.tki_line 必须是正整数或 null")
    setting = choice(item.get("tki_setting", item.get("lorlatinib_setting", "unknown")), {
        "advanced", "other", "unknown",
    }, "progression.tki_setting")
    response = choice(item.get("best_response", "unknown"), {"CR", "PR", "SD", "PD", "unknown"},
                      "progression.best_response")
    months = item.get("months_to_progression")
    if months is not None and (type(months) not in (int, float) or months < 0
                               or (type(months) is float and not math.isfinite(months))):
        raise InputError("progression.months_to_progression 必须是非负有限数字或 null")
    progression = {"failed_tki": failed_tki, "pattern": pattern, "tki_line": line, "tki_setting": setting,
                   "best_response": response, "months_to_progression": months}
    if failed_tki == "lorlatinib":
        progression.update(lorlatinib_line=line, lorlatinib_setting=setting)
    return progression


def normalize_case(document):
    root = object_value(document, "case")
    if type(root.get("schema_version")) is not int or root["schema_version"] != 1:
        raise InputError("schema_version 必须为 1")
    if root.get("disease") != "ALK_fusion_NSCLC":
        raise InputError("disease 必须为 ALK_fusion_NSCLC")
    case_id = string_value(root.get("case_id"), "case_id")
    clinical = normalize_clinical(root.get("clinical", {}))
    progression_input = object_value(root.get("progression", {}), "progression")
    progression = normalize_progression(progression_input)
    rows = list_value(root.get("specimens", []), "specimens")
    unique_ids(rows, "specimens")
    specimens = {}
    for row in rows:
        sid = row["id"].strip()
        where = f"specimens/{sid}"
        assays = normalize_assays(list_value(row.get("assays", []), f"{where}.assays"), f"{where}.assays")
        findings = list_value(row.get("findings", []), f"{where}.findings")
        unique_ids(findings, f"{where}.findings")
        fraction = row.get("tumor_fraction")
        if fraction is not None:
            validate_fraction(fraction, f"{where}.tumor_fraction")
        baseline_id = row.get("baseline_sample_id")
        if baseline_id is not None:
            baseline_id = string_value(baseline_id, f"{where}.baseline_sample_id")
        matched = object_value(row.get("comparable_baseline_assays", {}), f"{where}.comparable_baseline_assays")
        specimens[sid] = {
            "id": sid, "assays": assays, "tumor_fraction": fraction,
            "tumor_fraction_method": string_value(row.get("tumor_fraction_method", "unknown"),
                                                 f"{where}.tumor_fraction_method"),
            "timepoint": choice(row.get("timepoint", "unknown"), TIMES, f"{where}.timepoint"),
            "material": choice(row.get("material", "unknown"), MATERIALS, f"{where}.material"),
            "site": string_value(row.get("site", "unknown"), f"{where}.site"),
            "qc": choice(row.get("qc", "unknown"), QUALITY, f"{where}.qc"),
            "genome_build": choice(row.get("genome_build", "unknown"), {"GRCh37", "GRCh38", "unknown"}, f"{where}.genome_build"),
            "baseline_sample_id": baseline_id, "comparable_baseline_assays": matched,
            "findings": [normalize_finding(f, assays, f"{where}/{f['id']}") for f in findings],
        }
    if ("failed_tki" not in progression_input
            and any(s["timepoint"] in TKI_TIMES["alectinib"] for s in specimens.values())):
        raise InputError("含阿来替尼相关样本时请明确填写 progression.failed_tki")
    for s in specimens.values():
        key = s["baseline_sample_id"]
        if key is None and not s["comparable_baseline_assays"]:
            continue
        baseline = specimens.get(key)
        expected_pre = PRE_FOR_PROGRESSION.get(s["timepoint"])
        if expected_pre is None or baseline is None or baseline["timepoint"] != expected_pre:
            raise InputError(f"样本 {s['id']} 的基线须对应同一种药，并指向用药前样本")
        for post, pre in s["comparable_baseline_assays"].items():
            if post not in s["assays"] or not isinstance(pre, str) or pre not in baseline["assays"]:
                raise InputError(f"样本 {s['id']} 的基线比较引用了未知检测")
    return {
        "case_id": case_id, "clinical": clinical, "specimens": specimens,
        "progression": progression,
    }
