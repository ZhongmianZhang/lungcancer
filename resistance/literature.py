"""Reproducible search acquisition; metadata retrieval never verifies clinical claims."""
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'
NODES = {
    '01_upstream': '(MET OR ERBB2 OR HER2 OR ERBB3 OR HER3 OR IGF1R OR INSR OR IRS1 OR GAB1)',
    '02_pi3k_akt': '(PIK3CA OR PIK3CB OR PIK3R1 OR PDPK1 OR AKT1 OR AKT2 OR AKT3)',
    '03_negative_regulators': '(PTEN OR INPP4B OR PHLPP1 OR PHLPP2 OR TSC1 OR TSC2 OR STK11)',
    '04_mtor_feedback': '(MTOR OR RICTOR OR RPTOR OR RHEB OR EIF4EBP1 OR RPS6 OR mTORC1 OR mTORC2)',
    '05_crosstalk': '(KRAS OR NRAS OR BRAF OR RET OR ALK OR NTRK OR FGFR OR AXL OR YAP OR TEAD OR SHP2 OR SOS1)',
    '06_combination_clinical': '(FLAURA2 OR "FLAURA 2" OR chemotherapy OR pemetrexed OR platinum OR COMPEL)',
    '07_chemo_metabolism': '(BCL2 OR MCL1 OR BCL2L1 OR BIM OR TYMS OR DHFR OR KEAP1 OR NRF2 OR GPX4 OR ERCC1 OR RB1 OR autophagy)',
    '08_evidence_synthesis': '("PI3K" OR "AKT" OR "mTOR") AND (resistance OR progression OR trial OR biopsy)',
}


def search_plan():
    base = '(osimertinib OR AZD9291) AND ("lung cancer" OR NSCLC)'
    date = 'FIRST_PDATE:[2016-10-30 TO 2026-10-30]'
    return {
        'window': {'start': '2016-10-30', 'end': '2026-10-30'},
        'endpoint': ENDPOINT, 'date_field': 'FIRST_PDATE',
        'queries': {key: f'{base} AND {terms} AND {date}' for key, terms in NODES.items()},
        'direct_combination_overlay': '(chemotherapy OR pemetrexed OR platinum OR FLAURA2) AND (resistance OR progression)',
        'scope_note': 'No journal filter: avoid missing negative/less prominent studies. Screen population and original study manually.',
        'conference_search': 'Manual ASCO/ESMO/WCLC/AACR archives and journal supplements required; Europe PMC does not establish complete conference coverage.',
        'not_a_systematic_review': True,
    }


def fetch_searches(node='all', max_pages=3, opener=None):
    if node != 'all' and node not in NODES:
        raise ValueError('Unknown node')
    if type(max_pages) is not int or not 1 <= max_pages <= 100:
        raise ValueError('max_pages must be 1–100')
    opener = urlopen if opener is None else opener
    plan = search_plan()
    report = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'plan': plan,
              'status': 'metadata_retrieved', 'full_text_verified': False,
              'conference_search_completed': False, 'registry_automatically_updated': False,
              'results': {}}
    selected = list(NODES) if node == 'all' else [node]
    denied = False
    for key in selected:
        if denied:
            report['results'][key] = {'status': 'not_run_after_access_failure', 'hit_count': None, 'records': []}
            continue
        result = {'status': 'pending', 'query': plan['queries'][key], 'hit_count': None, 'pages': 0, 'records': []}
        report['results'][key] = result
        cursor, seen_cursors, seen_records = '*', set(), set()
        try:
            for _ in range(max_pages):
                url = ENDPOINT + '?' + urlencode({'query': result['query'], 'format': 'json',
                    'resultType': 'core', 'pageSize': 100, 'cursorMark': cursor})
                request = Request(url, headers={'User-Agent': 'lungcancer-evidence-research/0.1'})
                # Inherits platform HTTPS proxy and CA trust. No proxy bypass or TLS override.
                with opener(request, timeout=30) as response:
                    page = json.load(response)
                if not isinstance(page, dict) or not isinstance(page.get('resultList'), dict):
                    raise ValueError('Unexpected Europe PMC response shape')
                count = page.get('hitCount')
                records = page.get('resultList', {}).get('result')
                if type(count) is not int or count < 0 or not isinstance(records, list):
                    raise ValueError('Unexpected Europe PMC response shape')
                result['hit_count'] = count
                result['pages'] += 1
                for record in records:
                    if not isinstance(record, dict):
                        raise ValueError('Unexpected Europe PMC record')
                    identity = (record.get('source'), record.get('id'))
                    if not all(isinstance(x, str) and x for x in identity):
                        raise ValueError('Record missing source/id')
                    if identity not in seen_records:
                        seen_records.add(identity)
                        result['records'].append({field: record.get(field) for field in
                            ('id', 'source', 'pmid', 'pmcid', 'doi', 'title', 'authorString', 'pubYear', 'firstPublicationDate', 'abstractText', 'journalInfo')})
                next_cursor = page.get('nextCursorMark')
                if not records or len(result['records']) >= count or not next_cursor or next_cursor == cursor or next_cursor in seen_cursors:
                    break
                seen_cursors.add(cursor)
                cursor = next_cursor
            result['status'] = 'metadata_retrieved' if len(result['records']) >= result['hit_count'] else 'truncated_metadata_search'
            if result['status'] == 'truncated_metadata_search':
                report['status'] = 'incomplete'
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            denied = True
            result['status'] = 'access_failed'
            # Avoid credential-bearing arbitrary HTTP bodies / proxy logs in retained artifacts.
            result['error_type'] = type(exc).__name__
            if isinstance(exc, HTTPError):
                result['http_status'] = exc.code
            elif isinstance(exc, URLError):
                result['reason_category'] = 'proxy_connect_forbidden' if '403' in str(exc.reason) else 'connection_or_tls_failure'
            report['status'] = 'blocked'
        except (ValueError, TypeError) as exc:
            result['status'] = 'invalid_response'
            result['error_type'] = type(exc).__name__
            report['status'] = 'incomplete'
    return report
