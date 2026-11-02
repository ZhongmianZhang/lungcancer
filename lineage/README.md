# 保留EGFR的组织学／谱系转化：研究判读程序

对象是EGFR突变NSCLC在**奥希替尼与铂类／培美曲塞同期联合后进展**，出现小细胞、鳞癌、LCNEC或混合表型的研究判断。8个子智能体分别整理克隆来源、病理、鳞转化、可塑性、SCLC治疗、SCC治疗、取样与新试验。证据窗为 **2016-11-02至2026-11-02**。

本版32条去重文献记录：31篇实时核对题录并审读摘要，1篇只有题录。包含2026 ASCO e23350实际会议摘要，但其转化/非肺原发混合亚组不能当作EGFR转化专属疗效。未声称阅读全文、完成系统综述或临床算法验证。

## 核心问题

**保留EGFR DNA ≠ 同源性已证明 ≠ EGFR功能依赖 ≠ 应继续奥希替尼。**

EGFR保留可支持祖源线索，但单一常见热点或血浆结果不能定位到转化病灶。配对组织、专家审查的私有主干/结构事件等可增强同源判断。部分转化模型即使恢复突变EGFR表达仍不恢复TKI敏感；另有研究出现蛋白保留和有限联合信号，所以也不能断言所有转化病例永远不依赖EGFR。

程序把**当前表型、组织学变化、克隆来源、EGFR依赖及治疗讨论**分别输出，不通过一个基因或IHC数值将它们合并。

## 运行

Python 3.10+标准库，无需pip，在仓库根目录运行；使用现有checkout。

```bash
python3 -m lineage validate-knowledge
python3 -m lineage analyze --input lineage/examples/sclc_retained_egfr.json --output lineage/generated/example
python3 -m lineage build --output site/lineage
python3 -m lineage recheck-metadata --output lineage/generated/metadata_audit.json
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

判读结果为 `result.json` 和自包含离线 `result.html`。研究工作台为 `site/lineage/index.html`，全部示例均为合成数据。**结果不是病理诊断、处方或患者获益预测。** 程序不读取切片、不注释原始VCF、不构建系统发育树，也不验证输入的专家声明。

## 输入说明

根字段为 `schema_version/context/baseline_pathology/progression_pathology/molecular`，可选短标签 `case_label`。多余字段、字符串冒充布尔值和不一致的组合治疗历史会被拒绝。

- `context`：EGFR原始驱动、奥希替尼与铂/培美曲塞的同期/进展历史、基线材料、取样时序、全身/寡进展/CNS进展及其他既往药物。
- `baseline_pathology`：原始腺癌、腺鳞或混合等，以及是否已回顾原始成分。基线混合或未回顾时，不能把新活检发现简单称为新发生的转化。
- `progression_pathology`：当前类别、可评估形态的样本、诊断充分性、病理医师/形态/IHC整合确认及与基线比较。`adequacy`指**足以支持当前病理类别**，不等于DNA测序量。充分细胞学可选 `cytology`；`plasma/csf`在本字段指仅液体分子资料，有CSF细胞学形态时应选 `cytology` 并记录CNS背景。
- `molecular.original_driver_retained`：原驱动是否保留及检出来源；`matched_tissue_genomics/genomics_validated`与基线、进展时序共同检查。
- `additional_shared_somatic_events`：由专家注释的共享事件。列表非空不自动证明同源；还需 `expert_clonality_reviewed` 与 `shared_private_or_structural_evidence`，并核实样本对应。即使满足，输出仍只是**依据输入专家审查的支持**，不是程序独立建立的克隆结论。
- `egfr_protein_expression`与`functional_egfr_dependence`分别记录。模型支持需要进展时取样、患者匹配模型、实验有效性及同一进展材料；仍不能升级为临床药敏。
- `tp53_rb1_coaltered/rb_pathway_altered`仅为风险/机制线索，不能确诊SCLC；Rb轴也参与鳞状转化。
- `ne_marker_positive/ki67_high/p40_positive`不作为单指标诊断阈值。NE低/阴性不自动排除病理证实SCLC，LCNEC不自动套SCLC。
- `research_liquid_signature`用于记录研究性cfDNA表观组线索，不当作病理确认。常规血浆突变面板的盲区，不等于否定一切液体多组学技术。

## 治疗讨论边界

只有目标联合治疗序列、进展时取样与整合病理确认均满足，才输出该场景的讨论路线：

- SCLC：病理导向的系统治疗讨论，如铂类/依托泊苷框架；既往已用铂、间隔、PS和毒性必须审查，不机械重复。
- SCC：重新讨论鳞状病理适用的方案；一般鳞癌随机试验不能直接迁移为EGFR转化证据。
- LCNEC：专门分型与专家讨论，不与SCLC混同。
- 混合：审查各成分和多病灶，保留残余腺癌或其他亚克隆的可能；不自动拼接全部药物。

EGFR-TKI继续或停止始终为 `not_automatically_decided`。PD-L1高不自动选免疫；DLL3高仅触发转化人群试验资格核查，不自动预测tarlatamab药敏。旧免疫单药低响应与2026化疗免疫回顾关联并列，不能说所有免疫联合均无效。2026转化SCLC的olaparib+durvalumab小型II期阴性结果也保留，未按生物学理据自动配药。

任何情况下 `treatment_recommendations=[]`、`doses=[]`、`response_probabilities=null`。该工具用于研究与分子肿瘤委员会审查，没有患者级敏感度、特异度、校准或临床效用验证。

## Firecrawl优先及实际检索来源

当前会话无Firecrawl工具、CLI或注入密钥，因此**本版研究实际通过Europe PMC/PubMed/Crossref完成**。代码提供Firecrawl v2 Search优先适配器，协议通过mock测试，尚未实际调用Firecrawl验证：

```bash
python3 -m lineage search --query 'EGFR AND small-cell AND transformation' --provider auto --output lineage/generated/search_audit.json
```

`auto`在存在 `FIRECRAWL_API_KEY` 时先请求Firecrawl；缺失或失败时记录原因后回退Europe PMC。`--provider firecrawl`强制模式失败会非零退出，不冒充成功或静默回退。返回检索候选不等于纳入论文或读过全文；Firecrawl搜索是网页发现，不是同行评议或元数据确认。

已在云环境草稿声明 `FIRECRAWL_API_KEY` 安全凭据需求及 `api.firecrawl.dev` 允许目标；密钥应在环境设置安全填写、保存并按产品流程发布，不放进代码、聊天或报告。保存需求不等于已有值或已应用。检索保持TLS/现有代理，不绕过网络策略。分析命令离线，不访问检索客户端；只显式文献检索命令发送使用者输入的文献查询。

## 代码与验证

- `knowledge/node01..node08.json`：8个研究模块、题录/摘要核验状态与证据限制。
- `engine.py`：证据完整性、表型/来源/依赖的独立判读与场景门控。
- `search.py`：Firecrawl优先、回退及无凭据泄露的诊断记录。
- `render.py`：离线中文工作台和研究判读报告。
- `examples/`：小细胞、鳞癌、混合、LCNEC及仅液体风险等合成输入。
- `generated/metadata_audit.json`：独立Europe PMC/Crossref题录复核。
- `../tests/test_lineage.py`：关键临床误判和检索协议回归测试。

论文清单是有目的的叙述性整理，不是穷尽的PRISMA系统综述；全文、偏倚评估、现行地区标签与临床试验招募仍需独立核查。奥希替尼后或转化后再化疗，不等于同期奥希替尼＋化疗后。
