"""j2b CLI：python -m j2b convert <pack> -o <out> [選項]。"""

from __future__ import annotations

import argparse
import sys

from .convert import convert_pack
from .versions import OutputConfig, parse_bedrock_version


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="j2b",
        description="Minecraft Java 版材質包 -> Bedrock 版 + Geyser custom item mappings 轉換器",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    conv = sub.add_parser("convert", help="轉換一個 Java 材質包")
    conv.add_argument("pack", help="Java 材質包目錄（含 assets/ 或 assets/ 本身）")
    conv.add_argument("-o", "--out", required=True, help="輸出目錄")
    conv.add_argument("--bedrock-version", default="1.21.0", help="Bedrock min_engine_version（預設 1.21.0）")
    conv.add_argument("--geyser-api", default="v2", choices=["v1", "v2"], help="Geyser mappings API 版本")
    conv.add_argument("--no-icons", action="store_true", help="略過 GUI icon 3D 渲染")
    conv.add_argument("--pack-name", default="sunrisepack", help="Bedrock pack 名稱")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "convert":
        config = OutputConfig(
            bedrock_version=parse_bedrock_version(args.bedrock_version),
            geyser_api=args.geyser_api,
            render_icons=not args.no_icons,
            pack_name=args.pack_name,
        )
        report = convert_pack(args.pack, args.out, config)
        print(f"[j2b] 轉換完成：{report.stats.get('converted', 0)} 物品")
        print(f"[j2b] 略過 {report.stats.get('skipped', 0)}，警告 {len(report.warnings)}")
        print(f"[j2b] icon 渲染 {report.stats.get('icons_rendered', 0)}/{report.stats.get('icons_requested', 0)}")
        print(f"[j2b] 報告：{args.out}/report.txt")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
