#!/usr/bin/env python3
"""Create one portable HTML with original text, PDBs, viewer and exports inline."""
from pathlib import Path
from html.parser import HTMLParser
import argparse
import base64
import hashlib
import html
import json
import re
import zipfile

BASE=Path(__file__).resolve().parent
ASSETS=BASE/'offline_assets'
DEFAULT_OUTPUT=BASE/'generated/EGFR_structure_offline_20261115.html'


def safe_inline_json(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<',chr(92)+'u003c').replace('>',chr(92)+'u003e')


def safe_inline_script(value):
    return re.sub(r'</script',lambda match:'<'+chr(92)+'/script',value,flags=re.IGNORECASE)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    parser.add_argument('--zip-output',type=Path)
    args=parser.parse_args(argv)
    output=args.output.resolve()
    zip_output=(args.zip_output or output.with_suffix('.zip')).resolve()
    if output==zip_output:
        parser.error('HTML and ZIP destinations must differ')
    data=json.loads((BASE/'report_data.json').read_text(encoding='utf-8'))
    original=(BASE/'report.html').read_text(encoding='utf-8')
    engine=(ASSETS/'3Dmol-min.js').read_text(encoding='utf-8')
    provenance=json.loads((ASSETS/'3dmol_provenance.json').read_text(encoding='utf-8'))
    assert hashlib.sha256((ASSETS/'3Dmol-min.js').read_bytes()).hexdigest()==provenance['assets']['3Dmol-min.js']['sha256']
    files={}
    def asset(key,path,mime):
        raw=path.read_bytes()
        files[key]=dict(filename=path.name,mime=mime,base64=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest())
    for structure in data['structures']:
        path=BASE/structure['path'];asset('pdb:'+structure['pdb_id'],path,'chemical/x-pdb')
        assert files['pdb:'+structure['pdb_id']]['sha256']==structure['sha256']
    for name,mime in [('factors.csv','text/csv;charset=utf-8'),('references.csv','text/csv;charset=utf-8'),
                      ('report_data.json','application/json'),('structure_manifest.json','application/json'),
                      ('provenance/4LRM_uniprot_mapping.json','application/json')]:asset(name,BASE/name,mime)
    source_data=html.escape(data['meta']['viewer_delivery'],quote=True)
    delivery='本单文件HTML已内置9个实验PDB、3D查看器、正文和资料导出，无需网络、服务器或其他本地文件。外部原文/官方页面链接仅在联网时访问。'
    original=original.replace(source_data,delivery)
    original=original.replace('本页提供原始实验坐标下载及官方3D查看链接；坐标未修改。', '本页内置实验坐标和离线3D查看功能，坐标未修改。')
    original=original.replace('点击“官方3D”可进入可旋转的官方结构页面（需网络）；“下载PDB”用于本地支持PDB格式的结构查看器。',
      '点击“在本页查看”可离线切换到内置3D结构；“下载PDB”可直接从本文件导出原始坐标。外部官方页面需要网络。')
    original=original.replace('<h1>EGFR突变蛋白结构如何影响TKI疗效</h1>', '<p class="offline-tag">单文件 · 完整脱机版</p><h1>EGFR突变蛋白结构如何影响TKI疗效</h1>')
    original=original.replace('<nav class="links">', '<nav class="links"><a href="#offline-viewer">离线3D演示</a>',1)
    for structure in data['structures']:
        code=structure['pdb_id'];source=html.escape(structure['official_3d_url'],quote=True)
        marker='<a class="button" href="'+source+'" target="_blank" rel="noopener noreferrer">官方3D</a>'
        replacement='<button class="button" type="button" data-view="'+code+'">在本页查看</button><a class="button secondary" href="'+source+'" target="_blank" rel="noopener noreferrer">官方页面（联网）</a>'
        assert original.count(marker)==1,code
        original=original.replace(marker,replacement)
        marker='download href="'+structure['path']+'"'
        assert original.count(marker)==1,code
        original=original.replace(marker,'download="'+code+'.pdb" href="#offline-viewer" data-export="pdb:'+code+'"')
    for key,record in files.items():
        if key.startswith('pdb:'):continue
        original=original.replace('href="'+key+'"', 'href="#offline-viewer" data-export="'+key+'"')
    options=''.join('<option value="'+s['pdb_id']+'"'+(' selected' if s['pdb_id']=='6LUD' else '')+'>'+html.escape(s['pdb_id']+' · '+s['label'])+'</option>' for s in data['structures'])
    viewer='''<section id="offline-viewer" class="offline-panel" data-ready="false"><h2>离线交互3D结构</h2><p>9个实验结构均内置于此文件。拖动旋转、滚轮或双指缩放；右键或Ctrl＋拖动平移。</p><div class="viewer-controls"><label class="structure-label">选择结构<select id="structure-select">'''+options+'''</select></label><label>蛋白显示<select id="protein-style"><option value="cartoon">骨架/带状</option><option value="sticks">原子棍状</option></select></label></div><div class="viewer-controls toggles"><label><input id="show-pocket" type="checkbox" checked>显示5 Å邻域</label><label><input id="show-labels" type="checkbox" checked>关键位点标签</label><label><input id="show-all-chains" type="checkbox">显示其他蛋白链</label></div><h3 id="structure-title">正在准备内置结构</h3><div id="molecule-canvas" aria-label="可旋转的EGFR蛋白三维结构"></div><img id="print-molecule" alt="当前EGFR三维视图"><p id="viewer-error" hidden role="alert"></p><div class="viewer-controls viewer-buttons"><button id="reset-button" type="button">重置视图</button><button id="full-button" type="button">全蛋白</button><button id="pocket-button" type="button">结合口袋</button><button id="spin-button" type="button">自动旋转</button><button id="png-button" type="button">保存视图PNG</button><button id="current-pdb-download" type="button" data-export="pdb:6LUD">导出当前PDB</button></div><p id="viewer-status" role="status">正在启动本地3D查看器…</p><p id="structure-metadata" class="muted"></p><p id="structure-description"></p><p id="structure-caveat" class="notice"></p><p id="pocket-summary" class="muted"></p><p class="muted">蛋白为蓝青色，目标配体碳为绿色，关键残基碳为橙色；其他元素按元素色显示。编号采用PDB作者链和作者残基号，4LRM中标准C797对应作者C800。球棍和邻域用于结构演示，不代表药敏判定。</p></section>'''
    marker='<section><h2>结构位置与动力学：应同时观察什么</h2>'
    assert original.count(marker)==1
    original=original.replace(marker,viewer+marker)
    style='''.offline-tag{display:inline-block;padding:3px 11px;background:#2c6976;border-radius:6px;font-size:13px}.offline-panel{scroll-margin-top:12px}.viewer-controls{display:flex;gap:12px;flex-wrap:wrap;align-items:end;margin:12px 0}.viewer-controls label{font-size:13px;display:grid;gap:5px}.viewer-controls .structure-label{flex:1;min-width:200px}.viewer-controls select{font:inherit;padding:9px;border:1px solid #abc4cd;border-radius:6px;background:white;max-width:100%;width:100%}.toggles{align-items:center}.toggles label{display:flex;align-items:center;gap:6px}.toggles input{flex:none;min-width:0;width:17px;height:17px}.viewer-buttons button{padding:8px 12px;font-size:13px}.viewer-buttons button:disabled{opacity:.45;cursor:default}#molecule-canvas{width:100%;height:550px;position:relative;background:#071b29;border-radius:10px;overflow:hidden;touch-action:none}#print-molecule{display:none;width:100%}#viewer-status{color:#155768;font-weight:600}.card .button{font:inherit;border:0;cursor:pointer}.card .links{align-items:center}.viewer-controls input:focus-visible,.viewer-controls select:focus-visible,button:focus-visible{outline:3px solid #d78f26;outline-offset:3px}.offline-license{font-size:12px}.offline-license pre{white-space:pre-wrap;max-height:320px}@media(max-width:650px){#molecule-canvas{height:400px}.viewer-controls{gap:8px}.viewer-buttons button{flex:1;min-width:95px;padding:9px 7px}}@media print{#molecule-canvas,.viewer-controls,#viewer-status{display:none!important}#print-molecule{display:block}.offline-panel{break-inside:avoid}}'''
    original=original.replace('</style>',style+'</style>',1)
    policy="default-src 'none'; script-src 'unsafe-inline' blob:; style-src 'unsafe-inline'; img-src data: blob:; worker-src blob:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'"
    original=original.replace('<meta charset="utf-8">','<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+html.escape(policy,quote=True)+'">',1)
    original=original.replace('<title>EGFR结构与TKI疗效：证据与实验3D演示</title>','<title>EGFR结构与TKI疗效 · 单文件离线3D版</title>')
    licenses=(ASSETS/'3Dmol_LICENSE.txt').read_text(encoding='utf-8')+'\n'+(ASSETS/'3Dmol_third_party_licenses.txt').read_text(encoding='utf-8')
    license_panel='<section class="offline-license"><details><summary>离线版本与软件许可</summary><p>离线导出日期：2026-11-15。3Dmol.js '+provenance['version']+'；查看器和PDB均已内置，不从CDN加载。原始坐标的SHA-256保留在结构溯源清单中。</p><p>3Dmol.js源码许可及第三方声明：</p><pre>'+html.escape(licenses)+'</pre></details></section>'
    original=original.replace('</main>',license_panel+'</main>',1)
    embedded_data=dict(data)
    embedded_data['meta']=dict(data['meta'],original_viewer_delivery=data['meta']['viewer_delivery'],viewer_delivery=delivery,
                              offline_single_file=True,offline_export_date='2026-11-15',viewer_engine='3Dmol.js '+provenance['version'])
    # Export JSON reflects the portable edition while preserving all scientific content.
    json_bytes=(json.dumps(embedded_data,ensure_ascii=False,indent=2)+'\n').encode()
    files['report_data.json'].update(base64=base64.b64encode(json_bytes).decode(),sha256=hashlib.sha256(json_bytes).hexdigest())
    embedded=dict(report=embedded_data,files=files,viewer_provenance=provenance)
    payload=safe_inline_json(embedded)
    # Source-map comments are irrelevant in a portable HTML. Preserve the vendor code/license otherwise.
    engine=safe_inline_script(re.sub(r'(?m)^//# sourceMappingURL=.*$','',engine))
    app=safe_inline_script((ASSETS/'offline_viewer.js').read_text(encoding='utf-8'))
    additions='<script id="offline-assets" type="application/json">'+payload+'</script><script id="embedded-3dmol">'+engine+'</script><script id="offline-viewer-app">'+app+'</script>'
    original=original.replace('</body>',additions+'</body>',1)
    validate(original,embedded)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(original,encoding='utf-8')
    zip_output.parent.mkdir(parents=True,exist_ok=True)
    member=zipfile.ZipInfo(output.name,date_time=(2026,11,15,0,0,0))
    member.compress_type=zipfile.ZIP_DEFLATED
    member.external_attr=0o644<<16
    with zipfile.ZipFile(zip_output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        archive.writestr(member,output.read_bytes())
    with zipfile.ZipFile(zip_output) as archive:
        assert archive.namelist()==[output.name]
        assert archive.read(output.name)==output.read_bytes()
        assert archive.testzip() is None
    downloads={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (output,zip_output)}
    (output.parent/'SHA256SUMS.txt').write_text(''.join(record['sha256']+'  '+name+'\n' for name,record in downloads.items()),encoding='utf-8')
    manifest=dict(html=output.name,zip=zip_output.name,zip_entries=[output.name],single_file=True,structures=9,references=30,external_runtime_assets=0,library='3Dmol.js '+provenance['version'],downloads=downloads)
    (output.parent/'download_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(file=str(output),zip=str(zip_output),downloads=downloads,structures=len(data['structures']),references=len(data['references']),external_runtime_assets=0),ensure_ascii=False))


def validate(document,embedded):
    class Parser(HTMLParser):
        def __init__(self):super().__init__();self.ids=[];self.links=[];self.runtime=[];self.in_assets=False;self.asset_chunks=[]
        def handle_starttag(self,tag,attrs):
            a=dict(attrs)
            if tag=='script':self.in_assets=a.get('id')=='offline-assets'
            if a.get('id'):self.ids.append(a['id'])
            if tag=='a' and a.get('href'):self.links.append(a['href'])
            if tag in ('script','img','iframe','source') and a.get('src'):self.runtime.append(a['src'])
            if tag=='link' and a.get('href'):self.runtime.append(a['href'])
        def handle_endtag(self,tag):
            if tag=='script':self.in_assets=False
        def handle_data(self,text):
            if self.in_assets:self.asset_chunks.append(text)
    p=Parser();p.feed(document)
    assert len(p.ids)==len(set(p.ids))
    assert not p.runtime,p.runtime
    assert all(h.startswith(('#','https://','http://','mailto:')) for h in p.links)
    assert all(h[1:] in p.ids for h in p.links if h.startswith('#'))
    restored=json.loads(''.join(p.asset_chunks))
    assert restored==embedded
    for s in restored['report']['structures']:
        raw=base64.b64decode(restored['files']['pdb:'+s['pdb_id']]['base64'])
        assert hashlib.sha256(raw).hexdigest()==s['sha256']
    assert len(embedded['report']['references'])==30


if __name__=='__main__':main()
