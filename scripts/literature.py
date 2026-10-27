#!/usr/bin/env python3
"""Retrieve and audit literature metadata without claiming full-text review.

Standard-library only. HTTPS uses the inherited proxy and CA configuration.
Examples:
  python3 scripts/literature.py search --output data/search.json
  python3 scripts/literature.py verify --input data/sources.json --output data/verified.json
  python3 scripts/literature.py rank --input data/sources.json --ranks data/journal_ranks.csv --year 2025 --output data/ranked.json

Ranking CSV columns: journal,issn,category,rank,jif_year,source. A supplied CSV
provides a reproducible selection rule, not independent JCR authentication.
"""

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
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
DEFAULT_START = "2011-10-21"
DEFAULT_END = "2026-10-21"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def plain_text(value: Any) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).strip()


def normalized_title(value: Any) -> str:
    value = unicodedata.normalize("NFKC", plain_text(value)).casefold()
    return "".join(c for c in value if c.isalnum())


def normalized_doi(value: Any) -> str:
    value = str(value or "").strip().casefold()
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value)


class LiteratureError(RuntimeError):
    def __init__(self, message: str, *, diagnostic: dict[str, Any]):
        super().__init__(message)
        self.diagnostic = diagnostic


class EuropePMCClient:
    def __init__(self, *, timeout: float = 20, retries: int = 1,
                 cache_dir: str | pathlib.Path | None = None):
        if timeout <= 0 or retries < 0:
            raise ValueError("timeout must be positive and retries nonnegative")
        self.timeout = timeout
        self.retries = retries
        self.cache_dir = pathlib.Path(cache_dir) if cache_dir else None

    def request(self, query: str, *, cursor: str = "*", page_size: int = 100) -> dict:
        parameters = {"query": query, "format": "json", "resultType": "core",
                      "pageSize": min(max(page_size, 1), 1000), "cursorMark": cursor}
        url = API_URL + "?" + urllib.parse.urlencode(parameters)
        cache_path = None
        if self.cache_dir:
            cache_path = self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".json")
            if cache_path.is_file():
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if cached.get("request_url") == url and isinstance(cached.get("response"), dict):
                    response = copy.deepcopy(cached["response"])
                    response["_retrieval"] = {"request_url": url, "cached": True,
                                               "retrieved_at": cached["retrieved_at"]}
                    return response
        for attempt in range(1, self.retries + 2):
            status = None
            try:
                request = urllib.request.Request(url, headers={
                    "User-Agent": "lungcancer-tme-literature-audit/1.0",
                    "Accept": "application/json"})
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.load(response)
                if not isinstance(payload, dict) or "resultList" not in payload:
                    raise ValueError("Europe PMC returned an unexpected JSON structure")
                retrieved_at = utc_now()
                if cache_path:
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(json.dumps({"request_url": url,
                        "retrieved_at": retrieved_at, "response": payload}, ensure_ascii=False,
                        indent=2), encoding="utf-8")
                payload["_retrieval"] = {"request_url": url, "cached": False,
                                           "retrieved_at": retrieved_at}
                return payload
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                    OSError, ValueError) as error:
                if isinstance(error, urllib.error.HTTPError):
                    status = error.code
                else:
                    match = re.search(r"\b(401|403|429|5\d\d)\b", str(error))
                    status = int(match.group(1)) if match else None
                blocked = status in (401, 403)
                retryable = not blocked and (status is None or status == 429 or status >= 500)
                if retryable and attempt <= self.retries:
                    time.sleep(min(attempt, 2))
                    continue
                kind = "access_denied" if blocked else "retrieval_failed"
                raise LiteratureError(str(error), diagnostic={
                    "kind": kind, "http_status": status, "attempts": attempt,
                    "request_url": url, "query": query, "observed_at": utc_now(),
                    "error": str(error),
                    "required_domain": "www.ebi.ac.uk",
                    "guidance": "Use the supported environment network settings or existing authentication. "
                                "Do not disable TLS verification or bypass the proxy.",
                }) from error
        raise AssertionError("unreachable")


def build_query(start: str, end: str) -> str:
    first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if first > last:
        raise ValueError("start must not be after end")
    return (
        '((TITLE_ABS:EGFR OR TITLE_ABS:"epidermal growth factor receptor") '
        'AND (TITLE_ABS:"lung cancer" OR TITLE_ABS:NSCLC OR TITLE_ABS:"lung adenocarcinoma") '
        'AND (TITLE_ABS:resistan* OR TITLE_ABS:toleran* OR TITLE_ABS:osimertinib '
        'OR TITLE_ABS:gefitinib OR TITLE_ABS:erlotinib) '
        'AND (TITLE_ABS:microenvironment OR TITLE_ABS:fibroblast* OR TITLE_ABS:macrophage* '
        'OR TITLE_ABS:immune OR TITLE_ABS:cytokine* OR TITLE_ABS:chemokine* '
        'OR TITLE_ABS:FGF OR TITLE_ABS:VEGF OR TITLE_ABS:HGF OR TITLE_ABS:angiogen* '
        f'OR TITLE_ABS:stromal)) AND FIRST_PDATE:[{first.isoformat()} TO {last.isoformat()}]'
    )


def record_to_reference(record: dict) -> dict:
    journal_info = record.get("journalInfo") or {}
    journal = journal_info.get("journal") or {}
    pmid = str(record.get("pmid") or "")
    doi = normalized_doi(record.get("doi"))
    identifier = str(record.get("id") or pmid or doi)
    source = record.get("source", "MED")
    year_text = str(record.get("pubYear") or "")
    return {
        "id": "EPMC_" + source + "_" + identifier,
        "title": plain_text(record.get("title")),
        "authors": record.get("authorString", ""),
        "year": int(year_text) if year_text.isdigit() else None,
        "first_publication_date": record.get("firstPublicationDate", ""),
        "journal": journal.get("title") or journal.get("medlineAbbreviation") or "",
        "issn": journal.get("issn", ""), "doi": doi, "pmid": pmid,
        "url": ("https://doi.org/" + doi if doi else
                "https://europepmc.org/article/" + source + "/" + identifier),
        "abstract": plain_text(record.get("abstractText")),
        "verification": "metadata_retrieved", "full_text_reviewed": False,
        "evidence_scope": "unscreened",
        "screening_status": "requires_human_eligibility_and_claim_review",
        "journal_rank": None, "rank_status": "unranked",
    }


def search_literature(client: EuropePMCClient, *, start: str, end: str,
                      max_results: int = 200) -> dict:
    if max_results < 1:
        raise ValueError("max_results must be positive")
    query = build_query(start, end)
    output = {"status": "in_progress", "query": query, "searched_at": utc_now(),
              "date_field": "FIRST_PDATE", "window_start": start, "window_end": end,
              "provider": "Europe PMC", "max_results": max_results,
              "references": [], "retrievals": [], "diagnostics": [],
              "ranking_status": "No journal ranking has been applied.",
              "full_text_reviewed": False}
    cursor, seen_records, seen_cursors = "*", set(), set()
    try:
        while len(output["references"]) < max_results:
            page = client.request(query, cursor=cursor,
                                  page_size=min(100, max_results - len(output["references"])))
            output["retrievals"].append(page.get("_retrieval", {}))
            output["total_hits"] = int(page.get("hitCount", 0))
            records = page.get("resultList", {}).get("result", [])
            for record in records:
                key = (record.get("source"), record.get("id"))
                if key not in seen_records:
                    output["references"].append(record_to_reference(record))
                    seen_records.add(key)
                if len(output["references"]) >= max_results:
                    break
            next_cursor = page.get("nextCursorMark")
            if (not records or not next_cursor or next_cursor == cursor or
                    next_cursor in seen_cursors):
                break
            seen_cursors.add(cursor)
            cursor = next_cursor
        output["retrieved_count"] = len(output["references"])
        output["truncated"] = output.get("total_hits", 0) > len(output["references"])
        output["status"] = "complete"
    except LiteratureError as error:
        output["status"] = "blocked" if error.diagnostic["kind"] == "access_denied" else "failed"
        output["diagnostics"].append(error.diagnostic)
        output["retrieved_count"] = len(output["references"])
        output["truncated"] = True
    return output


def matching_record(seed: dict, candidates: list[dict]) -> dict | None:
    """Require title AND catalogue publication year; DOI also when supplied."""
    title = normalized_title(seed.get("title"))
    year = str(seed.get("year") or "")
    if not title or not re.fullmatch(r"\d{4}", year):
        return None
    doi = normalized_doi(seed.get("doi"))
    matches = []
    for record in candidates:
        if normalized_title(record.get("title")) != title or str(record.get("pubYear")) != year:
            continue
        if doi and normalized_doi(record.get("doi")) != doi:
            continue
        matches.append(record)
    if len(matches) == 1:
        return matches[0]
    # Duplicate index representations are not an independent match to select arbitrarily.
    return None


def verify_references(client: EuropePMCClient, document: dict | list) -> dict:
    result = copy.deepcopy(document if isinstance(document, dict) else {"references": document})
    if not isinstance(result.get("references"), list):
        raise ValueError("Input must be a reference list or an object containing references")
    diagnostics = []
    verification = {"provider": "Europe PMC", "checked_at": utc_now(),
                    "match_policy": "normalized exact title AND pubYear AND DOI when supplied",
                    "full_text_reviewed": False, "diagnostics": diagnostics}
    result["metadata_verification"] = verification
    blocked = False
    for seed in result["references"]:
        if blocked:
            seed["verification"] = "unverified_network_blocked"
            seed["verification_details"] = {"reason": "Earlier request was denied; no unchanged retry made.",
                                               "full_text_reviewed": False}
            continue
        if not normalized_title(seed.get("title")) or not re.fullmatch(r"\d{4}", str(seed.get("year", ""))):
            seed["verification"] = "unverified_invalid_seed"
            continue
        doi = normalized_doi(seed.get("doi"))
        # Title quotes are removed, never interpreted as query operators.
        query = ('DOI:"' + doi.replace('"', '') + '"') if doi else (
            'TITLE:"' + plain_text(seed["title"]).replace('"', '') + '"')
        try:
            page = client.request(query, page_size=100)
            candidates = page.get("resultList", {}).get("result", [])
            record = matching_record(seed, candidates)
            details = {"query": query, "retrieval": page.get("_retrieval", {}),
                       "candidate_count": len(candidates), "full_text_reviewed": False}
            if record:
                canonical = record_to_reference(record)
                seed["verified_metadata"] = {key: canonical[key] for key in
                    ("title", "authors", "year", "journal", "issn", "doi", "pmid", "url")}
                seed["verification"] = "metadata_verified"
                details["record_id"] = record.get("id")
                details["matched_fields"] = ["normalized_title", "pubYear"] + (["doi"] if doi else [])
            else:
                seed["verification"] = "unverified_no_unique_exact_match"
            seed["verification_details"] = details
        except LiteratureError as error:
            diagnostics.append(error.diagnostic)
            seed["verification"] = "unverified_network_error"
            seed["verification_details"] = {"error": error.diagnostic, "full_text_reviewed": False}
            blocked = error.diagnostic["kind"] == "access_denied"
    statuses = [r.get("verification", "") for r in result["references"]]
    verification["verified_count"] = statuses.count("metadata_verified")
    verification["reference_count"] = len(statuses)
    verification["status"] = ("blocked" if blocked else "partial" if diagnostics or any(
        status != "metadata_verified" for status in statuses) else "complete")
    return result


def normalized_journal(value: Any) -> str:
    return normalized_title(value)


def load_journal_ranks(path: str | pathlib.Path | None) -> list[dict]:
    """Read supplied ranks, rejecting malformed data, not authenticating JCR."""
    if path is None:
        return []
    required = {"journal", "issn", "category", "rank", "jif_year", "source"}
    ranks, seen = [], set()
    with pathlib.Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Ranking CSV requires: " + ",".join(sorted(required)))
        for line, row in enumerate(reader, 2):
            if not any(str(v or "").strip() for v in row.values()):
                continue
            row = {key: (row.get(key) or "").strip() for key in required}
            try:
                rank, year = int(row["rank"]), int(row["jif_year"])
            except ValueError as error:
                raise ValueError(f"Invalid integer rank/year at CSV line {line}") from error
            if rank < 1 or not 1900 <= year <= 2100:
                raise ValueError(f"Invalid rank/year at CSV line {line}")
            if not row["journal"] or not row["category"] or not row["source"]:
                raise ValueError(f"Journal, category and source required at CSV line {line}")
            issns = re.split(r"[;,|\s]+", row["issn"]) if row["issn"] else []
            if any(not re.fullmatch(r"\d{4}-\d{3}[\dXx]", issn) for issn in issns):
                raise ValueError(f"Invalid ISSN at CSV line {line}")
            key = (normalized_journal(row["journal"]), row["category"].casefold(), year)
            if key in seen:
                raise ValueError(f"Duplicate journal/category/year at CSV line {line}")
            seen.add(key)
            row.update(rank=rank, jif_year=year, issns=[x.upper() for x in issns],
                       provenance_status="user_supplied_unverified")
            ranks.append(row)
    return ranks


def annotate_journal_ranks(references: list[dict], ranks: list[dict], *, max_rank: int = 79,
                           jif_year: int | None = None, categories: list[str] | None = None) -> list[dict]:
    if max_rank < 1:
        raise ValueError("max_rank must be positive")
    output = copy.deepcopy(references)
    categories_set = {x.casefold() for x in categories or []}
    available_years = [r["jif_year"] for r in ranks if not categories_set or
                       r["category"].casefold() in categories_set]
    selected_year = jif_year if jif_year is not None else (
        max(available_years) if available_years else None)
    for ref in output:
        source_metadata = ref.get("verified_metadata") or ref
        journal = normalized_journal(source_metadata.get("journal"))
        issn = str(source_metadata.get("issn") or "").upper()
        matches = [r for r in ranks if (
            normalized_journal(r["journal"]) == journal or (issn and issn in r["issns"]))
            and r["jif_year"] == selected_year
            and (not categories_set or r["category"].casefold() in categories_set)]
        if not matches:
            ref.update(journal_rank=None, rank_year=selected_year, rank_source=None,
                       rank_status="unranked", rank_eligible=None, rank_matches=[])
            continue
        chosen = min(matches, key=lambda r: r["rank"])
        ref.update(journal_rank=chosen["rank"], rank_year=selected_year,
                   rank_source=chosen["source"], rank_status="user_supplied_unverified",
                   rank_eligible=chosen["rank"] <= max_rank, rank_matches=matches,
                   rank_rule=f"rank <= {max_rank} in any supplied selected category; "
                             "one common latest supplied year when year is unspecified; not independent JCR verification")
    return output


def apply_journal_ranks(references: list[dict], ranks: list[dict], *, rank_limit: int = 79,
                        jif_year: int | None = None, categories: list[str] | None = None) -> list[dict]:
    """Generator-friendly alias; all references use one common ranking year."""
    return annotate_journal_ranks(references, ranks, max_rank=rank_limit,
                                  jif_year=jif_year, categories=categories)


def read_document(path: str) -> dict | list:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def write_document(path: str, document: dict | list) -> None:
    target = pathlib.Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    search = sub.add_parser("search", help="Retrieve candidate metadata; not a systematic-review inclusion decision")
    search.add_argument("--start", default=DEFAULT_START)
    search.add_argument("--end", default=DEFAULT_END)
    search.add_argument("--max-results", type=int, default=200)
    search.add_argument("--output", required=True)
    verify = sub.add_parser("verify", help="Require exact title/year and DOI where provided")
    verify.add_argument("--input", required=True)
    verify.add_argument("--output", required=True)
    for command in (search, verify):
        command.add_argument("--timeout", type=float, default=20)
        command.add_argument("--retries", type=int, default=1)
        command.add_argument("--cache-dir", default=".cache/literature")
    rank = sub.add_parser("rank", help="Apply a supplied journal ranking CSV without fabricating missing ranks")
    rank.add_argument("--input", required=True)
    rank.add_argument("--ranks")
    rank.add_argument("--output", required=True)
    rank.add_argument("--year", type=int)
    rank.add_argument("--max-rank", type=int, default=79)
    rank.add_argument("--category", action="append")
    args = parser.parse_args(argv)
    try:
        if args.command == "rank":
            document = read_document(args.input)
            result = copy.deepcopy(document if isinstance(document, dict) else {"references": document})
            result["references"] = annotate_journal_ranks(result["references"],
                load_journal_ranks(args.ranks), max_rank=args.max_rank, jif_year=args.year,
                categories=args.category)
            result["ranking_audit"] = {"source_file": args.ranks, "requested_jif_year": args.year,
                "max_rank": args.max_rank, "categories": args.category,
                "independently_verified_jcr": False,
                "status": "user_supplied_unverified" if args.ranks else "unranked"}
            code = 0
        else:
            client = EuropePMCClient(timeout=args.timeout, retries=args.retries, cache_dir=args.cache_dir)
            if args.command == "search":
                result = search_literature(client, start=args.start, end=args.end, max_results=args.max_results)
                code = 0 if result["status"] == "complete" else 3
            else:
                result = verify_references(client, read_document(args.input))
                status = result["metadata_verification"]["status"]
                code = 0 if status == "complete" else 3 if status == "blocked" else 2
        write_document(args.output, result)
        print(json.dumps({"output": args.output, "exit_code": code,
                          "status": result.get("status") or result.get("metadata_verification", {}).get("status")
                          or result.get("ranking_audit", {}).get("status")}, ensure_ascii=False))
        return code
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("Error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
