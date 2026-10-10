"""版本與輸出設定。

管理 Bedrock 輸出版本（geometry/attachable format_version、manifest min_engine_version）
與 Geyser mappings API 版本（v1 / v2 schema 不同）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# Rainbow golden 使用的固定模板版本（位元級對照基準）。
GEOMETRY_FORMAT_VERSION = "1.21.0"
ATTACHABLE_FORMAT_VERSION = "1.21.0"
ANIMATION_FORMAT_VERSION = "1.8.0"
SOUND_DEFINITIONS_FORMAT_VERSION = "1.20.20"
MANIFEST_FORMAT_VERSION = 2


def parse_bedrock_version(text: str) -> List[int]:
    """把 "1.21.0" 這種字串轉成 [1, 21, 0]。"""
    parts: List[int] = []
    for chunk in text.strip().split("."):
        chunk = chunk.strip()
        if chunk == "":
            continue
        parts.append(int(chunk))
    while len(parts) < 3:
        parts.append(0)
    return parts[:3]


@dataclass
class OutputConfig:
    """一次轉換的輸出設定。"""

    bedrock_version: List[int] = field(default_factory=lambda: [1, 21, 0])
    geyser_api: str = "v2"
    render_icons: bool = True
    pack_name: str = "sunrisepack"
    pack_description: str = "Converted by j2b (Java->Bedrock)"

    @property
    def geometry_format_version(self) -> str:
        return GEOMETRY_FORMAT_VERSION

    @property
    def attachable_format_version(self) -> str:
        return ATTACHABLE_FORMAT_VERSION

    @property
    def animation_format_version(self) -> str:
        return ANIMATION_FORMAT_VERSION

    @property
    def sound_definitions_format_version(self) -> str:
        return SOUND_DEFINITIONS_FORMAT_VERSION

    @property
    def mappings_format_version(self) -> int:
        # v2 schema 用 format_version 2（custom_model_data / type:legacy）。
        if self.geyser_api == "v1":
            return 1
        return 2
