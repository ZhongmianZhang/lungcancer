"""Run the interpreter locally with the Python standard library."""

import argparse
import json
import os
import sys
from tempfile import NamedTemporaryFile
from pathlib import Path

from .adapters import import_tsv, import_vcf
from .engine import assess
from .input import InputError, object_value


def write_report(path, text):
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="解释 ALK 融合 NSCLC 洛拉替尼进展样本的耐药证据")
    parser.add_argument("--case", required=True, type=Path, help="带样本和检测元数据的 JSON")
    parser.add_argument("--findings-tsv", action="append", type=Path, default=[],
                        help="已审阅的 CNV、融合、病理和其他多组学结果，可重复")
    parser.add_argument("--vcf", action="append", nargs=4, default=[],
                        metavar=("SAMPLE_ID", "ASSAY_ID", "TUMOR_COLUMN", "VCF"))
    parser.add_argument("--trust-vcf-read-phasing", action="store_true",
                        help="仅当本批所有 VCF 的 GT/PS 定相已独立确认源于读取分子时启用")
    parser.add_argument("--output", type=Path, default=None, help="UTF-8 JSON，默认标准输出")
    args = parser.parse_args(argv)
    try:
        vcf_targets = [(row[0], row[1]) for row in args.vcf]
        if len(vcf_targets) != len(set(vcf_targets)):
            raise InputError("同一样本和检测只可导入一个 VCF，避免跨文件合并相位")
        if args.output:
            inputs = [args.case, *args.findings_tsv, *(Path(row[3]) for row in args.vcf)]
            if args.output.resolve() in {p.resolve() for p in inputs}:
                raise InputError("输出路径不能覆盖输入文件")
        document = object_value(json.loads(args.case.read_text(encoding="utf-8-sig")), "case")
        imports = [import_tsv(document, path) for path in args.findings_tsv]
        imports.extend(import_vcf(document, sample, assay, tumor, path,
                                  trust_phase=args.trust_vcf_read_phasing)
                       for sample, assay, tumor, path in args.vcf)
        report = assess(document)
        report["imports"] = imports
        result = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output is None:
            sys.stdout.write(result)
        else:
            write_report(args.output, result)
    except (InputError, OSError, ValueError) as error:
        print(f"输入或执行错误：{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
