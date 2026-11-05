from __future__ import annotations

import datetime as dt
from pathlib import Path

from rasmapk.knowledge import load_knowledge as load_modules
from .ranking import assess_reference, load_ranks

BASE = Path(__file__).resolve().parent
START, END = dt.date(2011, 11, 4), dt.date(2026, 11, 4)


def load_knowledge(ranks: Path | None = None):
    kb = load_modules(BASE / 'knowledge', expected_nodes=7, start=START, end=END)
    rows, provenance = load_ranks(ranks)
    for ref in kb['evidence'] + kb['unique_evidence']:
        ref['ranking'] = assess_reference(ref, rows)
    kb['topic'] = 'unresolved_EGFR_resistance_and_multiomics_detection_interpretation'
    kb['journal_selection'] = {
        'jcr_edition': 2025, 'jif_year': 2024, 'metric': 'JIF category rank', 'rank_at_most': 80,
        'categories': ['Oncology', 'Immunology', 'Genetics & Heredity'],
        'policy': 'Union of the three within-category top-80 sets; conference evidence assessed separately.',
        'table': provenance,
        'passed_unique_journal_records': sum(r['ranking']['meets_journal_top80'] for r in kb['unique_evidence']),
        'not_claimed_satisfied_without_matching_table': True,
    }
    kb['search_provenance'] = {
        'preferred_provider': 'Firecrawl MCP', 'live_firecrawl_used': False,
        'reason': 'No callable Firecrawl MCP tool, CLI or injected credential was available.',
        'actual_providers': ['Europe PMC', 'PubMed', 'Crossref'],
        'systematic_review': False, 'full_text_systematically_reviewed': False,
        'unexplained_fraction': 'No universal 50% assumption; study populations, assays, sampling and denominators differ.',
    }
    return kb
