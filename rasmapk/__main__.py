from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .engine import analyze
from .knowledge import BASE, load_knowledge
from .render import write_case, write_catalog


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="RAS/RAF/MAPK耐药研究工具；不用于自动处方")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-knowledge")
    a = sub.add_parser("analyze")
    a.add_argument("--input", required=True, type=Path)
    a.add_argument("--output", required=True, type=Path)
    b = sub.add_parser("build")
    b.add_argument("--output", type=Path, default=BASE.parent / "site/ras-mapk")
    b.add_argument("--example", type=Path, default=BASE / "examples/braf_v600e.json")
    m = sub.add_parser("recheck-metadata")
    m.add_argument("--output", type=Path, default=BASE / "generated/metadata_audit.json")
    args = p.parse_args(argv)
    try:
        kb = load_knowledge()
        if args.command == "validate-knowledge":
            print(json.dumps({"status": "valid", "counts": kb["counts"], "window": kb["window"]}, ensure_ascii=False))
        elif args.command == "analyze":
            result = analyze(json.loads(args.input.read_text(encoding="utf-8")), kb)
            write_case(result, kb, args.output)
            print(json.dumps({"status": "research_report_generated", "findings": len(result["findings"]), "output": str(args.output)}, ensure_ascii=False))
        elif args.command == "build":
            path = write_catalog(kb, args.output)
            (args.output / "README.md").write_text((BASE / "README.md").read_text(encoding="utf-8"), encoding="utf-8")
            result = analyze(json.loads(args.example.read_text(encoding="utf-8")), kb)
            (args.output / "example_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps({"html": str(path), "counts": kb["counts"]}, ensure_ascii=False))
        else:
            from .retrieve import recheck
            audit = recheck(kb, args.output)
            print(json.dumps({"status": audit["status"], "matched": audit["matched_count"], "total": audit["publication_count"], "output": str(args.output)}, ensure_ascii=False))
            return 0 if audit["status"] == "complete" else 3
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print("错误：" + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
