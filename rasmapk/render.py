from __future__ import annotations

import html
import json
from pathlib import Path

SCOPE = {"post_osimertinib_chemo": "明确奥希替尼+化疗后", "post_osimertinib": "奥希替尼后，非本联合序列专属", "other_egfr_tki": "其他EGFR-TKI背景", "de_novo_other": "其他驱动／非本目标人群", "preclinical": "临床前", "mixed": "混合人群／证据"}
DESIGN = {"randomized": "随机试验", "prospective": "前瞻研究", "retrospective": "回顾研究", "case_series": "病例系列", "case_report": "单病例", "preclinical": "临床前实验", "review": "综述／病例汇总", "conference_abstract": "会议摘要题录"}
STATUS = {"supported_mechanistic_hypothesis": "支持机制假说，未证明临床可行动性", "requires_validation": "尚需验证", "not_supported_benign": "良性注释不支持", "not_tumor_resistance": "血细胞来源，不是肿瘤耐药证据", "readout_only_not_driver": "仅通路状态读出", "unclassified_requires_expert_review": "需专业分型"}
CSS = """
:root{--ink:#15353f;--muted:#61767e;--teal:#117c83;--line:#d8e4e7}*{box-sizing:border-box}body{margin:0;background:#f3f7f8;color:var(--ink);font:15px/1.85 system-ui,'Microsoft YaHei',sans-serif}a{color:#08737c;overflow-wrap:anywhere}header{background:linear-gradient(115deg,#102f40,#145d62);color:white;padding:56px max(5%,calc((100% - 1240px)/2)) 38px}header a{color:#bcebee}h1{font-size:clamp(27px,3.6vw,45px);line-height:1.4;max-width:1080px;margin:14px 0}h2{font-size:25px;margin:8px 0 20px}h3{font-size:19px}h4{font-size:15px;margin-bottom:6px}.kicker{font-size:11px;letter-spacing:.18em;color:#a7d9d8}.sub{max-width:1020px;color:#d4e5e8}.layout{max-width:1360px;margin:auto;display:grid;grid-template-columns:220px minmax(0,1fr);gap:32px;padding:32px 26px}aside{position:sticky;top:24px;align-self:start}aside a{display:block;text-decoration:none;font-size:12px;padding:7px 9px;border-left:2px solid #b8d8dc;margin-bottom:3px}main{min-width:0}.box,.node,.paper,.result{background:white;border:1px solid var(--line);border-radius:12px;padding:24px;margin-bottom:22px}.notice{padding:15px 20px;background:#fff7e8;border:1px solid #eed5a5;border-radius:9px;color:#7b5425;margin:15px 0}.stats{display:flex;flex-wrap:wrap;gap:24px;margin-top:24px}.stat{min-width:100px;border-left:2px solid #71b8bc;padding-left:15px}.stat strong{display:block;font-size:29px}.stat span{font-size:12px;color:#c4dfe2}.badges{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}.badge{display:inline-block;background:#e9f3f4;color:#2c6d72;border-radius:4px;padding:3px 8px;font-size:11px}.badge.warn{background:#fff0db;color:#8c5d1f}.badge.dim{background:#eef0f5;color:#626783}details>summary{cursor:pointer;font-weight:650;padding:9px 0}.description{color:#3b5862}.row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:15px}input,select,button{font:inherit;border:1px solid #c2d5db;border-radius:7px;padding:9px 13px;background:white;color:var(--ink)}input{flex:1;min-width:160px}button{cursor:pointer}button:hover{background:#e7f4f5}table{border-collapse:collapse;width:100%;font-size:12px}td,th{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:12px 9px;overflow-wrap:anywhere}th{background:#edf5f6}.table-wrap{overflow-x:auto}p{margin:11px 0}ul{padding-left:22px}.strategy{border-left:3px solid #8bc2c3;padding:10px 16px;background:#f4f9fa;margin:12px 0}.paper h4{margin:5px 0}.paper:target,.result:target{outline:2px solid #13969b}.citations a{display:inline-block;margin:2px 5px 2px 0;background:#edf4f6;border-radius:4px;padding:1px 6px;font-size:11px}.muted{font-size:12px;color:var(--muted)}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#102f40;color:#d5eef1;padding:20px;border-radius:8px;font-size:12px}code{font-size:.92em}.diagram{width:100%;height:auto;min-width:680px}.diagram-wrap{overflow-x:auto;background:#f5fafb;border:1px solid var(--line);border-radius:8px}.diagram text{font-family:system-ui,'Microsoft YaHei',sans-serif;fill:#214d57}footer{padding:25px;text-align:center;color:var(--muted);font-size:12px}[hidden]{display:none!important}@media(max-width:840px){.layout{grid-template-columns:1fr;padding:20px 15px}aside{position:static;display:flex;overflow-x:auto;gap:6px}aside a{min-width:150px}.box,.node,.paper,.result{padding:18px}header{padding:35px 20px}.stats{gap:15px}.stat{min-width:90px}h2{font-size:22px}}@media print{aside,.controls,.row,button{display:none!important}.layout{display:block;padding:0}header{background:white;color:#15353f;padding:15px}header .sub,.stat span,.kicker{color:#335b64}.box,.node,.paper,.result{break-inside:avoid;border-color:#bbb}body{background:white;font-size:11px}.notice{background:white}details{display:block}a{color:inherit;text-decoration:none}}
"""


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def paras(values) -> str:
    return "".join("<p>" + esc(v) + "</p>" for v in values)


def items(values) -> str:
    return "<ul>" + "".join("<li>" + esc(v) + "</li>" for v in values) + "</ul>"


def cite(ids) -> str:
    return '<div class="citations">' + "".join(f'<a href="#ref-{esc(i)}">{esc(i)}</a>' for i in ids) + "</div>"


def evidence_html(kb: dict, selected: set[str] | None = None) -> str:
    parts = []
    for ref in kb["unique_evidence"]:
        if selected is not None and not selected.intersection(ref["source_ids"]):
            continue
        anchors = "".join(f'<span id="ref-{esc(i)}"></span>' for i in ref["source_ids"][1:])
        state = "已核元数据并审读摘要；未审全文" if ref["verification"] == "metadata_abstract_checked" else "仅核题录；不得提取未取得的结果"
        parts.append(f'<article class="paper" id="ref-{esc(ref["id"])}">{anchors}<div class="badges"><span class="badge">{esc(ref["publication_date"])}</span><span class="badge">{esc(DESIGN[ref["design"]])}</span><span class="badge warn">{esc(SCOPE[ref["scope"]])}</span></div><h4>{esc(ref["title"])}</h4><p class="muted">{esc(ref["authors"])} · {esc(ref["journal"])}</p><p><a href="https://doi.org/{esc(ref["doi"])}" target="_blank" rel="noopener noreferrer">DOI {esc(ref["doi"])}</a> · {esc(state)}</p><p>{esc(ref["main_finding_zh"])}</p><div class="notice">{esc(ref["limitation_zh"])}</div><p class="muted">来源节点：{esc(", ".join(ref["node_ids"]))}；核验：{esc(ref["retrieval"]["provider"])}，{esc(ref["retrieval"]["checked_at"])}</p></article>')
    return "".join(parts)


def diagram() -> str:
    labels = [(20, 25, "RTK：EGFR/MET/ERBB2", "node01"), (270, 25, "SHP2–GRB2–SOS1/2", "node02"), (520, 25, "KRAS / NRAS / HRAS", "node03"), (770, 25, "BRAF / RAF1 / ARAF", "node05"), (770, 140, "MEK1/2", "node07"), (520, 140, "ERK1/2 / DUSP反馈", "node08"), (270, 140, "NF1 / RASA1负调控", "node04"), (20, 140, "PI3K / AXL / YAP交叉", "node09")]
    out = ['<div class="diagram-wrap"><svg class="diagram" viewBox="0 0 1020 255" role="img" aria-label="RAS RAF MEK ERK通路概念图"><defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0L10,5L0,10" fill="#5a959d"/></marker></defs>']
    for path in ("M240 53H267", "M490 53H517", "M740 53H767", "M880 81V137", "M770 168H743", "M380 140V108H600V83", "M130 140V80"):
        out.append(f'<path d="{path}" stroke="#5a959d" fill="none" stroke-width="2" marker-end="url(#arrow)"/>')
    for x, y, label, node in labels:
        out.append(f'<a href="#{node}"><rect x="{x}" y="{y}" width="220" height="56" rx="8" fill="white" stroke="#8fbec4"/><text x="{x+110}" y="{y+33}" text-anchor="middle" font-size="12">{esc(label)}</text></a>')
    out.append('<text x="20" y="235" font-size="11">概念连接，不代表活性、概率、因果强度；负反馈和并行驱动需分别验证。</text></svg></div>')
    return "".join(out)


def shell(title: str, body: str, *, aside: str = "", subtitle: str = "", stats: str = "", script: str = "") -> str:
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>{CSS}</style></head><body><header><div class="kicker">EGFR RESISTANCE / RAS–RAF–MEK–ERK</div><h1>{esc(title)}</h1><p class="sub">{esc(subtitle)}</p>{stats}</header><div class="layout"><aside>{aside}<button onclick="window.print()">打印 / 保存PDF</button></aside><main>{body}</main></div><footer>研究与分子肿瘤委员会讨论用途 · 不生成个体处方 · 证据截止2026-11-01</footer><script>{script}</script></body></html>'


def write_catalog(kb: dict, output: Path) -> Path:
    output.mkdir(parents=True, exist_ok=True)
    c = kb["counts"]
    stats = '<div class="stats">' + "".join(f'<div class="stat"><strong>{number}</strong><span>{label}</span></div>' for number, label in [(10, "独立子智能体 / 节点"), (c["unique_publications"], "去重文献记录"), (c["abstract_checked"], "已核题录及摘要"), (c["metadata_only"], "会议题录 / 无结果审读")]) + '</div>'
    aside = '<a href="#principles">判读边界</a><a href="#map">通路图</a>' + "".join(f'<a href="#{esc(n["node_id"])}">{esc(n["node_id"])} · {esc(n["title"].split("：")[0])}</a>' for n in kb["nodes"]) + '<a href="#papers">证据文献</a><a href="#run">运行代码</a>'
    body = '''<section class="box" id="principles"><h2>从检出事件到机制假说，再到治疗证据</h2><p>对象是EGFR突变NSCLC在奥希替尼与铂类／培美曲塞联合后进展。不同于奥希替尼单药后、其他EGFR-TKI后或de novo RAS/BRAF肺癌。程序不把检测到变异、通路激活与已证明药敏混为一谈。</p><div class="notice">本工具没有患者队列验证、敏感度/特异度评估或临床效用试验，不输出处方、剂量或虚构的应答概率。确切治疗仍需病理、既往治疗、地区现行适应证与临床试验核查。</div><p>时间窗：2016-11-01至2026-11-01。10个独立节点研究任务均已完成；当前去重题录中，部分为重要临床前研究，部分是病例或阴性试验。期刊名、年份和会议题录不替代单篇证据质量。</p><h3>必须保留的反例与外推限制</h3>'''
    body += items(["2026 ORCHARD BRAF模块不支持继续评估奥希替尼+selumetinib，不能用‘BRAF异常→加MEK药’的规则。", "2026 SOS1±MEK早期研究存在严重毒性信号；2026 ERK篮式试验阴性，不能当作通用后线策略。", "NF1失活不等于MEK或SHP2药敏；低ERK也可能参与持留，pERK高低均不能单独定位病因。", "血浆KRAS可能来自克隆性造血；共检出EGFR和RAS不证明同一细胞、同一克隆或获得性。", "两条FLAURA2会议摘要（P2.237、514MO）只核到Crossref题录；未取得结果，未提取频率或疗效。", "元数据/摘要核验不等同于阅读全文；没有把奥希替尼后结果升级为本联合序列的治疗标准。"])
    body += cite([r["id"] for r in kb["unique_evidence"] if str(r.get("pmid")) in {"42202477", "42048384", "42578969", "29567812"}]) + '</section>'
    body += '<section class="box" id="map"><h2>节点与反馈关系</h2>' + diagram() + '</section><div class="row controls"><input id="node-search" aria-label="检索机制节点" placeholder="检索节点、基因或机制，例如 BRAF、NF1、阴性…"><button id="expand-nodes">展开全部</button></div>'
    for node in kb["nodes"]:
        rows = "".join(f'<tr><td>{esc(b["marker"])}</td><td>{esc(b["meaning"])}</td><td>{esc(b["limitations"])}</td></tr>' for b in node["biomarker_interpretation"])
        strategies = "".join(f'<article class="strategy"><strong>{esc(s["strategy"])}</strong><span class="badge warn">{esc(s["status"])}</span><p>{esc(s["setting"])}</p><p>{esc(s["limitations"])}</p>{cite(s["evidence_ids"])}</article>' for s in node["treatment_hypotheses"])
        body += f'<section class="node" id="{esc(node["node_id"])}"><div class="badges"><span class="badge">{esc(node["node_id"])}</span><span class="badge dim">{esc(" / ".join(node["genes"]))}</span></div><h2>{esc(node["title"])}</h2><details><summary>深入机制、标志物解释及研究性干预</summary>{paras(node["mechanism_zh"])}<div class="table-wrap"><table><thead><tr><th>标志物</th><th>可能意义</th><th>判读限制</th></tr></thead><tbody>{rows}</tbody></table></div><h3>治疗研究线索：不等于自动推荐</h3>{strategies}<h3>尚待回答的问题</h3>{items(node["research_gaps"])}</details></section>'
    body += '<section class="box" id="run"><h2>运行判读程序</h2><p>Python 3.10+标准库，无需pip；本地JSON输入，不上传临床数据。示例是合成测试数据。</p><pre>python3 -m rasmapk validate-knowledge\npython3 -m rasmapk analyze --input rasmapk/examples/braf_v600e.json --output rasmapk/generated/example\npython3 -m rasmapk build --output site/ras-mapk\npython3 -m unittest discover -s tests -p "test_*.py"</pre><p><a href="knowledge.json" download>下载完整节点知识库JSON</a> · <a href="example_result.json" download>查看合成示例判读JSON</a> · <a href="README.md">模块说明（仓库路径）</a></p></section>'
    body += '<section id="papers"><h2>可追溯证据库</h2><div class="row controls"><input id="paper-search" aria-label="检索文献" placeholder="题名、期刊、PMID关联节点或发现…"></div>' + evidence_html(kb) + '</section>'
    script = '''for(const [input,selector] of [['node-search','.node'],['paper-search','.paper']]){document.getElementById(input).addEventListener('input',e=>{let q=e.target.value.toLowerCase();document.querySelectorAll(selector).forEach(n=>n.hidden=!n.textContent.toLowerCase().includes(q));});}document.getElementById('expand-nodes').onclick=()=>document.querySelectorAll('.node details').forEach(d=>d.open=true);document.querySelectorAll('.citations a').forEach(a=>a.addEventListener('click',()=>{document.getElementById('paper-search').value='';document.querySelectorAll('.paper').forEach(n=>n.hidden=false);}));let before=[];addEventListener('beforeprint',()=>{before=[...document.querySelectorAll('details')].map(d=>d.open);document.querySelectorAll('details').forEach(d=>d.open=true)});addEventListener('afterprint',()=>document.querySelectorAll('details').forEach((d,i)=>d.open=before[i]));'''
    path = output / "index.html"
    path.write_text(shell("RAS/BRAF及上下游耐药证据工作台", body, aside=aside, stats=stats, subtitle="10个独立研究节点 · 机制判读与临床证据分离 · 合成示例可复现", script=script), encoding="utf-8")
    (output / "knowledge.json").write_text(json.dumps(kb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_case(result: dict, kb: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    body = '<section class="box"><h2>输入适用性与缺失信息</h2><div class="notice">本报告输出机制假说和研究性措施，不是经过验证的诊断、处方或患者获益预测。仓库所附示例为合成数据。</div>' + items(result["alerts"]) + '<p>缺少的病史字段：' + esc(", ".join(result["missing_context"]) or "未发现基础病史字段缺失；不代表临床资料充分") + '</p></section>'
    selected = set()
    for r in result["findings"]:
        selected.update(r["evidence_ids"])
        routes = "".join(f'<article class="strategy"><strong>{esc(s["strategy"])}</strong><p>{esc(s["limitation"])}</p><p class="muted">{esc(s["status"])}</p></article>' for s in r["research_options"])
        body += f'<section class="result"><span class="badge">{esc(r["mechanism"])}</span><h2>{esc(r["gene"])} {esc(r["variant"])}</h2><div class="notice">{esc(STATUS[r["status"]])}</div><p>{esc(r["rationale"])}</p>{items(r["validation_needed"]+r["cautions"])}<h3>可供讨论的研究路径</h3>{routes or "<p>验证条件不足或不支持自动匹配；先完成检测/病理复核。</p>"}{cite(r["evidence_ids"])}</section>'
    body += '<section class="box"><h2>禁止的简化映射</h2>' + items(result["blocked_automatic_mappings"]) + '<h2>下一步</h2>' + items(result["next_steps"]) + '</section><h2>相关文献</h2>' + evidence_html(kb, selected)
    (output / "result.html").write_text(shell("RAS/MAPK研究判读报告", body, subtitle="病例数据仅在本地处理；请结合原始检测与分子肿瘤委员会审校"), encoding="utf-8")
