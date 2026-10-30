# 子任务 8：文献方法、证据适用性与判读引擎审计

整理日期：2026-10-30（上海时区）。拟定证据窗口为 **2016-10-30 至 2026-10-30**。本任务独立审阅其他节点笔记和 `resistance/engine.py` 初稿；未修改其他子任务文件或代码。以下是审计方法和交付验收要求，不能把它们理解成全部检查已执行或所有建议均已实现。

**当前来源状态：未完成在线检索和全文核验。** 本环境医学数据库/API 访问被代理网络策略拒绝；配置草稿保存不等于规则已生效。没有用镜像绕过限制、关闭 TLS 或虚填会议摘要号。本轮笔记是离线可识别研究的证据地图，不能声称“已检索完整近十年大刊和国际会议”。未定位到直接研究，也不证明该研究不存在。

## 1. 把研究问题写成可以审查的人群与结局

目标人群应为已经确诊 EGFR 突变 NSCLC、接受奥希替尼与含铂/培美曲塞作为同一治疗策略，并在诱导或维持阶段确认进展的患者。需要分别记录经典 exon19del/L858R 与其他 EGFR 亚型、治疗线次、诱导组成、维持组成、是否继续奥希替尼及进展模式。仅“曾用过奥希替尼和化疗”不足以符合该定义。

研究问题分成三条，证据不能互相替代：

1. **观察层：** 进展样本是否存在明确基因改变、蛋白缺失、磷酸化输出或细胞状态变化？
2. **机制层：** 该变化是否在同一肿瘤背景中维持耐药，是否有遗传扰动、药理扰动、救援实验、克隆/纵向证据？
3. **治疗层：** 按该标志物选择患者并干预该节点，能否在目标治疗背景下改善临床结局，毒性与 CNS 控制如何？

FLAURA2 初始组合策略的有效性，不能回答组合进展后某节点的频率或挽救方案。单药后 MET 试验、跨癌种 AKT/PI3K 试验、其他瘤种药物标签分别只能承担其实际支持的命题。

## 2. 可复现检索计划

这部分为**待网络恢复后执行的方案**，并非已运行检索结果。正式运行时保存数据库、完整检索式、UTC 检索时刻、检索日的本地时区、结果总数、实际取回数、分页是否完整、API/数据库版本与访问错误。HTTP 403/超时不能记成“0 篇文献”。

### 2.1 数据库与期刊

优先使用 PubMed/MEDLINE、Europe PMC 和原始期刊页面；ClinicalTrials.gov 用于设计和结果登记核对，Crossref 用于题录/DOI 去重。研究注册不是药物有效、招募开放或获批的证明。

需要覆盖但不能只限于：NEJM、Lancet/Lancet Oncology、JCO、JAMA Oncology、Annals of Oncology、Cancer Discovery、Cancer Cell、Clinical Cancer Research、JTO、Nature Medicine、Nature Cancer、Nature Genetics、Nature Communications、Cancer Research。预先用期刊过滤可能漏掉关键机制或阴性试验，因此先进行主题检索，再按研究角色与质量筛选，不能只按影响因子给证据加权。

PubMed 核心疾病/治疗块：

```text
(("Carcinoma, Non-Small-Cell Lung"[Mesh] OR NSCLC[tiab]
  OR "lung adenocarcinoma"[tiab] OR "lung cancer"[tiab])
 AND (EGFR[tiab] OR "epidermal growth factor receptor"[tiab])
 AND (osimertinib[tiab] OR AZD9291[tiab]))
 AND ("2016/10/30"[Date - Publication] : "2026/10/30"[Date - Publication])
```

将上述块分别与以下主题块组合；先不强制要求题名/摘要包含 `resistance` 或 `chemotherapy`，否则容易漏掉相关功能研究。另做直接组合人群精检：

```text
(chemotherapy[tiab] OR carboplatin[tiab] OR cisplatin[tiab]
 OR pemetrexed[tiab] OR FLAURA2[tiab] OR FLAURA-2[tiab])
```

| 检索组 | 节点主题块示例 |
|---|---|
| 上游受体/适配 | MET OR ERBB2 OR HER2 OR ERBB3 OR HER3 OR IGF1R OR INSR OR IRS1 OR IRS2 OR GAB1 |
| PI3K–AKT | PI3K OR PIK3CA OR PIK3CB OR PIK3R1 OR PDPK1 OR AKT1 OR AKT2 OR AKT3 OR phospho-AKT |
| 负调控 | PTEN OR INPP4B OR PHLPP1 OR PHLPP2 OR TSC1 OR TSC2 OR STK11 OR AMPK |
| mTOR/翻译 | MTOR OR mTORC1 OR mTORC2 OR RICTOR OR RPTOR OR RHEB OR MAPKAP1 OR RPS6KB1 OR RPS6 OR EIF4EBP1 OR EIF4E |
| 交叉/状态 | RAS OR RAF OR BRAF OR MEK OR ERK OR PTPN11 OR SHP2 OR SOS1 OR FGFR OR AXL OR YAP OR TEAD OR EMT OR transformation |
| 化疗/代谢/凋亡 | MCL1 OR BCL2 OR BCL2L1 OR BCL2L11 OR BIM OR KEAP1 OR NFE2L2 OR TYMS OR DHFR OR SLC19A1 OR autophagy OR ferroptosis |
| 节点匹配干预 | capivasertib OR ipatasertib OR alpelisib OR copanlisib OR taselisib OR everolimus OR vistusertib OR sapanisertib OR PI3K-inhibitor OR AKT-inhibitor OR mTOR-inhibitor |
| 临床/阴性研究 | FLAURA2 OR MARIPOSA-2 OR COMPEL OR HERTHENA OR TROPION OR INSIGHT OR SAVANNAH OR SACHI OR TATTON OR S1400B OR NCI-MATCH |

每个词需根据数据库语法加适当字段和括号。Europe PMC 可用 `FIRST_PDATE:[2016-10-30 TO 2026-10-30]` 表达首次发表日期窗口；它与 PubMed 最终出版日期不是同一字段。提前线上发表、正式卷期与会议日期分别保存，不能通过改日期把窗口外背景文献算入十年核心证据。窗口外的引用追溯可以保留，但标为背景。

检索先覆盖目标人群，随后分层补充奥希替尼单药、早代 TKI、其他 EGFR 治疗背景、其他 NSCLC 基因型、泛癌种、其他癌种及模型证据；这些层不混算。对真正“同步组合进展后”的资料稀少时，保留空缺，不以同通路跨癌种文章填充为直接证据。

### 2.2 国际会议

逐年检索 ASCO Annual Meeting、ESMO Congress、IASLC WCLC 和 AACR Annual Meeting 的官方摘要/期刊增刊。采用试验名、NCT 号、节点同义词与上述疾病块交叉检索；重要研究有后续更新时核对 late-breaking、口头报告、海报与正式论文对应关系。当前没有可负责地标成“已核验”的会议条目。

建议访问的官方入口包括 ASCO/JCO 官方摘要、ESMO/OncologyPRO 与 Annals of Oncology 增刊、IASLC 官方会议库与 JTO 增刊、AACR 与 Cancer Research 增刊。所需站点若未列入环境网络策略，应通过环境设置追加准确域名；不能替换未知的允许列表或改变代理路径绕过拒绝。

每条会议记录至少保存：会议及年份、摘要号、准确题名、作者、研究号、数据截止、分母、分析集、是否仅摘要、是否同行评审全文、是否后续正式发表、可追踪 URL、访问状态。仅有“某大会报道”而无定位信息的条目只能进入待查列表，不能直接为机器规则加权。没有找到摘要号时留空并标明未核验，不能推算摘要编号。

### 2.3 纳入、排除与去重

纳入原始临床队列、机制验证、介入试验及其重要阴性/早停结果；综述用于追溯和背景，不能替代原始结果。记录病例、小系列、单臂、随机研究及体外/动物研究，不能把它们合为一个等级。

先按 DOI/PMID/NCT/摘要标识去重，再由研究名、作者、招募时间、中心、样本和分析集识别重叠。相同 NCT 的不同队列或不同治疗阶段未必相同人群；不同论文也未必是独立队列。同一队列的会议初报、正式论文和 OS/耐药后续分析应建立版本关系，按具体结局选择相关版本，不能简单删除或累加。

排除项需要写出原因，包括人群不同、仅背景、无可判定节点证据、同队列重复、窗口外或无法定位。检索因访问阻断而未完成的来源标为 `retrieval_blocked`，不能标为“排除：无证据”。保存逐项筛选记录后才有条件报告筛选数量或 PRISMA 流程；本轮不提供虚构筛选计数。

## 3. 来源和规则的数据结构要求

建议每条来源保留：

```text
source_id, title, authors, journal_or_meeting, year,
doi, pmid, pmcid, nct_id, abstract_id,
publication_type, source_access_status, accessed_at,
population, treatment_sequence, biomarker_definition,
specimen_and_assay, denominator, endpoint,
support_role, limitations, overlapping_cohort_ids,
fulltext_or_abstract, data_cutoff, current_label_verified
```

不知道的值用明确的 `unknown`/空值和待查原因，不编造。`metadata_verified`、`abstract_read`、`fulltext_read`、`claim_verified` 应分开；能打开 DOI 或匹配题名不等于整篇主张得到证实。

规则需分别记录机制证据和治疗证据；`randomized` 只能说明原试验设计，不能把“乳腺癌随机试验”变成“本肺癌背景有随机匹配证据”。每次显示治疗研究方向时必须伴随真实人群与 `population_fit`。当前地区标签、具体适应证与药物可及性只能在权威标签核对后标为已验证；NCT、期刊发表和历史公告均不等价。

## 4. 对节点笔记的独立交叉审查

本轮离线审阅未发现可以确定的明显题录/年份错误；这只是内部一致性检查，不构成题录在线核验。以下问题需在整合时保留：

- 多个子任务重复使用 FLAURA2、Schoenfeld 2020、Blakely 2017 等来源。它们是相同研究，不能因 8 个子智能体独立引用就计作 8 份证据，也不能为所有节点分别提供因果背书。
- [负调控笔记](03-negative-regulators.md) NEG02 的 Yu 等 CCR 2018（`Concurrent Alterations ... Characterization of MTOR as a Mediator of Resistance`）是需要优先核对的 EGFR/MTOR 直接机制线索；比只用临床共变异或转化文献支撑 MTOR 更贴近具体命题，但仍非同步组合后干预证据。
- [PI3K–AKT 笔记](02-pi3k-akt.md) 中 SOLAR-1、CAPItello-291 与 NCI-MATCH 各自只能承担相应癌种/篮式背景的治疗证据。不得从研究设计层级推导目标人群适用性。
- [mTOR 笔记](04-mtor-feedback.md) 将 Cheng 2015 等标为窗口外背景是必要处理；不能在合并时删去这一限制。
- MARIPOSA-2、COMPEL、HERTHENA、TROPION、MET 试验分别回答不同问题。既往 TKI/铂类暴露与起始同步组合失败不是同一入组条件，必须逐队列核对。
- “未核验到”“未定位到”不能改写为“绝不存在”“该药未获批”。2025–2026 资料及会议覆盖尚缺，不能用本次整理日期暗示证据完整性。

## 5. 引擎初稿的具体审计事项

初稿已经显式区分同步/序贯、确认进展、基线/进展样本、VUS、磷酸化与基因事件，并保留 `treatment_recommendation=null`、`automatic_treatment_match=false`；这些边界需要贯穿所有输出格式。

以下是对初稿提出的改进要求；最终是否解决应以根任务的代码与实际回归测试为准：

1. **检测方法与事件类型一一约束。** 初稿把所有基因组事件放在一组，导致 FISH 可被输入为点突变、RNA NGS 可被输入为双等位缺失。应为每种事件设置可接受方法，不把生物学不可能的输入转成规则阳性。
2. **磷酸位点参与纵向比较。** 只比较基因、事件和变异会把基线 pAKT T308 与进展 pAKT S473 误判为同一观察。比较中应保留位点，并说明动态磷酸化不等于新生基因组事件。
3. **反馈的治疗暴露上下文。** 取样时 PI3K/AKT/mTOR 抑制剂暴露可能改变 pAKT/pERK/pS6。缺少这类输入时不能声称已排除反馈；至少应明确暴露未知，若已知用药则显示混杂提示。
4. **无内对照的蛋白缺失不可解释。** PTEN IHC 无同片内部阳性对照应显示不可解释/待确认，不能称为功能缺失已得到支持。技术失败与真正生物学缺失须分开。
5. **时间线和阴性证据的强度。** 基线阴性只有在实际基线样本、质量、可比方法与覆盖支持时，才能称“治疗后首次检出候选”。即使如此也不证明绝对新生。基线已有的实际观察优先于人工填写“基线缺如”。
6. **状态优先级明确。** 非适用癌种、未确认进展、无进展标本与转化优先分支可能同时出现；不能让后面的提示意外覆盖更基础的范围限制。所有失败门控均不能生成普通药物匹配。
7. **不能把肿瘤含量阈值当跨平台通用标准。** `adequate` 为实验室/人工输入，不是本工具自动确定；零肿瘤含量或质量受限必须显式降级。血浆阴性与未检测不能合并。
8. **来源状态应来源于数据。** 当前全部未核验，硬编码警示暂时与事实相符；未来增加已核验记录时应按每条来源动态呈现，不能只改全局开关就升级所有结论。
9. **输出不包含未经校准的主导机制概率或多药累加。** 多节点命中可能是同一通路的上下游读出，也可能多克隆并存；不能把命中数当独立驱动数。

## 6. 必须覆盖的回归测试情境

这些是有明确预期行为的验收情境，测试应针对真实风险分支，而不是只检查帮助文本或复述实现。

| 情境 | 预期行为 |
|---|---|
| 合格进展样本 PIK3CA H1047R、致病注释 | 可列候选 PI3K 激活及确认事项；不输出已证实因果/处方 |
| 相同位点被标 VUS | 不获得普通热点候选/治疗匹配资格，保留不确定观察 |
| AKT1 E17K 与 AKT2 未知变异 | E17K 特异研究不迁移到 AKT2 |
| PIK3CA 点突变被填为 FISH | 拒绝不可能的检测/事件组合 |
| MET IHC 高表达被填为扩增 | 拒绝或保持表达线索，不能生成已确认扩增 |
| MET 扩增未正交确认 | 需要确认局灶性、平台阈值/倍体等；不称因果已定 |
| PTEN 单等位丢失或 VUS | 不视为已验证功能缺失，不匹配 PI3Kα |
| PTEN 蛋白缺失但无内对照 | 显示不可解释/需确认，不能与有效 IHC 缺失同级 |
| TSC2 任意错义或单等位事件 | 不自动视为 mTOR 药敏感 |
| 基线实际已有相同热点、进展仍有 | `preexisting_or_persistent`，不能称新获得 |
| 仅填写基线 absent，无真实可比样本 | 纵向状态未知，不能称新获得 |
| 基线 T308、进展 S473 | 不混为同一磷酸化观察；不确定上游来源 |
| 单独 pAKT/pS6 阳性 | 仅通路输出线索；不能反推 MET/PIK3CA/RICTOR |
| AKT/mTOR 抑制剂暴露下 pAKT 增高 | 提示药效/反馈混杂，不自动判为药物失效或新增机制 |
| 仅血浆阴性或质量受限 | 明确未排除组织/融合/蛋白/转化机制 |
| 仅 TP53/RB1 异常 | 不诊断小细胞转化 |
| 病理确认转化 | 优先病理/MDT路径；不能继续普通通路治疗匹配 |
| 未确认进展或只有基线样本 | 阻断耐药归因，不生成普通候选治疗 |
| 同步组合失败与序贯暴露 | 输出不同背景，不把单药后研究标为直接匹配 |
| 文献/会议元数据未核验 | 保持未核验；登记号和题名可定位不升级为疗效已证实 |
| 非布尔字符串、NaN/无穷肿瘤含量、重复/悬空样本 | 明确输入错误并以非零状态退出，不悄悄纠正 |
| 无规则命中 | “证据不足/未解析”，不输出“无耐药/通路不活跃” |

成功运行这些合成情境只验证软件规则及输入门控，不验证临床准确率、疗效预测能力或患者结局。真正临床使用前仍需原文核对、专家审阅和独立样本验证；本轮交付应如实报告完成的软件检查与未完成的文献工作。
