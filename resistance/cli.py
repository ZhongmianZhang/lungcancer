"""Dependency-free command line: strict JSON / annotated CSV in, JSON or Markdown out."""
import argparse
import csv
import json
import sys
from pathlib import Path

from .engine import InputError, assess, load_knowledge
from .literature import fetch_searches, search_plan


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def read_json(path):
    def invalid_constant(value):
        raise InputError(f'Non-finite JSON constant: {value}')
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=_pairs,
                      parse_constant=invalid_constant)


def read_csv(path):
    required = {'id', 'sample_id', 'gene', 'alteration', 'assay', 'significance'}
    optional = {'variant', 'phosphosite', 'functional_confirmation', 'orthogonal_confirmation',
                'internal_positive_control', 'baseline_status', 'baseline_sample_id', 'baseline_comparable',
                'fusion_in_frame', 'kinase_domain_retained'}
    booleans = {'functional_confirmation', 'orthogonal_confirmation', 'internal_positive_control', 'baseline_comparable',
                'fusion_in_frame', 'kinase_domain_retained'}
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle, strict=True)
        header = reader.fieldnames
        if (not header or len(header) != len(set(header)) or not required <= set(header)
                or set(header) - required - optional):
            raise InputError('CSV requires unique documented finding columns including id/sample_id/gene/alteration/assay/significance')
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise InputError('CSV row has too many or too few columns')
            parsed = {key: value.strip() for key, value in row.items() if value.strip()}
            for key in booleans & parsed.keys():
                if parsed[key] not in {'true', 'false'}:
                    raise InputError(f'CSV {key} must be lowercase true/false or empty')
                parsed[key] = parsed[key] == 'true'
            rows.append(parsed)
        return rows


def markdown(report):
    def text(value):
        return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|').replace('\n', ' ')
    lines = ['# PI3K/AKT/mTOR 耐药研究性判读', '', report['disclaimer_zh'], '',
             f'状态：{text(report["status"])}；治疗背景：{text(report["treatment_setting"])}',
             '', '**来源尚未完成全文核验；没有提供自动治疗推荐。**', '', '## 优先核对', '']
    lines += [f'- {text(item)}' for item in report['priority_actions_zh']]
    lines += ['', '## 解释与局限', '']
    lines += [f'- {text(item)}' for item in report['warnings_zh']]
    lines += ['', '## 候选机制与研究方向', '']
    if not report['candidates']:
        lines.append('未生成候选。此结果不能排除耐药机制或通路活动。')
    for candidate in report['candidates']:
        lines += [f'### {text(candidate["rule_id"])} — {text(candidate["node_zh"])}', '',
                  f'依据：{text(candidate["finding_id"])}；支持层级：{text(candidate["support_level"])}；时间关系：{text(candidate["temporal_interpretation"])}。',
                  '', text(candidate['mechanism_zh']), '',
                  f'人群适用性：{text(candidate["population_fit"])}；因果尚未建立。', '',
                  f'机制证据：{text(candidate["mechanism_evidence"]["level"])}；治疗证据：{text(candidate["treatment_evidence"]["level"])}。', '',
                  '需要确认：', '']
        lines += [f'- {text(item)}' for item in candidate['confirmation_needed_zh']]
        lines += ['', '研究方向（不构成处方或治疗匹配）：', '']
        lines += [f'- {text(item)}' for item in candidate['research_options_zh']] or ['- 无可由该读数直接推导的治疗方向。']
        lines += ['', '局限：', ''] + [f'- {text(item)}' for item in candidate['limitations_zh']]
        lines += ['', '来源与支持用途：', '']
        for source in candidate['sources']:
            # Registry URLs are curated; input sample content cannot inject links.
            lines.append(f'- [{text(source["id"])}]({source["url"]})：{text(source["title"])}；{text(source["year"])}；本规则用途 {text(source["rule_support_role"])}；{text(source["verification_status"])}。')
        lines.append('')
    lines += ['## 未用于判读的输入', '']
    lines += [f'- {text(item["finding_id"])}：{text(item["reason"])}' for item in report['unmatched_findings']] or ['无。']
    return '\n'.join(lines) + '\n'


def write_output(content, output, force=False):
    if output is None:
        print(content, end='' if content.endswith('\n') else '\n')
    else:
        with Path(output).open('w' if force else 'x', encoding='utf-8') as handle:
            handle.write(content)
            if not content.endswith('\n'):
                handle.write('\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description='EGFR NSCLC pathway research support; not a diagnostic or prescribing tool.')
    sub = parser.add_subparsers(dest='command', required=True)
    evaluate = sub.add_parser('assess', help='Generate hypotheses from curated findings (not raw NGS reads/VCF)')
    evaluate.add_argument('case')
    evaluate.add_argument('--findings-csv', help='Use annotated CSV; JSON findings must be empty')
    evaluate.add_argument('--format', choices=['json', 'markdown'], default='json')
    evaluate.add_argument('--out')
    evaluate.add_argument('--force', action='store_true')
    catalog = sub.add_parser('catalog', help='Show complete evidence status, source registry, and rules')
    catalog.add_argument('--out')
    catalog.add_argument('--force', action='store_true')
    queries = sub.add_parser('queries', help='Print reproducible eight-node Europe PMC search plan (offline)')
    queries.add_argument('--out')
    queries.add_argument('--force', action='store_true')
    search = sub.add_parser('search', help='Run static literature queries; never uploads case data')
    search.add_argument('--node', choices=['all'] + list(search_plan()['queries']), default='all')
    search.add_argument('--max-pages', type=int, default=3)
    search.add_argument('--out', required=True)
    search.add_argument('--force', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'assess':
            case = read_json(args.case)
            if args.findings_csv:
                if not isinstance(case, dict) or case.get('findings') != []:
                    raise InputError('With --findings-csv, JSON must explicitly contain findings: []')
                case['findings'] = read_csv(args.findings_csv)
            report = assess(case)
            content = markdown(report) if args.format == 'markdown' else json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
        elif args.command == 'catalog':
            content = json.dumps(load_knowledge(), ensure_ascii=False, indent=2)
        elif args.command == 'queries':
            content = json.dumps(search_plan(), ensure_ascii=False, indent=2)
        else:
            if not 1 <= args.max_pages <= 100:
                raise InputError('--max-pages must be 1–100')
            # Check destination before network work; never silently overwrite.
            if Path(args.out).exists() and not args.force:
                raise FileExistsError(args.out)
            report = fetch_searches(args.node, args.max_pages)
            write_output(json.dumps(report, ensure_ascii=False, indent=2), args.out, args.force)
            print(f'Literature search status: {report["status"]}; saved audit log to {args.out}', file=sys.stderr)
            return 0 if report['status'] == 'metadata_retrieved' else 3
        write_output(content, args.out, args.force)
        return 0
    except (InputError, OSError, ValueError, csv.Error) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
