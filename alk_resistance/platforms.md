# 检测平台及纵向研究资源

本表核查公开原文、补充文件和访问规则。所查资源中尚未确认可以公开取得、覆盖同一患者洛拉替尼用药前与进展后 WGS、RNA 和甲基化的临床队列。原发或横断面的结果可验证检测方法及提出节点假说。配对和受控病例适合检验真正的耐药假说，须先验证时间轴和测量范围。

| 平台或研究资源 | 模态与已核实的观察 | 数据及可开展的分析 |
|---|---|---|
| **CPTAC LUAD** | 110 份未治疗肿瘤、101 份配对邻近组织。WGS 名义深度 15×、WES 150×，独立 RNA、EPIC 甲基化及蛋白组。7 例同框 ALK 融合中 5 例由 WGS 定位断点，7 例 ALK RNA 表达离群，4 例检出 ALK 蛋白。这些计数说明层间互补，不能当作临床灵敏度。 | 补充表提供处理结果，原始按文件经 GDC/dbGaP phs001287 审查。可检验融合、断点、RNA 与蛋白的同一样本一致性。 [Cell 原文](https://doi.org/10.1016/j.cell.2020.06.013) |
| **CPTAC/ICPC LUAD** | 406 份原发 LUAD、388 份邻近组织，17 例 ALK 融合。四个亚队列做 WGS/WES/RNA，EPIC 仅 CPTAC.A/B。CPTAC.A 含 Gillette 2020 样本。 | 可提取公共图表中的 ALK 蛋白信号和 NKX2-1 甲基化/转录背景。DNA/RNA 数据按 phs001287、phs001954 权限获取。 [Cancer Cell](https://doi.org/10.1016/j.ccell.2025.07.011) · [PDC](https://pdc.cancer.gov/pdc/cohort/cptac-icpc-luad) |
| **APOLLO-LUAD** | 87 例切除肺腺癌，肿瘤/正常 WGS 平均 116×/39×，配有 RNA、蛋白及磷酸化。该研究无独立甲基化层。 | 高深度原发 WGS 的对照，适合评估 SV/CNV 和蛋白读出。原始数据按 phs003011.v1.p1 访问。 [论文](https://doi.org/10.1016/j.xcrm.2022.100819) · [GDC](https://gdc.cancer.gov/about-data/publications/APOLLO-LUAD-2022) |
| **Hartwig Medical Foundation** | 转移癌论文有 2,520 个肿瘤/血正常对、2,399 人，中位深度 106×/38×。部分患者多样本，发表时的患者级分析取最高纯度样本。 | 受控申请。可按治疗与取样日期筛选真正前后配对。文件包括 somatic VCF、SV VCF、PURPLE CNV、LINX fusion、临床 TSV 和部分 RNA。 [Nature](https://doi.org/10.1038/s41586-019-1689-y) · [文件规范](https://hartwigmedical.github.io/documentation/data-access-request-guide.html) · [申请](https://www.hartwigmedicalfoundation.nl/en/data/data-access-request/) |
| **Genomics England** | 13,880 个实体肿瘤、33 癌种。可链接 WGS 与纵向治疗，94.5% 为切除样本，其中 93.6% 治疗前取得。 | 安全研究环境、按权限访问，导出结果经审查。用治疗和取样记录查找可能的配对病例。 [Nature Medicine](https://doi.org/10.1038/s41591-023-02682-0) · [数据访问](https://www.genomicsengland.co.uk/research/data) |
| **ICGC/TCGA PCAWG** | 2,658 个肿瘤、38 种类型的 WGS，其中跨癌种配套 WGS/RNA 分析为 1,188 份。 | 可作非编码、断点和 CNV 背景。公开处理结果在对象存储，受控数据走 DACO，部分原始另经 dbGaP phs000178。 [WGS](https://doi.org/10.1038/s41586-020-1969-6) · [转录组](https://doi.org/10.1038/s41586-020-1970-0) · [访问指引](https://docs.icgc-argo.org/docs/data-access/icgc-25k-data) |
| **AACR GENIE BPC NSCLC v2.0** | 1,846 人、4 个中心。靶向面板、相对用药和进展日期、版本覆盖。部分试验药有掩码，cBioPortal 仅子集。 | Synapse syn27056697 提供完整处理数据入口。先确认用药日期、可报告区域和重采配对，适合估计各面板待复核比例。 [CCR](https://doi.org/10.1158/1078-0432.CCR-23-0580) · [公开入口](https://aacrprojectgenie.org/data/bpc-nsclc-v2-0-public/) |
| **MSK-IMPACT / MSK-FUSION** | MSK-IMPACT 为配对正常的靶向 DNA，研究版和 FDA 原始报告范围需分别确认。在 DNA 无已知驱动且成功补做 RNA 的选择亚组中，36/254 有新增发现，包括 27 例同框融合及 6 例 MET exon 14 跳跃。 | RNA 补测可核对患癌驱动和进展 SV。选择后亚组的阳性率不能外推到全人群。 [技术文件](https://www.accessdata.fda.gov/cdrh_docs/reviews/den170058.pdf) · [RNA 补测](https://doi.org/10.1158/1078-0432.CCR-19-0225) |
| **FoundationOne CDx / Liquid CDx** | 组织和血浆靶向 DNA。液体 324 基因版本验证的重排 95% LoD 中位数为增强区/标准区 0.37%/0.90% VAF，扩增和缺失限分别为 21.7% 与 30.4% 肿瘤分数。 | 实际报告需记录版本、输入和逐事件 LoD，研究验证汇总值不能直接应用于某基因或病例。 [组织版](https://doi.org/10.1371/journal.pone.0264138) · [液体版](https://doi.org/10.1371/journal.pone.0237802) |
| **Guardant360/CDx 与 Infinity** | Guardant360 原始 FDA 文件的 SNV/indel 范围为 55 基因，融合含 ALK/NTRK1/RET/ROS1，扩增含 MET/ERBB2。历史研究另有 70/73 基因版本。CROWN 七年采用 Infinity 755 基因加甲基化肿瘤分数。 | 适合研究血浆进展和组织—血浆互补。需按版本、分子数、肿瘤分数、基因和事件类别记录分母。 [Guardant360 技术文件](https://www.accessdata.fda.gov/cdrh_docs/pdf20/P200010B.pdf) · [CROWN](https://doi.org/10.1016/j.annonc.2026.05.692) |
| **浅层血浆 WGS 与靶向测序** | Dietz 等分析 73 人的 271 份纵向血浆。0.5× sWGS 的拷贝数异常检出为 18% 样本，靶向方法为 6%。34/43 次进展中 sWGS 的 t-MAD 拷贝不稳定性指标上升。 | 对照不同方法的技术互补。混合 ALK TKI 人群的浅层 WGS 不适合用来证明具体 SNV、短 indel、相位或洛拉替尼特异因果。 [原文](https://pmc.ncbi.nlm.nih.gov/articles/PMC7670098/) |
| **ALK 纵向甲基化与 GEO 模型** | cfMeDIP-seq 21 人、79 份血浆，混合 TKI；5 人曾用洛拉替尼。有公开色瑞替尼耐药模型的甲基化或单细胞结果，以及早代 ALK TKI 模型的表观调控数据。 | 人体原始数据 EGA EGAS00001006573 受控。先验证真正用药前/进展配对。GEO GSE139388、GSE81487 仅模型验证，适合测试方向和交叉组学处理。 [人体研究](https://pmc.ncbi.nlm.nih.gov/articles/PMC9719130/) · [EGA](https://ega-archive.org/studies/EGAS00001006573) · [GSE139388](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE139388) · [GSE81487](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE81487) |

## 从平台结果到耐药假说

1. **明确配对分母。** 先有治疗时间、既往 TKI、进展部位与取样时间。分别计入治疗前、进展、因其他原因停药及同部位配对。按患者和中心隔离发现集与验证集。
2. **把阴性与不可评价分开。** 每个变异类别保留局部深度或有效分子数、坐标和版本，组织的纯度、倍性及正常样本，血浆的肿瘤分数及位点 LoD。低脱落、CNS/寡进展、面板缺口或低质量先归入不可评价。在可行且临床合适时用进展组织补查。 [ESMO ctDNA](https://doi.org/10.1016/j.annonc.2022.05.520)
3. **做正交验证。** VCF 的转录本、ALT 与相位复核。PURPLE 的基因/片段拷贝数须结合纯度、倍性、片段宽度及实际平台规则。LINX 的融合断点与 RNA 接头核对。MET 记录 FISH 比值/组织拷贝数/血浆拷贝数及单位。保留报告的阴性或无法评估原因。
4. **分解表观与细胞组成。** 独立保存 EPIC/WGBS/原生长读段修饰检测、ATAC、RNA、IHC 的测量值及单位。按样本、病灶、平台匹配，核查批次、肿瘤纯度和细胞成分，跟踪同一候选位点的方向、基线和功能证据。血浆肿瘤分数估算与肿瘤表观标记采用不同的输入字段。
5. **先验证解释，再验证临床效用。** 对不同治疗线和样本类型分别报告可解释率、不可评价率、机制一致性及误报案例。由独立分子肿瘤团队审阅，机制发现和治疗响应分别验证。这里的程序验证采用模拟结果和论文汇总证据，尚未在病例级队列测得性能。
