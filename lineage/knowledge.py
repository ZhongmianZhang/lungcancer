from pathlib import Path
import datetime as dt

from rasmapk.knowledge import load_knowledge as load_modules, citations

BASE = Path(__file__).resolve().parent
START = dt.date(2016, 11, 2)
END = dt.date(2026, 11, 2)


def load_knowledge():
    kb = load_modules(BASE / 'knowledge', expected_nodes=8, start=START, end=END)
    kb['topic'] = 'histologic_lineage_transformation_with_retained_EGFR'
    kb['search_provenance'] = {
        'preferred_provider': 'Firecrawl',
        'firecrawl_live_used_in_this_edition': False,
        'reason': 'No callable Firecrawl tool, CLI or injected API credential was available.',
        'actual_providers': ['Europe PMC', 'PubMed', 'Crossref'],
        'full_text_reviewed': False,
    }
    return kb
