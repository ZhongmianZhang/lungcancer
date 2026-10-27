(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('report-data').textContent);
  const refs = Array.isArray(data.references) ? data.references : [];
  const mechanisms = Array.isArray(data.mechanisms) ? data.mechanisms : [];
  const meta = data.meta || {};
  const overview = data.overview || {};
  const audit = data.audit || {};
  const refsById = new Map(refs.map(ref => [ref.id, ref]));
  const state = { query: '', category: '', year: '', evidence: '', verifiedOnly: false, node: '', graphId: '', expanded: false };
  const scopeNames = { egfr_lung_direct: 'EGFR 肺癌直接研究', egfr_lung_association: 'EGFR 肺癌相关观察', other_cancer: '非 EGFR 特定 / 跨癌种背景', review: '综述', clinical_trial: '临床试验' };
  const scopeClasses = { egfr_lung_direct: 'direct', egfr_lung_association: 'association', other_cancer: 'external', review: 'review', clinical_trial: 'clinical' };
  const $ = id => document.getElementById(id);
  const text = value => value === undefined || value === null ? '' : typeof value === 'object' ? JSON.stringify(value) : String(value);
  function el(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = text(content);
    return node;
  }
  function safeURL(value) {
    try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? url.href : ''; }
    catch (_) { return ''; }
  }
  function externalLink(label, url, className) {
    const a = el('a', className, label);
    const href = safeURL(url);
    if (href) { a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; }
    else a.removeAttribute('href');
    return a;
  }
  function verified(ref) {
    const value = text(ref.verification).toLowerCase();
    return !value.includes('unverified') && (value.startsWith('verified') || ['metadata_verified', 'abstract_verified', 'fulltext_verified'].includes(value));
  }
  function verificationLabel(ref) {
    const value = text(ref.verification).toLowerCase();
    if (!verified(ref)) return '元数据待核验';
    if (value.includes('fulltext')) return '全文已核验';
    if (value.includes('abstract')) return '摘要已核验';
    return '元数据已核验';
  }
  function citations(ids) {
    const box = el('div', 'citation-strip');
    box.append(el('span', '', '相关文献'));
    (ids || []).forEach(id => {
      const ref = refsById.get(id);
      const a = el('a', 'citation-link', id);
      a.href = '#ref-' + encodeURIComponent(id);
      a.title = ref ? text(ref.title) : '文献记录缺失';
      a.addEventListener('click', () => {
        state.year = ''; state.evidence = ''; state.verifiedOnly = false; state.query = '';
        $('year-filter').value = ''; $('evidence-filter').value = ''; $('verified-only').checked = false; $('report-search').value = '';
        renderReferences(); renderMechanisms();
      });
      box.append(a);
    });
    return box;
  }
  function option(select, value, label) { const o = el('option', '', label); o.value = text(value); select.append(o); }
  function paragraphs(target, values) { (values || []).forEach(value => target.append(el('p', '', value))); }
  function listItems(target, values) { (values || []).forEach(value => target.append(el('li', '', value))); }
  function scopeBadge(ref) { return el('span', 'badge ' + (scopeClasses[ref.evidence_scope] || 'association'), ref.evidence_scope_label || scopeNames[ref.evidence_scope] || ref.evidence_scope || '证据范围待分类'); }
  function initOverview() {
    if (meta.title) { $('report-title').textContent = meta.title; document.title = meta.title; }
    $('date-window').textContent = '文献时间窗：' + text(meta.window_start || '未指定') + ' — ' + text(meta.window_end || '未指定');
    $('generated-at').textContent = '生成时间：' + text(meta.generated_at || '未记录');
    const pending = refs.filter(ref => !verified(ref)).length;
    const rankingPending = refs.some(ref => ref.journal_rank === undefined || ref.journal_rank === null || ref.journal_rank === '');
    $('draft-status').hidden = !pending && !rankingPending;
    if (rankingPending || meta.ranking_status) {
      const n = el('div', rankingPending ? 'notice' : 'notice info');
      n.append(el('strong', '', rankingPending ? '期刊排名筛选尚未完成。' : '期刊排名筛选状态。'));
      n.append(el('p', '', meta.ranking_status || '尚未导入可核验的 JCR 年份与相关学科排名；当前候选文献不等于已满足 IF 排名前 79 名要求。'));
      $('status-notices').append(n);
    }
    if (pending || meta.network_status) {
      const n = el('div', pending ? 'notice' : 'notice info');
      n.append(el('strong', '', pending ? pending + ' 条候选文献的元数据尚未实时核验。' : '文献核验状态。'));
      n.append(el('p', '', meta.network_status || '请将候选条目与原始论文核对；未核验条目不应被解读为已完成系统检索的纳入结果。'));
      $('status-notices').append(n);
    }
    if (meta.scope_note) { const n = el('div', 'notice info'); n.textContent = meta.scope_note; $('status-notices').append(n); }
    const stats = [[mechanisms.length, '机制模块'], [refs.length, '候选文献记录'], [refs.filter(verified).length, '已核验元数据'], [refs.filter(ref => ref.in_window === true).length, '位于指定时间窗']];
    stats.forEach(([number, label]) => { const node = el('div', 'stat'); node.append(el('span', 'stat-number', number), el('span', 'stat-label', label)); $('stats-grid').append(node); });
    paragraphs($('overview-intro'), overview.intro);
    (overview.conclusions || []).forEach((value, i) => { const box = el('article', 'takeaway'); box.append(el('span', 'takeaway-index', String(i + 1).padStart(2, '0')), el('div', '', value)); $('overview-conclusions').append(box); });
    $('crosstalk-heading').hidden = !(overview.crosstalk || []).length;
    (overview.crosstalk || []).forEach(item => {
      const box = el('article', 'crosstalk-card');
      box.append(el('h4', '', item.title), el('div', 'crosstalk-chain', Array.isArray(item.chain) ? item.chain.join(' → ') : item.chain), el('p', '', item.description));
      $('crosstalk-list').append(box);
    });
    (overview.translational || []).forEach(item => {
      const card = el('article', 'translation-card');
      card.append(el('h3', '', item.title), el('p', '', item.description));
      if (item.evidence) card.append(el('div', 'translation-evidence', '证据边界：' + text(item.evidence)));
      if ((item.refs || item.references || []).length) card.append(citations(item.refs || item.references));
      $('translation-list').append(card);
    });
    paragraphs($('methods-copy'), overview.methods);
    listItems($('limitations-list'), audit.limitations);
    const countLabels = {references:'候选文献',mechanisms:'机制模块',in_window:'时间窗内',outside_window:'时间窗外',date_uncertain:'日期待核对',metadata_verified:'元数据已核验',fulltext_reviewed:'全文已审阅',rank_eligible:'排名条件匹配',jcr_independently_verified:'JCR独立核验',journals:'期刊数'};
    Object.entries(audit.counts || {}).forEach(([key, value]) => $('audit-counts').append(el('span', 'audit-stat', (countLabels[key] || key) + '：' + text(value))));
    (audit.checks || []).forEach(check => {
      const label = typeof check === 'string' ? check : [check.name || check.check || check.id, check.status, check.message || check.detail].filter(Boolean).join(' · ');
      $('audit-checks').append(el('li', '', label));
    });
  }
  function mechanismMatches(m, includeNode = true) {
    if (state.category && m.category !== state.category) return false;
    if (includeNode && state.node && !(m.nodes || []).includes(state.node) && !(m.edges || []).some(edge => edge.source === state.node || edge.target === state.node)) return false;
    if (!state.query) return true;
    const related = (m.references || []).map(id => refsById.get(id)).filter(Boolean);
    return JSON.stringify([m.title, m.category, m.summary, m.chain, m.details, m.nodes, m.research_questions, related]).toLowerCase().includes(state.query);
  }
  function renderMechanisms() {
    const matches = mechanisms.filter(m => mechanismMatches(m));
    const fragment = document.createDocumentFragment();
    matches.forEach(m => {
      const card = el('article', 'mechanism-card'); card.id = 'mechanism-' + text(m.id);
      const top = el('div', 'mechanism-top'); const tags = el('div', 'mechanism-meta');
      tags.append(el('span', 'mechanism-index', 'M' + String(mechanisms.indexOf(m) + 1).padStart(2, '0')), el('span', 'badge', m.category || '机制'));
      if (m.evidence_level) tags.append(el('span', 'badge association', m.evidence_level));
      top.append(tags, el('h3', '', m.title), el('p', 'mechanism-summary', m.summary));
      card.append(top);
      const chain = el('div', 'signal-chain');
      (m.chain || []).forEach((value, i) => { if (i) chain.append(el('span', 'chain-arrow', '→')); chain.append(el('span', 'chain-node', value)); });
      card.append(chain);
      const details = el('details', 'mechanism-body'); details.open = state.expanded;
      details.append(el('summary', '', '机制解释 · 证据边界 · 待解决问题'));
      const content = el('div', 'mechanism-content'); paragraphs(content, m.details);
      if (m.clinical_boundary) { const box = el('div', 'boundary'); box.append(el('strong', '', '临床解释边界'), el('div', '', m.clinical_boundary)); content.append(box); }
      if ((m.research_questions || []).length) { content.append(el('h4', 'question-heading', '可检验的研究问题')); const ul = el('ul', 'research-questions'); listItems(ul, m.research_questions); content.append(ul); }
      content.append(citations(m.references)); details.append(content); card.append(details); fragment.append(card);
    });
    if (!matches.length) fragment.append(el('div', 'empty-state', '没有符合当前筛选的机制。可清除筛选，或换用基因、细胞名称检索。'));
    $('mechanism-list').replaceChildren(fragment);
    $('mechanism-count').textContent = '显示 ' + matches.length + ' / ' + mechanisms.length + ' 条机制';
    $('node-filter').hidden = !state.node;
    $('node-filter').textContent = state.node ? '节点：' + state.node + ' ×' : '';
  }
  function renderReferences() {
    const matches = refs.filter(ref => {
      if (state.year && String(ref.year) !== state.year) return false;
      if (state.evidence && ref.evidence_scope !== state.evidence) return false;
      if (state.verifiedOnly && !verified(ref)) return false;
      return !state.query || JSON.stringify(ref).toLowerCase().includes(state.query);
    });
    const fragment = document.createDocumentFragment();
    matches.forEach(ref => {
      const tr = el('tr'); tr.id = 'ref-' + text(ref.id);
      const source = el('td'); source.append(el('span', 'ref-id', ref.id));
      if (ref.exact_title === false) source.append(el('span', 'badge unverified', '检索线索 · 正式题名待核对'));
      source.append(el('span', 'ref-title', ref.title));
      source.append(el('div', 'ref-bibliography', [ref.authors, ref.journal, ref.year].filter(Boolean).join(' · ')));
      if (ref.in_window === false) source.append(el('span', 'badge background', '时间窗外背景文献'));
      const links = el('div', 'ref-links');
      if (ref.doi) links.append(externalLink('DOI ↗', 'https://doi.org/' + ref.doi));
      if (ref.pmid) links.append(externalLink('PubMed ↗', 'https://pubmed.ncbi.nlm.nih.gov/' + encodeURIComponent(ref.pmid) + '/'));
      if (ref.url && safeURL(ref.url)) links.append(externalLink(ref.url.includes('term=') || ref.url.includes('query=') ? '文献检索入口 ↗' : '来源入口 ↗', ref.url));
      source.append(links);
      const finding = el('td'); finding.append(scopeBadge(ref), el('p', 'ref-finding', ref.finding_zh));
      if (ref.limitation_zh) finding.append(el('p', 'ref-limit', '边界：' + text(ref.limitation_zh)));
      const status = el('td'); status.append(el('span', 'badge ' + (verified(ref) ? 'verified' : 'unverified'), verificationLabel(ref)));
      const rankParts = [];
      if (ref.journal_rank !== null && ref.journal_rank !== undefined && ref.journal_rank !== '') rankParts.push('期刊排名：' + text(ref.journal_rank));
      else rankParts.push('IF 排名前79名：待核对');
      if (ref.rank_year) rankParts.push('排名年份：' + text(ref.rank_year));
      if (ref.rank_source) rankParts.push('来源：' + text(ref.rank_source));
      if (ref.rank_status) rankParts.push('筛选状态：' + text(ref.rank_status));
      status.append(el('div', 'ref-ranking', rankParts.join('；')));
      tr.append(source, finding, status); fragment.append(tr);
    });
    if (!matches.length) { const tr = el('tr'); const cell = el('td', 'empty-state', '没有符合当前筛选的文献。'); cell.colSpan = 3; tr.append(cell); fragment.append(tr); }
    $('reference-table-body').replaceChildren(fragment);
    $('reference-count').textContent = '显示 ' + matches.length + ' / ' + refs.length + ' 条候选记录';
  }
  function initTimeline() {
    const groups = new Map(); refs.forEach(ref => { if (ref.year) groups.set(String(ref.year), (groups.get(String(ref.year)) || 0) + 1); });
    const max = Math.max(1, ...groups.values());
    [...groups.entries()].sort((a, b) => Number(a[0]) - Number(b[0])).forEach(([year, count]) => {
      const button = el('button', 'timeline-year'); button.type = 'button'; button.setAttribute('aria-label', '查看 ' + year + ' 年的 ' + count + ' 条文献');
      const bar = el('span', 'timeline-bar'); bar.style.width = (count / max * 100) + '%';
      button.append(el('strong', '', year), bar, el('small', '', count + ' 条候选文献'));
      button.addEventListener('click', () => { state.year = year; $('year-filter').value = year; renderReferences(); $('references').scrollIntoView({ behavior: 'smooth' }); });
      $('publication-timeline').append(button);
    });
  }
  const svgNS = 'http://www.w3.org/2000/svg';
  function svg(tag, attributes, content) {
    const node = document.createElementNS(svgNS, tag);
    Object.entries(attributes || {}).forEach(([key, value]) => node.setAttribute(key, value));
    if (content !== undefined) node.textContent = text(content);
    return node;
  }
  function nodeColumn(name) {
    if (/CAF|TAM|MDSC|Treg|CD[48]|NK|DC|巨噬|成纤维|髓系|内皮|中性粒|肿瘤细胞|细胞毒|树突|免疫细胞|T 细胞/i.test(name)) return 0;
    if (/耐药|耐受|存活|逃逸|增殖|EMT|DTP|可塑|表型|修复|凋亡|免疫抑制|组织学|干性|耗竭|血管异常|低灌注/i.test(name)) return 3;
    if (/IL[-－]?\d|CXCL|CCL|HGF|FGF(?!R)|VEGF(?!R)|TGF|ECM|胶原|缺氧|腺苷|乳酸|细胞因子|外泌体/i.test(name)) return 1;
    return 2;
  }
  function renderGraph() {
    const chosen = state.graphId ? mechanisms.filter(m => m.id === state.graphId) : mechanisms.filter(m => mechanismMatches(m, false));
    const frequencies = new Map(); const edgeMap = new Map();
    chosen.forEach(m => {
      new Set([...(m.nodes || []), ...(m.edges || []).flatMap(edge => [edge.source, edge.target])]).forEach(name => frequencies.set(name, (frequencies.get(name) || 0) + 1));
      (m.edges || []).forEach(edge => { if (edge.source && edge.target) edgeMap.set([edge.source, edge.target, edge.label || ''].join('|'), edge); });
    });
    const allNames = [...frequencies.keys()].filter(Boolean);
    const names = state.graphId ? allNames : allNames.sort((a, b) => frequencies.get(b) - frequencies.get(a) || a.localeCompare(b, 'zh')).slice(0, 36);
    const nameSet = new Set(names); const cols = [[], [], [], []]; names.forEach(name => cols[nodeColumn(name)].push(name));
    cols.forEach(col => col.sort((a, b) => frequencies.get(b) - frequencies.get(a) || a.localeCompare(b, 'zh')));
    const height = Math.max(430, Math.max(...cols.map(col => col.length), 1) * 67 + 70);
    const positions = new Map();
    cols.forEach((col, x) => col.forEach((name, i) => positions.set(name, { x: 125 + x * 250, y: 48 + i * ((height - 85) / Math.max(col.length, 1)) + ((height - 85) / Math.max(col.length, 1)) / 2 })));
    const root = $('mechanism-graph'); root.replaceChildren(); root.setAttribute('viewBox', '0 0 1000 ' + height);
    root.append(svg('title', { id: 'graph-svg-title' }, 'EGFR 肺癌微环境信号关系示意'), svg('desc', { id: 'graph-svg-desc' }, '概念图按细胞来源、配体与微环境、受体与信号通路、细胞状态与结局排列。点击或按回车选中节点以筛选机制。'));
    const defs = svg('defs'); const marker = svg('marker', { id: 'graph-arrow', viewBox: '0 0 10 10', refX: '9', refY: '5', markerWidth: '5', markerHeight: '5', orient: 'auto-start-reverse' }); marker.append(svg('path', { d: 'M 0 0 L 10 5 L 0 10 z', fill: '#88a8b2' })); defs.append(marker); root.append(defs);
    const edges = [...edgeMap.values()].filter(edge => nameSet.has(edge.source) && nameSet.has(edge.target));
    edges.forEach((edge, index) => {
      const a = positions.get(edge.source), b = positions.get(edge.target); if (!a || !b || edge.source === edge.target) return;
      const direction = b.x >= a.x ? 1 : -1;
      const x1 = a.x + direction * 103, x2 = b.x - direction * 106;
      const sameColumn = a.x === b.x;
      const bend = sameColumn ? 70 + (index % 3) * 17 : Math.max(45, Math.abs(x2 - x1) * .42);
      const pathValue = sameColumn ? 'M ' + (a.x + 104) + ' ' + a.y + ' C ' + (a.x + 104 + bend) + ' ' + a.y + ', ' + (b.x + 104 + bend) + ' ' + b.y + ', ' + (b.x + 104) + ' ' + b.y : 'M ' + x1 + ' ' + a.y + ' C ' + (x1 + direction * bend) + ' ' + a.y + ', ' + (x2 - direction * bend) + ' ' + b.y + ', ' + x2 + ' ' + b.y;
      const active = state.node && (edge.source === state.node || edge.target === state.node);
      const path = svg('path', { d: pathValue, class: 'graph-edge' + (active ? ' active' : ''), 'marker-end': 'url(#graph-arrow)' });
      path.append(svg('title', {}, edge.source + ' → ' + edge.target + (edge.label ? '：' + edge.label : ''))); root.append(path);
      if (state.graphId && edges.length < 18 && edge.label && !sameColumn) root.append(svg('text', { x: (x1 + x2) / 2, y: (a.y + b.y) / 2 - 5, 'text-anchor': 'middle', class: 'graph-edge-label' }, edge.label));
    });
    names.forEach(name => {
      const p = positions.get(name); const g = svg('g', { class: 'graph-node' + (state.node === name ? ' selected' : ''), tabindex: '0', role: 'button', 'aria-label': '筛选相关机制：' + name, 'aria-pressed': state.node === name ? 'true' : 'false', transform: 'translate(' + p.x + ',' + p.y + ')' });
      g.append(svg('rect', { x: '-104', y: '-23', width: '208', height: '46', rx: '8' }), svg('title', {}, name + '；涉及 ' + frequencies.get(name) + ' 个当前机制模块'));
      const label = svg('text', { 'text-anchor': 'middle' });
      const chars = Array.from(name); const split = chars.length > 23 ? 22 : chars.length > 17 ? 17 : chars.length;
      if (chars.length > split) { label.append(svg('tspan', { x: '0', y: '-3' }, chars.slice(0, split).join('')), svg('tspan', { x: '0', dy: '14' }, chars.slice(split, split * 2).join('') + (chars.length > split * 2 ? '…' : ''))); }
      else label.setAttribute('y', '4'), label.textContent = name;
      g.append(label);
      const activate = () => { state.node = state.node === name ? '' : name; renderMechanisms(); renderGraph(); $('mechanisms').scrollIntoView({ behavior: 'smooth', block: 'start' }); };
      g.addEventListener('click', activate); g.addEventListener('keydown', event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); } }); root.append(g);
    });
    const omitted = allNames.length - names.length;
    $('graph-caption').textContent = (state.graphId ? '单机制完整节点图。' : '全局图优先展示共享节点，完整关系请切换至单条机制。') + ' 当前显示 ' + names.length + ' 个节点、' + edges.length + ' 条关系。' + (omitted ? '为保证可读性，另有 ' + omitted + ' 个节点未在全局图展示。' : '') + ' 各列为阅读分组，不代表空间位置或时间顺序。';
  }
  function initControls() {
    [...new Set(mechanisms.map(m => m.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh')).forEach(category => option($('category-filter'), category, category));
    [...new Set(refs.map(ref => ref.year).filter(Boolean))].sort((a, b) => b - a).forEach(year => option($('year-filter'), year, year));
    [...new Set(refs.map(ref => ref.evidence_scope).filter(Boolean))].forEach(scope => option($('evidence-filter'), scope, scopeNames[scope] || scope));
    option($('graph-select'), '', '全局概念图'); mechanisms.forEach(m => option($('graph-select'), m.id, m.title));
    $('report-search').addEventListener('input', event => { state.query = event.target.value.trim().toLowerCase(); renderMechanisms(); renderReferences(); renderGraph(); });
    $('category-filter').addEventListener('change', event => { state.category = event.target.value; renderMechanisms(); renderGraph(); });
    $('year-filter').addEventListener('change', event => { state.year = event.target.value; renderReferences(); });
    $('evidence-filter').addEventListener('change', event => { state.evidence = event.target.value; renderReferences(); });
    $('verified-only').addEventListener('change', event => { state.verifiedOnly = event.target.checked; renderReferences(); });
    $('graph-select').addEventListener('change', event => { state.graphId = event.target.value; renderGraph(); });
    $('node-filter').addEventListener('click', () => { state.node = ''; renderMechanisms(); renderGraph(); });
    $('clear-filters').addEventListener('click', () => { state.query = ''; state.category = ''; state.node = ''; state.year = ''; state.evidence = ''; state.verifiedOnly = false; $('report-search').value = ''; $('category-filter').value = ''; $('year-filter').value = ''; $('evidence-filter').value = ''; $('verified-only').checked = false; renderMechanisms(); renderReferences(); renderGraph(); });
    $('expand-all').addEventListener('click', () => { state.expanded = !state.expanded; document.querySelectorAll('.mechanism-body').forEach(node => node.open = state.expanded); $('expand-all').textContent = state.expanded ? '收起全部详情' : '展开全部详情'; });
    $('print-report').addEventListener('click', () => window.print());
    let openBeforePrint = [];
    window.addEventListener('beforeprint', () => { openBeforePrint = [...document.querySelectorAll('details')].map(node => [node, node.open]); openBeforePrint.forEach(([node]) => node.open = true); });
    window.addEventListener('afterprint', () => { openBeforePrint.forEach(([node, open]) => node.open = open); });
  }
  initOverview(); initControls(); initTimeline(); renderMechanisms(); renderReferences(); renderGraph();
  const staticReport = $('static-report');
  if (staticReport) staticReport.hidden = true;
})();
