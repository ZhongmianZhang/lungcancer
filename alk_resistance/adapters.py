"""Import signed-out TSV findings or protein annotations from somatic VCF."""

import csv
import gzip
import json
import re
from collections import Counter
from pathlib import Path

from .input import InputError, is_alk_reference, list_value, protein_key


TSV_COLUMNS = {"sample_id", "assay_id", "id", "kind", "gene", "feature", "status", "qc", "attributes_json"}
ANN_FIELDS = (
    "Allele", "Annotation", "Annotation_Impact", "Gene_Name", "Gene_ID",
    "Feature_Type", "Feature_ID", "Transcript_BioType", "Rank", "HGVS.c", "HGVS.p",
)
# VCF processing is intentionally limited to genes used by the curated rules.
VCF_GENES = {
    "ALK", "BRAF", "CDKN2A", "CDKN2B", "EGFR", "FAT1", "FLT1", "HDAC6",
    "KRAS", "LRP5", "MAP2K1", "MET", "NF2", "NTRK1", "PIK3CA", "PTEN", "RB1", "TP53", "XRCC2",
}


def specimen_row(document, sample_id):
    for row in list_value(document.get("specimens", []), "specimens"):
        if isinstance(row, dict) and row.get("id") == sample_id:
            return row
    raise InputError(f"导入文件引用未知样本 {sample_id}")


def import_tsv(document, path):
    count = 0
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if (reader.fieldnames is None or not TSV_COLUMNS <= set(reader.fieldnames)
                or len(reader.fieldnames) != len(set(reader.fieldnames))):
            raise InputError(f"{Path(path).name} 的 TSV 标题不合规")
        for line, row in enumerate(reader, 2):
            if None in row or any(row[header] is None for header in TSV_COLUMNS):
                raise InputError(f"{Path(path).name}:{line} 列数错误")
            attrs = row.pop("attributes_json")
            try:
                row["attributes"] = json.loads(attrs) if attrs.strip() else {}
            except ValueError as error:
                raise InputError(f"{Path(path).name}:{line} attributes_json 不是有效 JSON") from error
            sample = specimen_row(document, row.pop("sample_id"))
            list_value(sample.setdefault("findings", []), "findings").append(row)
            count += 1
    return {"importer": "findings_tsv", "imported": count}


def open_vcf(path):
    return gzip.open(path, "rt", encoding="utf-8") if str(path).endswith((".gz", ".bgz")) else Path(path).open(encoding="utf-8")


def vep_allele(ref, alt):
    if alt.startswith("<") or "[" in alt or "]" in alt or alt in {"*", "."}:
        return alt
    while ref and alt and ref[-1] == alt[-1] and (len(ref) > 1 or len(alt) > 1):
        ref, alt = ref[:-1], alt[:-1]
    while ref and alt and ref[0] == alt[0]:
        ref, alt = ref[1:], alt[1:]
    return alt or "-"


def allele_number(annotation, ref, alts):
    number = annotation.get("ALLELE_NUM", "")
    if number:
        return int(number) if number.isdecimal() and 1 <= int(number) <= len(alts) else None
    allele = annotation.get("Allele", "")
    candidates = [i for i, alt in enumerate(alts, 1) if allele in {alt, vep_allele(ref, alt)}]
    return candidates[0] if len(candidates) == 1 else None


def number_or_none(text):
    try:
        value = int(text)
        return value if value >= 0 else None
    except (ValueError, TypeError):
        return None


def allele_attributes(fields, idx, alt_count, contig, assay_id, trust_phase):
    attrs = {}
    depth = number_or_none(fields.get("DP"))
    if depth is not None:
        attrs["depth"] = depth
    depths = [number_or_none(x) for x in fields.get("AD", "").split(",")]
    if len(depths) == alt_count + 1:
        if depths[idx] is not None:
            attrs["alt_depth"] = depths[idx]
        if None not in depths and sum(depths) > 0:
            attrs["vaf"] = depths[idx] / sum(depths)
    genotype = fields.get("GT", ".")
    phase_set = fields.get("PS", ".")
    if (trust_phase and depth != 0 and attrs.get("alt_depth") != 0
            and phase_set.isdecimal() and re.fullmatch(r"[0-9]+\|[0-9]+", genotype)):
        alleles = [int(allele) for allele in genotype.split("|")]
        # Homozygous and caller-specific multi-ALT genotypes do not prove subclonal linkage.
        if all(allele <= alt_count for allele in alleles) and 0 in alleles and alleles.count(idx) == 1:
            attrs["phase"] = {
                "method": "read_backed", "block": f"{assay_id}:{contig}:{phase_set}",
                "haplotype": str(alleles.index(idx) + 1),
            }
    return attrs


def row_annotations(info, formats, index):
    for token in info.split(";"):
        name, _, values = token.partition("=")
        if name == "CSQ" and name not in formats:
            raise InputError(f"VCF 第 {index} 行有 CSQ，但标题缺少 VEP Format")
        if name not in formats:
            continue
        for value in values.split(","):
            yield dict(zip(formats[name], value.split("|")))


def import_vcf(document, sample_id, assay_id, tumor_sample, path, *, trust_phase=False):
    specimen = specimen_row(document, sample_id)
    assays = list_value(specimen.get("assays", []), "assays")
    if not any(isinstance(assay, dict) and assay.get("id") == assay_id for assay in assays):
        raise InputError(f"VCF 引用了未知检测 {sample_id}/{assay_id}")
    findings = list_value(specimen.setdefault("findings", []), "findings")
    formats = {"ANN": ANN_FIELDS}
    counts = Counter()
    tumor_col = None
    header_seen = False
    seen = set()
    with open_vcf(path) as handle:
        for index, line in enumerate(handle, 1):
            line = line.rstrip("\r\n")
            if line.startswith("##INFO=<ID=CSQ,"):
                match = re.search(r'Format:\s*([^"]+)"', line)
                if match:
                    formats["CSQ"] = tuple(part.strip() for part in match[1].split("|"))
            if line.startswith("#CHROM\t"):
                columns = line.split("\t")
                if tumor_sample == "-" and len(columns) != 8:
                    raise InputError("有样本列的 VCF 必须显式选择肿瘤样本")
                if tumor_sample != "-":
                    if columns[9:].count(tumor_sample) != 1:
                        raise InputError(f"VCF 肿瘤样本列 {tumor_sample} 缺失或重复")
                    tumor_col = columns.index(tumor_sample, 9)
                header_seen = True
            if line.startswith("#") or not line:
                continue
            columns = line.split("\t")
            if not header_seen or len(columns) < 8 or (tumor_col is not None and len(columns) <= tumor_col):
                raise InputError(f"VCF 第 {index} 行缺少标题或字段")
            contig, position, _, ref, alt, _, record_filter, info = columns[:8]
            if not position.isdecimal() or int(position) < 1:
                raise InputError(f"VCF 第 {index} 行的 POS 无效")
            counts["records_read"] += 1
            alts = alt.split(",")
            sample_fields = {} if tumor_col is None else dict(zip(columns[8].split(":"), columns[tumor_col].split(":")))
            called = re.split(r"[/|]", sample_fields.get("GT", "."))
            for ann in row_annotations(info, formats, index):
                gene = (ann.get("SYMBOL") or ann.get("Gene_Name") or "").upper()
                hgvsp = ann.get("HGVSp") or ann.get("HGVS.p")
                if gene not in VCF_GENES or not hgvsp or hgvsp == ".":
                    continue
                transcript = ann.get("MANE_SELECT") or ann.get("Feature") or ann.get("Feature_ID") or ""
                if gene == "ALK" and not is_alk_reference(transcript):
                    counts["alk_non_reference_or_unidentified_transcript"] += 1
                    continue
                idx = allele_number(ann, ref, alts)
                if idx is None:
                    counts["ambiguous_alt_annotation"] += 1
                    continue
                if not re.fullmatch(r"[ACGTN]+", ref) or not re.fullmatch(r"[ACGTN]+", alts[idx - 1]):
                    counts["non_sequence_allele"] += 1
                    continue
                if any(a.isdecimal() for a in called) and str(idx) not in called:
                    counts["alt_not_in_selected_genotype"] += 1
                    continue
                feature = protein_key(hgvsp)
                record = (contig, position, ref, alts[idx - 1], gene, feature)
                if record in seen:
                    continue
                seen.add(record)
                attrs = allele_attributes(sample_fields, idx, len(alts), contig, assay_id, trust_phase)
                attrs["genomic"] = f"{contig}:{position}:{ref}>{alts[idx - 1]}"
                if transcript:
                    attrs["transcript"] = transcript
                if ann.get("HGVSc") or ann.get("HGVS.c"):
                    attrs["coding"] = ann.get("HGVSc") or ann["HGVS.c"]
                sample_filter = sample_fields.get("FT", ".")
                qc = "fail"
                if record_filter in {"PASS", "."} and sample_filter in {"PASS", ".", ""}:
                    qc = "pass" if record_filter == "PASS" else "unknown"
                if attrs.get("depth") == 0 or attrs.get("alt_depth") == 0:
                    qc = "fail"
                    counts["zero_support"] += 1
                elif tumor_col is not None and str(idx) not in called and "alt_depth" not in attrs:
                    qc = "unknown" if qc != "fail" else qc
                    counts["tumor_allele_support_unknown"] += 1
                findings.append({
                    "id": f"vcf:{assay_id}:{index}:{idx}:{gene}:{feature}",
                    "assay_id": assay_id, "kind": "variant", "gene": gene, "feature": feature,
                    "status": "detected", "qc": qc, "attributes": attrs,
                })
                counts["imported"] += 1
    if not header_seen:
        raise InputError("VCF 缺少 #CHROM 标题")
    counts.setdefault("imported", 0)
    return {"importer": "annotated_somatic_vcf", "sample_id": sample_id, "assay_id": assay_id, **counts}
