#!/usr/bin/env python3
"""Offline structural checks for lungcancer; no medical or external-link verification."""
import csv
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
errors = []

def check(ok, message):
    if not ok:
        errors.append(message)

paths = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).decode().split('\0')
docs = {root / p: (root / p).read_text(encoding='utf-8') for p in paths if p.endswith('.md')}
check(bool(docs), 'No tracked Markdown documents found')
anchors = {}
for path, content in docs.items():
    explicit = re.findall(r'<a\s+id=[\"\']([^\"\']+)[\"\']\s*>', content)
    check(len(explicit) == len(set(explicit)), f'{path.name}: duplicate explicit anchors')
    ids, seen, fence = set(explicit), Counter(), None
    for line in content.splitlines():
        check(not re.match(r'^(<<<<<<< |=======\s*$|>>>>>>> )', line), f'{path.name}: conflict marker')
        delimiter = re.match(r'^\s{0,3}(`{3,}|~{3,})(.*)$', line)
        if delimiter:
            marker, suffix = delimiter.groups()
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence) and not suffix.strip():
                fence = None
            continue
        if fence is not None:
            continue
        heading = re.match(r'^#{1,6}\s+(.+?)(?:\s+#+)?\s*$', line)
        if heading:
            title = re.sub(r'<[^>]+>', '', heading[1]).lower()
            slug = ''.join(c for c in title if c in '-_ ' or unicodedata.category(c)[0] in 'LN').replace(' ', '-')
            count = seen[slug]
            seen[slug] += 1
            ids.add(slug if not count else f'{slug}-{count}')
    check(fence is None, f'{path.name}: unclosed code fence')
    anchors[path] = ids

local_links = 0
external_links = 0
for path, content in docs.items():
    for label, target in re.findall(r'\[([^\]\n]+)\]\(([^\s)]+)\)', content):
        url = urlsplit(target.strip('<>'))
        if url.scheme or url.netloc:
            external_links += 1
            continue
        local_links += 1
        dest = (path.parent / unquote(url.path)).resolve() if url.path else path
        check(dest.is_file(), f'{path.name}: missing local target {target}')
        if url.fragment:
            check(dest in anchors and unquote(url.fragment) in anchors[dest], f'{path.name}: missing anchor {target}')
        if re.fullmatch(r'R\d+', label):
            check(dest == root / 'docs/references.md' and url.fragment == label.lower(), f'{path.name}: citation mismatch {label}')

expected_header = ['id', '机制', '分类', '频率表述_非排名', '机制证据', '治疗证据', '主要检测', '克服策略', '该继发情境的批准边界', '主要局限与风险', '未来方向', '来源编号', '本轮核验状态']
with (root / 'docs/evidence-matrix.csv').open(encoding='utf-8', newline='') as handle:
    reader = csv.DictReader(handle, strict=True)
    check(reader.fieldnames == expected_header, 'Unexpected CSV schema')
    rows = list(reader)
check(bool(rows), 'CSV contains no mechanism rows')
for row in rows:
    check(set(row) == set(expected_header) and all(isinstance(v, str) and v.strip() for v in row.values()), f'CSV row {row.get("id")}: missing/extra/empty field')

article = docs[root / 'docs/egfr-bypass-resistance.md']
heading_ids = re.findall(r'^### (\d{2})\. ', article, re.M)
overview = [tuple(cell.strip() for cell in line.strip('|').split('|')) for line in article.splitlines() if re.match(r'^\| \d{2} \|', line)]
ids = [row['id'] for row in rows]
check(ids == heading_ids == [row[0] for row in overview] == [f'{i:02}' for i in range(1, 16)], 'CSV, overview, and section IDs must all be 01–15 in order')
reference_ids = set(re.findall(r'<a id="(r\d+)"></a>', docs[root / 'docs/references.md']))
compact = lambda value: re.sub(r'\s+', '', value)
for row, summary in zip(rows, overview):
    check(compact(row['机制证据'] + '/' + row['治疗证据']) == compact(summary[-1]), f'ID {row["id"]}: evidence grades differ between CSV and overview')
    for source in row['来源编号'].split(';'):
        check(source.lower() in reference_ids, f'ID {row["id"]}: undefined CSV reference {source}')
for path, content in docs.items():
    for source in re.findall(r'\[(R\d+)\]', content):
        check(source.lower() in reference_ids, f'{path.name}: undefined reference {source}')

subprocess.run(['git', '-C', str(root), 'diff', '--check'], check=True)
subprocess.run(['git', '-C', str(root), 'diff', '--cached', '--check'], check=True)
if errors:
    print('\n'.join(f'FAIL: {error}' for error in errors))
    sys.exit(1)
print(f'PASS: {len(docs)} Markdown files; {local_links} local links/anchors; {len(rows)} CSV rows × {len(expected_header)} columns; {len(reference_ids)} reference anchors; matching mechanism IDs and evidence grades; no conflict markers or whitespace errors.')
print(f'NOT CHECKED: {external_links} external-link occurrences, medical claims, current regulatory labels, and Mermaid rendering.')
