"""Interpret curated ALK fusion junctions and co-alteration associations."""

import re

from .input import TKI_TIMES, is_alk_reference, usable


FUSION = re.compile(r"^([A-Z][A-Z0-9.-]*)::ALK$")
EML4_JUNCTIONS = {"13": "v1", "20": "v2", "6": "v3", "6a": "v3", "6b": "v3"}
PATHOGENIC = {"pathogenic", "likely_pathogenic"}
PROFILE_GENES = {"TP53", "CDKN2A", "CDKN2B", "RB1", "NF2", "MET", "CD274", "MTAP"}


def exon(value):
    if type(value) in (int, str):
        text = str(value).strip().lower().removeprefix("exon").strip().removeprefix("e")
        if re.fullmatch(r"[1-9][0-9]*[ab]?", text):
            return text
    return None


def declared_variant(value):
    if type(value) not in (int, str):
        return None
    text = str(value).strip().lower().removeprefix("variant").strip().removeprefix("v")
    if text in {"3", "3a", "3b", "3a/b", "3ab"}:
        return "v3"
    return "v" + text if re.fullmatch(r"[1-9][0-9]*[ab]?", text) else None


def profile_entry(data, key):
    return {"id": key, **data["profiles"][key]}


def fusion_call(data, specimen, row):
    attrs = row["attributes"]
    match = FUSION.fullmatch(row["feature"].strip().upper())
    partner = match[1] if match else None
    partner_exon = exon(attrs.get("partner_exon"))
    alk_exon = exon(attrs.get("alk_exon"))
    declared = declared_variant(attrs.get("reported_variant"))
    inferred = EML4_JUNCTIONS.get(partner_exon) if partner == "EML4" and alk_exon == "20" else None
    assay = specimen["assays"][row["assay_id"]]
    expressed = (assay["modality"] in {"rna", "single_cell_rna"}
                 and attrs.get("in_frame") is True and attrs.get("kinase_domain_retained") is True)

    status, family, key = "transcript_unresolved", None, "fusion_unresolved"
    if row["status"] == "detected" and usable(specimen, row):
        if inferred and declared and inferred != declared:
            status = "discordant_junction"
        elif partner and expressed:
            if partner != "EML4":
                status, family, key = "verified_transcript", "non_eml4", "fusion_non_eml4"
            elif partner_exon and alk_exon:
                status, family = "verified_transcript", inferred or "other_eml4"
                key = {
                    "v1": "fusion_v1_v2", "v2": "fusion_v1_v2", "v3": "fusion_v3",
                    "other_eml4": "fusion_other_eml4",
                }[family]
        elif inferred:
            status = "junction_prediction_only"

    return {
        **profile_entry(data, key), "finding_id": row["id"], "assay_id": row["assay_id"],
        "reported_feature": row["feature"], "partner": partner, "partner_exon": partner_exon,
        "alk_exon": alk_exon, "reported_variant": declared, "candidate_variant": inferred,
        "transcript_family": family, "status": status,
    }


def pathogenic_variant(row):
    return row["kind"] == "variant" and row["attributes"].get("classification") in PATHOGENIC


def loss_of_function(row):
    attrs = row["attributes"]
    return ((pathogenic_variant(row) and attrs.get("loss_of_function") is True)
            or (row["kind"] == "copy_number" and row["feature"] == "homozygous_deletion"
                and attrs.get("validated_call") is True))


def documented_focal(row):
    attrs = row["attributes"]
    return (row["kind"] == "copy_number" and row["feature"] == "amplification"
            and attrs.get("focality") == "focal" and attrs.get("validated_call") is True
            and isinstance(attrs.get("criteria"), str) and bool(attrs["criteria"].strip()))


def mtap_loss(specimen, row):
    if row["gene"] != "MTAP" or specimen["material"] != "tissue":
        return False
    attrs = row["attributes"]
    if row["kind"] == "copy_number":
        return row["feature"] == "homozygous_deletion" and attrs.get("validated_call") is True
    return (row["kind"] == "expression" and row["feature"] == "complete_loss"
            and specimen["assays"][row["assay_id"]]["modality"] == "pathology"
            and attrs.get("internal_control_positive") is True)


def coalteration(data, specimen, row):
    gene = row["gene"]
    attrs = row["attributes"]
    if row["status"] != "detected" or not usable(specimen, row):
        return None
    if gene in {"TP53", "RB1", "NF2"} and specimen["material"] in {"plasma", "csf"}:
        if attrs.get("tumor_origin") != "confirmed":
            return {**profile_entry(data, "circulating_origin"), "gene": gene,
                    "feature": row["feature"], "finding_id": row["id"],
                    "assay_id": row["assay_id"]}
    key = None
    if gene == "TP53" and pathogenic_variant(row):
        key = "tp53_prognosis"
    elif gene in {"CDKN2A", "CDKN2B"} and loss_of_function(row):
        key = "cdkn2ab_prognosis"
    elif gene == "RB1" and loss_of_function(row):
        key = "rb1_lineage"
    elif gene == "NF2" and loss_of_function(row):
        key = "nf2_coalteration"
    elif gene == "MET" and documented_focal(row):
        key = "met_coalteration"
    elif mtap_loss(specimen, row):
        key = "mtap_trial_marker"
    elif gene == "CD274" and row["kind"] == "expression" and row["feature"] == "TPS":
        assay = specimen["assays"][row["assay_id"]]
        percent = attrs.get("value")
        if (assay["modality"] == "pathology" and specimen["material"] == "tissue"
                and attrs.get("unit") == "percent" and type(percent) in (int, float)
                and 50 <= percent <= 100):
            key = "pdl1_context"
    if key is None:
        return None
    return {**profile_entry(data, key), "gene": gene, "feature": row["feature"],
            "finding_id": row["id"], "assay_id": row["assay_id"]}


def assess_profiles(case, data):
    progression = case["progression"]
    pre, post = TKI_TIMES[progression["failed_tki"]]
    months = progression["months_to_progression"]
    early_alectinib = (progression["failed_tki"] == "alectinib" and progression["tki_line"] == 1
                       and progression["best_response"] == "PD" and months is not None and months <= 3)
    profiles = []
    for specimen in case["specimens"].values():
        if specimen["timepoint"] not in {pre, post}:
            continue
        stage = "before_tki" if specimen["timepoint"] == pre else "progression"
        fusions = []
        alterations = []
        experimental = []
        for row in specimen["findings"]:
            if row["gene"] == "ALK" and row["kind"] == "fusion":
                fusions.append(fusion_call(data, specimen, row))
            if row["gene"] in PROFILE_GENES:
                result = coalteration(data, specimen, row)
                if result is not None:
                    alterations.append(result)
            if row["gene"] == "ALK" and row["kind"] == "variant" and row["status"] == "detected" and usable(specimen, row):
                key = data["alk_model_features"].get(row["feature"])
                reference = row["attributes"].get("transcript")
                if key and (reference is None or is_alk_reference(reference)):
                    experimental.append({**profile_entry(data, key), "finding_id": row["id"],
                                         "assay_id": row["assay_id"], "variant": row["feature"]})
        if not fusions and not alterations and not experimental:
            continue
        identities = {(item["partner"], item["transcript_family"]) for item in fusions if item["transcript_family"]}
        tp53_ids = [item["finding_id"] for item in alterations if item["id"] == "tp53_prognosis"]
        joint = []
        discordance = any(item["status"] == "discordant_junction" for item in fusions)
        if stage == "before_tki" and identities == {("EML4", "v3")} and not discordance and tp53_ids:
            v3_ids = [item["finding_id"] for item in fusions if item["transcript_family"] == "v3"]
            joint.append({**profile_entry(data, "v3_tp53"), "finding_ids": v3_ids + tp53_ids})
        nf2_ids = [item["finding_id"] for item in alterations if item["id"] == "nf2_coalteration"]
        if stage == "before_tki" and early_alectinib and nf2_ids:
            joint.append({**profile_entry(data, "alectinib_early_nf2"), "finding_ids": nf2_ids})
        profiles.append({
            "sample_id": specimen["id"], "stage": stage, "material": specimen["material"],
            "multiple_verified_families": len(identities) > 1, "discordant_junction": discordance,
            "fusions": fusions, "coalterations": alterations, "joint_associations": joint,
            "experimental_associations": experimental,
        })
    return profiles
