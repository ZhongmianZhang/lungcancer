"""Recheck curated bibliography against live Europe PMC/Crossref metadata.

Clinical input never enters these requests. Abstract interpretation is separately
attributed to node reviewers; metadata checks do not assert full-text review.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import urllib.parse
import urllib.request

from scripts.literature import EuropePMCClient, LiteratureError, normalized_title
from .knowledge import plain


def recheck(kb: dict, output: Path) -> dict:
    client = EuropePMCClient(timeout=30, retries=1)
    refs = kb["unique_evidence"]
    by_pmid = {}
    med = [r for r in refs if r.get("pmid")]
    requests, errors = [], []
    for offset in range(0, len(med), 20):
        group = med[offset:offset + 20]
        query = "SRC:MED AND (" + " OR ".join('EXT_ID:"' + str(r["pmid"]) + '"' for r in group) + ")"
        try:
            page = client.request(query, page_size=100)
            requests.append(page.get("_retrieval", {}))
            for record in page.get("resultList", {}).get("result", []):
                by_pmid[str(record.get("pmid"))] = record
        except LiteratureError as error:
            errors.append(error.diagnostic)
            if error.diagnostic.get("http_status") in (401, 403):
                break
    records = []
    for ref in refs:
        canonical = None
        provider = "Europe PMC" if ref.get("pmid") else "Crossref"
        if ref.get("pmid"):
            found = by_pmid.get(str(ref["pmid"]))
            if found:
                canonical = {"title": found.get("title", ""), "doi": found.get("doi", ""),
                             "first_publication_date": found.get("firstPublicationDate"),
                             "journal": (found.get("journalInfo", {}).get("journal") or {}).get("title", ""),
                             "abstract_available": bool(found.get("abstractText"))}
        else:
            url = "https://api.crossref.org/works/" + urllib.parse.quote(ref["doi"], safe="")
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "lungcancer-rasmapk-research/1.0"}), timeout=30) as response:
                    message = json.load(response)["message"]
                canonical = {"title": (message.get("title") or [""])[0], "doi": message.get("DOI", ""),
                             "first_publication_date": message.get("published", {}).get("date-parts"),
                             "journal": (message.get("container-title") or [""])[0],
                             "abstract_available": bool(message.get("abstract"))}
                requests.append({"request_url": url})
            except (OSError, ValueError, KeyError) as error:
                errors.append({"url": url, "error": str(error)})
        title_match = bool(canonical) and normalized_title(plain(canonical["title"])) == normalized_title(plain(ref["title"]))
        doi_match = bool(canonical) and canonical["doi"].casefold() == ref["doi"].casefold()
        records.append({"source_ids": ref["source_ids"], "pmid": ref.get("pmid"), "doi": ref["doi"],
                        "provider": provider, "status": "matched" if title_match and doi_match else "needs_review",
                        "title_match": title_match, "doi_match": doi_match, "canonical": canonical,
                        "full_text_reviewed": False})
    result = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "status": "complete" if not errors and all(r["status"] == "matched" for r in records) else "incomplete",
              "publication_count": len(records), "matched_count": sum(r["status"] == "matched" for r in records),
              "requests": requests, "errors": errors, "records": records,
              "scope": "Bibliographic recheck only; node reviewers read abstracts; no claim of full-text or regulatory verification."}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
