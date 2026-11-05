from __future__ import annotations

import csv
import json
from pathlib import Path

from rasmapk.render import CSS, esc, items, paras, cite

STATUS = {
    'assay_or_time_unresolved': '检测QC、版本或进展时序未明',
    'event_not_validated_by_assay': '该次检测未验证此事件类别',
    'not_somatic_tumor_source': '血细胞/胚系来源，不能当作肺癌体细胞耐药',
    'origin_unresolved': '尚未确认为肿瘤来源',
    'compartment_unresolved': '细胞区室未明确',
    'coverage_or_confirmation_missing': '位点可检测性或独立确认不足',
    'below_assay_validated_lod': '低于该实验室本次提供的SNV/indel验证检出限',
    'benign_or_vus_not_driver': '良性/VUS/未注释改变不作为已知驱动',
    'nonmalignant_state_readout': '非恶性细胞线索，尚需连接肿瘤表型',
    'clonal_relationship_unresolved': '与EGFR恶性克隆的关系未明确',
    'contradictory_negative_assay': '同一检测被声明为阴性又有阳性事件，需纠正',
    'event_specific_validation_needed': '缺少事件特异的结构/功能确认',
    'background_or_risk_not_mechanism': '背景驱动或风险因素，不是耐药机制证明',
    'hypothesis_requires_functional_validation': '机制假说，仍需功能验证',
    'curated_candidate_not_patient_causal_proof': '已知机制候选，尚未证明患者中的耐药因果',
    'model_hypothesis_not_clinical_validation': '患者匹配模型支持假说，尚非临床验证',
    'supplied_test_not_supportive_not_global_exclusion': '该实验未支持，不代表所有病灶均被排除',
    'requires_further_validation': '实验条件仍需进一步核验',
}
RANK_LABELS = {
    'passed_supplied_table': '按所供表符合前80；原表真实性仍需审查',
    'outside_top80': '按所供表不在前80',
    'unverified_no_matching_rank': 'JCR排名待核验',
    'conference_separate_from_jcr': '会议记录单列，不适用期刊JIF排名',
}
EXTRA_CSS = '''main,aside{min-width:0}.box,.node,.paper,.result,.platform{overflow-wrap:anywhere}.flow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.flow a{padding:16px;border:1px solid #c7dfe3;border-radius:10px;background:#f2faf9;text-decoration:none}.flow strong,.flow small{display:block}.platform{margin:12px 0;padding:18px;border:1px solid #d2e3e7;border-radius:10px}.rank{display:block;margin:8px 0;font-size:13px;color:#83521b}code,pre{overflow-wrap:anywhere}td{vertical-align:top}@media(max-width:700px){.flow{grid-template-columns:1fr}.platform{padding:12px}}'''


def shell(title, body, nav=''):
    script = """(()=>{for(const [id,selector] of [['module-search','.node'],['paper-search','.paper'],['platform-search','.platform']]){const input=document.getElementById(id);if(input)input.oninput=()=>{const q=input.value.toLowerCase();document.querySelectorAll(selector).forEach(n=>n.hidden=!n.textContent.toLowerCase().includes(q))}}const button=document.getElementById('expand');if(button)button.onclick=()=>document.querySelectorAll('.node details').forEach(n=>n.open=true);document.querySelectorAll('.citations a').forEach(a=>a.onclick=()=>{const input=document.getElementById('paper-search');if(input)input.value='';document.querySelectorAll('.paper').forEach(n=>n.hidden=false)});let before=[];addEventListener('beforeprint',()=>{before=[...document.querySelectorAll('details')].map(d=>d.open);document.querySelectorAll('details').forEach(d=>d.open=true)});addEventListener('afterprint',()=>document.querySelectorAll('details').forEach((d,i)=>d.open=before[i]));})();"""
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{CSS}{EXTRA_CSS}</style></head><body><header><div class="kicker">EGFR / UNRESOLVED RESISTANCE / MULTI-OMICS</div><h1>{esc(title)}</h1><p class="sub">检测范围、检出能力、克隆归属、功能因果与治疗证据逐层审查</p></header><div class="layout"><aside>{nav}<button onclick="window.print()">打印 / 保存PDF</button></aside><main>{body}</main></div><footer>研究用途 · 未经临床队列验证 · 证据版2011-11-04—2026-11-04</footer><script>{script}</script></body></html>'


def evidence_html(kb, selected=None):
    body = ''
    for ref in kb['unique_evidence']:
        if selected is not None and not set(ref['source_ids']) & set(selected):
            continue
        aliases = ''.join(f'<span id="ref-{esc(i)}"></span>' for i in ref['source_ids'])
        rank = ref['ranking']
        rank_text = RANK_LABELS[rank['status']]
        if rank['matches']:
            rank_text += '；' + ' / '.join(f'{r["category"]} #{r["rank"]}，JCR {r["jcr_edition"]}，JIF {r["jif_year"]}' for r in rank['matches'])
        checked = '题录及摘要已核' if ref['verification'] == 'metadata_abstract_checked' else '仅核题录；未审读结果'
        body += f'<article class="paper">{aliases}<span class="badge">{esc(" / ".join(ref["source_ids"]))}</span><h3>{esc(ref["title"])}</h3><p>{esc(ref["authors"])}</p><p>{esc(ref["journal"])} · {esc(ref["publication_date"])} · {esc(ref["design"])} · {esc(ref["scope"])}</p><span class="rank">{esc(rank_text)}</span><p><a href="{esc(ref["url"])}" target="_blank" rel="noopener noreferrer">原始来源</a> · DOI {esc(ref.get("doi",""))} · PMID {esc(ref.get("pmid",""))} · {checked}</p><p><strong>发现：</strong>{esc(ref["main_finding_zh"])}</p><p><strong>边界：</strong>{esc(ref["limitation_zh"])}</p></article>'
    return body


def write_catalog(kb, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    c, ranking = kb['counts'], kb['journal_selection']
    nav = '<a href="#principles">机制未明的不同含义</a><a href="#platforms">平台与版本</a><a href="#modalities">检测方式比较</a>'
    nav += ''.join(f'<a href="#{esc(n["node_id"])}">{esc(n["node_id"])} · {esc(n["title"].split("：")[0])}</a>' for n in kb['nodes'])
    nav += '<a href="#run">运行与合成示例</a><a href="#papers">文献与排名状态</a>'
    body = f'<section class="box" id="principles"><h2>“未解释”需要先定位缺口</h2><p>7个研究模块，{c["unique_publications"]}条去重记录；{c["abstract_checked"]}条核题录并审读摘要，{c["metadata_only"]}条只核题录。不是穷尽检索或全文系统综述。</p><div class="notice">目标是EGFR突变肺癌同期奥希替尼+铂类/培美曲塞后进展。既往TKI后、奥希替尼单药后、初治及泛癌研究须分别解释。“近一半”不是通用患病概率。</div>'
    body += '<div class="flow"><a href="#node06"><strong>① 未检出</strong><small>低脱落、低肿瘤分数、CNS及实验LoD</small></a><a href="#node01"><strong>② 未覆盖</strong><small>panel设计、复杂SV、RNA与表观状态</small></a><a href="#node02"><strong>③ 检出未解释</strong><small>VUS、非编码、ecDNA及克隆归属</small></a><a href="#node03"><strong>④ 结构未连接功能</strong><small>转录本、同框与激酶域</small></a><a href="#node04"><strong>⑤ 非遗传状态</strong><small>甲基化、染色质与谱系可塑性</small></a><a href="#node07"><strong>⑥ 机制未连接治疗</strong><small>临床证据、具体序列与毒性</small></a></div>'
    body += '<h3>筛选口径与证据边界</h3>' + items([
        f'2025版JCR（2024 JIF）Oncology、Immunology、Genetics & Heredity各前80名并集；按所供表符合的去重期刊记录：{ranking["passed_unique_journal_records"]}。会议单列。',
        '尚无原表时全部期刊排名待核验；程序可导入来源明确的CSV并生成严格筛选集，但不能独立认证JCR授权数据。Nature等综合期刊不能凭声誉自动获得所选学科排名资格。',
        'WGS不是甲基化组或全转录组；覆盖更广不保证低频检出更敏感。平台、版本、事件类型与样本条件必须分别核对。',
        '甲基化/fragmentomics的癌症检测、组织来源分类及ctDNA清除与耐药靶点不是同一终点；可操作率、用药率与获益率分母不同。',
        '变异共检出不证明同一EGFR克隆；血细胞来源、VUS及肿瘤/免疫/CAF区室均不自动映射药物。',
        '病例分析离线运行，只消费已注释和专业审查的结果；不处理原始FASTQ/切片、不自动判定致病性、处方、剂量或个体疗效。',
        'Firecrawl MCP/CLI及注入凭据本次不可用，实际检索核验采用Europe PMC、PubMed和Crossref，保留优先适配器与回退日志。',
    ]) + '</section>'
    platform_node = kb['nodes'][0]
    body += '<section class="box" id="platforms"><h2>国际平台：以发表时版本为准</h2><input id="platform-search" aria-label="检索平台" placeholder="检索MSK、Foundation、Guardant或WGS…">'
    for p in platform_node.get('platforms', []):
        body += f'<article class="platform"><h3>{esc(p["name"])}</h3><p>{esc(p["institution"])} · {esc(p["studied_version"])}</p><p>{esc(p["specimen"])} · {"WGS" if p["is_wgs"] else "非WGS"}</p>{items(p["validated_capabilities_zh"])}<p>{esc(p["assay_specific_performance_zh"])}</p><strong>盲区</strong>{items(p["blind_spots_zh"])}{cite(p["evidence_ids"])}</article>'
    body += '</section><section class="box" id="modalities"><h2>模态回答的问题不同</h2><div class="table-wrap"><table><tr><th>方法</th><th>能回答</th><th>盲区/限制</th></tr>'
    for m in platform_node.get('modality_comparison', []):
        body += f'<tr><td>{esc(m["modality"])}</td><td>{esc(m["answers_zh"])}</td><td>{esc(m["blind_spots_zh"])} {esc(m.get("validation_note_zh",""))}</td></tr>'
    body += '</table></div></section><div class="row controls"><input id="module-search" aria-label="检索机制" placeholder="检索SV、甲基化、MET、阴性、CNS…"><button id="expand">展开全部机制</button></div>'
    for n in kb['nodes']:
        rows = ''.join(f'<tr><td>{esc(b["marker"])}</td><td>{esc(b["meaning"])}</td><td>{esc(b["limitations"])}</td></tr>' for b in n['biomarker_interpretation'])
        strategies = ''.join(f'<article class="strategy"><strong>{esc(s["strategy"])}</strong><span class="badge warn">{esc(s["status"])}</span><p>{esc(s["setting"])}</p><p>{esc(s["limitations"])}</p>{cite(s["evidence_ids"])}</article>' for s in n['treatment_hypotheses'])
        notes = ''
        for note in n.get('integrity_notes', []):
            value = note.get('finding_zh') or note.get('interpretation_zh') or note.get('note_zh') or json.dumps(note, ensure_ascii=False)
            notes += '<div class="notice"><strong>更正与完整性说明</strong><p>' + esc(value) + '</p></div>'
            url = note.get('note_url') or note.get('url') or note.get('correction_url') or ('https://doi.org/' + note['note_doi'] if note.get('note_doi') else '')
            if isinstance(url, str) and url.startswith('https://'):
                notes += '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">核对更正来源</a>'
        body += f'<section class="node" id="{esc(n["node_id"])}"><span class="badge">{esc(n["node_id"])}</span><h2>{esc(n["title"])}</h2><details><summary>机制、标志物、治疗研究及限制</summary>{paras(n["mechanism_zh"])}<div class="table-wrap"><table><tr><th>观察</th><th>意义</th><th>边界</th></tr>{rows}</table></div>{strategies}{notes}<h3>研究缺口</h3>{items(n["research_gaps"])}</details></section>'
    body += '<section class="box" id="run"><h2>运行代码与合成示例</h2><p>Python 3.10+标准库；在完整仓库根目录运行。浏览器验证另需Playwright/Chromium。</p><pre>python3 -m omniresist validate-knowledge\npython3 -m omniresist analyze --input omniresist/examples/plasma_negative.json --output omniresist/generated/plasma\npython3 -m omniresist analyze --input omniresist/examples/ret_fusion.json --output omniresist/generated/ret\npython3 -m omniresist build\npython3 -m omniresist rank --ranks /path/to/licensed_jcr_2025.csv --output /tmp/ranked.json</pre><p><a href="example/result.html">液体阴性的合成示例</a> · <a href="knowledge.json" download>完整知识库</a> · <a href="references.csv" download>文献与筛选状态CSV</a> · <a href="conference_discovery.json">另列会议题录发现记录</a> · <a href="README.md">输入契约与使用说明</a> · <a href="../jak-stat/index.html">JAK/STAT</a> · <a href="../ras-mapk/index.html">RAS/MAPK</a> · <a href="../lineage/index.html">组织学转化</a></p></section><section id="papers"><h2>原始来源与筛选状态</h2><input id="paper-search" aria-label="检索文献" placeholder="题名、期刊、PMID、发现、JCR状态…">' + evidence_html(kb) + '</section>'
    (output / 'index.html').write_text(shell('机制未明的EGFR耐药：多组学检测与解释工作台', body, nav), encoding='utf-8')
    (output / 'knowledge.json').write_text(json.dumps(kb, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (output / 'references.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        columns = ['source_ids', 'title', 'journal', 'publication_date', 'doi', 'pmid', 'design', 'scope', 'verification', 'jcr_status', 'meets_journal_top80', 'url']
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator='\n'); writer.writeheader()
        for ref in kb['unique_evidence']:
            row = {k: ref.get(k, '') for k in columns}
            row.update(source_ids=';'.join(ref['source_ids']), jcr_status=ref['ranking']['status'], meets_journal_top80=ref['ranking']['meets_journal_top80'])
            writer.writerow(row)
    discoveries = kb['nodes'][-1].get('review_provenance', {}).get('conference_search_audit', [])
    (output / 'conference_discovery.json').write_text(json.dumps({'scope': 'Discovery records kept separate; metadata alone does not permit result interpretation.', 'records': discoveries}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_case(result, kb, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    selected = set()
    body = '<section class="box"><h2>适用性与证据状态</h2><div class="notice">研究输出，不是临床诊断或处方。仓库示例全为合成数据；模型和确认字段由专业人员提供，程序不独立验证实验。</div>' + items(result['alerts']) + '</section>'
    for a in result['assay_assessments']:
        body += f'<section class="result assay"><h2>{esc(a["id"])} · {esc(a["platform_name"])}</h2><p>{esc(a["platform_version"])} · {esc(a["modality"])}</p>{items(a["limitations"])}<p>{esc(a["caution"])}</p><p>{esc(a["negative_interpretation"])}</p></section>'
    for r in result['mechanism_hypotheses']:
        selected.update(r['evidence_ids'])
        body += f'<section class="result finding"><h2>{esc(r["gene"])} {esc(r["variant"])}</h2><div class="notice">{esc(STATUS[r["status"]])}</div><p>{esc(r["explanation"])}</p>{items(r["validation_needed"]+r["cautions"])}{cite(r["evidence_ids"])}</section>'
    body += '<section class="box"><h2>未解决维度与补检讨论</h2>'
    for g in result['unresolved_dimensions']:
        selected.update(g['evidence_ids'])
        body += f'<article class="gap"><strong>{esc(g["code"])}</strong><p>{esc(g["reason"])}</p>{cite(g["evidence_ids"])}</article>'
    body += '</section><section class="box"><h2>研究性治疗讨论</h2>'
    if not result['research_directions']:
        body += '<p>当前没有满足门控的研究匹配；保留线索和补检路径，不代表没有耐药机制或没有常规后线选择。</p>'
    for d in result['research_directions']:
        selected.update(d['evidence_ids'])
        body += f'<article class="strategy"><strong>{esc(d["mechanism"])}</strong><p>{esc(d["strategy"])}</p><p>{esc(d["limitations"])}</p><p>JCR筛选：{esc(d["jcr_requirement_status"])}</p>{cite(d["evidence_ids"])}</article>'
    body += '</section><h2>相关文献</h2>' + evidence_html(kb, selected)
    (output / 'result.html').write_text(shell('多组学耐药研究判读报告', body), encoding='utf-8')
