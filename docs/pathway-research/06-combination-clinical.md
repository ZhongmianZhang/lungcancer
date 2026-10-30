# 子任务 6：奥希替尼＋化疗进展后的直接临床证据与人群边界

记录日期：2026-10-30（上海时区）。拟研究窗口：2016-10-30—2026-10-30。**本笔记是可识别研究的离线证据地图，不是完成该窗口实时检索的系统综述。** 本轮没有可用的文献搜索工具，文献与监管域名的运行策略仍拒绝访问；下表全部条目均为“未在线核验”，题录线索及入组条件须回到原文、方案和补充材料逐项确认。没有把待核验的 2025–2026 会议或监管信息填作已知结果。

## 结论与适用范围

PI3K/AKT/mTOR 是具有生物学依据的信号枢纽；**不能据此声称它已被证明是奥希替尼＋铂/培美曲塞进展后的主要耐药构成，或给出其人群占比。** 这一断言需要该具体组合队列的配对样本、检测策略、可评估分母和机制判定标准。pAKT/pS6 升高、PIK3CA 检出、MET 扩增及 PTEN 蛋白丢失代表不同证据层面，不能合并成一个“PI3K 通路阳性率”。

至少分开三个人群：

1. `concurrent_combination_failed`：有明确时间线证明奥希替尼与铂/培美同期作为同一治疗策略，并在该策略或其维持阶段确认进展；诱导与维持组成应分别记录。
2. `sequential_prior_exposure`：先后接受 EGFR-TKI 和含铂化疗；两种药物出现在既往史中，不能自动归入上述组合耐药。
3. `unknown`：药物清单、研究摘要或样本记录不足以确定先后关系。代码要求补充时间线，不能默认为直接匹配。

“停用奥希替尼后接受化疗”“继续奥希替尼并在进展后新加化疗”“一线起始奥希替尼＋化疗后进展”也应保留为不同标签。持续奥希替尼用于 CNS 控制的可行性与逆转某个 PI3K 节点耐药不是同一问题。

## 可识别的临床来源

`直接匹配` 在这里指**论文研究的失败治疗情境**与“已经在奥希替尼＋化疗策略下进展”是否相同，而不是该论文是否属于 EGFR 肺癌。来源标识是定位线索，不表示本轮已打开页面或全文。

| 来源 | 可识别研究、期刊/登记 | 研究解决的问题 | 与本任务直接匹配程度 | 来源状态及不可推断内容 |
|---|---|---|---|---|
| C01 | Planchard D, et al. *Osimertinib with or without Chemotherapy in EGFR-Mutated Advanced NSCLC*. **New England Journal of Medicine**, 2023. DOI [10.1056/NEJMoa2306434](https://doi.org/10.1056/NEJMoa2306434)；FLAURA2：[NCT04035486](https://clinicaltrials.gov/study/NCT04035486) | 一线起始奥希替尼＋铂/培美与奥希替尼单药的随机比较 | 是相关的一线组合来源；**不是组合进展后匹配 PI3K 抑制剂的试验** | 未在线核验；疗效主文不能代替配对耐药分析，不能从总体 PFS 推出任何节点的发生率或逆转方案 |
| C02 | Passaro A, et al. *Amivantamab plus chemotherapy with and without lazertinib in EGFR-mutant advanced NSCLC after disease progression on osimertinib: primary results from the phase III MARIPOSA-2 study*. **Annals of Oncology**, 2024. DOI [10.1016/j.annonc.2023.10.117](https://doi.org/10.1016/j.annonc.2023.10.117)；[NCT04988295](https://clinicaltrials.gov/study/NCT04988295) | 奥希替尼进展后含 amivantamab 的化疗策略 | 不可直接套用为“既往奥希替尼＋同类铂/培美组合失败”的随机证据；需核对确切既往治疗限制 | 未在线核验；不是 MET 扩增或 PI3K 通路筛选试验，不证明某个旁路的特异逆转，也不支持自动重用已失败化疗 |
| C03 | COMPEL：[NCT04765059](https://clinicaltrials.gov/study/NCT04765059)；正式全文题录与分析版本待核对 | 一线奥希替尼发生非 CNS 进展后，化疗背景下继续奥希替尼的策略 | 属于单药进展后引入化疗，**不是起始组合失败后继续同一组合** | 未在线核验；“非 CNS 进展”不等于“无脑转移”；未核对样本量、统计方案与后续分析，不报告精确效应量 |
| C04 | Yu HA, et al. *HERTHENA-Lung01, a Phase II Trial of Patritumab Deruxtecan (HER3-DXd) in EGFR-Mutated Non-Small-Cell Lung Cancer After EGFR Tyrosine Kinase Inhibitor Therapy and Platinum-Based Chemotherapy*. **Journal of Clinical Oncology**, 2023. DOI [10.1200/JCO.23.01476](https://doi.org/10.1200/JCO.23.01476)；[NCT04619004](https://clinicaltrials.gov/study/NCT04619004) | EGFR-TKI 和含铂化疗既往暴露后的 HER3 ADC 单臂研究 | 既往暴露较接近，但不能据题名断言每例为同一并发组合失败；组合来源亚组未知 | 未在线核验；HER3 递送靶点并不证明 HER3→PI3K 信号为致耐药因果；响应不能反推 PI3K 依赖，单臂不等于随机生存获益或当前获批 |
| C05 | TROPION-Lung05：[NCT04484142](https://clinicaltrials.gov/study/NCT04484142)；Dato-DXd，用于有可靶向基因改变的既往治疗 NSCLC，JCO 相关正式报告题录待核对 | 驱动基因阳性、既往靶向和化疗暴露后 TROP2 ADC | 包含相关暴露，是否有可分离的起始组合失败亚组未知 | 未在线核验；多驱动亚型不能合并为 EGFR 组合失败者，TROP2 表达/ADC 活性不等于 PI3K 依赖；不填未核实的 pooled ORR |
| C06 | TROPION-Lung01：[NCT04656652](https://clinicaltrials.gov/study/NCT04656652)；Dato-DXd 对多西他赛随机研究，正式全文题录和驱动亚组定义待核对 | 既往治疗 NSCLC 的后线 ADC 对照证据 | 整体 NSCLC 与 EGFR 亚组、化疗暴露顺序、组织学需要分别审查；不预设直接匹配 | 未在线核验；总体试验与特定驱动小亚组的效应不能互换，不能由某地区历史批准推出现行全球标签 |
| C07 | Wu YL, et al. *Tepotinib plus osimertinib in patients with EGFR-mutated non-small-cell lung cancer with MET amplification following progression on first-line osimertinib (INSIGHT 2): a multicentre, open-label, phase 2 trial*. **The Lancet Oncology**, 2024；[NCT03940703](https://clinicaltrials.gov/study/NCT03940703) | MET 扩增筛选的一线奥希替尼后 EGFR＋MET 联合 | 题名指向一线奥希替尼进展；不能默认既往已接受奥希替尼＋铂/培美 | 未在线核验；血浆和 FISH 入组/主分析定义需核对，不是 PIK3CA/PTEN 异常的匹配治疗证明，也不能把 MET IHC 当作扩增 |
| C08 | Hartmaier RJ, et al. *Osimertinib + Savolitinib to Overcome Acquired MET-Mediated Resistance in Epidermal Growth Factor Receptor-Mutated, MET-Amplified Non-Small Cell Lung Cancer: TATTON*. **Cancer Discovery**, 2023；[NCT02143466](https://clinicaltrials.gov/study/NCT02143466) | 不同 EGFR-TKI 既往治疗队列中的 MET 联合与标志物 | 多队列不能合并为一个起始组合失败人群，需逐队列记录既往三代 TKI/化疗 | 未在线核验；不能按通路相连性将 MET 试验有效性移植到任何 pAKT 阳性者 |
| C09 | SAVANNAH：[NCT03778229](https://clinicaltrials.gov/study/NCT03778229)；奥希替尼＋赛沃替尼，MET 过表达/扩增富集；正式全文及更新版本待核对 | 奥希替尼后 MET 富集阈值和联合活性 | 是否符合起始组合失败、是否此前化疗及阈值版本需原文确认 | 未在线核验；高 IHC/FISH 阈值人群不能与 INSIGHT 2/TATTON 混算，未确认的亚组不视为直接证据 |
| C10 | SACHI：[NCT05015608](https://clinicaltrials.gov/study/NCT05015608)；中国随机研究，赛沃替尼＋奥希替尼与化疗比较；正式全文及现行地区标签待核对 | EGFR-TKI 后、MET 扩增筛选的联合与化疗比较 | EGFR-TKI 类型、既往三代药暴露、既往化疗与具体组合失败亚组需核对，不能仅凭三期研究自动直接匹配 | 未在线核验；不能把随机性升级成所有 MET/PI3K 阳性者适用，更不能从报道推出任意地区现行标签 |

这些临床研究定位跨越不同证据层级。C01 为一线策略，C02/C03 为进展后策略，C04–C06 为跨机制 ADC，C07–C10 为 MET 富集；**没有一项仅因被列入此表就变成“PI3K/AKT/mTOR 定向治疗奥希替尼＋化疗耐药”的直接确证证据。** 对 alpelisib、capivasertib、everolimus 等药物，其在其他癌种、其他分子背景或泛肿瘤探索中的结果不能提供这里缺失的人群证据。

## 重要国际会议与最新结果的核验缺口

需要检索 ASCO、ESMO 和 IASLC WCLC 的 FLAURA2 耐药/配对组织与 ctDNA 分析，以及上述后线研究的成熟 OS、CNS 和组合既往暴露亚组。此轮未获得可在线逐项核实的摘要号、摘要全文及完整筛选结果，因此**不创建猜测的会议条目或摘要号，不以“国际会议报道”给规则加权**。将来每条会议证据至少记录会议、年份、摘要号、准确题名、研究注册号、数据截止、入组分母、是否仅摘要、是否已有正式发表。对应正式论文发表后应去重，不能把同一队列的会议和全文作为两份独立证据。

2025–2026 FLAURA2 更新、COMPEL 正式分析、HERTHENA 后续随机结果以及 ADC 的批准/撤回/更新状态均不能由这份离线笔记推断。当前代码应显示 `current_label_verified=false`，而不是写死“已获批”或“未获批”。

## 可直接实现的全局门控规则

| 规则 | 必需输入/触发 | 应输出 | 禁止的推断 |
|---|---|---|---|
| G01 治疗时间线 | EGFR 亚型；药物；起止日期；同期/序贯；诱导/维持；进展发生在哪一阶段 | 明确区分上述三个人群，缺失为 `unknown`，提示补充真实治疗记录 | 既往两种治疗名同时出现就算组合耐药；把经典 EGFR 双突变适用性外推到所有 EGFR 变异 |
| G02 进展和取样 | 是否影像/临床确认进展；样本距进展/后续换药的时间；样本部位 | 未确认进展时输出“尚不能做耐药归因”；基线或治疗前标本只能输出共变异/基础生物学线索 | 基线 PIK3CA/PTEN 异常就是后天耐药；进展后经历新治疗的样本一定代表前一治疗选择压力 |
| G03 组织学优先 | 是否组织再活检；小细胞/鳞状转化；病理与原发关系 | 已确认转化时提示转化路径的病理/MDT评估，分子旁路仍可并存但不能独占解释；仅 TP53/RB1 异常提示风险，不能诊断转化 | 用血浆或 TP53/RB1 共变异排除/确诊转化；仅凭 PI3K 改变自动进入靶向联合 |
| G04 检测可评估性 | 组织/血浆；肿瘤含量或 ctDNA 可检出性；DNA/RNA/拷贝数/蛋白检测覆盖 | 低脱落或肿瘤含量未知的阴性血浆输出“不确定、未排除”；缺 RNA、FISH、IHC 时提示特定检测缺口 | DNA panel 阴性代表通路不活跃；阴性血浆等于没有耐药机制；IHC表达等于磷酸化/功能依赖 |
| G05 进展模式 | 寡进展、局限 CNS、全身进展、症状及影像情况 | 局限/CNS进展提示相应影像、取样可及性及局部/系统策略讨论；缺失则不预设 | pAKT 阳性就能解释 CNS 药物暴露或所有病灶；继续 EGFR 的 CNS 意义证明旁路被逆转 |
| G06 因果与异质性 | 配对治疗前后结果；具体功能位点；新出现/富集；正交/功能证据；同一肿瘤背景 | 变异线索→候选机制；多证据提高“支持程度”但不输出已验证诊断准确率；多机制并存时逐项呈现 | 任意新变异就是进展主因；独立原发肿瘤信号/样本混合可直接归入旁路；把启发式等级称为概率 |
| G07 治疗证据适用性 | 研究人群、既往治疗顺序、分子定义、研究层级、来源核验状态 | 每个候选策略附 `population_fit`、机制与治疗的独立等级、来源和待确认内容；人群不符/未核验清楚标注 | 体外协同、单臂 ORR、其他癌种批准或同通路药物有效自动变成患者适用方案 |
| G08 来源与地区标签 | 题录是否核验；全文/摘要；数据时间；国家/地区；标签访问日期 | 未核验条目保留“供研究追溯”，不得输出标签已验证；临床选项需专业复核；研究药物不提供联合剂量 | 把 2026-10-30 笔记日期写成搜索截止；以 NCT 登记证明有效、招募开放或已获批 |

可采用的报告总标题是“候选耐药机制与证据核对清单”。不输出个人化剂量、不依据规则自动生成处方、不输出未校准的“耐药概率”。这些边界源于证据结构本身，而不是用统一免责声明替代机制判读。

## 对输入设计的最小建议

`treatment_context`、`progression_confirmed`、`progression_pattern`、`sample_timing`、`sample_type`、`histology` 与具体观察项应独立于基因变异列表。`unknown` 必须与 `negative` 分开；`not_tested` 必须与 `negative` 分开。每个观察项保留检测方法、功能分类来源、治疗前后状态及确认状态。只有上游事件时不要自动伪造 pAKT/pS6 观察，只有下游磷酸化时不要反向伪造 PIK3CA 或 MET 变异。

对治疗措施的可用输出包括：机制确认所需检测、可追溯临床试验/研究方向、适用性障碍和 MDT 讨论事项。没有直接匹配证据时，明确保留跨机制后线评估和临床试验查询入口，不将所有患者导向 PI3K/AKT/mTOR 抑制剂。
