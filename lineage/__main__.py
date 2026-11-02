from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .knowledge import BASE, load_knowledge
from .engine import analyze
from .render import write_catalog,write_case


def main(argv=None):
    p=argparse.ArgumentParser(description='EGFR保留与组织学转化研究工具；不自动诊断或处方')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('validate-knowledge')
    a=sub.add_parser('analyze');a.add_argument('--input',required=True,type=Path);a.add_argument('--output',required=True,type=Path)
    b=sub.add_parser('build');b.add_argument('--output',type=Path,default=BASE.parent/'site/lineage');b.add_argument('--example',type=Path,default=BASE/'examples/sclc_retained_egfr.json')
    r=sub.add_parser('recheck-metadata');r.add_argument('--output',type=Path,default=BASE/'generated/metadata_audit.json')
    s=sub.add_parser('search');s.add_argument('--query',required=True);s.add_argument('--provider',choices=['auto','firecrawl','europepmc'],default='auto');s.add_argument('--limit',type=int,default=10);s.add_argument('--output',required=True,type=Path)
    args=p.parse_args(argv)
    try:
        if args.command=='search':
            from .search import search,write_search
            result=search(args.query,provider=args.provider,limit=args.limit);write_search(result,args.output)
            print(json.dumps({'status':result['status'],'actual_provider':result.get('actual_provider'),'output':str(args.output)},ensure_ascii=False))
            return 0 if result['status']=='complete' else 3
        kb=load_knowledge()
        if args.command=='validate-knowledge':
            print(json.dumps({'status':'valid','counts':kb['counts'],'window':kb['window']},ensure_ascii=False))
        elif args.command=='analyze':
            result=analyze(json.loads(args.input.read_text(encoding='utf-8')),kb);write_case(result,kb,args.output)
            print(json.dumps({'status':'research_report_generated','output':str(args.output)},ensure_ascii=False))
        elif args.command=='build':
            write_catalog(kb,args.output)
            (args.output/'README.md').write_text((BASE/'README.md').read_text(encoding='utf-8'),encoding='utf-8')
            result=analyze(json.loads(args.example.read_text(encoding='utf-8')),kb)
            (args.output/'example_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(json.dumps({'html':str(args.output/'index.html'),'counts':kb['counts']},ensure_ascii=False))
        else:
            from rasmapk.retrieve import recheck
            audit=recheck(kb,args.output)
            print(json.dumps({'status':audit['status'],'matched':audit['matched_count'],'total':audit['publication_count']},ensure_ascii=False))
            return 0 if audit['status']=='complete' else 3
        return 0
    except (ValueError,OSError,KeyError,TypeError) as error:
        print('错误：'+str(error),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
