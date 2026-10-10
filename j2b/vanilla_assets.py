"""Vanilla 資產 fallback 轉換：自訂模型以外的所有資產。

處理類別（逐類 best-effort，未知的寫進 report 不靜默丟失）：
- flat 物品/方塊貼圖覆蓋：assets/minecraft/textures/item|block/*.png -> textures/items|blocks/
- 字體 font：assets/<ns>/font/*.json + textures/font/*.png -> font/（Bedrock glyph atlas）
- GUI/HUD：assets/minecraft/textures/gui/** -> textures/ui/**
- lang 語言檔：assets/<ns>/lang/*.json -> texts/*.lang
- 音效：assets/minecraft/sounds.json + sounds/*.ogg -> sounds/sound_definitions.json + sounds/

這些是「與 Java 盡量一致」的 best-effort 路徑重映射，非位元級。
"""

from __future__ import annotations

import json
import os
import shutil
from typing import Dict, List

from .report import Report


# Java 貼圖資料夾 -> Bedrock 貼圖資料夾（最常見對照；其餘歸類到 report）。
_TEXTURE_DIR_MAP = {
    "item": "items",
    "items": "items",
    "block": "blocks",
    "blocks": "blocks",
    "gui": "ui",
    "entity": "entity",
    "particle": "particle",
    "environment": "environment",
    "painting": "painting",
}


def _copy(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy(src, dst)


def convert_all(assets_root: str, pack_out: str, report: Report) -> None:
    _convert_flat_textures(assets_root, pack_out, report)
    _convert_lang(assets_root, pack_out, report)
    _convert_font(assets_root, pack_out, report)
    _convert_sounds(assets_root, pack_out, report)


def _convert_flat_textures(assets_root: str, pack_out: str, report: Report) -> None:
    """複製 minecraft 命名空間的 vanilla 2D 貼圖到 Bedrock 對應路徑。

    僅處理 minecraft 命名空間（原版覆蓋）；自訂命名空間的貼圖已由 convert.py
    的模型流程處理，避免重複。
    """
    mc_tex = os.path.join(assets_root, "minecraft", "textures")
    if not os.path.isdir(mc_tex):
        return
    copied = 0
    for category in sorted(os.listdir(mc_tex)):
        src_dir = os.path.join(mc_tex, category)
        if not os.path.isdir(src_dir):
            continue
        bedrock_cat = _TEXTURE_DIR_MAP.get(category)
        if bedrock_cat is None:
            report.warnings.append(f"vanilla 貼圖類別未對照，略過：textures/{category}")
            continue
        for root, _dirs, files in os.walk(src_dir):
            for name in files:
                if not name.lower().endswith(".png"):
                    continue
                rel = os.path.relpath(os.path.join(root, name), src_dir)
                dst = os.path.join(pack_out, "textures", bedrock_cat, rel)
                _copy(os.path.join(root, name), dst)
                copied += 1
    report.stats["vanilla_textures_copied"] = copied


def _convert_lang(assets_root: str, pack_out: str, report: Report) -> None:
    """Java lang/*.json -> Bedrock texts/*.lang（key=value 純文字）。

    Java 語系碼 en_us -> Bedrock en_US（地區碼大寫）。
    """
    converted = 0
    for namespace in sorted(os.listdir(assets_root)):
        lang_dir = os.path.join(assets_root, namespace, "lang")
        if not os.path.isdir(lang_dir):
            continue
        for name in sorted(os.listdir(lang_dir)):
            if not name.endswith(".json"):
                continue
            src = os.path.join(lang_dir, name)
            try:
                with open(src, encoding="utf-8") as handle:
                    data = json.load(handle)
            except (json.JSONDecodeError, OSError):
                report.warnings.append(f"lang 解析失敗：{namespace}/lang/{name}")
                continue
            code = os.path.splitext(name)[0]
            bedrock_code = _bedrock_lang_code(code)
            lines = [f"{key}={value}" for key, value in data.items()]
            dst = os.path.join(pack_out, "texts", f"{bedrock_code}.lang")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with open(dst, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            converted += 1
    if converted:
        report.stats["lang_files_converted"] = converted


def _bedrock_lang_code(java_code: str) -> str:
    """en_us -> en_US；zh_tw -> zh_TW。"""
    if "_" in java_code:
        lang, region = java_code.split("_", 1)
        return f"{lang}_{region.upper()}"
    return java_code


def _convert_font(assets_root: str, pack_out: str, report: Report) -> None:
    """字體：複製 textures/font/*.png 到 Bedrock font/ 並記錄需手動對 glyph atlas。

    Bedrock 自訂字體走 font/glyph_E1.png 這類固定 unicode-page atlas（每頁 16x16 格），
    與 Java 的 providers(bitmap/ttf/space) 機制差異大。此處先搬運 bitmap provider 的
    png 並在 report 標明哪些需要人工對 glyph 頁；ttf/space provider 無法自動轉。
    """
    found_any = False
    for namespace in sorted(os.listdir(assets_root)):
        font_tex = os.path.join(assets_root, namespace, "textures", "font")
        font_def = os.path.join(assets_root, namespace, "font")
        if os.path.isdir(font_tex):
            found_any = True
            for name in sorted(os.listdir(font_tex)):
                if name.lower().endswith(".png"):
                    _copy(
                        os.path.join(font_tex, name),
                        os.path.join(pack_out, "font", name),
                    )
            report.warnings.append(
                f"字體 {namespace}/textures/font 已複製，但 Bedrock 需對 glyph_E*.png "
                f"unicode 頁；請確認字元範圍（bitmap provider 可對，ttf/space 無法自動轉）"
            )
        if os.path.isdir(font_def):
            for name in sorted(os.listdir(font_def)):
                if name.endswith(".json"):
                    report.warnings.append(
                        f"字體定義 {namespace}/font/{name} 需人工對 Bedrock glyph 頁（providers 機制不同）"
                    )
    if found_any:
        report.stats["font_handled"] = 1


def _convert_sounds(assets_root: str, pack_out: str, report: Report) -> None:
    """Java sounds.json + sounds/*.ogg -> Bedrock sounds/sound_definitions.json。

    與 build_bedrock_sound_pack.py 同邏輯：每個 event key 映射到 ogg，鍵名保持一致，
    讓 Geyser 的 custom playSound 轉送能在基岩端查到。
    """
    sounds_json = os.path.join(assets_root, "minecraft", "sounds.json")
    sounds_dir = os.path.join(assets_root, "minecraft", "sounds")
    if not os.path.isfile(sounds_json) or not os.path.isdir(sounds_dir):
        return
    try:
        with open(sounds_json, encoding="utf-8") as handle:
            events = json.load(handle)
    except (json.JSONDecodeError, OSError):
        report.warnings.append("sounds.json 解析失敗，略過音效")
        return

    definitions: Dict[str, dict] = {}
    copied = 0
    for event_key, spec in events.items():
        names: List[str] = []
        for sound in spec.get("sounds", []):
            filename = (sound if isinstance(sound, str) else sound.get("name", "")).split(":")[-1]
            ogg = os.path.join(sounds_dir, filename + ".ogg")
            if os.path.exists(ogg):
                dst = os.path.join(pack_out, "sounds", "custom", filename + ".ogg")
                if not os.path.exists(dst):
                    _copy(ogg, dst)
                    copied += 1
                names.append(f"sounds/custom/{filename}")
        if names:
            is_music = "music" in event_key or "record" in event_key
            definitions[event_key] = {
                "category": "music" if is_music else "neutral",
                "min_distance": 0.0,
                "max_distance": 9999.0 if is_music else 64.0,
                "sounds": names,
            }

    if definitions:
        out = {"format_version": "1.14.0", "sound_definitions": definitions}
        dst = os.path.join(pack_out, "sounds", "sound_definitions.json")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "w", encoding="utf-8") as handle:
            json.dump(out, handle, ensure_ascii=False, indent=1)
        report.stats["sound_events"] = len(definitions)
        report.stats["sound_files_copied"] = copied
