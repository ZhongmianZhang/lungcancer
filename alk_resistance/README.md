# ALK 融合亚型、共变异和 ALK TKI 进展判读

这是供研究和分子肿瘤团队复核的离线 Python 工具。它解释阿来替尼或洛拉替尼前后的融合转录本、共变异和进展证据，并列出临床语境相符的指南讨论项、适应证核对、病例资料和在研试验。一次运行保留各病灶的结果、证据出处和未解析状态。程序使用规则与人工审阅的输入，尚无病例级外部验证。

- [十年综述 · 融合亚型、共变异和耐药](fusion_variant_review.md)
- [十年书目及公开前 70 优先级](variant_literature.json)
- [研究、临床与期刊审计](evidence_review.md)
- [平台、队列与多组学重分析](platforms.md)
- [机器可读知识库](knowledge.json)
- [论文索引与期刊优先级](references.json)
- [队列计数及原始表图](cohort_observations.tsv)

## 运行

在仓库根目录执行。Python 3.10 或以上，标准库即可。所有样本和坐标均为模拟。

```bash
python3 -m alk_resistance --case alk_resistance/examples/synthetic_alectinib_profile.json
```

阿来替尼示例包含治疗前的 EML4::ALK V3、TP53 与 CDKN2A，及进展时新检出的 G1202R。输出给出风险关联、阿来替尼进展证据、功能图谱冲突说明、后续指南和美国标签核对。下面的洛拉替尼示例展示 VCF/TSV 导入。

```bash
python3 -m alk_resistance \
  --case alk_resistance/examples/synthetic_case.json \
  --vcf T1 WGS TUMOR alk_resistance/examples/synthetic_calls.vcf \
  --trust-vcf-read-phasing \
  --findings-tsv alk_resistance/examples/synthetic_findings.tsv \
  --output /tmp/alk-resistance-demo.json

python3 -m unittest discover -s tests -v
```

模拟结果中，T1 组织提示顺式复合 ALK 变异及新检出的局灶 MET 扩增，可同时保留。P1 血浆结果为未解析。既往两种 ALK TKI 但未用过含铂化疗，例中不符合 neladalkib 美国既往治疗条件。省略 `--trust-vcf-read-phasing` 后，仅共检出的 ALK 变异会降为未证实的顺式关系。省略 `--output` 写到标准输出。

## 病例、质量与时序

| 字段 | 合同 |
|---|---|
| `schema_version`、`case_id`、`disease` | 版本为整数 1，病例使用去标识 ID，病种固定为已证实的 `ALK_fusion_NSCLC`。工具无需上传。 |
| `progression` | `failed_tki` 为 `alectinib` 或 `lorlatinib`。现有洛拉替尼输入可省略，旧 `lorlatinib_line`、`lorlatinib_setting` 仍被识别。新输入填写 `tki_line`（正整数或 null）和 `tki_setting`（`advanced`、`other`、`unknown`）。`pattern` 为 `systemic`、`oligoprogression`、`isolated_cns` 或 `unknown`，用影像复核后的范围。可填 `best_response`（CR/PR/SD/PD/unknown）和 `months_to_progression`（月）。 |
| `clinical` | `age_group`、`setting`、`baseline_histology`、`jurisdiction`。后者填写实际用药监管地区，如 `US`、`CN`。状态缺失用 `unknown`。选值见模拟病例和源文件。 |
| 既往用药 | 仅填不可切除局部晚期或转移阶段使用的 `prior_advanced_alk_tkis` 和 `prior_advanced_platinum`（true、false 或 null）。按有效治疗阶段和英文通用名录入。已知商品名归并为通用名，未知名称标记待核。本次发生进展时所用的晚期 ALK TKI 计入已用药。仅曾全面核对才填写 `advanced_treatment_history_complete: true`。 |
| `specimens[]` | `id`、`timepoint`、`material`（`tissue`、`plasma`、`csf` 等）、`site`、`genome_build`（`GRCh37`、`GRCh38`）、`tumor_fraction`（0–1 或 null）、`tumor_fraction_method` 及 `qc`（`pass`、`limited`、`fail` 或 `unknown`）。时点用 `pre_alectinib` / `progression_on_alectinib` 或 `pre_lorlatinib` / `progression_on_lorlatinib`。每次只评估所选药物的一对时点。含阿来替尼样本时须明确 `failed_tki`。 |
| `assays[]` | 每样本的检测带独立 `id`、`modality`、`platform`、`qc` 、`platform_version` 及 `coverage[]`。可报告 `adequate`、`limited`、`not_assayed` 或 `unknown`，按 `gene`、`kind`、`feature` 及 `details` 记录。仅当预先定义的目标区域及所申报的事件类别可评估时使用 `feature: "*"`。孤立位点会报告 `locus_only`。 |
| 纵向配对 | 在进展样本指定 `baseline_sample_id`。用 `comparable_baseline_assays` 把经审阅可比的进展检测 ID 映射到基线检测 ID。仅当同部位组织、相同已知基因组版本、质量合格、该位点可评价且基线报告明确阴性时，程序标记新检出。声明检测可比时应基于该事件的纯度、深度和 LoD 复核。结果仍无法排除阈值下的早期克隆。 |
| `findings[]` | `id`、`assay_id`、`kind`、`gene`、`feature`、`status`、`qc`、`attributes`。使用 `detected` 或 `not_detected`。基因名用 HGNC 符号，组学签名可用 `EMT` 或 `EPIGENOME`。检测失败或未知的结果保留在输出，只参与质控复核。可记录 `tumor_origin`，已证实为造血或胚系来源的结果不触发耐药规则。 |

协同评估要先核对采样日期、治疗线和病灶。没有报告或覆盖声明的结果仍为未知。基线检测若已检出同样事件，按可见的基线记录展示，不推断同一克隆或相位。

## 三种输入途径

**病例 JSON** 可以直接填入检测报告的 `findings`。蛋白变异接受 `G1202R`、`p.Gly1202Arg`、`p.Lys1150dup` 等。若未提供转录本，录入者需确认 ALK 为参考蛋白编号。对于从报告提取的顺式，`attributes.phase` 需要 `method`（`read_backed`、`long_read` 或 `molecular_linkage`）、`block` 和 `haplotype`。组 ID 仅在一个样本、一个检测内有效。多个独立分子组使用不同 ID。统计相位或共现不能作物理定相。 [HGVS](https://hgvs-nomenclature.org/stable/recommendations/protein/alleles/)

**注释后的体细胞 VCF** 用 `--vcf 病例内样本ID 检测ID 肿瘤列名 文件`。接受明文和 gzip/BGZF 文本。仅位点 VCF 用 `-` 显式声明，该类文件没有可导入的肿瘤 GT/PS。读取 VEP CSQ 或 SnpEff ANN 的指定基因蛋白注释，优先 CSQ 的 `ALLELE_NUM`。多 ALT 如无法确定等位基因则跳过且计数。ALK VCF 注释要求参考转录本，导入保留筛选状态、坐标、等位基因计数推导的 VAF 和可用深度。只有在实验室已核实 GT/PS 代表读取分子时才使用信任相位参数。程序仍要求明确 PS、同一染色体、相同相位组及可定位到单一单倍型的肿瘤等位基因。一个样本检测只导入一份 VCF。SNV 或短 indel 的 VCF 空行不构成阴性。 [VCF](https://samtools.github.io/hts-specs/VCFv4.3.pdf) · [VEP](https://www.ensembl.org/info/docs/tools/vep/vep_formats.html)

**已审阅结果 TSV** 接受与 JSON 同一模型。固定列见 [模拟结果](examples/synthetic_findings.tsv)。`attributes_json` 为空或合法对象；包含 JSON 引号的复杂单元格可用标准 TSV 引用。输入 CNV、SV/融合、非编码变异、IHC/病理、转录、甲基化、ATAC 或组蛋白需声明实际独立检测。普通短读段 WGS 可提供变异、结构与拷贝线索。甲基化、染色质状态、转录活性和组织学需要相应测量。结构或非编码事件可用 `structural_variant`、`noncoding_variant` 保存。未匹配规则的事件可在报告中查阅。

## 关键规则

| 情形 | 录入要点及输出 |
|---|---|
| ALK 顺式双变异 | 洛拉替尼进展内置 G1202R+L1196M 和 C1156Y+L1198F，并记录其他经定相的病例候选。需在同一样本、检测及物理组内得到精确变异组合。同一病例报出两项或 VAF 相近仍待复核。存在另一个未排除 ALK 变异时，C1156Y+L1198F 的再挑战病例不列作匹配选项。K1150dup 单列罕见候选。 |
| 阿来替尼靶内变异 | 进展时已知的位点包括 G1202R、I1171N/S/T 与 V1180L。多个 ALK 位点或肿瘤来源待核时先作为候选。纵向状态由同一药物的配对基线决定。模型面对 G1202R 等获得的结果在 `experimental_associations` 展示。 |
| MET 扩增及融合 | `copy_number/amplification` 的 `focality: "focal"`、`validated_call: true` 和具体 `criteria` 记录平台结论。推荐同时保留 `value`、`unit`、纯度、倍性和片段范围。无可比基线时保持候选。ST7::MET 用同份进展标本的 DNA 与 RNA、相同 `event_link`、RNA `exon_junction: "ST7:1-MET:2"` 及局灶扩增复核。 |
| 组织学 | `histology` 的 `feature` 为 `SCLC`、`LCNEC` 或 `SQUAMOUS`。有组织检查、腺癌基线及 `pathologist_confirmed`、`morphology_and_ihc`、`baseline_histology_compared` 才把转化作为有支持的证据。血浆特征、TP53/RB1 或模型线索不会单独触发小细胞方案。 |
| 表达、甲基化、染色质 | `expression`、`methylation`、`chromatin_accessibility`、`histone_mark` 按测量定义提交。保留细胞来源、方法、效应大小、单位和坐标版本。肿瘤 EMT 签名须有 `tumor_cell_localized`、`multiple_markers`、`paired_reviewed` 才成为候选。AXL、CDA、NKX2-1 及小细胞甲基化签名为可查证研究线索。完整键见知识库。 |

`assessment: supported_hypothesis` 表示至少有一个进展样本达到内置的证据要求。程序同时列出所有未解析病灶。候选及覆盖缺口不折算成百分比。临床选项保留指南、监管标签、回顾性、病例、临床前及试验类型。最终的机制和治疗策略应由分子肿瘤团队结合本地标签、病理、影像、毒性与完整既往治疗史复核。

## 融合转录本、共变异与功能结果

- **融合亚型**使用 `kind: "fusion"`、`gene: "ALK"`、`feature: "EML4::ALK"` 或同格式的其他伴侣。RNA 结果带 `partner_exon`、`alk_exon`、`in_frame: true` 和 `kinase_domain_retained: true`。可填 `reported_variant`（例如 V3a）。EML4 E13/E20/E6a/b 与 ALK A20 对应 V1/V2/V3。只用 DNA 推测会输出 `junction_prediction_only`。接头与声明不符会提示复核。已验证的不同转录本并存时均保留。
- **TP53、CDKN2A/B、RB1、NF2**使用人工审阅的致病分级。TP53 液体结果须经白细胞复核、匹配组织或其他验证证据认可后填写 `tumor_origin: "confirmed"`。CDKN2A/B、RB1、NF2 的序列丢失需要同时填写可信分类及 `loss_of_function: true`，纯合缺失需要 `validated_call: true`。同一样本的基线 V3 和 TP53 记录共现和人群风险。
- **NF2 早期线索**仅在一线阿来替尼，最佳反应 PD 且 3 个月内进展，并有已核实的基线 NF2 功能丧失时提示。此规则对应研究假说。
- **MTAP** 纯合缺失或内对照阳性的完全蛋白丢失可记录研究资格线索。蛋白结果用组织病理 `expression/complete_loss` 与 `internal_control_positive: true`。单独 CDKN2A/B 缺失不触发此规则。符合预筛条件的洛拉替尼进展组织可显示 TAP-ALK 登记，证据记录为尚未招募。
- **功能图谱**按精确 ALK 单变异匹配研究结果，仅进入 `molecular_profiles.experimental_associations`，证据来源包括 H3122 V1 的细胞筛查。程序的耐药机制等级和治疗匹配不依赖这个模型栏目。

## 用授权榜单复核排名

现有仓库的排名程序可重新标注十年书目。按 [CSV 模板](../data/journal_ranks.template.csv) 填写有权限的 JCR 导出，类别保留官方名称。跨类别补充研究与临床文件保留在索引中以便追溯。

```bash
python3 scripts/literature.py rank \
  --input alk_resistance/variant_literature.json \
  --ranks /path/to/authorized-jcr-2025.csv \
  --year 2025 --category Oncology --category Immunology \
  --category 'Genetics & Heredity' --max-rank 70 \
  --output /tmp/alk-journal-audit.json
```
