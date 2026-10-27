#!/usr/bin/env python3
"""Package the existing research report as a general-purpose static website.

This prepares files only; it does not create a Sites project or publish a URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "site")
    parser.add_argument("--archive", type=Path, default=ROOT.parent / "egfr_tme_website.zip")
    parser.add_argument("--source-archive", type=Path, default=ROOT.parent / "lungcancer_tme_report.zip")
    args = parser.parse_args()
    try:
        report = ROOT / "reports/egfr_tme_resistance.html"
        assets = {
            "references.csv": ROOT / "reports/references.csv",
            "report_data.json": ROOT / "reports/report_data.json",
            "evidence_audit.json": ROOT / "reports/evidence_audit.json",
            "research_code.zip": args.source_archive,
        }
        for path in [report, *assets.values()]:
            if not path.is_file():
                raise ValueError(f"Required report artifact is missing: {path}")
        content = report.read_text(encoding="utf-8")
        marker = '      <div class="meta-row">'
        if content.count(marker) != 1:
            raise ValueError("Report hero structure changed; download placement requires review")
        links = '''      <nav class="site-downloads" aria-label="下载研究资料">
        <a class="button" href="./downloads/references.csv" download>下载文献表</a>
        <a class="button secondary" href="./downloads/report_data.json" download>下载机制数据</a>
        <a class="button secondary" href="./downloads/research_code.zip" download>下载报告源码</a>
        <a class="button secondary" href="./downloads/evidence_audit.json" download>查看证据审计</a>
      </nav>
'''
        content = content.replace(marker, links + marker, 1)
        extra_css = '.site-downloads{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 22px}.site-downloads a{text-decoration:none}@media print{.site-downloads{display:none}}'
        content = content.replace("</style>", extra_css + "</style>", 1)
        content = content.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n  <meta name="description" content="EGFR突变肺癌微环境耐药机制研究草稿：免疫细胞、CAF、细胞因子及血管生成的交互图谱、候选文献与证据边界。">', 1)
        output = args.output.resolve()
        downloads = output / "downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        (output / "index.html").write_text(content, encoding="utf-8")
        for name, source in assets.items():
            shutil.copyfile(source, downloads / name)
        data = json.loads(assets["report_data.json"].read_text(encoding="utf-8"))
        manifest = {
            "title": data["meta"]["title"], "entrypoint": "index.html",
            "status": "prepared_not_deployed", "platform": "general_static_files",
            "sites_import_compatibility": "not_verified",
            "counts": data["audit"]["counts"],
            "source_report_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
            "research_status": "文献与JCR期刊排名待核验的研究草稿",
            "files": ["index.html", *["downloads/" + name for name in assets]],
        }
        (output / "site-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.archive, "w", zipfile.ZIP_DEFLATED) as archive:
            for name in manifest["files"] + ["site-manifest.json"]:
                archive.write(output / name, name)
            if archive.testzip() is not None:
                raise ValueError("Website archive integrity check failed")
        print(json.dumps({"status": "prepared_not_deployed", "entrypoint": str(output / "index.html"),
                          "archive": str(args.archive), "files": len(manifest["files"]) + 1}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print("Site build failed: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
