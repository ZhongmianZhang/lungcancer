"""Prefer Firecrawl when configured; auditable scholarly fallback otherwise.

Only explicit literature queries enter this module. Case analysis imports no
network client. No credentials or HTTP response bodies enter diagnostics.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import urllib.error
import urllib.request

from scripts.literature import EuropePMCClient, LiteratureError
from rasmapk.knowledge import plain


class FirecrawlError(RuntimeError):
    def __init__(self, kind: str, http_status: int | None = None):
        super().__init__(kind)
        self.kind, self.http_status = kind, http_status


class FirecrawlClient:
    def __init__(self, *, timeout=30):
        self.key = os.environ.get('FIRECRAWL_API_KEY')
        self.timeout = timeout

    def search(self, query: str, limit: int = 5) -> list[dict]:
        if not self.key:
            raise FirecrawlError('missing_credential')
        payload = json.dumps({'query':query,'limit':limit,'sources':['web']}).encode()
        request = urllib.request.Request('https://api.firecrawl.dev/v2/search', data=payload,
            headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json','User-Agent':'lungcancer-lineage-research/1.0'}, method='POST')
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
        except urllib.error.HTTPError as error:
            raise FirecrawlError('http_error',error.code) from None
        except (OSError,ValueError):
            raise FirecrawlError('connection_or_json_error') from None
        if not isinstance(data,dict) or data.get('success') is not True:
            raise FirecrawlError('service_response_not_successful')
        results = data.get('data')
        if isinstance(results,dict):
            results = results.get('web')
        if not isinstance(results,list):
            raise FirecrawlError('unexpected_response_shape')
        safe=[]
        for row in results[:limit]:
            if isinstance(row,dict) and str(row.get('url','')).startswith('https://'):
                safe.append({k:row.get(k,'') for k in ('title','url','description')})
        return safe


def search(query: str, *, provider='auto', limit=10) -> dict:
    if provider not in {'auto','firecrawl','europepmc'} or not isinstance(query,str) or not query.strip():
        raise ValueError('A nonempty literature query and supported provider are required')
    if not 1 <= limit <= 25:
        raise ValueError('limit must be between 1 and 25')
    out={'preferred_provider':'Firecrawl','provider_requested':provider,
         'searched_at':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
         'query':query,'attempts':[],'results':[],'status':'not_run','case_analysis_inputs_accessed':False}
    if provider in {'auto','firecrawl'}:
        try:
            out['results']=FirecrawlClient().search(query,limit)
            out['attempts'].append({'provider':'Firecrawl','status':'executed'})
            out.update(status='complete',actual_provider='Firecrawl',result_count=len(out['results']))
            return out
        except FirecrawlError as error:
            out['attempts'].append({'provider':'Firecrawl','status':'unavailable_or_failed','kind':error.kind,'http_status':error.http_status})
            if provider=='firecrawl':
                out.update(status='blocked',actual_provider=None,result_count=0)
                return out
    bounded=f'({query}) AND FIRST_PDATE:[2016-11-02 TO 2026-11-02]'
    try:
        page=EuropePMCClient(timeout=30,retries=1).request(bounded,page_size=limit)
        records=page.get('resultList',{}).get('result',[])
        for r in records:
            pmid=str(r.get('pmid') or '')
            out['results'].append({'title':plain(r.get('title','')),'pmid':pmid,'doi':r.get('doi',''),
                'publication_date':r.get('firstPublicationDate'),'verification':'retrieved_candidate_metadata_not_screened',
                'url':'https://pubmed.ncbi.nlm.nih.gov/'+pmid+'/' if pmid else 'https://europepmc.org/article/'+r.get('source','MED')+'/'+str(r.get('id',''))})
        out['attempts'].append({'provider':'Europe PMC','status':'executed','retrieval':page.get('_retrieval',{})})
        out.update(status='complete',actual_provider='Europe PMC',total_hits=page.get('hitCount'),result_count=len(out['results']),truncated=int(page.get('hitCount',0))>len(out['results']))
    except LiteratureError as error:
        out['attempts'].append({'provider':'Europe PMC','status':'failed','diagnostic':error.diagnostic})
        out.update(status='blocked_or_failed',actual_provider='Europe PMC',result_count=0)
    return out


def write_search(result: dict, output: Path) -> None:
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
