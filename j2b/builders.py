"""組裝 geometry.geo.json、attachable、geyser mappings 的高階產生器。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from . import geometry, uv
from .versions import OutputConfig


def model_identifier(namespace: str, path: str) -> str:
    """Bedrock geometry identifier。

    "qualityarmory" + "gun/ak47" -> "geometry.qualityarmory.gun_ak47"。
    """
    flat = path.replace("/", "_")
    return f"geometry.{namespace}.{flat}"


def attachable_identifier(namespace: str, path: str) -> str:
    """attachable 的 identifier = 原始 Java ref，如 "qualityarmory:gun/ak47"。"""
    return f"{namespace}:{path}"


def anim_base(namespace: str, path: str) -> str:
    """動畫命名基底，如 "qualityarmory.gun_ak47"。"""
    flat = path.replace("/", "_")
    return f"{namespace}.{flat}"


def build_geometry(
    identifier: str,
    elements: List[Dict[str, Any]],
    texture_width: int,
    texture_height: int,
    offsets: Optional[Dict[str, Tuple[float, float]]],
    config: OutputConfig,
    uv_scale: Optional[Tuple[float, float]] = None,
) -> Dict[str, Any]:
    """產生一個 geometry.geo.json 的 dict。

    uv_scale: (tex_w/16, tex_h/16)。Java face.uv 永遠 0-16 空間，非 16x16 貼圖需縮放。
    單貼圖時由呼叫端依實際貼圖解析度算；atlas 時位移已含在 offsets，scale 用 (1,1)。
    """
    pivot = geometry.bone_pivot(elements)
    scale = uv_scale if uv_scale is not None else (1.0, 1.0)
    cubes: List[Dict[str, Any]] = []
    for index, element in enumerate(elements):
        cube = geometry.convert_cube(element)
        cube["uv"] = uv.build_cube_uv(element, index, offsets, scale)
        cubes.append(cube)

    return {
        "format_version": config.geometry_format_version,
        "minecraft:geometry": [
            {
                "description": {
                    "identifier": identifier,
                    "visible_bounds_width": 4.0,
                    "visible_bounds_height": 4.0,
                    "visible_bounds_offset": [0.0, 0.75, 0.0],
                    "texture_width": texture_width,
                    "texture_height": texture_height,
                },
                "bones": [
                    {
                        "name": "bone",
                        "binding": "q.item_slot_to_bone_name(context.item_slot)",
                        "pivot": pivot,
                        "cubes": cubes,
                    }
                ],
            }
        ],
    }


def build_attachable(
    namespace: str,
    path: str,
    geometry_id: str,
    texture_path: str,
    config: OutputConfig,
) -> Dict[str, Any]:
    """產生 attachable json。texture_path 不含副檔名，如 "textures/all/texturedmaterials1"。"""
    identifier = attachable_identifier(namespace, path)
    base = anim_base(namespace, path)
    return {
        "format_version": config.attachable_format_version,
        "minecraft:attachable": {
            "description": {
                "identifier": identifier,
                "materials": {
                    "default": "entity_alphatest",
                    "enchanted": "entity_alphatest_glint",
                },
                "textures": {
                    "default": texture_path,
                    "enchanted": "textures/misc/enchanted_item_glint",
                },
                "geometry": {
                    "default": geometry_id,
                },
                "animations": {
                    "third_person": f"animation.{base}.hold_third_person",
                    "first_person": f"animation.{base}.hold_first_person",
                    "head": f"animation.{base}.head",
                },
                "scripts": {
                    "animate": [
                        {
                            "first_person": (
                                "context.is_first_person == 1.0 && "
                                "(context.item_slot == 'main_hand' || "
                                "context.item_slot == 'off_hand')"
                            )
                        },
                        {
                            "third_person": (
                                "context.is_first_person == 0.0 && "
                                "(context.item_slot == 'main_hand' || "
                                "context.item_slot == 'off_hand')"
                            )
                        },
                        {
                            "head": (
                                "context.is_first_person == 0.0 && "
                                "context.item_slot == 'head'"
                            )
                        },
                    ]
                },
                "render_controllers": ["controller.render.item_default"],
            }
        },
    }


def build_item_mappings(
    item_to_entries: Dict[str, List[Dict[str, Any]]],
    config: OutputConfig,
) -> Dict[str, Any]:
    """產生 geyser_item_mappings.json。

    item_to_entries: vanilla_item -> list of entry dicts（已排序）。
    """
    return {
        "format_version": config.mappings_format_version,
        "items": item_to_entries,
    }


def mapping_entry(
    bedrock_identifier: str,
    icon_name: str,
    custom_model_data: int,
) -> Dict[str, Any]:
    """單一 geyser mapping entry（v2 schema）。"""
    return {
        "bedrock_identifier": bedrock_identifier,
        "bedrock_options": {
            "icon": icon_name,
        },
        "custom_model_data": custom_model_data,
        "type": "legacy",
    }
