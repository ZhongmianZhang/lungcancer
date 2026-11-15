# EGFR结构报告：可复现的单文件离线构建

已生成的文件与下载入口见 [离线报告下载目录](../site/egfr-structure/)。

HTML包含完整正文、30条参考来源、9个实验PDB坐标、3Dmol.js 2.5.5以及CSV/JSON/PDB导出功能。正常阅读和3D交互不请求网络，不需要服务器或其他本地文件；访问论文原文等外部链接时才需要联网。单文件ZIP仅含该HTML。

## 构建

在仓库根目录运行；只需要Python 3标准库，无需联网安装依赖：

~~~bash
python egfr_structure/build_offline_html.py --output site/egfr-structure/EGFR_structure_offline_20261115.html
~~~

同时输出同名ZIP、SHA256SUMS.txt和download_manifest.json。也可使用 --output、--zip-output 指定其他位置。全部文本明确按UTF-8读写，支持Windows路径。

构建时校验PDB和内置查看器的来源哈希、内联JSON的完整往返、HTML内部链接、零外部运行资源，以及ZIP仅含一个且字节一致的HTML。文本中的小于号、大于号、中文和脚本结束标记会安全序列化。

## 浏览器检查

如已安装Playwright及Chromium：

~~~bash
python egfr_structure/tests/verify_offline.py --html site/egfr-structure/EGFR_structure_offline_20261115.html
~~~

测试在离线浏览器中载入复制到独立目录的单个HTML，覆盖9个结构、旋转/缩放/复位、显示、PDB/PNG/CSV/JSON导出、打印快照和手机宽度。云端受管浏览器禁止 file:// 导航，故采用文档API载入同一文件字节，并记录实际方法；未修改浏览器策略。

## 科学与许可

结构和证据边界保留在 report_data.json、structure_manifest.json 及原始 report.html 中。坐标未改造；4LRM作者C800对应标准C797。6JXT/6LUD含结晶工程改造；7TVD并非最常见E746_A750del；5D41并非C797S三突变。

3Dmol.js按BSD-3-Clause分发，版权和第三方声明位于 offline_assets 并嵌入导出的HTML；版本和来源哈希位于 3dmol_provenance.json。这里没有患者特异药敏模型，也不由结构自动生成处方。
