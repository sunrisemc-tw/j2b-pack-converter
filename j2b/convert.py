"""轉換主流程：把一個 Java 材質包轉成 Bedrock pack + Geyser mappings。

輸出結構：
  <out>/pack/manifest.json
  <out>/pack/models/entity/geometry.<ns>.<path>.geo.json
  <out>/pack/attachables/<ns>.<path>.json
  <out>/pack/animations/<ns>.<path>.animation.json
  <out>/pack/textures/...（貼圖，含多貼圖 atlas 的 _stitched.png）
  <out>/pack/textures/item_texture.json
  <out>/pack/sounds/sound_definitions.json（若有音效）
  <out>/custom_mappings/geyser_item_mappings.json
  <out>/report.txt
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from . import builders, parser, textures, animation
from .report import Report
from .versions import OutputConfig


def _write_json(path: str, data: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)


def _custom_namespace(namespace: str) -> str:
    """Bedrock 自訂 item ID 不允許使用保留的 minecraft namespace。"""
    return "sunrise" if namespace == "minecraft" else namespace


def _bedrock_item_id(namespace: str, path: str) -> str:
    return f"{_custom_namespace(namespace)}:{path}"


def _icon_name(namespace: str, path: str) -> str:
    """icon 識別名：qualityarmory + gun/ak47 -> qualityarmory.gun_ak47_icon。"""
    flat = path.replace("/", "_")
    return f"{_custom_namespace(namespace)}.{flat}_icon"


def _icon_rel(namespace: str, path: str) -> str:
    """icon 貼圖相對路徑（不含副檔名），依類別分資料夾。"""
    flat = path.replace("/", "_")
    # path 形如 gun/ak47 -> 類別 gun；無斜線則歸 item
    category = path.split("/")[0] if "/" in path else "item"
    leaf = path.split("/")[-1]
    return f"textures/{category}/{leaf}_icon"


def convert_pack(pack_dir: str, out_dir: str, config: OutputConfig) -> Report:
    report = Report()
    assets_root = parser.find_assets_root(pack_dir)
    pack_out = os.path.join(out_dir, "pack")
    os.makedirs(pack_out, exist_ok=True)

    cmd_entries = parser.discover_cmd_entries(assets_root)
    report.stats["cmd_entries_found"] = len(cmd_entries)

    # vanilla_item -> list of geyser mapping entries
    item_to_entries: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    # item_texture.json 的 texture_data
    item_texture_data: Dict[str, Dict[str, str]] = {}
    # 要渲染的 icon 清單：(icon_name, icon_rel, JavaModel, texture_abs_or_atlas)
    icon_jobs: List[Tuple[str, str, parser.JavaModel, Optional[str]]] = []

    for entry in cmd_entries:
        model = parser.load_model(assets_root, entry.model_ref)
        if model is None:
            report.skipped.append(f"{entry.model_ref} (CMD {entry.custom_model_data}): 找不到模型檔")
            continue

        # 2D sprite 物品：無 elements 但有 layer0 貼圖（parent=item/generated）。
        # golden 證實這類也要收：直接 mapping + 平面 icon，不產 geo/attachable/animation。
        if not model.elements:
            layer0 = model.textures.get("layer0") or model.textures.get("0")
            if layer0:
                icon_name = _icon_name(model.namespace, model.path)
                icon_rel = _icon_rel(model.namespace, model.path)
                abs_tex = textures.find_texture_file(assets_root, layer0)
                if abs_tex and os.path.exists(abs_tex):
                    dst = os.path.join(pack_out, icon_rel + ".png")
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy(abs_tex, dst)
                bedrock_id = _bedrock_item_id(model.namespace, model.path)
                item_to_entries[entry.vanilla_item].append(
                    builders.mapping_entry(bedrock_id, icon_name, entry.custom_model_data)
                )
                item_texture_data[icon_name] = {"textures": icon_rel}
                report.converted_items.append(
                    f"{entry.vanilla_item} CMD{entry.custom_model_data} -> {entry.model_ref} (2D sprite)"
                )
                report.stats["sprite_items"] = report.stats.get("sprite_items", 0) + 1
                continue
            report.skipped.append(f"{entry.model_ref} (CMD {entry.custom_model_data}): 無 elements 且無 layer0")
            continue

        output_namespace = _custom_namespace(model.namespace)
        geo_id = builders.model_identifier(output_namespace, model.path)
        anim_base = builders.anim_base(output_namespace, model.path)

        # --- 貼圖：收集 model 用到的 texkey -> 檔案，決定單貼圖 or atlas ---
        texkeys = textures.used_texkeys(model.elements)
        tile_paths: List[Tuple[str, str]] = []
        for tk in texkeys:
            tex_ref = model.textures.get(tk) or model.textures.get(tk.lstrip("#"))
            if not tex_ref:
                continue
            abs_tex = textures.find_texture_file(assets_root, tex_ref)
            if abs_tex and os.path.exists(abs_tex):
                tile_paths.append((tk, abs_tex))

        offsets = None
        texture_width, texture_height = 16, 16
        uv_scale: Tuple[float, float] = (1.0, 1.0)
        if len(tile_paths) == 1:
            # 單貼圖：直接複製
            tk, abs_tex = tile_paths[0]
            tex_ref = model.textures.get(tk) or model.textures.get(tk.lstrip("#")) or ""
            bedrock_rel = textures.bedrock_texture_path(tex_ref)  # textures/all/xxx
            dst = os.path.join(pack_out, bedrock_rel + ".png")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if not os.path.exists(dst):
                shutil.copy(abs_tex, dst)
            default_texture = bedrock_rel
            try:
                texture_width, texture_height = textures.image_size(abs_tex)
            except Exception:
                pass
            # Java face.uv 永遠 0-16；非 16x16 貼圖需把 UV 乘上 tex/16。
            uv_scale = (texture_width / 16.0, texture_height / 16.0)
        elif len(tile_paths) >= 2:
            # 多貼圖：atlas 拼接（位移已是 Bedrock 像素空間；uv_scale 保持 1,1 由 offset 處理）
            stitched_rel = f"textures/{model.path.split('/')[0]}/{model.path.split('/')[-1]}_stitched"
            dst = os.path.join(pack_out, stitched_rel + ".png")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            atlas_img, offsets, (texture_width, texture_height) = textures.stitch_atlas(tile_paths)
            atlas_img.save(dst)
            default_texture = stitched_rel
        else:
            report.warnings.append(f"{entry.model_ref}: 找不到任何貼圖，用 fallback")
            default_texture = "textures/misc/missing"

        # --- geometry ---
        geo = builders.build_geometry(
            geo_id, model.elements, texture_width, texture_height, offsets, config, uv_scale
        )
        _write_json(
            os.path.join(pack_out, "models", "entity", f"geometry.{anim_base}.geo.json"),
            geo,
        )

        # --- attachable ---
        att = builders.build_attachable(
            output_namespace, model.path, geo_id, default_texture, config
        )
        _write_json(
            os.path.join(pack_out, "attachables", f"{anim_base}.json"),
            att,
        )

        # --- animation ---
        anim = animation.build_animation_json(
            anim_base, model.display, config.animation_format_version
        )
        _write_json(
            os.path.join(pack_out, "animations", f"{anim_base}.animation.json"),
            anim,
        )

        # --- mapping + icon ---
        icon_name = _icon_name(model.namespace, model.path)
        icon_rel = _icon_rel(model.namespace, model.path)
        bedrock_id = _bedrock_item_id(model.namespace, model.path)
        item_to_entries[entry.vanilla_item].append(
            builders.mapping_entry(bedrock_id, icon_name, entry.custom_model_data)
        )
        item_texture_data[icon_name] = {"textures": icon_rel}
        icon_abs = tile_paths[0][1] if tile_paths else None
        icon_jobs.append((icon_name, icon_rel, model, icon_abs))

        report.converted_items.append(f"{entry.vanilla_item} CMD{entry.custom_model_data} -> {entry.model_ref}")

    # --- geyser mappings ---
    for item in item_to_entries:
        item_to_entries[item].sort(key=lambda e: e["custom_model_data"])
    mappings = builders.build_item_mappings(dict(item_to_entries), config)
    _write_json(os.path.join(out_dir, "custom_mappings", "geyser_item_mappings.json"), mappings)

    # --- item_texture.json ---
    _write_json(
        os.path.join(pack_out, "textures", "item_texture.json"),
        {"resource_pack_name": config.pack_name, "texture_name": "atlas.items", "texture_data": item_texture_data},
    )

    # --- manifest ---
    _write_json(os.path.join(pack_out, "manifest.json"), _build_manifest(config))

    # --- icons（可選，moderngl 離屏渲染）---
    report.stats["icons_requested"] = len(icon_jobs)
    if config.render_icons:
        try:
            from . import icon_render
            rendered = icon_render.render_all(icon_jobs, pack_out, assets_root)
            report.stats["icons_rendered"] = rendered
        except Exception as exc:  # 渲染失敗不應中斷整個轉換
            report.warnings.append(f"icon 渲染略過：{exc}")
            report.stats["icons_rendered"] = 0
    else:
        report.stats["icons_rendered"] = 0

    # --- vanilla 資產 fallback（貼圖/字體/gui/lang/sound）---
    try:
        from . import vanilla_assets
        vanilla_assets.convert_all(assets_root, pack_out, report)
    except Exception as exc:
        report.warnings.append(f"vanilla 資產轉換略過：{exc}")

    report.stats["converted"] = len(report.converted_items)
    report.stats["skipped"] = len(report.skipped)
    _write_report(os.path.join(out_dir, "report.txt"), report)
    return report


def _build_manifest(config: OutputConfig) -> Dict[str, Any]:
    return {
        "format_version": 2,
        "header": {
            "name": config.pack_name,
            "description": config.pack_description,
            "uuid": str(uuid.uuid4()),
            "version": [1, 0, 0],
            "min_engine_version": config.bedrock_version,
        },
        "modules": [
            {
                "type": "resources",
                "uuid": str(uuid.uuid4()),
                "version": [1, 0, 0],
            }
        ],
    }


def _write_report(path: str, report: Report) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines: List[str] = ["# j2b 轉換報告", ""]
    lines.append("## 統計")
    for key, value in report.stats.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append(f"## 已轉換 ({len(report.converted_items)})")
    lines.extend(report.converted_items)
    lines.append("")
    lines.append(f"## 略過 ({len(report.skipped)})")
    lines.extend(report.skipped)
    lines.append("")
    lines.append(f"## 警告 ({len(report.warnings)})")
    lines.extend(report.warnings)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
