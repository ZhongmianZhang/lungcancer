# lungcancer：EGFR 突变肺癌耐药研究

本仓库整理 EGFR 突变非小细胞肺癌（NSCLC）接受 EGFR-TKI，尤其奥希替尼治疗后，**15 类重点旁路及下游再激活耐药机制**的生物学、检测、克服策略和研究前景。

**不能将这 15 类解释为经过统一人群验证的“发生率前 15 名”。** MET 扩增是最一致地反复检出的主要旁路；其余事件的频率受治疗线次、取样和检测方法影响，部分仅有病例或临床前证据。

## 阅读入口

- [中文综述：机制、克服方法与未来前景](docs/egfr-bypass-resistance.md)
- [15 类机制证据表（CSV，可下载分析）](docs/evidence-matrix.csv)
- [参考文献、试验登记与核验状态](docs/references.md)
- [范围、证据分级、8 个子智能体分工及局限](docs/methodology.md)

## 版本与核验边界

整理日期：**2026-10-29**。这是基于既有可识别文献整理的**叙述性综述工作稿**，不是完成实时检索的系统综述。此次云环境的代理拒绝访问医学文献及监管网站，未在线复核全文、全部题录或截至整理日的现行说明书；不能把整理日期当成证据检索截止日期。网络限制和待核验项目见[方法说明](docs/methodology.md)。

文中将机制证据与治疗证据分开；研究性双靶向、其他驱动亚型的单药批准、特定地区历史批准记录均有明确边界。药名用于说明证据与研究策略，未提供个体处方或联合剂量。

本仓库为 Markdown/CSV 文档，无安装依赖；GitHub 可直接阅读表格和 Mermaid 图。后续更新应优先补齐原文核验、队列分母和地区现行监管标签。

## RAS–RAF–MEK–ERK 机制判读代码（2026-11-01）

新增研究模块由10个子智能体分工，整理49篇去重记录（47篇核题录并审读摘要、2条会议仅核题录）。程序分别解释通路各节点、证据人群与研究性干预，并保留阴性研究结果。

- [判读模块说明与运行方法](rasmapk/README.md)
- [可离线阅读的证据工作台HTML](site/ras-mapk/index.html)
- [合成示例判读报告HTML](rasmapk/generated/example/result.html)
- [49篇题录的独立实时复核审计](rasmapk/generated/metadata_audit.json)
- [10个子智能体分工记录](rasmapk/research_team.json)

```bash
python3 -m rasmapk analyze --input rasmapk/examples/braf_v600e.json --output rasmapk/generated/example
python3 -m rasmapk build
```

原有交互微环境报告及生成代码见 [TME报告使用指南](TME_REPORT_GUIDE.md)。GitHub文件浏览页显示HTML源码，下载后在浏览器打开；代码推送不等同于启用了GitHub Pages。

原有综述文档和远程提交均予保留。新模块仅为研究与分子肿瘤委员会讨论提供可追溯线索，不是经过临床验证的自动处方工具。

## 组织学转化与EGFR保留（2026-11-02）

8个子智能体研究小细胞、鳞癌、谱系可塑性、克隆来源、取样和治疗证据。32条去重记录中31条核题录并审读摘要，1条仅题录，含实际取得摘要的2026 ASCO研究。**EGFR DNA保留、同源性、功能依赖和临床药敏分别判读。**

- [程序说明与输入契约](lineage/README.md)
- [离线研究工作台HTML](site/lineage/index.html)
- [合成小细胞转化示例报告](lineage/generated/example/result.html)
- [独立实时题录复核](lineage/generated/metadata_audit.json)

```bash
python3 -m lineage analyze --input lineage/examples/sclc_retained_egfr.json --output lineage/generated/example
python3 -m lineage build
```

Firecrawl优先适配器已提供；本次无可用工具和凭据，实际文献核验通过Europe PMC/PubMed/Crossref完成。该研究代码不读取切片、不构建系统发育、不输出个体处方，临床使用需独立验证和专家审查。

## JAK/STAT及上下游机制判读（2026-11-04）

按7个子智能体分工补齐IL6/gp130配体、JAK、STAT3、IFN/其他STAT免疫网络、负反馈、交叉通路和临床/会议证据。39条去重记录均核题录并审读摘要；部分结果及编辑说明另作定点核对。**信号读出、来源/区室、功能依赖和临床药敏分别处理。**

- [代码与输入契约](jakstat/README.md)
- [离线研究工作台HTML](site/jak-stat/index.html)
- [仅有临床读出的合成示例](jakstat/generated/example/result.html)
- [患者匹配模型的合成示例](jakstat/generated/model/result.html)
- [独立题录复核](jakstat/generated/metadata_audit.json)

```bash
python3 -m jakstat analyze --input jakstat/examples/readouts_only.json --output jakstat/generated/example
python3 -m jakstat build
```

pSTAT3/IL6升高、VUS、血液克隆或负调控失活均不会自动映射药物；只有满足完整模型与临床场景门控才列出研究路线，不提供个体处方。Firecrawl优先接口沿用共享适配器，当前无凭据的真实回退保存在检索审计。
