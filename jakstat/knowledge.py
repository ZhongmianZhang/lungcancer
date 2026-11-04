from pathlib import Path
import datetime as dt

from rasmapk.knowledge import load_knowledge as load_modules

BASE=Path(__file__).resolve().parent
START=dt.date(2016,11,4)
END=dt.date(2026,11,4)


def load_knowledge():
    kb=load_modules(BASE/'knowledge',expected_nodes=7,start=START,end=END)
    kb['topic']='compartment_and_dependency_aware_JAK_STAT_resistance'
    kb['search_provenance']={
        'preferred_provider':'Firecrawl','live_firecrawl_used_for_this_curated_edition':False,
        'reason':'No callable Firecrawl tool, CLI or injected API credential was available.',
        'actual_citation_providers':['Europe PMC','PubMed','Crossref'],
        'firecrawl_adapter':'shared lineage.search; protocol mock-tested; live use requires configured credential',
        'systematic_review':False,'full_text_systematically_reviewed':False,
    }
    return kb
