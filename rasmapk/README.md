# RAS–RAF–MEK–ERK 耐药机制研究判读程序

面向 **EGFR突变NSCLC在奥希替尼与铂类／培美曲塞联合后进展**的研究整理与分子肿瘤委员会讨论。10个独立子智能体分别研究10个节点模块，证据窗为 **2016-11-01至2026-11-01**。49篇去重记录中，47篇已实时核对元数据并审读摘要；2条会议摘要只核到题录，未提取未取得的结果。未声称审阅全文，也未完成系统综述。

**程序没有经过患者队列验证，不能诊断耐药、自动开药或估计应答概率。** 它把已注释的检测事件分成支持机制假说、需要验证、仅状态读出、非肿瘤来源、未分类等，明确列出依据、反证与下一步检查。药物研究线索不是本治疗序列的标准治疗。

## 安装与运行

Python 3.10+标准库，无需pip。使用现有checkout，工作目录为仓库根目录。

```bash
python3 -m rasmapk validate-knowledge
python3 -m rasmapk analyze --input rasmapk/examples/braf_v600e.json --output rasmapk/generated/example
python3 -m rasmapk build --output site/ras-mapk
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

结果包括 `result.json` 和可离线阅读的 `result.html`。节点研究网站位于 `site/ras-mapk/index.html`，知识库位于同目录的 `knowledge.json`。所有示例均为**合成数据，非真实患者**。

在线独立复核49篇题录：

```bash
python3 -m rasmapk recheck-metadata --output rasmapk/generated/metadata_audit.json
```

该命令仅将公开论文ID发送至Europe PMC／Crossref，不接触病例输入。保留HTTPS、代理和证书验证；失败非零退出并保存审计。元数据匹配不代表临床结论或全文已验证。离线判读与报告生成不需要联网。

## 输入契约

完整示例见 `examples/`。根对象只接受 `schema_version`、`context`、`findings` 和可选的合成 `case_label`；不会静默忽略拼写错误。

`context` 应说明：

- EGFR原始驱动；是否用过奥希替尼、铂类／培美曲塞，是否同期联合及是否联合后进展。
- 是否有基线对照、是否在进展时取样。
- 组织类型及是否由进展期病理确认转化。
- 全身、寡进展或中枢进展；额外的既往药物名称。

`findings` 每条使用明确的 `gene`、`variant`、`alteration_type`、`classification`、`sample_type`、`tumor_origin`、`acquisition` 和相关验证字段。事件类型允许 `snv/indel/amplification/fusion/loss_of_function/expression/phosphoprotein/unknown`；VUS写为 `vus`。布尔值须为JSON `true/false`，不接受字符串冒充。

- `assay_validated`：检测本身是否已确认。
- `amplification_confirmed`：由实验室结合平台、倍体、肿瘤含量等确认，不是程序自行用一个拷贝数阈值切分。
- `rna_confirmed/in_frame/kinase_domain_retained`：融合的表达与结构确认。
- `biallelic_loss`：NF1/RASA1失活的双等位背景确认。
- `functional_activation`：需要具体等位功能审校的节点，不等同于pERK高。
- 液体样本 `tumor_origin='confirmed'` 时还须提供 `tumor_origin_evidence` 说明；共检出EGFR、VAF高低不能自行证明同克隆或排除克隆性造血。

这些注释来自原始实验室及专业审校，程序不替代变异分类。原始FASTQ/BAM/VCF、单位不明的拷贝数或VAF不能直接作为输入；缺少依据时应保留未知，而非编造验证状态。

## 机制判读与治疗证据分别处理

1. 校验病史、样本、变异类型及证据完整性。
2. 按**具体等位变异**保守匹配机制，未知不强行分类；保留多个事件，不假设同一克隆。
3. 对血细胞来源、VUS、未确认扩增/融合、仅表达/磷酸化读出设置阻断。
4. 仅在目标联合治疗序列与进展期取样均明确、验证条件满足且无转化优先分支时，才列出需要MTB或临床试验核查的研究路径。其他背景保留一般机制说明并阻断本场景研究匹配；临床可行动性始终单独标为未建立。
5. 任何情况下 `treatment_recommendations=[]`、`doses=[]`、`response_probabilities=null`，避免把候选路径伪装为处方、剂量或预测概率。

**BRAF分类表为保守子集，不是完整变异数据库。** V600E、选定class II/III、融合和未分类分别保留；V600K不借用V600E证据，多BRAF事件不将整个病例强行定类。MEK/SHP2/ERK等节点不能只按基因名判断药敏。

## 重要反例

- 2026 ORCHARD BRAF模块（PMID42202477）：奥希替尼＋selumetinib结果不支持继续评估，不能默认推荐该组合。
- 2026 SOS1±MEK早期研究（PMID42048384）：疗效与严重肺毒性限制必须保留；不是本目标治疗序列。
- 2026 ERK跨癌篮式研究（PMID42578969）：不能支持BRAF非V600／融合的通用ERK标准治疗。
- NF1篮式MEK研究（PMID37053535）及SHP2抵抗机制（PMID36820830）反对“NF1缺失就选MEK/SHP2”的简化。
- 血浆KRAS的克隆性造血来源（PMID29567812）以及ERK负反馈／持留反例都进入判读限制。

这些原始试验、病例与临床前模型的人群不同。特别是**奥希替尼后不等于奥希替尼＋化疗后**；FLAURA2随机疗效试验也不能证明某个RAS耐药事件的发生率或匹配药物疗效。

## 会议与来源核验

2026 JTO **P2.237**（DOI `10.1016/j.jtho.2026.105019`）与2023 Annals of Oncology **514MO**（DOI `10.1016/j.annonc.2023.10.593`）已核对Crossref题录，标记 `metadata_only` 和 `result_interpretation_allowed=false`。会议归属和具体结果未由官方材料核验，不提供RAS/BRAF频率或治疗效果。

会议官网、ClinicalTrials.gov和FDA在本次访问时返回出口代理403；必要域名已保存为云环境配置草稿，保存草稿不代表运行时已应用或已发布。正式期刊摘要及题录已通过现可访问的Europe PMC/PubMed/Crossref核验。地区现行说明书、试验当前招募及全部全文仍需独立核查。

## 文件结构

- `knowledge/node01..node10.json`：10个节点的机制、标志物、研究策略和可追溯引用。
- `knowledge.py`：引用完整性、日期精度、十模块与题录去重校验。
- `engine.py`：确定性、无概率权重的保守研究判读。
- `retrieve.py`：独立实时题录复核，临床输入不会发往外部。
- `render.py`：离线中文证据工作台和个案研究报告。
- `examples/`：BRAF V600E混合事件、NF1失活、未证实融合、中枢进展阴性样本等合成示例。
- `generated/metadata_audit.json`：独立题录复核记录。
- `../tests/test_rasmapk.py`：关键临床误判场景与输出引用的回归测试。

没有执行PRISMA系统筛选、全文双人审校、偏倚评估或临床算法验证，不应据此宣称所有重要论文/会议已穷尽。新增论文和适用人群需继续由专业人员审查。
