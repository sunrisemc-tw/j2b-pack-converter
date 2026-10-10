"""Java 材質包解析：CMD 對照表（新/舊格式）+ 模型載入。

跨版本輸入：
  新格式 (1.21.4+): assets/<ns>/items/<item>.json，model.type=range_dispatch，
                    property=custom_model_data，entries[].threshold = CMD int。
  舊格式 (<=1.21.3): assets/minecraft/models/item/<item>.json，
                    overrides[].predicate.custom_model_data + overrides[].model。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class CmdEntry:
    """一個自訂物品：由某個 vanilla item 的某個 custom_model_data 觸發。"""

    vanilla_item: str       # 如 "minecraft:crossbow"
    custom_model_data: int  # 如 4
    model_ref: str          # 如 "qualityarmory:gun/ak47"


@dataclass
class JavaModel:
    """解析後的 Java 模型（已 resolve 命名空間與路徑）。"""

    ref: str                       # "qualityarmory:gun/ak47"
    namespace: str                 # "qualityarmory"
    path: str                      # "gun/ak47"
    data: Dict[str, Any]           # 原始 json
    elements: List[Dict[str, Any]]
    textures: Dict[str, str]
    display: Dict[str, Any]


def _read_json(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def normalize_ref(ref: str) -> str:
    """確保 model ref 帶命名空間；"item/quartz" -> "minecraft:item/quartz"。"""
    if ":" not in ref:
        return f"minecraft:{ref}"
    return ref


def ref_to_path_parts(ref: str):
    """"qualityarmory:gun/ak47" -> ("qualityarmory", "gun/ak47")。"""
    ref = normalize_ref(ref)
    namespace, path = ref.split(":", 1)
    # 模型 ref 可能帶 "item/" 前綴（flat item），也可能是純粹 "gun/ak47"。
    return namespace, path


def find_assets_root(pack_dir: str) -> str:
    """找 assets/ 目錄（允許 pack_dir 本身或其下）。"""
    candidate = os.path.join(pack_dir, "assets")
    if os.path.isdir(candidate):
        return candidate
    if os.path.basename(pack_dir.rstrip("/")) == "assets" and os.path.isdir(pack_dir):
        return pack_dir
    return candidate


def parse_cmd_entries_new_format(items_dir: str, vanilla_item_file: str) -> List[CmdEntry]:
    """解析一個新格式 items/<item>.json，回傳其 CMD entries。"""
    path = os.path.join(items_dir, vanilla_item_file)
    data = _read_json(path)
    item_name = os.path.splitext(vanilla_item_file)[0]
    vanilla_item = f"minecraft:{item_name}"
    entries: List[CmdEntry] = []
    model = data.get("model", {})
    found = _collect_range_dispatch_entries(model)
    for threshold, model_ref in found:
        entries.append(
            CmdEntry(
                vanilla_item=vanilla_item,
                custom_model_data=int(threshold),
                model_ref=normalize_ref(model_ref),
            )
        )
    return entries


def _collect_range_dispatch_entries(node: Any) -> List[Any]:
    """遞迴找出所有 custom_model_data range_dispatch 的 entries。

    新格式有時把真正的 CMD dispatch 包在 fallback 的巢狀結構裡（如 crossbow），
    因此遞迴搜尋所有 property=custom_model_data 的 range_dispatch 節點。
    """
    results: List[Any] = []
    if isinstance(node, dict):
        is_cmd_dispatch = (
            node.get("type", "").endswith("range_dispatch")
            and node.get("property", "").endswith("custom_model_data")
        )
        if is_cmd_dispatch:
            for entry in node.get("entries", []):
                threshold = entry.get("threshold")
                model_ref = _extract_model_ref(entry.get("model", {}))
                if threshold is not None and model_ref:
                    results.append((threshold, model_ref))
        # 仍遞迴進子節點（fallback 可能另含巢狀 dispatch，但 CMD dispatch 通常只有一層）。
        for value in node.values():
            results.extend(_collect_range_dispatch_entries(value))
    elif isinstance(node, list):
        for value in node:
            results.extend(_collect_range_dispatch_entries(value))
    return results


def _extract_model_ref(model_node: Any) -> Optional[str]:
    """從 model 節點取出 model 字串 ref。"""
    if isinstance(model_node, dict):
        ref = model_node.get("model")
        if isinstance(ref, str):
            return ref
    return None


def parse_cmd_entries_old_format(models_item_dir: str, vanilla_item_file: str) -> List[CmdEntry]:
    """解析舊格式 models/item/<item>.json 的 overrides[] predicate.custom_model_data。"""
    path = os.path.join(models_item_dir, vanilla_item_file)
    data = _read_json(path)
    item_name = os.path.splitext(vanilla_item_file)[0]
    vanilla_item = f"minecraft:{item_name}"
    entries: List[CmdEntry] = []
    for override in data.get("overrides", []):
        predicate = override.get("predicate", {})
        cmd = predicate.get("custom_model_data")
        model_ref = override.get("model")
        if cmd is None or not model_ref:
            continue
        entries.append(
            CmdEntry(
                vanilla_item=vanilla_item,
                custom_model_data=int(cmd),
                model_ref=normalize_ref(model_ref),
            )
        )
    return entries


def discover_cmd_entries(assets_root: str) -> List[CmdEntry]:
    """掃描整個 pack，收集所有 CMD entries（新 + 舊格式都支援）。"""
    entries: List[CmdEntry] = []
    seen = set()

    # 新格式：assets/<ns>/items/*.json
    for namespace in sorted(os.listdir(assets_root)):
        items_dir = os.path.join(assets_root, namespace, "items")
        if not os.path.isdir(items_dir):
            continue
        for filename in sorted(os.listdir(items_dir)):
            if not filename.endswith(".json"):
                continue
            for entry in parse_cmd_entries_new_format(items_dir, filename):
                key = (entry.vanilla_item, entry.custom_model_data)
                if key not in seen:
                    seen.add(key)
                    entries.append(entry)

    # 舊格式：assets/minecraft/models/item/*.json 的 overrides[]
    models_item_dir = os.path.join(assets_root, "minecraft", "models", "item")
    if os.path.isdir(models_item_dir):
        for filename in sorted(os.listdir(models_item_dir)):
            if not filename.endswith(".json"):
                continue
            try:
                old_entries = parse_cmd_entries_old_format(models_item_dir, filename)
            except (json.JSONDecodeError, KeyError):
                continue
            for entry in old_entries:
                key = (entry.vanilla_item, entry.custom_model_data)
                if key not in seen:
                    seen.add(key)
                    entries.append(entry)

    return entries


def load_model(assets_root: str, ref: str) -> Optional[JavaModel]:
    """載入並 resolve 一個 Java 模型（處理 parent，但本專案資產多為自含 elements）。"""
    namespace, path = ref_to_path_parts(ref)
    model_path = os.path.join(assets_root, namespace, "models", path + ".json")
    if not os.path.exists(model_path):
        return None
    data = _read_json(model_path)
    elements = list(data.get("elements", []))
    textures = dict(data.get("textures", {}))
    display = dict(data.get("display", {}))

    # 若無 elements 但有 parent，往上合併（簡化：只合併 elements/textures/display）。
    parent_ref = data.get("parent")
    guard = 0
    while not elements and parent_ref and guard < 8:
        guard += 1
        parent_ref_norm = normalize_ref(parent_ref)
        p_ns, p_path = ref_to_path_parts(parent_ref_norm)
        parent_path = os.path.join(assets_root, p_ns, "models", p_path + ".json")
        if not os.path.exists(parent_path):
            break
        parent_data = _read_json(parent_path)
        elements = list(parent_data.get("elements", []))
        merged_tex = dict(parent_data.get("textures", {}))
        merged_tex.update(textures)
        textures = merged_tex
        if not display:
            display = dict(parent_data.get("display", {}))
        parent_ref = parent_data.get("parent")

    return JavaModel(
        ref=normalize_ref(ref),
        namespace=namespace,
        path=path,
        data=data,
        elements=elements,
        textures=textures,
        display=display,
    )
