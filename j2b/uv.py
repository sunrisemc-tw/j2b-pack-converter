"""UV 轉換：Java face.uv=[x1,y1,x2,y2] → Bedrock per-face uv + uv_size。

逆推自 Rainbow，golden 單貼圖 cube 位元級吻合：
  一般面 (north/south/east/west): uv=[x1,y1]  uv_size=[x2-x1, y2-y1]
  up / down 面:                   uv=[x2,y2]  uv_size=[-(x2-x1), -(y2-y1)]   # 負向翻轉
多貼圖 atlas：再加上該 texkey 在 atlas 中的 (offset_x, offset_y)。
每面一個 material_instance = "#<texkey>_<face>_<cube_index>"（如 #1_north_0）。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Bedrock cube 的 6 面；Rainbow 固定以此順序輸出。
FACE_ORDER = ["south", "north", "east", "west", "down", "up"]
FLIP_FACES = {"up", "down"}


def convert_face_uv(
    java_uv: List[float],
    face: str,
    offset: Tuple[float, float] = (0.0, 0.0),
    scale: Tuple[float, float] = (1.0, 1.0),
):
    """回傳 (uv, uv_size)。

    offset 為 atlas 拼接位移（Bedrock 像素空間）。
    scale 為 (texture_width/16, texture_height/16)：Java 的 face.uv 永遠在 0-16 空間，
    與貼圖實際解析度無關；Bedrock uv 用實際像素座標，故需乘 scale（16x16 時 scale=1）。
    """
    x1, y1, x2, y2 = java_uv
    sx, sy = scale
    ox, oy = offset
    x1, x2 = x1 * sx, x2 * sx
    y1, y2 = y1 * sy, y2 * sy
    if face in FLIP_FACES:
        uv = [x2 + ox, y2 + oy]
        uv_size = [-(x2 - x1), -(y2 - y1)]
    else:
        uv = [x1 + ox, y1 + oy]
        uv_size = [x2 - x1, y2 - y1]
    return uv, uv_size


def texkey_of(texture_ref: str) -> str:
    """"#1" -> "1"；"#0" -> "0"。"""
    return texture_ref.lstrip("#")


def build_cube_uv(
    element: Dict[str, Any],
    cube_index: int,
    offsets: Optional[Dict[str, Tuple[float, float]]] = None,
    scale: Tuple[float, float] = (1.0, 1.0),
) -> Dict[str, Any]:
    """為一個 element 建出 Bedrock cube 的 uv 區塊（per-face dict）。

    offsets: texkey -> (ox, oy) 的 atlas 位移表（單貼圖時給 None 或空）。
    scale:   (texture_width/16, texture_height/16)，非 16x16 貼圖需縮放 UV。
    """
    offsets = offsets or {}
    faces = element.get("faces", {})
    uv_block: Dict[str, Any] = {}
    for face in FACE_ORDER:
        if face not in faces:
            continue
        face_data = faces[face]
        java_uv = face_data["uv"]
        texref = face_data.get("texture", "#0")
        key = texkey_of(texref)
        offset = offsets.get(key, (0.0, 0.0))
        uv, uv_size = convert_face_uv(java_uv, face, offset, scale)
        uv_block[face] = {
            "uv": uv,
            "uv_size": uv_size,
            "material_instance": f"#{key}_{face}_{cube_index}",
        }
    return uv_block
