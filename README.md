# EGFR突变肺癌：微环境与耐药机制报告

中文、可交互、可离线阅读的研究报告及可复现生成代码。覆盖免疫细胞、CAF、HGF/MET、FGF/FGFR、IL-6/STAT3、趋化因子、TGF-β/ECM、缺氧/血管生成等主题，明确区分EGFR肺癌直接实验、人体关联、一般肿瘤背景、综述与临床试验。

**当前为文献与期刊排名待核验的研究草稿。** 数据库请求遭当前出口代理403拒绝，不能将候选清单称为完成系统检索的结果；尚未提供指定JCR榜单，因此未宣称符合相关学科IF排名前79名。书目元数据核验也不等于阅读了全文或证明机制因果。

## 仓库中的报告与网站

- [报告HTML文件](reports/egfr_tme_resistance.html)
- [网站首页文件](site/index.html)
- [候选文献表](reports/references.csv)
- [机制数据](reports/report_data.json)
- [证据审计](reports/evidence_audit.json)
- [报告源码下载包](site/downloads/research_code.zip)

GitHub文件页面展示HTML源码；下载后用浏览器打开即可阅读交互报告。`site/` 是可部署到静态托管服务的网站目录；代码推送与网站托管是两个步骤。

## 打开与重新生成

直接在浏览器打开 `reports/egfr_tme_resistance.html`。HTML内嵌全部正文、样式、脚本和数据，无CDN或在线字体；禁用JavaScript仍有完整静态正文。可在页面中检索、筛选证据、点击机制节点、展开全文或打印成PDF。

生成器仅依赖Python 3.10及以上标准库，无需pip安装。默认工作目录为本仓库，云环境路径为 `/workspace/lungcancer`；使用现有checkout，无需创建worktree。

```bash
python3 scripts/build_report.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

可选浏览器验证需要已安装Playwright和Chromium，独立于标准库测试：

```bash
python3 tests/browser_smoke.py --browser /usr/bin/chromium
```

浏览器检查在离线模式加载HTML，验证交互、静态回退、移动端布局和零外部资源请求；缺少浏览器或测试失败会返回非零状态。

输出包含HTML、完整结构化JSON、UTF-8 BOM文献CSV及证据审计JSON。默认时间窗为 **2011-10-21至2026-10-21**；时间窗外经典文献单列背景，不计入近15年候选数量。边界年份若缺具体发表日，标记日期不确定。

## 文献检索与核验

以下命令保留TLS验证及现有代理，记录检索式、分页、上限、缓存、时间及错误，不绕过网络策略。

```bash
python3 scripts/literature.py search --start 2011-10-21 --end 2026-10-21 --max-results 300 --output reports/search_results.json
python3 scripts/literature.py verify --input reports/report_data.json --output reports/verified_references.json
python3 scripts/build_report.py --verified-references reports/verified_references.json
```

检索命令返回0表示请求执行完成，**不代表人工筛选完成**；结果达到上限时标记 `truncated`。访问被拒绝返回3并保存诊断；元数据无法唯一精确匹配返回非零，不自动接受相似的第一条论文。核验采用规范化题名、年份以及已有DOI共同匹配；首次403后停止同样的后续请求。`metadata_verified`仅是书目信息匹配，原文发现及因果解释仍须人工审校。检索下载的新候选不会自动插入机制正文，须人工筛选并补入数据模块。

当前所需网络域名已保存为环境配置草稿：`www.ebi.ac.uk`、`europepmc.org`、`pubmed.ncbi.nlm.nih.gov`、`eutils.ncbi.nlm.nih.gov`、`pmc.ncbi.nlm.nih.gov`、`api.crossref.org`、`doi.org`。草稿保存不等于运行时已生效或已发布。可在环境设置审阅保存，按产品流程发布；访问生效后再重新运行检索与核验。

## IF前79名的可审计筛选

从所采用的正式JCR学科榜单导出CSV，使用 `data/journal_ranks.template.csv` 的字段：

| 字段 | 内容 |
|---|---|
| journal / issn | 期刊全名、ISSN；有多项ISSN可用分号分隔 |
| category | 榜单中的学科名称；跨学科刊可分别列多行 |
| rank | 该学科内JIF名次，正整数 |
| jif_year | JIF所属年份，区别于榜单发布年份 |
| source | 可追溯的榜单来源及版本 |

将文件保存为 `data/journal_ranks.csv`。以下2025仅演示参数，应替换为实际榜单的JIF年份，不表示已获取或认证该榜单：

```bash
python3 scripts/build_report.py --journal-ranks data/journal_ranks.csv --jif-year 2025
python3 scripts/build_report.py --journal-ranks data/journal_ranks.csv --jif-year 2025 --strict-ranking
```

默认规则为同一JIF年份、任一输入相关学科中 `rank <= 79`；程序不自行推断综合期刊的学科排名。普通模式保留未匹配条目并明确标注；严格模式在时间窗候选缺少合格排名时失败，避免静默删除引用而使正文失去支持。输入榜单本身标记为 `user_supplied_unverified`，不冒充程序已独立认证JCR。

## 内容与代码结构

- `data/stromal.json`：CAF、生长因子、ECM及血管机制与候选引用。
- `data/immune.json`：免疫细胞、趋化因子、腺苷及治疗动态。
- `data/overview.json`：综合反馈环、方法、证据边界与研究方向。
- `scripts/literature.py`：公开数据库检索、精确元数据匹配及期刊榜单处理。
- `scripts/build_report.py`：验证引用和图节点、去重、日期判断及自包含HTML生成。
- `templates/`：无外部依赖的交互界面。
- `tests/`：网络失败、错误文献匹配、日期、排名、引用完整性和HTML安全测试。
- `reports/evidence_audit.json`：真实检索状态、证据数量和未完成事项。

机制图是概念示意，不是表达量或因果强度模型。一般免疫抑制不等同于直接TKI耐药；随机试验获益也不等于证实其中某条微环境解释。关于奥希替尼联合化疗、埃万妥单抗或ADC之后的机制，报告明确保留外推限制。
