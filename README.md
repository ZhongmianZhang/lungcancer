# lungcancer：EGFR 突变肺癌耐药研究

本仓库整理 EGFR 突变非小细胞肺癌（NSCLC）接受 EGFR-TKI，尤其奥希替尼治疗后，**15 类重点旁路及下游再激活耐药机制**的生物学、检测、克服策略和研究前景。

**不能将这 15 类解释为经过统一人群验证的“发生率前 15 名”。** MET 扩增是最一致地反复检出的主要旁路；其余事件的频率受治疗线次、取样和检测方法影响，部分仅有病例或临床前证据。

## PI3K/AKT/mTOR 耐药研究代码

新增 **Python 3.10+、零运行依赖**的可解释规则工具，面向 EGFR 突变 NSCLC 奥希替尼＋铂/培美治疗后进展的研究性判读。8 个子智能体完成了[节点研究与方法审计](docs/pathway-research/README.md)，代码包含 34 条规则、29 条来源线索及 JSON/CSV 示例。

```bash
python3 -m resistance assess examples/combination_progression.json --format markdown
python3 -m resistance assess examples/csv_context.json --findings-csv examples/findings.csv
python3 -m unittest discover -s tests -v
python3 scripts/check_repository.py
```

输入为人工注释的分子/病理背景，输出候选机制、需要补充的确认、研究性干预方向及逐来源证据用途。工具不读取原始测序数据，不提供处方、剂量或药物获益排序。**未完成临床验证，也未完成近十年文献和国际会议的在线检索核验**：当前文献域名仍被代理拒绝（403）。所有来源均保留未在线核验状态，部分节点仅有背景或模型线索；不把奥希替尼单药后、其他癌种或一线起始策略的证据当成联合进展后的直接证据。

详见[使用说明、输入字段和限制](docs/pathway-research/README.md)、[可复现检索与独立审计](docs/pathway-research/08-evidence-audit.md)、[实际检索运行日志](docs/pathway-research/search-run-2026-10-30.json)。检索目标窗口为 **2016-10-30—2026-10-30**，不代表已完成覆盖到该日期的系统检索。

## 阅读入口

- [中文综述：机制、克服方法与未来前景](docs/egfr-bypass-resistance.md)
- [15 类机制证据表（CSV，可下载分析）](docs/evidence-matrix.csv)
- [参考文献、试验登记与核验状态](docs/references.md)
- [范围、证据分级、8 个子智能体分工及局限](docs/methodology.md)

## 版本与核验边界

整理日期：**2026-10-29**。这是基于既有可识别文献整理的**叙述性综述工作稿**，不是完成实时检索的系统综述。此次云环境的代理拒绝访问医学文献及监管网站，未在线复核全文、全部题录或截至整理日的现行说明书；不能把整理日期当成证据检索截止日期。网络限制和待核验项目见[方法说明](docs/methodology.md)。

文中将机制证据与治疗证据分开；研究性双靶向、其他驱动亚型的单药批准、特定地区历史批准记录均有明确边界。药名用于说明证据与研究策略，未提供个体处方或联合剂量。

原有综述为 Markdown/CSV 文档，GitHub 可直接阅读表格和 Mermaid 图；新增研究工具仅使用 Python 标准库。后续更新应优先补齐原文核验、队列分母和地区现行监管标签。
