#!/usr/bin/env python3
"""Build a self-contained, auditable Chinese research report using Python stdlib."""

from __future__ import annotations

import argparse
import copy
import csv
import datetime as dt
import hashlib
import html
import json
import pathlib
import re
import sys
from typing import Any

from literature import annotate_journal_ranks, load_journal_ranks, normalized_title

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCOPES = {
    "egfr_lung_direct": "EGFR肺癌直接实验",
    "egfr_lung_association": "EGFR肺癌人体关联",
    "other_cancer": "非EGFR特定／跨癌种背景",
    "review": "综述与概念框架",
    "clinical_trial": "临床试验",
}


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def date_eligibility(reference: dict, start: dt.date, end: dt.date) -> tuple[bool | None, str]:
    """Do not invent a publication day when only a boundary year is known."""
    raw = reference.get("publication_date") or reference.get("first_publication_date")
    if raw:
        day = dt.date.fromisoformat(raw)
        return start <= day <= end, "exact_date"
    year = reference.get("year")
    if not isinstance(year, int):
        return None, "publication_year_missing"
    if year < start.year or year > end.year:
        return False, "year_outside_window"
    if (year == start.year and start != dt.date(year, 1, 1)) or (
        year == end.year and end != dt.date(year, 12, 31)
    ):
        return None, "boundary_date_unconfirmed"
    return True, "year_sufficient_for_window"


def validate_module(module: dict, source: str) -> None:
    if not isinstance(module.get("references"), list) or not isinstance(module.get("mechanisms"), list):
        raise ValueError(f"{source}: references and mechanisms must be lists")
    for ref in module["references"]:
        for key in ("id", "title", "journal", "verification", "evidence_scope"):
            if not isinstance(ref.get(key), str) or not ref[key].strip():
                raise ValueError(f"{source}: reference requires {key}")
        if not isinstance(ref.get("year"), int) or not 1900 <= ref["year"] <= 2100:
            raise ValueError(f"{source}: invalid year for {ref['id']}")
        if ref["evidence_scope"] not in SCOPES:
            raise ValueError(f"{source}: unknown evidence_scope for {ref['id']}")
        if ref.get("doi") and not re.fullmatch(r"10\.\d{4,9}/\S+", ref["doi"], re.I):
            raise ValueError(f"{source}: malformed DOI for {ref['id']}")
        if ref.get("url") and not ref["url"].startswith("https://"):
            raise ValueError(f"{source}: reference URL must use HTTPS")
    for mechanism in module["mechanisms"]:
        for key in ("id", "title", "category", "summary", "clinical_boundary", "evidence_level"):
            if not mechanism.get(key):
                raise ValueError(f"{source}: mechanism requires {key}")
        for key in ("chain", "details", "references", "research_questions", "nodes", "edges"):
            if not isinstance(mechanism.get(key), list) or not mechanism[key]:
                raise ValueError(f"{source}: mechanism requires nonempty {key}")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", mechanism["id"]):
            raise ValueError("Mechanism IDs must be safe HTML identifiers")
        nodes = set(mechanism["nodes"])
        for edge in mechanism["edges"]:
            if edge.get("source") not in nodes or edge.get("target") not in nodes:
                raise ValueError(f"{mechanism['id']}: graph edge refers to unknown node")


def merge_modules(modules: list[dict]) -> tuple[list[dict], list[dict], list[str]]:
    references, mechanisms, aliases, identities, notes = [], [], {}, {}, []
    original_ids: set[str] = set()
    for module in modules:
        for original in module["references"]:
            ref = copy.deepcopy(original)
            if ref["id"] in original_ids:
                raise ValueError(f"Duplicate reference ID: {ref['id']}")
            original_ids.add(ref["id"])
            key = ("doi", ref["doi"].casefold()) if ref.get("doi") else (
                "title", normalized_title(ref["title"]), ref["year"])
            if key in identities:
                canonical = identities[key]
                aliases[ref["id"]] = canonical["id"]
                canonical.setdefault("source_ids", [canonical["id"]]).append(ref["id"])
                if normalized_title(canonical["title"]) != normalized_title(ref["title"]):
                    notes.append(f"同DOI题名不一致，需人工核对：{canonical['id']} / {ref['id']}")
            else:
                identities[key] = ref
                aliases[ref["id"]] = ref["id"]
                references.append(ref)
        mechanisms.extend(copy.deepcopy(module["mechanisms"]))
    ids: set[str] = set()
    for m in mechanisms:
        if m["id"] in ids:
            raise ValueError(f"Duplicate mechanism ID: {m['id']}")
        ids.add(m["id"])
        unknown = set(m["references"]) - set(aliases)
        if unknown:
            raise ValueError(f"{m['id']}: unresolved references {sorted(unknown)}")
        m["references"] = list(dict.fromkeys(aliases[r] for r in m["references"]))
    return references, mechanisms, notes


def apply_verified_metadata(references: list[dict], document: dict | None) -> None:
    if not document:
        return
    updates = {r["id"]: r for r in document.get("references", [])}
    for ref in references:
        update = updates.get(ref["id"])
        if not update:
            continue
        if normalized_title(update.get("title")) != normalized_title(ref["title"]) or update.get("year") != ref["year"]:
            raise ValueError(f"Verified input does not match seed identity: {ref['id']}")
        for key in ("verification", "verification_details", "verified_metadata", "metadata_verification"):
            if key in update:
                ref[key] = copy.deepcopy(update[key])
        if ref.get("verification") == "metadata_verified" and ref.get("verified_metadata"):
            canonical = ref["verified_metadata"]
            if normalized_title(canonical.get("title")) != normalized_title(ref["title"]) or canonical.get("year") != ref["year"]:
                raise ValueError(f"Canonical metadata does not match seed: {ref['id']}")
            ref["seed_metadata"] = {key: ref.get(key) for key in ("title", "authors", "year", "journal", "doi", "pmid", "url")}
            for key in ("title", "authors", "journal", "issn", "doi", "pmid", "url", "first_publication_date"):
                if canonical.get(key):
                    ref[key] = canonical[key]
            ref["exact_title"] = True
        # Downloading metadata never constitutes full-text review.
        ref["full_text_reviewed"] = False


def build_dataset(data_dir: pathlib.Path, *, start: str, end: str,
                  rank_file: pathlib.Path | None = None, rank_year: int | None = None,
                  rank_limit: int = 79, strict_ranking: bool = False,
                  verified_file: pathlib.Path | None = None,
                  search_file: pathlib.Path | None = None) -> dict:
    first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if first > last:
        raise ValueError("Start date must not be after end date")
    module_paths = [data_dir / "stromal.json", data_dir / "immune.json"]
    modules = []
    for path in module_paths:
        module = read_json(path)
        validate_module(module, path.name)
        modules.append(module)
    refs, mechanisms, dedup_notes = merge_modules(modules)
    overview = read_json(data_dir / "overview.json")
    verification_document = read_json(verified_file) if verified_file else None
    apply_verified_metadata(refs, verification_document)
    ranks = load_journal_ranks(rank_file)
    refs = annotate_journal_ranks(refs, ranks, max_rank=rank_limit, jif_year=rank_year)
    for ref in refs:
        ref["in_window"], ref["date_status"] = date_eligibility(ref, first, last)
        ref["evidence_scope_label"] = SCOPES[ref["evidence_scope"]]
        ref.setdefault("exact_title", False)
        ref.setdefault("full_text_reviewed", False)
    if strict_ranking:
        if not ranks or rank_year is None:
            raise ValueError("Strict ranking requires an explicit ranking CSV and --jif-year")
        excluded = [r["id"] for r in refs if r["in_window"] is not False and not r.get("rank_eligible")]
        if excluded:
            raise ValueError("Strict ranking failed; references lack an eligible supplied rank: " + ", ".join(excluded))
    search = read_json(search_file) if search_file and search_file.is_file() else {"status": "not_run"}
    verified = sum(r["verification"] == "metadata_verified" for r in refs)
    inside = sum(r["in_window"] is True for r in refs)
    eligible = sum(r.get("rank_eligible") is True and r["in_window"] is True for r in refs)
    counts = {
        "references": len(refs), "mechanisms": len(mechanisms), "in_window": inside,
        "outside_window": sum(r["in_window"] is False for r in refs),
        "date_uncertain": sum(r["in_window"] is None for r in refs),
        "metadata_verified": verified, "fulltext_reviewed": 0,
        "rank_eligible": eligible, "jcr_independently_verified": 0,
        "journals": len({r["journal"].casefold() for r in refs}),
    }
    ranking_status = ("已按提供榜单匹配；榜单真实性未独立核验" if ranks else
                      "未提供JCR榜单；未应用IF前79名筛选")
    meta = {
        "title": overview.pop("title"), "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec="seconds"),
        "window_start": start, "window_end": end, "ranking_status": ranking_status,
        "network_status": {"blocked": "文献数据库访问被网络策略拒绝，系统检索尚未完成。",
                           "failed": "文献数据库检索失败，需检查检索审计。",
                           "complete": "已执行候选文献检索；仍需人工筛选和全文审校。",
                           "not_run": "尚未执行数据库检索。"}.get(search.get("status", "not_run"), "数据库检索状态待确认。"),
        "search_status": search.get("status", "not_run"),
        "scope_note": "机制研究草稿：书目信息、结论与期刊排名需分层核验，尚非完成系统检索的综述。",
        "ranking_file": str(rank_file) if rank_file else None,
        "requested_jif_year": rank_year, "rank_limit": rank_limit,
        "strict_ranking": strict_ranking,
        "source_sha256": {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in module_paths + [data_dir / "overview.json"]},
    }
    limitations = [
        "候选文献清单不等同于完成数据库系统检索；403访问失败不是零检索结果。",
        "尚未取得用户指定版本的JCR学科榜单，不声称符合IF前79名。",
        "书目信息核对与机制全文审校相互独立；metadata_verified不表示结论已核验。",
        "其他癌种机制、单细胞关联与临床试验效果不能替代EGFR肺癌患者级因果证据。",
        "奥希替尼联合化疗、埃万妥单抗及ADC后的完整治疗序列缺少本报告直接核验的证据。",
    ]
    if ranks:
        limitations[1] = "使用输入榜单的排名规则，不等于已独立认证该榜单或全部JCR收录条件。"
    audit = {
        "counts": counts,
        "checks": ["机制引用均能解析", "重复文献已按DOI／规范题名合并", "日期边界不臆造发表日",
                   "未填造IF或期刊排名", "未将书目下载标为全文阅读"],
        "limitations": limitations, "deduplication_notes": dedup_notes,
        "search": {key: search.get(key) for key in ("status", "query", "searched_at", "total_hits", "retrieved_count", "truncated", "diagnostics")},
        "ranking": {"file": str(rank_file) if rank_file else None, "jif_year": rank_year,
                    "max_rank": rank_limit, "independently_verified_jcr": False},
        "metadata_verification": (verification_document or {}).get("metadata_verification", {"status": "not_run"}),
    }
    return {"meta": meta, "references": refs, "mechanisms": mechanisms,
            "overview": overview, "audit": audit}


def safe_json(document: dict) -> str:
    """Prevent JSON data from ending its HTML script element."""
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).replace(
        "<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace(
        "\u2028", "\\u2028").replace("\u2029", "\\u2029")


def static_content(data: dict) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    parts = ["<h2>离线正文与证据清单</h2>"]
    parts.extend(f"<p>{esc(p)}</p>" for p in data["overview"]["intro"])
    parts.append("<h2>核心判断</h2><ul>")
    parts.extend(f"<li>{esc(p)}</li>" for p in data["overview"].get("conclusions", []))
    parts.append("</ul><h2>微环境反馈关系</h2>")
    for loop in data["overview"].get("crosstalk", []):
        parts.append(f'<h3>{esc(loop["title"])}</h3><p>{esc(loop["chain"])}</p><p>{esc(loop["description"])}</p>')
    for mechanism in data["mechanisms"]:
        parts.append(f'<section id="static-{esc(mechanism["id"])}"><h3>{esc(mechanism["title"])}</h3>')
        parts.append(f'<p><strong>证据：</strong>{esc(mechanism["evidence_level"])}</p>')
        parts.append(f'<p>{esc(" → ".join(mechanism["chain"]))}</p>')
        parts.extend(f"<p>{esc(p)}</p>" for p in mechanism["details"])
        parts.append(f'<p><strong>临床边界：</strong>{esc(mechanism["clinical_boundary"])}</p>')
        parts.append("<h4>可检验的研究问题</h4><ul>")
        parts.extend(f"<li>{esc(q)}</li>" for q in mechanism["research_questions"])
        parts.append("</ul>")
        parts.append('<p>参考：' + " · ".join(f'<a href="#static-ref-{esc(i)}">{esc(i)}</a>' for i in mechanism["references"]) + '</p></section>')
    parts.append("<h2>转化研究方向</h2>")
    for direction in data["overview"].get("translational", []):
        parts.append(f'<h3>{esc(direction["title"])}</h3><p>{esc(direction["description"])}</p><p>{esc(direction["evidence"])}</p>')
    parts.append("<h2>参考文献候选清单</h2>")
    for ref in data["references"]:
        title_note = "" if ref["exact_title"] else "［题名待核对／检索线索］"
        parts.append(f'<article id="static-ref-{esc(ref["id"])}"><p><strong>{esc(ref["id"])}</strong> '
                     f'{esc(title_note + ref["title"])}. {esc(ref.get("authors", ""))}. '
                     f'{esc(ref["journal"])} ({esc(ref["year"])}). '
                     f'<a href="{esc(ref.get("url", ""))}" target="_blank" rel="noopener noreferrer">检索原文</a></p>'
                     f'<p>核验：{esc(ref["verification"])}；范围：{esc(ref["evidence_scope_label"])}；'
                     f'排名：{esc(ref["rank_status"])}；时间窗：{esc(ref["in_window"])}</p>'
                     f'<p>{esc(ref.get("finding_zh", ""))}</p><p>{esc(ref.get("limitation_zh", ""))}</p></article>')
    parts.append("<h2>方法与限制</h2>")
    parts.extend(f"<p>{esc(p)}</p>" for p in data["overview"]["methods"])
    return "\n".join(parts)


def write_outputs(data: dict, output_dir: pathlib.Path, template_dir: pathlib.Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    template = (template_dir / "report.html").read_text(encoding="utf-8")
    replacements = {
        "__REPORT_CSS__": (template_dir / "report.css").read_text(encoding="utf-8"),
        "__REPORT_JS__": (template_dir / "report.js").read_text(encoding="utf-8"),
        "__STATIC_CONTENT__": static_content(data), "__REPORT_DATA__": safe_json(data),
    }
    for token, value in replacements.items():
        if token not in template:
            raise ValueError("Template missing placeholder: " + token)
        template = template.replace(token, value)
    if re.search(r"__(?:REPORT|STATIC)_[A-Z_]+__", template):
        raise ValueError("Unresolved template placeholder")
    page = output_dir / "egfr_tme_resistance.html"
    page.write_text(template, encoding="utf-8")
    json_files = {"report_data.json": data, "evidence_audit.json": data["audit"]}
    for name, document in json_files.items():
        (output_dir / name).write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = ["id", "title", "authors", "year", "journal", "doi", "pmid", "url", "verification",
              "evidence_scope", "exact_title", "in_window", "date_status", "journal_rank", "rank_year", "rank_source", "rank_status", "rank_eligible"]
    with (output_dir / "references.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(data["references"])
    return {"html": str(page), "data": str(output_dir / "report_data.json"), "audit": str(output_dir / "evidence_audit.json")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=pathlib.Path, default=ROOT / "data")
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "reports")
    parser.add_argument("--templates", type=pathlib.Path, default=ROOT / "templates")
    parser.add_argument("--start", default="2011-10-21")
    parser.add_argument("--end", default="2026-10-21")
    parser.add_argument("--journal-ranks", type=pathlib.Path)
    parser.add_argument("--jif-year", type=int)
    parser.add_argument("--rank-limit", type=int, default=79)
    parser.add_argument("--strict-ranking", action="store_true")
    parser.add_argument("--verified-references", type=pathlib.Path)
    parser.add_argument("--search-results", type=pathlib.Path, default=ROOT / "reports/search_results.json")
    args = parser.parse_args(argv)
    try:
        data = build_dataset(args.data_dir, start=args.start, end=args.end,
            rank_file=args.journal_ranks, rank_year=args.jif_year, rank_limit=args.rank_limit,
            strict_ranking=args.strict_ranking, verified_file=args.verified_references,
            search_file=args.search_results)
        paths = write_outputs(data, args.output, args.templates)
        print(json.dumps({"outputs": paths, "counts": data["audit"]["counts"],
                          "ranking_status": data["meta"]["ranking_status"]}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Build failed: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
