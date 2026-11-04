# JAK/STAT耐药机制研究程序：7个节点模块

面向EGFR突变肺癌在**同期奥希替尼与铂类/培美曲塞后进展**的研究判读。7个子智能体继续整理已有资料，覆盖配体/受体、JAK、STAT3、IFN/其他STAT免疫网络、SOCS/PTP/PIAS反馈、并行通路和临床/会议证据。

证据窗为 **2016-11-04至2026-11-04**。39条去重文献/会议记录均核对了题录并审读摘要；部分研究的结果段和编辑说明另作定点核对，未进行全部研究全文系统审校。AACR2018摘要为临床前依据，出现试验号不等于有患者疗效或当前招募。

**程序未经过临床队列验证。** 它整理机制假说、验证缺口和MTB/试验研究路径，不读取切片、不注释原始VCF、不验证实验，也不输出处方、剂量或虚构的应答概率。

## 运行

Python 3.10+标准库，无需pip；在完整仓库根目录运行，使用现有checkout。

```bash
python3 -m jakstat validate-knowledge
python3 -m jakstat analyze --input jakstat/examples/readouts_only.json --output jakstat/generated/example
python3 -m jakstat analyze --input jakstat/examples/patient_model.json --output jakstat/generated/model
python3 -m jakstat analyze --input jakstat/examples/src_bypass.json --output jakstat/generated/src
python3 -m jakstat build --output site/jak-stat
python3 -m jakstat recheck-metadata --output jakstat/generated/metadata_audit.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

输出 `result.json/result.html`；研究工作台为 `site/jak-stat/index.html`，可离线阅读与检索。**所有示例都是合成数据。**

## 四个不能混同的层次

1. **信号读出**：IL6、RNA、pSTAT3等受细胞来源、时间、炎症和检测方法影响。高低不是功能依赖。
2. **变异及区室**：血浆JAK2 V617F等先定源血细胞/肿瘤；免疫STAT5、PTPN2与肿瘤信号不同，保护作用也可能被抑制。
3. **实验依赖**：研究模型需选择性靶点作用、正交干预/救援、下游轴与耐药表型等审查；匹配患者进展模型仍不是临床药敏证明。
4. **临床适用性**：初治、其他TKI后、多实体瘤及免疫高PD-L1人群，不能直接迁移到奥希替尼同期化疗后。

IL6可以通过LAMA5/FAK或SRC/YAP分叉；pSTAT3不证明JAK来源。Y705/S727、核/线粒体及非磷酸化STAT3不可互换；STAT3/IFN也存在促凋亡或抗肿瘤保护反例。低SOCS表达不等于已证实DNA失活，BCL2家族表达也不等于BH3药敏。

## 输入契约

顶层为 `schema_version='1.0'`、`context`、`observations`，可选 `dependency_tests`及短合成标签。未知字段、重复ID、断开的实验引用、字符串冒充布尔值均拒绝。

`context`沿用RAS模块的治疗时序、基线材料、取样时点、进展模式和病理注释，并增加 `egfr_driver_confirmed`：必须专业确认EGFR敏感驱动且有非空、非野生型的具体注释。程序不独立验证变异致癌性。只有驱动确认、目标同期治疗后、进展取样且确认当前腺癌病理，才可能形成本场景研究匹配；小细胞/鳞状转化或病理未明先走组织学/MTB分支。

`observations`支持：

- `gene/id/kind`：`snv/indel/amplification/loss_of_function/expression/phosphoprotein/cytokine/signature`。
- `level/site/variant`：高/低/正常/未知、磷酸位点与具体变异；不使用统一IHC或细胞因子阈值。
- `sample_type/compartment/compartment_confirmed`：样本与肿瘤、免疫、基质、血清、混合或未知区室。
- `tumor_origin/tumor_origin_evidence/classification`：分子来源与外部专业变异注释；血浆VAF或与EGFR共检出不能代替定源。
- `assay_validated/amplification_confirmed/loss_effect_confirmed/acquisition`：实验室验证声明与基线关系。

DNA变异仅为候选，VUS/良性/造血来源/未确认来源不作肿瘤依赖；JAK/STAT正向成分失活不作激活。血清/免疫/基质信号保留为TME线索，但不能只凭这些建立肿瘤耐药或药敏。

`dependency_tests`必须关联已记录的观察ID，声明明确的轴和实验结果。`validated/compartment_resolved/selective_target_engagement/orthogonal_perturbation/rescue_or_reconstitution/resistance_phenotype_measured/downstream_axis_measured`均是**待审核的实验事实声明**，不是为了得到匹配而随意打开的开关。程序不独立验证这些实验。

只有进展期患者匹配模型、至少一个定位肿瘤的组织/模型观察、轴所需观察及全部审查条件满足，才标记模型机制假说。仅通用细胞系、一个非选择性药、缺乏救援或混合区室均不升级。STAT3非JAK轴另需 `jak_independence_tested`；不能用未检出JAK事件代替。

## 输出与治疗边界

- `signals`：读出、来源及变异的状态和解释，不把高低直接当驱动。
- `dependency_assessments`：实验是否支持假说及缺少的条件；负面实验不全局排除其他病灶。
- `research_options`：仅在模型与临床场景双重门控后列出研究路线。JAK非依赖分支不会映射为JAK药，免疫/反馈分支先审查双向作用。
- 始终 `treatment_recommendations=[]`、`doses=[]`、`response_probabilities=null`。

现有afatinib+ruxolitinib、erlotinib+momelotinib、ruxolitinib+cisplatin/pemetrexed、TTI101以及itacitinib+免疫研究各有人群、设计和毒性限制。早停试验不能说成充分否定全部JAK策略，非肺癌应答不能赋给肺癌，血液pSTAT降低也不证明肿瘤药效。组合感染/骨髓抑制等风险及当前地区标签、招募、既往ADC/抗体要求须临床独立核查。

## Firecrawl优先与可审计回退

```bash
python3 -m jakstat search --query 'EGFR AND STAT3 AND resistance' --provider auto --output jakstat/generated/search_audit.json
```

本版无可调用Firecrawl工具/CLI/注入密钥，**实际论文核验通过Europe PMC/PubMed/Crossref完成**。沿用 `lineage.search` 的Firecrawl v2 Search优先适配器：有密钥先请求，缺失或失败明确记录再回退；强制Firecrawl模式失败非零退出，未冒充成功。

共享检索接口传入本模块独立日期窗；Europe PMC使用FIRST_PDATE范围，Firecrawl网页发现仍须后续核对出版日期/题录，不能直接作为纳入结果。适配器只通过模拟协议测试，尚未以真实Firecrawl凭据实调用。分析命令离线、不调用检索客户端。

`FIRECRAWL_API_KEY`与`api.firecrawl.dev`的安全配置需求此前已存云环境草稿；可在环境设置安全填写、审阅保存并发布。需求已保存不代表已有密钥或已应用；密钥不写入代码或报告。检索保留TLS和既有代理。

## 来源完整性与验证

主库39条记录均提供DOI/PMID、来源URL、日期和审读状态。2017 JNCI STAT3/YAP研究及2026 Editor’s Note列在节点03/06的 `integrity_notes`，不计核心文献或用于治疗映射；编辑说明不等于撤稿，节点06核对了具体更正及编辑对主要结论的说明。这不是穷尽的完整性筛查。

7个模块、独立题录复核、单元/浏览器测试及合成示例分别记录在 `research_team.json` 和 `generated/`。采用共享知识库/检索/HTML工具，旧RAS和组织学模块保留；无PRISMA穷尽检索、全文偏倚评估或患者级敏感度/特异度/临床效用验证。
