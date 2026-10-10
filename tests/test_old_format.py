"""跨版本：舊格式（<=1.21.3 models/item/*.json overrides[]）CMD 解析測試。"""

from __future__ import annotations

import json
import os

from j2b import parser


def _make_old_format_pack(root):
    """造一個最小舊格式 pack：diamond_sword 用 overrides predicate.custom_model_data。"""
    assets = os.path.join(root, "assets")
    mc_item = os.path.join(assets, "minecraft", "models", "item")
    os.makedirs(mc_item, exist_ok=True)
    sword = {
        "parent": "item/handheld",
        "textures": {"layer0": "item/diamond_sword"},
        "overrides": [
            {"predicate": {"custom_model_data": 1}, "model": "myns:custom/blade1"},
            {"predicate": {"custom_model_data": 2}, "model": "myns:custom/blade2"},
        ],
    }
    with open(os.path.join(mc_item, "diamond_sword.json"), "w", encoding="utf-8") as handle:
        json.dump(sword, handle)
    # 自訂模型本體（含 elements）
    model_dir = os.path.join(assets, "myns", "models", "custom")
    os.makedirs(model_dir, exist_ok=True)
    blade = {
        "textures": {"0": "myns:custom/blade"},
        "elements": [
            {
                "from": [7, 0, 7],
                "to": [9, 16, 9],
                "faces": {
                    "north": {"uv": [0, 0, 2, 16], "texture": "#0"},
                    "up": {"uv": [0, 0, 2, 2], "texture": "#0"},
                },
            }
        ],
        "display": {"gui": {"rotation": [0, 90, 0]}},
    }
    for name in ("blade1", "blade2"):
        with open(os.path.join(model_dir, name + ".json"), "w", encoding="utf-8") as handle:
            json.dump(blade, handle)
    return assets


def test_old_format_overrides_parsed(tmp_path):
    assets = _make_old_format_pack(str(tmp_path))
    entries = parser.discover_cmd_entries(assets)
    by_cmd = {e.custom_model_data: e for e in entries}
    assert 1 in by_cmd and 2 in by_cmd, f"舊格式 overrides 未解析: {entries}"
    assert by_cmd[1].vanilla_item == "minecraft:diamond_sword"
    assert by_cmd[1].model_ref == "myns:custom/blade1"
    assert by_cmd[2].model_ref == "myns:custom/blade2"


def test_old_format_model_loads(tmp_path):
    assets = _make_old_format_pack(str(tmp_path))
    model = parser.load_model(assets, "myns:custom/blade1")
    assert model is not None
    assert len(model.elements) == 1
    assert model.elements[0]["from"] == [7, 0, 7]
