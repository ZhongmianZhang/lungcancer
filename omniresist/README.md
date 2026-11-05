# 机制未明的EGFR耐药：多组学检测与解释

针对EGFR突变肺癌在**同期奥希替尼+铂类/培美曲塞后进展**，把“没检出”“没测量”“检出后不能解释”“有机制而没有对应治疗证据”分开。7个研究分工覆盖国际平台、WGS、RNA、表观组、单细胞/空间、液体活检及临床解释。前6个分工的已写成果从中断任务恢复，主智能体负责整合及独立题录复核；执行状态见 `research_team.json`。

证据窗固定为 **2011-11-04至2026-11-04**，本版于2026-11-05整理。定向检索、题录/摘要审读及少数结果段定点核对，不是穷尽检索、全文系统综述或患者级算法验证。真实会议题录如缺摘要，仅保留发现线索，不提取“机制未明百分比”或疗效。“近一半”不能当作适用于所有治疗线次、样本和平台的固定比例。

## 运行与文件

Python 3.10+标准库，在**完整仓库根目录**运行；病例分析离线，无需pip或网络。以下输入全部为合成数据，数值不代表真实平台性能。

```bash
python3 -m omniresist validate-knowledge
python3 -m omniresist analyze --input omniresist/examples/plasma_negative.json --output omniresist/generated/plasma
python3 -m omniresist analyze --input omniresist/examples/ret_fusion.json --output omniresist/generated/ret
python3 -m omniresist analyze --input omniresist/examples/dna_fusion_only.json --output omniresist/generated/dna
python3 -m omniresist analyze --input omniresist/examples/met_amp.json --output omniresist/generated/met
python3 -m omniresist analyze --input omniresist/examples/epigenetic_model.json --output omniresist/generated/epigenetic
python3 -m omniresist build --output site/multiomics
python3 -m omniresist recheck-metadata --output omniresist/generated/metadata_audit.json
python3 -m unittest discover -s tests -p 'test_*.py'
```

每个判读生成 `result.json` 和 `result.html`。`site/multiomics/index.html` 为可离线搜索的研究工作台，含平台版本比较、方法盲区、7个机制模块、原始来源及更正说明。

## 2025 JCR：三学科各前80名

按用户确认，采用**2025版JCR（2024年度JIF）**，Oncology、Immunology、Genetics & Heredity各学科JIF排名前80名的并集。会议另列，不伪称拥有期刊排名。综合期刊不能凭声誉自动获得所选学科资格。

**当前未取得可核验的JCR排名原表，期刊前80筛选未完成。** 所有论文首先作为排名待核验的研究集合，不能宣传为已符合IF前80的筛选集。仓库不提供虚构排名，也不含JCR授权数据。

提供了空白 `jcr_2025_template.csv`，所需列为：

```text
journal,issn,category,rank,jcr_edition,jif_year,ranking_metric,source
```

导入来源明确的本地原表，JCR版年填2025、JIF年度填2024、指标填JIF；多学科或并列排名逐行保存。source须注明可追溯来源。程序校验字段并精确匹配ISSN；双方都有ISSN但冲突时，题名相似不能覆盖冲突。缺ISSN时仅允许标准化后的精确期刊名。程序不能独立认证原表真实性。

```bash
python3 -m omniresist rank --ranks /path/to/licensed_jcr_2025.csv --output /tmp/ranked.json
python3 -m omniresist analyze --ranks /path/to/licensed_jcr_2025.csv --input omniresist/examples/ret_fusion.json --output /tmp/ret_ranked
python3 -m omniresist build --ranks /path/to/licensed_jcr_2025.csv --output /tmp/multiomics_ranked
```

`rank_filtered_journal_records`是按所供表通过的严格期刊集合；未匹配、不在前80或会议分别保存。`strict_rank_screened_directions`要求**机制特异的原始证据**通过筛选，通用ESCAT/AMP指南或其他节点合格不能代替；该字段只表示书目筛选，不证明个体药敏或本治疗序列临床获益。普通 `research_directions`仍可作为明确标注排名状态的探索性线索。

## 输入契约

只接收专业人员整理的JSON：`schema_version='1.0'`、`context`、`assays`、`findings`，可选短 `case_label` 和 `functional_tests`。不接受原始FASTQ/BAM/VCF/切片；不执行比对、变异检测、基因组坐标转换、致病性注释或表观峰调用。全基因组结果须先经合适的临床/研究分析流程注释，选择可追溯事件进入本工具。

`context`沿用已有RAS模块的治疗史、基线、取样时序、进展部位及病理字段，并要求 `egfr_driver_confirmed` 与非空、非野生型的具体驱动说明。只有明确同期治疗后进展、进展期取样及当前确认腺癌病理，才生成该场景的研究匹配。小细胞/鳞状转化先进入病理与组织学模块；寡进展和CNS另保留局部/暴露评估。

`assays`（最多50项）：

- `id/platform_name/platform_version`：明确实际检测和版本。品牌不自动填充当前基因数或LoD；版本未知会阻止机制升级。
- `modality`：`target_dna/wes/wgs/long_read_dna/rna/methylation/atac/chip_seq/scrna/scatac/spatial/protein`。
- `sample_type/collection_timing/status`：组织、血浆、CSF、血细胞或模型；进展时序及QC。
- `validated_classes`：本次经验证的事件/读出类别。WGS不能声明直接测RNA/甲基化，WES不声明非编码或ecDNA架构；ChIP组蛋白标记与ATAC可及性分开。
- `target_scope`：实际靶区、断点/CpG/调控区域等范围摘要；阴性未注明范围会被保留为解释限制。某模态已提供不代表该模态所有基因/病灶均已排除。
- `negative_result/sensitivity_characterized/genome_coverage_evaluated`：阴性及其适用范围。最后一个字段是**实际设计区域/可检测区域的评估声明**，panel填true不代表全基因组已测。
  `negative_result`指该检测对所输入事件的阴性；“没有可靶向耐药机制”不能替代“没有事件检出”。
- `tumor_fraction/tumor_fraction_method/validated_min_tumor_fraction/lod_vaf`：0—1比例，注明实验室方法及适用条件。肿瘤分数不是VAF。LoD仅按适用的SNV/indel条件使用，不转移给扩增、融合或其他平台；不同位点验证条件不同时应分开记录检测条目。
- `rna_quality_passed/compartment_resolved/matched_normal_available/paired_wbc_available`：相关质控与配对材料声明。存在配对正常并不自动确立每个变异的来源。
- 特定原生长读甲基化需 `native_modification_validated=true` 且该类读出已验证，不从“长读”自动推断修饰可测。

`findings`（最多300条专业注释事件）：

- `id/assay_id/gene/alteration_type/variant`：SNV、indel、扩增、缺失、融合、剪接、结构、非编码、ecDNA、甲基化、可及性、组蛋白标记、表达、蛋白或签名。
- `classification/tumor_origin/tumor_origin_evidence/compartment/compartment_confirmed`：致病注释、肿瘤/造血/胚系来源及恶性细胞区室。VUS不被程序自动重分类，配对白细胞的存在也不替代定源。
- `egfr_clonal_link_confirmed/egfr_clonal_link_evidence`：与EGFR恶性克隆的关联及方法。血浆共检出或相近VAF不构成同一克隆证明。
- `orthogonal_confirmed/locus_coverage_confirmed`：该位点/读出的可检测性及独立确认声明，仍由专业人员审核。
- `acquisition/baseline_comparison_confirmed`：有可比基线才能证明获得性；缺基线时保留未证明状态。
- MET扩增需 `ploidy_reviewed/focal_amplification`；没有统一拷贝数、FISH或IHC阈值替所有平台选药。
- 融合需 `rna_confirmed/in_frame/kinase_domain_retained` 以及可解析的 `supporting_assay_ids`；主检测若已为合格RNA也可提供支持。低质量或历史RNA不能升级DNA断点。
- C797S需 `allele_phase/phase_partner/phase_confirmed`；相位对象必须注明。没有相位对象也须专业确认并说明，不能据此自动联合一/三代EGFR药。
- `original_egfr_driver=true`仅用于已确认原始EGFR驱动；其他EGFR事件如L718/G796不会被误归为原驱动保留。

`functional_tests`仅审查已记录观察的实验声明。进展期患者匹配模型、恶性区室、选择性靶点作用、正交干预、救援/补回、下游及耐药表型必须齐备；全部为待审核事实，不是为了得到匹配而打开的开关。负面实验不全局排除其他病灶。模型支持不会变成临床药敏。

## 输出与治疗证据

`assay_assessments`列检测/阴性解释限制，`mechanism_hypotheses`列候选与验证缺口，`unresolved_dimensions`列未充分评估的RNA、结构、表观与空间维度。这些不是要求每位患者完成所有研究检测。

`research_directions`仅在适用场景和事件特异条件满足后供MTB/临床试验讨论。MET/RET等联合研究的入组、阈值与治疗序列不能迁移到已用同期奥希替尼+化疗后；非编码/ecDNA、表观状态、RNA签名与TP53/RB1风险也不能按基因名或相关性直接选药。EZH2干预有促进耐药的反例，不能使用“表观异常→抑制表观药”的统一规则。

始终 `treatment_recommendations=[]`、`doses=[]`、`response_probabilities=null`。工具没有患者队列敏感度、特异度、诊断准确性、治疗获益或临床效用验证；正常后线治疗、局部治疗、当前地区标签及招募资格由临床团队另行核查。

## Firecrawl优先和实际回退

```bash
python3 -m omniresist search --query 'EGFR AND resistance AND (genome OR methylation)' --provider auto --output omniresist/generated/search_audit.json
```

当前无Firecrawl MCP工具、CLI或注入凭据，实际论文题录/摘要核验来自Europe PMC、PubMed及Crossref。沿用 `lineage.search` 中的Firecrawl v2 Search优先适配器；缺密钥/失败记审计后回退，强制Firecrawl失败非零退出。适配器只有模拟协议测试，不声称真实Firecrawl成功。

Europe PMC使用本模块15年FIRST_PDATE日期窗。Firecrawl网页发现不能直接作为纳入结果，仍须核对出版题录、日期及摘要。分析命令不访问网络，也不将病例数据交给检索工具。密钥只应通过现有云环境安全绑定配置，不写进源码、命令记录或报告。

## 可复核记录

`generated/metadata_audit.json`是独立题录复核，`generated/search_audit.json`记录实际来源，`generated/validation.json`记录单元/浏览器检查及源文件哈希；参考文献完整性说明包含PCAWG、TRACERx和2026 WGS研究更正。原始论文仅有少数结果段定点阅读，不声称全部全文审读或穷尽完整性筛查。
