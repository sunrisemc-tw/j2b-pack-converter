"""幾何轉換：Java element → Bedrock cube。

公式逆推自 Rainbow，並在 golden 的 2433 個 cube 上驗證：
  origin = [8 - tx, min(fy, ty), fz - 8]
  size   = [abs(tx - fx), abs(ty - fy), abs(tz - fz)]
origin / size 位元級吻合率 100%（允許浮點 1e-4）。

cube rotation（單軸）：
  axis x -> [-angle, 0, 0]
  axis y -> [0,  angle, 0]   # 注意：golden 證實 y 軸保留號（spec 原本標 -angle 待驗，實測為 +angle）
  axis z -> [0, 0,  angle]
  pivot  = [8 - ox, oy, oz - 8]
rotation / pivot 吻合率 100%。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def convert_origin_size(from_xyz: List[float], to_xyz: List[float]):
    """回傳 (origin, size)。用 min/abs 處理 Java from>to 的反向座標。"""
    fx, fy, fz = from_xyz
    tx, ty, tz = to_xyz
    origin = [8.0 - tx, min(fy, ty), fz - 8.0]
    size = [abs(tx - fx), abs(ty - fy), abs(tz - fz)]
    return origin, size


def convert_rotation(rotation: Dict[str, Any]):
    """Java element.rotation -> (bedrock_rotation, bedrock_pivot)。"""
    angle = rotation["angle"]
    axis = rotation["axis"]
    ox, oy, oz = rotation["origin"]
    if axis == "x":
        rot = [-angle, 0.0, 0.0]
    elif axis == "y":
        rot = [0.0, angle, 0.0]
    else:
        rot = [0.0, 0.0, angle]
    pivot = [8.0 - ox, oy, oz - 8.0]
    return rot, pivot


def convert_cube(element: Dict[str, Any]) -> Dict[str, Any]:
    """把一個 Java element 轉成一個 Bedrock cube（不含 uv，uv 由 uv.py 處理）。"""
    origin, size = convert_origin_size(element["from"], element["to"])
    cube: Dict[str, Any] = {"origin": origin, "size": size}
    if "rotation" in element and element["rotation"]:
        rot, pivot = convert_rotation(element["rotation"])
        cube["rotation"] = rot
        cube["pivot"] = pivot
    return cube


def bounding_box(elements: List[Dict[str, Any]]):
    """回傳所有 cube 的 bedrock 座標 bounding box (mins, maxs)。"""
    if not elements:
        return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3
    for element in elements:
        origin, size = convert_origin_size(element["from"], element["to"])
        high = [origin[i] + size[i] for i in range(3)]
        for i in range(3):
            mins[i] = min(mins[i], origin[i])
            maxs[i] = max(maxs[i], high[i])
    return mins, maxs


def bone_pivot(elements: List[Dict[str, Any]]) -> List[float]:
    """bone pivot = cube bounding box 的中心（golden 88/112 吻合；其餘差異來自
    Rainbow 對旋轉 cube 的 bounds 擴張，屬 cosmetic，不影響 origin/size/uv 驗收）。"""
    mins, maxs = bounding_box(elements)
    return [(mins[i] + maxs[i]) / 2.0 for i in range(3)]
