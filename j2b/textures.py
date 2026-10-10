"""貼圖處理：單貼圖複製 + 多貼圖 2D atlas 拼接（PIL），並回報 UV 偏移。

- 單貼圖模型：直接複製 png（golden 驗證像素 md5 diff=0，只是 PNG 重壓）。
- 多貼圖模型：把所有用到的 texkey 貼圖拼成一張 atlas，回傳每個 texkey 的
  (offset_x, offset_y) 供 uv.py 重算 UV。

Bedrock 貼圖路徑 remap：
  "qualityarmory:all/texturedmaterials1" -> "textures/all/texturedmaterials1"
  "icetea:item/icetea"                   -> "textures/item/icetea"
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

from PIL import Image


def texture_ref_to_rel(texture_ref: str) -> str:
    """Java 貼圖 ref -> 相對 (命名空間底下) 路徑；"ns:all/foo" -> "all/foo"。"""
    if ":" in texture_ref:
        _, rel = texture_ref.split(":", 1)
    else:
        rel = texture_ref
    return rel


def find_texture_file(assets_root: str, texture_ref: str) -> Optional[str]:
    """定位 Java 貼圖檔的實際路徑。"""
    if ":" in texture_ref:
        namespace, rel = texture_ref.split(":", 1)
    else:
        namespace, rel = "minecraft", texture_ref
    path = os.path.join(assets_root, namespace, "textures", rel + ".png")
    if os.path.exists(path):
        return path
    return None


def bedrock_texture_path(texture_ref: str) -> str:
    """回傳 Bedrock 用的貼圖路徑（不含副檔名），如 "textures/all/texturedmaterials1"。"""
    rel = texture_ref_to_rel(texture_ref)
    return f"textures/{rel}"


def image_size(path: str) -> Tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def used_texkeys(elements: List[dict]) -> List[str]:
    """回傳 elements 的 faces 實際用到的 texkey（去 '#'，保持首次出現順序）。"""
    seen: List[str] = []
    for element in elements:
        for face_data in element.get("faces", {}).values():
            ref = face_data.get("texture", "#0")
            key = ref.lstrip("#")
            if key not in seen:
                seen.append(key)
    return seen


def stitch_atlas(
    tile_paths: List[Tuple[str, str]],
    tile_size: int = 16,
):
    """把多張貼圖拼成網格 atlas。

    tile_paths: [(texkey, 絕對檔案路徑), ...]
    回傳 (atlas_image, offsets, (atlas_w, atlas_h))，
    offsets: texkey -> (offset_x, offset_y)。

    採橫向優先、每列最多 (atlas_cols) 格的簡單 bin 排列。因為 Rainbow 的實際
    atlas 排版是其內部實作細節（golden 中同組貼圖在不同群會落在不同位置），
    我們採用穩定可重現的排版，並據此重算 UV，保證自家 geo↔atlas 一致。
    """
    count = len(tile_paths)
    if count == 0:
        raise ValueError("stitch_atlas 需要至少一張貼圖")

    # 載入所有貼圖，取最大寬高作為格子基準（多數為 16，但也有 32/64）。
    images: List[Tuple[str, Image.Image]] = []
    max_w = tile_size
    max_h = tile_size
    for key, path in tile_paths:
        img = Image.open(path).convert("RGBA")
        images.append((key, img))
        max_w = max(max_w, img.width)
        max_h = max(max_h, img.height)

    cols = 1
    while cols * cols < count:
        cols += 1
    rows = (count + cols - 1) // cols

    atlas_w = cols * max_w
    atlas_h = rows * max_h
    atlas = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))
    offsets: Dict[str, Tuple[float, float]] = {}
    for index, (key, img) in enumerate(images):
        col = index % cols
        row = index // cols
        ox = col * max_w
        oy = row * max_h
        atlas.paste(img, (ox, oy))
        offsets[key] = (float(ox), float(oy))
    return atlas, offsets, (atlas_w, atlas_h)
