from __future__ import annotations

import json
from pathlib import Path

from rasmapk.render import CSS,esc,items,paras,cite,evidence_html

LABELS={'outside_curated_scope':'不在当前规则范围','not_tumor_resistance_source':'非肿瘤耐药来源，先定源',
 'benign_not_dependency':'良性注释不支持依赖','unclassified_variant_not_driver':'VUS/未知功能不当作驱动',
 'assay_requires_validation':'检测需要验证','molecular_origin_requires_validation':'分子来源需要验证',
 'loss_is_not_pathway_activation':'失活不等于通路激活','cell_compartment_unresolved':'细胞区室未明确',
 'systemic_or_microenvironment_signal':'全身或微环境线索，尚需连接肿瘤表型',
 'amplification_requires_validation':'扩增需平台/倍体等确认','feedback_loss_requires_validation':'负反馈失活需功能验证',
 'feedback_change_not_drug_sensitivity':'反馈变化不等于药敏','signal_readout_not_dependency':'信号读出，不是功能依赖',
 'tumor_alteration_not_dependency':'肿瘤改变，不是耐药/药敏证明','requires_dependency_validation':'功能依赖需进一步验证',
 'supplied_experiment_not_supportive_not_global_exclusion':'该实验未支持依赖，不能全局排除',
 'patient_model_hypothesis_not_clinical_validation':'患者匹配模型支持假说，尚非临床验证'}


def shell(title,body,nav=''):
    script="""(()=>{for(const [id,sel] of [['module-search','.node'],['paper-search','.paper']]){let i=document.getElementById(id);if(i)i.oninput=()=>{let q=i.value.toLowerCase();document.querySelectorAll(sel).forEach(n=>n.hidden=!n.textContent.toLowerCase().includes(q))}}let b=document.getElementById('expand');if(b)b.onclick=()=>document.querySelectorAll('details').forEach(d=>d.open=true);document.querySelectorAll('.citations a').forEach(a=>a.onclick=()=>{let i=document.getElementById('paper-search');if(i)i.value='';document.querySelectorAll('.paper').forEach(n=>n.hidden=false)});let old=[];addEventListener('beforeprint',()=>{old=[...document.querySelectorAll('details')].map(d=>d.open);document.querySelectorAll('details').forEach(d=>d.open=true)});addEventListener('afterprint',()=>document.querySelectorAll('details').forEach((d,i)=>d.open=old[i]));})();"""
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{CSS}</style></head><body><header><div class="kicker">EGFR / JAK–STAT / CELL CONTEXT</div><h1>{esc(title)}</h1><p class="sub">信号强弱、细胞来源、功能依赖与临床治疗证据分别处理</p></header><div class="layout"><aside>{nav}<button onclick="window.print()">打印 / 保存PDF</button></aside><main>{body}</main></div><footer>研究用途 · 未经临床算法验证 · 证据窗2016-11-04—2026-11-04</footer><script>{script}</script></body></html>'


def write_catalog(kb,output: Path):
    output.mkdir(parents=True,exist_ok=True);c=kb['counts']
    nav='<a href="#principle">机制与证据边界</a>'+''.join(f'<a href="#{esc(n["node_id"])}">{esc(n["node_id"])} · {esc(n["title"].split("：")[0])}</a>' for n in kb['nodes'])+'<a href="#run">运行代码</a><a href="#papers">文献库</a>'
    body=f'<section class="box" id="principle"><h2>JAK/STAT并不是单向的耐药开关</h2><p>{c["nodes"]}个研究子智能体模块，{c["unique_publications"]}条去重文献/会议记录；{c["abstract_checked"]}条已核题录并审读摘要。部分结果/讨论段补充核对，不代表完成全文审校或系统综述。</p><div class="notice">本工具消费已注释的病理、区室、变异与实验声明，不读取切片、不注释原始VCF、不验证实验、不生成个体处方或应答概率。模型支持不等于患者临床获益。</div>'
    body+=items(['IL6高可以走LAMA5/FAK或SRC/YAP等分叉；pSTAT3高不能直接指认JAK。','STAT3 Y705/S727、非磷酸化、核与线粒体作用不可互换；某些STAT3/IFN信号可参与凋亡或宿主保护。','血浆JAK2 V617F可能来自血细胞克隆；肿瘤来源、驱动性和药敏是不同层次。','IFN/STAT1/2及STAT5/6、SOCS/PTP等需按肿瘤/免疫/基质区室和时间解释，不能普遍抑制。','已有JAK联合试验的初治、既往TKI后、炎症非鳞肺癌或多实体瘤人群，不等于奥希替尼+同期化疗后。','Firecrawl本次没有可用工具/CLI/注入凭据；实际核验使用Europe PMC/PubMed/Crossref。优先适配器和透明回退沿用已验证的检索组件。'])
    body+='</section><section class="box"><h2>怎样获得可审查的输出</h2><p>读出/变异 → 来源与细胞区室 → 选择性靶点作用、正交干预/救援及耐药表型 → 进展期患者匹配模型 → 治疗时序/病理门控 → 仅供MTB或试验讨论的研究路径。</p><p>没有功能实验时，保留生物学线索和下一步检查，不将“未证明依赖”写成“没有耐药”。仅血液、血清或免疫/基质信号需与肿瘤接收和表型建立联系。</p></section><div class="row controls"><input id="module-search" aria-label="检索机制" placeholder="检索IL6、JAK2、STAT3、IFN、SOCS、毒性…"><button id="expand">展开全部</button></div>'
    for n in kb['nodes']:
        rows=''.join(f'<tr><td>{esc(b["marker"])}</td><td>{esc(b["meaning"])}</td><td>{esc(b["limitations"])}</td></tr>' for b in n['biomarker_interpretation'])
        strategies=''.join(f'<article class="strategy"><strong>{esc(s["strategy"])}</strong><span class="badge warn">{esc(s["status"])}</span><p>{esc(s["setting"])}</p><p>{esc(s["limitations"])}</p>{cite(s["evidence_ids"])}</article>' for s in n['treatment_hypotheses'])
        integrity=''
        for note in n.get('integrity_notes',[]):
            text=note.get('interpretation_zh') or note.get('finding_zh') or str(note)
            integrity+='<div class="notice"><strong>文献完整性说明</strong><p>'+esc(text)+'</p><p>'+esc(note.get('handling_zh',''))+'</p></div>'
            url=note.get('note_url') or note.get('notice_url') or ''
            if url.startswith('https://'):integrity+='<p><a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">核对编辑说明／题录</a></p>'
        body+=f'<section class="node" id="{esc(n["node_id"])}"><span class="badge">{esc(n["node_id"])}</span><h2>{esc(n["title"])}</h2><details><summary>深入机制、标志物、策略与证据限制</summary>{paras(n["mechanism_zh"])}<div class="table-wrap"><table><tr><th>标志物/观察</th><th>意义</th><th>边界</th></tr>{rows}</table></div>{strategies}{integrity}<h3>研究缺口</h3>{items(n["research_gaps"])}</details></section>'
    body+='<section class="box" id="run"><h2>离线判读与检索</h2><pre>python3 -m jakstat validate-knowledge\npython3 -m jakstat analyze --input jakstat/examples/readouts_only.json --output jakstat/generated/example\npython3 -m jakstat analyze --input jakstat/examples/patient_model.json --output jakstat/generated/model\npython3 -m jakstat build\npython3 -m jakstat search --query "EGFR AND STAT3 AND resistance" --provider auto --output jakstat/generated/search_audit.json</pre><p><a href="knowledge.json" download>完整知识库</a> · <a href="example_result.json" download>常见读出合成示例</a> · <a href="README.md">使用说明</a> · <a href="../lineage/index.html">组织学转化模块</a></p></section><section id="papers"><h2>可追溯文献/会议记录</h2><div class="row controls"><input id="paper-search" aria-label="检索文献" placeholder="题名、期刊、试验、发现或局限…"></div>'+evidence_html(kb)+'</section>'
    (output/'index.html').write_text(shell('JAK/STAT耐药研究与机制判读工作台',body,nav),encoding='utf-8')
    (output/'knowledge.json').write_text(json.dumps(kb,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def write_case(result,kb,output: Path):
    output.mkdir(parents=True,exist_ok=True)
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    selected=set();body='<section class="box"><h2>研究判读与适用性</h2><div class="notice">示例均为合成数据。功能验证字段是待审查的实验声明，不是程序独立验证的实验，也不建立患者临床药敏。</div>'+items(result['alerts'])+'</section>'
    for r in result['signals']:
        selected.update(r['evidence_ids'])
        body+=f'<section class="result signal"><span class="badge">{esc(r["id"])}</span><h2>{esc(r["gene"])} · {esc(r["kind"])} · {esc(r["site"])}</h2><div class="notice">{esc(LABELS[r["status"]])}</div><p>区室：{esc(r["compartment"])}；读出：{esc(r["level"])}。</p>{items(r["cautions"])}{cite(r["evidence_ids"])}</section>'
    for d in result['dependency_assessments']:
        selected.update(d['evidence_ids'])
        body+=f'<section class="result dependency"><h2>功能假说：{esc(d["axis"])}</h2><div class="notice">{esc(LABELS[d["status"]])}</div>{items(d["validation_needed"])}{cite(d["evidence_ids"])}</section>'
    body+='<section class="box"><h2>研究性干预讨论</h2>'
    for r in result['research_options']:
        selected.update(r['evidence_ids'])
        body+=f'<article class="strategy"><strong>{esc(r["id"])}</strong><p>{esc(r["strategy"])}</p><p>{esc(r["limitations"])}</p><span class="badge warn">{esc(r["status"])}</span>{cite(r["evidence_ids"])}</article>'
    if not result['research_options']:body+='<p>本输入尚不足以建立该场景的研究匹配；先核对来源、区室、时序与功能实验。</p>'
    body+='<h3>禁止的简化映射</h3>'+items(result['blocked_shortcuts'])+'<h3>下一步</h3>'+items(result['next_steps'])+'</section><h2>相关证据</h2>'+evidence_html(kb,selected)
    (output/'result.html').write_text(shell('JAK/STAT研究判读报告',body),encoding='utf-8')
