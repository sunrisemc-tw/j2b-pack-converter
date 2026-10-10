"""轉換報告：記錄未轉/部分轉的資產，避免靜默丟失。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Report:
    """收集轉換過程中的統計與未處理項目，最後寫成 report.txt。"""

    converted_items: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: Dict[str, int] = field(default_factory=dict)

    def add_converted(self, name: str) -> None:
        self.converted_items.append(name)

    def add_skipped(self, path: str, reason: str) -> None:
        self.skipped.append(f"{path}  —  {reason}")

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def bump(self, key: str, amount: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + amount

    def write(self, out_dir: str) -> str:
        path = os.path.join(out_dir, "report.txt")
        lines: List[str] = []
        lines.append("# j2b 轉換報告")
        lines.append("")
        lines.append("## 統計")
        for key in sorted(self.stats):
            lines.append(f"- {key}: {self.stats[key]}")
        lines.append("")
        lines.append(f"## 已轉換自訂物品（{len(self.converted_items)}）")
        for name in sorted(self.converted_items):
            lines.append(f"- {name}")
        lines.append("")
        lines.append(f"## 警告（{len(self.warnings)}）")
        for message in self.warnings:
            lines.append(f"- {message}")
        lines.append("")
        lines.append(f"## 未轉換 / 需人工檢查（{len(self.skipped)}）")
        for entry in self.skipped:
            lines.append(f"- {entry}")
        lines.append("")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
        return path
