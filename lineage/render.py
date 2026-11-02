from __future__ import annotations

import json
from pathlib import Path

from rasmapk.render import CSS, esc, paras, items, cite, evidence_html

LABELS = {
 'supplied_integrated_pathology_supported':'报告所述整合病理已满足输入确认条件',
 'marker_only_not_diagnostic':'仅标志物线索，不能诊断',
 'requires_pathology_confirmation':'需要形态与整合病理确认',
 'documented_phenotypic_change_origin_requires_integration':'有配对表型变化，来源仍需整合',
 'preexisting_component_or_new_primary_not_excluded':'未排除原有混合成分、漏采样或第二原发',
 'no_documented_lineage_shift_in_sampled_lesion':'该取样病灶未记录谱系变化',
 'transformation_not_established':'转化尚未建立',
 'shared_origin_supported_by_supplied_paired_genomics':'输入的配对基因组支持同源线索',
 'shared_events_with_egfr_discordance_require_review':'共享事件与EGFR结果不一致，需复核',
 'liquid_driver_not_localized_to_transformed_lesion':'液体EGFR未定位到转化病灶',
 'retained_driver_is_ancestry_clue_only':'保留EGFR仅为祖源线索',
 'clonal_origin_indeterminate':'克隆来源未定',
 'molecular_provenance_requires_validation':'遗传检测来源／有效性需验证',
 'paired_genomics_inconsistent_with_history':'配对基因组与基线历史不一致',
 'paired_sample_timing_requires_review':'配对进展样本与时序不一致',
 'shared_events_require_clonal_review':'共享事件仍需质量与克隆来源审查',
 'not_determined_by_dna_or_expression':'DNA或表达不能决定EGFR依赖',
 'model_support_only_not_clinical_sensitivity':'模型支持功能线索，非临床药敏证明',
 'model_lack_of_dependency_not_global_exclusion':'模型未支持依赖，不能全身一概排除',
 'functional_claim_requires_model_validation':'功能声明缺少患者进展模型验证',
}


def shell(title, body, nav=''):
    script="""for(const [id,sel] of [['module-search','.node'],['paper-search','.paper']]){const input=document.getElementById(id);if(input)input.oninput=()=>{let q=input.value.toLowerCase();document.querySelectorAll(sel).forEach(n=>n.hidden=!n.textContent.toLowerCase().includes(q))}}const button=document.getElementById('expand');if(button)button.onclick=()=>document.querySelectorAll('details').forEach(d=>d.open=true);document.querySelectorAll('.citations a').forEach(a=>a.onclick=()=>{const i=document.getElementById('paper-search');if(i)i.value='';document.querySelectorAll('.paper').forEach(p=>p.hidden=false)});let old=[];addEventListener('beforeprint',()=>{old=[...document.querySelectorAll('details')].map(d=>d.open);document.querySelectorAll('details').forEach(d=>d.open=true)});addEventListener('afterprint',()=>document.querySelectorAll('details').forEach((d,i)=>d.open=old[i]));"""
    script='(() => {'+script+'})();'
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{CSS}</style></head><body><header><div class="kicker">EGFR / LINEAGE PLASTICITY</div><h1>{esc(title)}</h1><p class="sub">组织学变化、克隆来源、EGFR功能依赖与治疗证据分别判读</p></header><div class="layout"><aside>{nav}<button onclick="window.print()">打印 / 保存PDF</button></aside><main>{body}</main></div><footer>研究用途 · 未经临床算法验证 · 证据窗2016-11-02—2026-11-02</footer><script>{script}</script></body></html>'


def write_catalog(kb: dict, output: Path):
    output.mkdir(parents=True,exist_ok=True)
    c=kb['counts']
    nav='<a href="#principle">核心问题</a>'+''.join(f'<a href="#{esc(n["node_id"])}">{esc(n["node_id"])} · {esc(n["title"].split("：")[0])}</a>' for n in kb['nodes'])+'<a href="#papers">参考证据</a><a href="#run">运行代码</a>'
    body=f'<section class="box" id="principle"><h2>保留突变，与保留药物依赖，是两件事</h2><p>{c["nodes"]}个子智能体模块，{c["unique_publications"]}篇去重文献记录；{c["abstract_checked"]}篇核对题录并审读摘要，{c["metadata_only"]}篇仅核题录。未声称审阅全文或完成系统综述。</p><div class="notice">这是研究判读程序，接收已由病理和检测人员注释的信息，不读取切片、不自行诊断、不生成剂量、处方或应答概率。不能仅凭保留EGFR、TP53/RB1、p40、NE标志物或Ki67确诊转化或选择治疗。</div>'
    body+=items(['EGFR DNA保留可支持克隆祖源，但单一常见热点不足独立证明同源。血浆EGFR可能来自未转化病灶。','表型变化可能是早期分支选择或原始混合成分被发现，不等于治疗新造克隆；EMT/basal-shift不等同鳞癌。','部分神经内分泌模型即使重新表达突变EGFR也不恢复TKI敏感；另一些研究存在表达保留及联合信号，应保留异质性。','转化SCLC的化疗骨架、继续EGFR-TKI、免疫联合及DLL3策略证据不同；不能把de novo SCLC标签直接外推。','一项2026 ASCO摘要取得了实际摘要，但其转化/非肺原发混合亚组不能当作EGFR专属疗效。','Firecrawl当前缺少可用工具和凭据，本版实际使用Europe PMC/PubMed/Crossref；代码提供配置后的Firecrawl优先检索及透明回退。'])
    body+='</section><section class="box"><h2>程序的四层判读</h2><div class="table-wrap"><table><tr><th>层次</th><th>主要依据</th><th>不会推断</th></tr><tr><td>当前表型</td><td>进展病灶形态、样本充分性及整合病理</td><td>从基因或单标志物自动诊断</td></tr><tr><td>克隆来源</td><td>基线比较、配对组织和共享事件</td><td>单个EGFR热点证明同源</td></tr><tr><td>EGFR依赖</td><td>表达与患者匹配模型分别记录</td><td>DNA保留等同药敏</td></tr><tr><td>治疗讨论</td><td>目标治疗时序与已确认当前病理</td><td>一律继续/停止TKI或按DLL3/PD-L1选药</td></tr></table></div></section><div class="row controls"><input id="module-search" aria-label="检索模块" placeholder="检索小细胞、鳞癌、克隆、EGFR依赖…"><button id="expand">展开全部</button></div>'
    for n in kb['nodes']:
        rows=''.join(f'<tr><td>{esc(b["marker"])}</td><td>{esc(b["meaning"])}</td><td>{esc(b["limitations"])}</td></tr>' for b in n['biomarker_interpretation'])
        strategies=''.join(f'<article class="strategy"><strong>{esc(s["strategy"])}</strong><span class="badge warn">{esc(s["status"])}</span><p>{esc(s["setting"])}</p><p>{esc(s["limitations"])}</p>{cite(s["evidence_ids"])}</article>' for s in n['treatment_hypotheses'])
        body+=f'<section class="node" id="{esc(n["node_id"])}"><span class="badge">{esc(n["node_id"])}</span><h2>{esc(n["title"])}</h2><details><summary>机制、标志物、治疗证据及缺口</summary>{paras(n["mechanism_zh"])}<div class="table-wrap"><table><tr><th>标志物/特征</th><th>意义</th><th>边界</th></tr>{rows}</table></div>{strategies}<h3>研究缺口</h3>{items(n["research_gaps"])}</details></section>'
    body+='<section id="run" class="box"><h2>运行与下载</h2><pre>python3 -m lineage validate-knowledge\npython3 -m lineage analyze --input lineage/examples/sclc_retained_egfr.json --output lineage/generated/example\npython3 -m lineage build\npython3 -m lineage search --query "EGFR AND small-cell AND transformation" --provider auto --output lineage/generated/search_audit.json</pre><p><a href="knowledge.json" download>知识库JSON</a> · <a href="example_result.json" download>合成示例判读</a> · <a href="README.md">模块使用说明</a></p><p class="muted">分析命令离线运行。只有显式文献检索命令联网；API密钥在环境设置填写，不写入代码或报告。</p></section><section id="papers"><h2>文献与证据边界</h2><div class="row controls"><input id="paper-search" aria-label="检索文献" placeholder="题名、发现、期刊或证据限制…"></div>'+evidence_html(kb)+'</section>'
    (output/'index.html').write_text(shell('EGFR保留与组织学转化：机制判读工作台',body,nav),encoding='utf-8')
    (output/'knowledge.json').write_text(json.dumps(kb,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def write_case(result: dict,kb: dict,output: Path):
    output.mkdir(parents=True,exist_ok=True)
    (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    body='<section class="box"><h2>研究判读结果</h2><div class="notice">仓库示例均为合成数据。程序只检查输入证据结构并整理讨论路线，未经过患者队列临床验证。</div>'+items(result['alerts'])+'</section>'
    selected=set()
    for key,title in [('pathology_assessment','当前病理'),('transformation_assessment','组织学变化'),('clonality_assessment','克隆来源'),('egfr_dependency_assessment','EGFR功能依赖')]:
        r=result[key];selected.update(r['evidence_ids'])
        body+=f'<section class="result"><h2>{title}</h2><div class="notice">{esc(LABELS.get(r["status"],r["status"]))}</div><p>{esc(r.get("explanation",""))}</p>{items(r.get("requirements",[]))}{cite(r["evidence_ids"])}</section>'
    body+='<section class="box"><h2>病理导向的讨论路线</h2>'
    for route in result['treatment_discussion_routes']:
        selected.update(route['evidence_ids'])
        body+=f'<article class="strategy"><h3>{esc(route["id"])}</h3><p>{esc(route["strategy"])}</p><p>{esc(route["limitations"])}</p><span class="badge warn">{esc(route["status"])}</span>{cite(route["evidence_ids"])}</article>'
    if not result['treatment_discussion_routes']:body+='<p>条件不足；先完成适用治疗时序、取样或整合病理核验。</p>'
    body+='<h3>下一步检查</h3>'+items(result['next_steps'])+'</section><h2>相关文献</h2>'+evidence_html(kb,selected)
    (output/'result.html').write_text(shell('组织学与EGFR依赖研究判读报告',body),encoding='utf-8')
