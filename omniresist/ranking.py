"""Exact, provenance-preserving application of a supplied JIF ranking export.

The program validates a CSV's shape; it cannot authenticate a JCR subscription.
2025 JCR edition uses 2024 JIF data. Conference abstracts are assessed separately.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import re

from scripts.literature import normalized_journal

CATEGORIES = {'oncology', 'immunology', 'genetics & heredity'}
REQUIRED = {'journal', 'issn', 'category', 'rank', 'jcr_edition', 'jif_year', 'ranking_metric', 'source'}


def issns(value):
    if isinstance(value, list):
        value = ' '.join(str(x) for x in value)
    return {x.upper() for x in re.split(r'[;,|\s]+', str(value or '')) if x}


def load_ranks(path: Path | None):
    if path is None:
        return [], {'status': 'not_supplied', 'authenticated_by_program': False}
    rows, seen = [], set()
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        if not REQUIRED <= set(reader.fieldnames or []):
            raise ValueError('JCR CSV requires: ' + ','.join(sorted(REQUIRED)))
        for number, row in enumerate(reader, 2):
            if not any(str(v or '').strip() for v in row.values()):
                continue
            row = {k: (row.get(k) or '').strip() for k in REQUIRED}
            try:
                row.update(rank=int(row['rank']), jcr_edition=int(row['jcr_edition']), jif_year=int(row['jif_year']))
            except ValueError as error:
                raise ValueError(f'Noninteger rank/year at line {number}') from error
            if row['rank'] < 1 or row['jcr_edition'] != 2025 or row['jif_year'] != 2024:
                raise ValueError('Expected 2025 JCR edition, 2024 JIF year, positive JIF rank')
            category = ' '.join(row['category'].casefold().split())
            if category not in CATEGORIES or row['ranking_metric'].upper() != 'JIF':
                raise ValueError('Expected JIF ranking in one of the three selected categories')
            if not row['journal'] or not row['source']:
                raise ValueError('Ranking journal and source are required')
            numbers = issns(row['issn'])
            if any(not re.fullmatch(r'\d{4}-\d{3}[\dX]', x) for x in numbers):
                raise ValueError('Malformed ISSN in ranking table')
            key = (normalized_journal(row['journal']), category)
            if key in seen:
                raise ValueError('Duplicate journal/category; supply one unambiguous ranking')
            seen.add(key)
            row.update(category=category, issns=sorted(numbers), provenance_status='supplied_not_independently_authenticated')
            rows.append(row)
    if not rows:
        raise ValueError('Ranking table is empty')
    return rows, {'status': 'supplied_not_independently_authenticated', 'rows': len(rows),
                  'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                  'authenticated_by_program': False}


def assess_reference(ref, rows):
    if ref['design'] == 'conference_abstract':
        return {'status': 'conference_separate_from_jcr', 'meets_journal_top80': False,
                'result_interpretation_allowed': ref['verification'] == 'metadata_abstract_checked', 'matches': []}
    numbers = issns(ref.get('issn'))
    title = normalized_journal(ref['journal'])
    matches = []
    for row in rows:
        # Two present ISSNs must agree: a similar title cannot override a mismatch.
        if numbers and row['issns']:
            match = bool(numbers & set(row['issns']))
        else:
            match = title == normalized_journal(row['journal'])
        if match:
            matches.append(row)
    passed = any(r['rank'] <= 80 for r in matches)
    return {'status': 'passed_supplied_table' if passed else 'outside_top80' if matches else 'unverified_no_matching_rank',
            'meets_journal_top80': passed, 'matches': matches,
            'result_interpretation_allowed': passed and ref['verification'] == 'metadata_abstract_checked'}
