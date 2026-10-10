"""display → animation 轉換。

公式由 golden 樣本以最小二乘 / 幾何推導解出，並在全部 golden 動畫上驗證
（third 106 筆、first 101 筆、head 51 筆，position/rotation 全部 0 誤差）：

third_person (來源 display.thirdperson_righthand):
  position = [-tx,  12.5 + tz, -ty]
  rotation = [ 90,  -rz,       -ry]
  scale    = Java scale 原樣

first_person (來源 display.firstperson_righthand):
  position = [-ty,  12.5 + tz,  tx]
  rotation = [-90 + ry, -rz,    rx]
  scale    = Java scale 原樣

head (來源 display.head):
  position = [-0.655*tx, 0.655*ty + 20, 0.655*tz]
  rotation = [-rx, -ry, rz]
  scale    = 0.655 * Java scale

（t=translation, r=rotation；Java 缺 translation/rotation 視為 [0,0,0]，缺 scale 視為 [1,1,1]。）
"""

from __future__ import annotations

from typing import Any, Dict, List

HEAD_SCALE_FACTOR = 0.655


def _vec3(value: Any, default: float) -> List[float]:
    if value is None:
        return [default, default, default]
    return [float(value[0]), float(value[1]), float(value[2])]


def third_person(display_entry: Dict[str, Any]) -> Dict[str, List[float]]:
    t = _vec3(display_entry.get("translation"), 0.0)
    r = _vec3(display_entry.get("rotation"), 0.0)
    s = _vec3(display_entry.get("scale"), 1.0)
    return {
        "position": [-t[0], 12.5 + t[2], -t[1]],
        "rotation": [90.0, -r[2], -r[1]],
        "scale": s,
    }


def first_person(display_entry: Dict[str, Any]) -> Dict[str, List[float]]:
    t = _vec3(display_entry.get("translation"), 0.0)
    r = _vec3(display_entry.get("rotation"), 0.0)
    s = _vec3(display_entry.get("scale"), 1.0)
    return {
        "position": [-t[1], 12.5 + t[2], t[0]],
        "rotation": [-90.0 + r[1], -r[2], r[0]],
        "scale": s,
    }


def head(display_entry: Dict[str, Any]) -> Dict[str, List[float]]:
    t = _vec3(display_entry.get("translation"), 0.0)
    r = _vec3(display_entry.get("rotation"), 0.0)
    s = _vec3(display_entry.get("scale"), 1.0)
    return {
        "position": [
            -HEAD_SCALE_FACTOR * t[0],
            HEAD_SCALE_FACTOR * t[1] + 20.0,
            HEAD_SCALE_FACTOR * t[2],
        ],
        "rotation": [-r[0], -r[1], r[2]],
        "scale": [HEAD_SCALE_FACTOR * s[i] for i in range(3)],
    }


def build_animation_json(
    anim_base: str,
    display: Dict[str, Any],
    format_version: str,
) -> Dict[str, Any]:
    """產生一個 *.animation.json（含 head / third / first 三個動畫）。

    anim_base 形如 "qualityarmory.gun_ak47"。
    """
    third_src = display.get("thirdperson_righthand", {})
    first_src = display.get("firstperson_righthand", {})
    head_src = display.get("head", {})

    def bone(entry_func, src):
        result = entry_func(src)
        return {
            "loop": True,
            "bones": {
                "bone": {
                    "position": result["position"],
                    "rotation": result["rotation"],
                    "scale": result["scale"],
                }
            },
        }

    animations = {
        f"animation.{anim_base}.head": bone(head, head_src),
        f"animation.{anim_base}.hold_third_person": bone(third_person, third_src),
        f"animation.{anim_base}.hold_first_person": bone(first_person, first_src),
    }
    return {
        "format_version": format_version,
        "animations": animations,
    }
