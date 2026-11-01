from __future__ import annotations

import calendar
import datetime as dt
import html
import json
from pathlib import Path
import re

BASE = Path(__file__).resolve().parent
START = dt.date(2016, 11, 1)
END = dt.date(2026, 11, 1)


def plain(value: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(html.unescape(value)))


def date_in_window(value: str) -> bool | None:
    parts = value.split("-")
    if len(parts) == 3:
        day = dt.date.fromisoformat(value)
        return START <= day <= END
    if len(parts) == 2:
        year, month = map(int, parts)
        first = dt.date(year, month, 1)
        last = dt.date(year, month, calendar.monthrange(year, month)[1])
    elif len(parts) == 1 and value.isdigit():
        first, last = dt.date(int(value), 1, 1), dt.date(int(value), 12, 31)
    else:
        raise ValueError("Invalid publication date: " + value)
    if last < START or first > END:
        return False
    return True if first >= START and last <= END else None


def load_knowledge(directory: Path | None = None) -> dict:
    directory = directory or BASE / "knowledge"
    paths = sorted(directory.glob("node[0-9][0-9].json"))
    if [p.stem for p in paths] != [f"node{i:02}" for i in range(1, 11)]:
        raise ValueError("Exactly ten completed node modules (node01..node10) are required")
    nodes, evidence, seen = [], [], set()
    for path in paths:
        node = json.loads(path.read_text(encoding="utf-8"))
        if node.get("node_id") != path.stem:
            raise ValueError(f"Node identity mismatch: {path}")
        for field in ("title", "genes", "mechanism_zh", "biomarker_interpretation", "treatment_hypotheses", "evidence", "research_gaps"):
            if not node.get(field):
                raise ValueError(f"{path.name}: missing {field}")
        local_ids = set()
        for ref in node["evidence"]:
            if not ref.get("id") or ref["id"] in seen:
                raise ValueError("Missing or duplicate evidence ID")
            seen.add(ref["id"]); local_ids.add(ref["id"])
            ref["title"] = plain(ref["title"])
            ref["node_id"] = node["node_id"]
            ref["in_window"] = date_in_window(ref["publication_date"])
            if ref["in_window"] is not True:
                raise ValueError(f"Evidence outside or uncertain date window: {ref['id']}")
            if ref.get("full_text_reviewed") is not False:
                raise ValueError("This edition must not claim full-text review")
            if ref.get("verification") not in {"metadata_abstract_checked", "metadata_only", "unverified"}:
                raise ValueError(f"Unknown verification state: {ref['id']}")
            if ref.get("design") == "conference_abstract" and ref.get("verification") == "metadata_only":
                ref["result_interpretation_allowed"] = False
            else:
                ref["result_interpretation_allowed"] = ref.get("verification") == "metadata_abstract_checked"
            evidence.append(ref)
        for strategy in node["treatment_hypotheses"]:
            if set(strategy.get("evidence_ids", [])) - local_ids:
                raise ValueError(f"Unresolved strategy citation in {node['node_id']}")
        nodes.append(node)
    unique = {}
    for ref in evidence:
        key = "PMID:" + str(ref["pmid"]) if ref.get("pmid") else "DOI:" + ref["doi"].casefold()
        if key not in unique:
            unique[key] = {**ref, "source_ids": [ref["id"]], "node_ids": [ref["node_id"]]}
        else:
            unique[key]["source_ids"].append(ref["id"])
            unique[key]["node_ids"].append(ref["node_id"])
    return {"version": "1.0.0", "window": {"start": str(START), "end": str(END)},
            "nodes": nodes, "evidence": evidence, "unique_evidence": list(unique.values()),
            "agent_count": 10,
            "counts": {"nodes": len(nodes), "evidence_assertions": len(evidence), "unique_publications": len(unique),
                       "abstract_checked": sum(r["verification"] == "metadata_abstract_checked" for r in unique.values()),
                       "metadata_only": sum(r["verification"] == "metadata_only" for r in unique.values()),
                       "full_text_reviewed": 0}}


def citations(kb: dict, nodes: list[str]) -> list[str]:
    return [ref["id"] for ref in kb["evidence"] if ref["node_id"] in nodes]
