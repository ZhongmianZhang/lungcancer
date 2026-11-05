from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .knowledge import BASE, START, END, load_knowledge
from .engine import analyze
from .render import write_catalog, write_case


def write_json(output, value):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main(argv=None):
    p = argparse.ArgumentParser(description='机制未明的EGFR耐药多组学研究；不诊断或处方')
    sub = p.add_subparsers(dest='command', required=True)
    v = sub.add_parser('validate-knowledge'); v.add_argument('--ranks', type=Path)
    a = sub.add_parser('analyze'); a.add_argument('--input', required=True, type=Path); a.add_argument('--output', required=True, type=Path); a.add_argument('--ranks', type=Path)
    b = sub.add_parser('build'); b.add_argument('--output', type=Path, default=BASE.parent/'site/multiomics'); b.add_argument('--ranks', type=Path)
    r = sub.add_parser('rank'); r.add_argument('--ranks', required=True, type=Path); r.add_argument('--output', required=True, type=Path)
    m = sub.add_parser('recheck-metadata'); m.add_argument('--output', type=Path, default=BASE/'generated/metadata_audit.json')
    s = sub.add_parser('search'); s.add_argument('--query', required=True); s.add_argument('--provider', choices=['auto', 'firecrawl', 'europepmc'], default='auto'); s.add_argument('--limit', type=int, default=10); s.add_argument('--output', required=True, type=Path)
    try:
        args = p.parse_args(argv)
        if args.command == 'search':
            from lineage.search import search, write_search
            result = search(args.query, provider=args.provider, limit=args.limit, start=str(START), end=str(END))
            write_search(result, args.output)
            print(json.dumps({'status': result['status'], 'actual_provider': result.get('actual_provider')}, ensure_ascii=False))
            return 0 if result['status'] == 'complete' else 3
        kb = load_knowledge(getattr(args, 'ranks', None))
        if args.command == 'validate-knowledge':
            print(json.dumps({'status': 'valid', 'counts': kb['counts'], 'window': kb['window'], 'journal_selection': kb['journal_selection']}, ensure_ascii=False))
        elif args.command == 'analyze':
            write_case(analyze(json.loads(args.input.read_text(encoding='utf-8')), kb), kb, args.output)
            print(json.dumps({'status': 'research_report_generated', 'output': str(args.output)}, ensure_ascii=False))
        elif args.command == 'build':
            write_catalog(kb, args.output)
            (args.output/'README.md').write_text((BASE/'README.md').read_text(encoding='utf-8'), encoding='utf-8')
            case = json.loads((BASE/'examples/plasma_negative.json').read_text(encoding='utf-8'))
            write_case(analyze(case, kb), kb, args.output/'example')
            print(json.dumps({'html': str(args.output/'index.html'), 'counts': kb['counts']}, ensure_ascii=False))
        elif args.command == 'rank':
            result = {'journal_selection': kb['journal_selection'], 'rank_filtered_journal_records': [r for r in kb['unique_evidence'] if r['ranking']['meets_journal_top80']], 'conference_records_separate': [r for r in kb['unique_evidence'] if r['design'] == 'conference_abstract'], 'all_records_with_status': kb['unique_evidence']}
            write_json(args.output, result)
            print(json.dumps({'status': 'supplied_table_applied_not_authenticated', 'passed_journal_records': len(result['rank_filtered_journal_records'])}))
        else:
            from rasmapk.retrieve import recheck
            result = recheck(kb, args.output)
            print(json.dumps({'status': result['status'], 'matched': result['matched_count'], 'total': result['publication_count']}))
            return 0 if result['status'] == 'complete' else 3
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('错误：' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
