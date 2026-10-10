"""golden 迴歸：比對 j2b 輸出與 Rainbow golden 的 geometry cube origin/size/uv。

只對「兩邊都有的模型（交集）」比對。origin/size 要位元級吻合（1e-4）；
uv 僅單貼圖 cube 有意義（多貼圖 atlas 排版不同，不比）。
"""

from __future__ import annotations

import glob
import json
import os
import sys

TOL = 1e-4


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def cubes_of(geo):
    g = geo["minecraft:geometry"][0]
    out = []
    for bone in g.get("bones", []):
        out.extend(bone.get("cubes", []))
    return out


def vclose(a, b, tol=TOL):
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def main():
    j2b_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/j2b_out/pack/models/entity"
    golden_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser(
        "~/Data/Dev/python/j2b-pack-converter/tests/golden/rainbow_output/pack/models/entity"
    )

    golden = {os.path.basename(p): p for p in glob.glob(os.path.join(golden_dir, "*.geo.json"))}
    ours = {os.path.basename(p): p for p in glob.glob(os.path.join(j2b_dir, "*.geo.json"))}
    common = sorted(set(golden) & set(ours))
    print(f"golden={len(golden)} ours={len(ours)} 交集={len(common)}")

    total_cubes = 0
    origin_ok = 0
    size_ok = 0
    uv_single_total = 0
    uv_single_ok = 0
    mismatched_models = []

    for name in common:
        gc = cubes_of(load(golden[name]))
        oc = cubes_of(load(ours[name]))
        if len(gc) != len(oc):
            mismatched_models.append(f"{name}: cube 數 {len(oc)} vs golden {len(gc)}")
            continue
        model_bad = False
        for g_cube, o_cube in zip(gc, oc):
            total_cubes += 1
            if vclose(g_cube["origin"], o_cube["origin"]):
                origin_ok += 1
            else:
                model_bad = True
            if vclose(g_cube["size"], o_cube["size"]):
                size_ok += 1
            else:
                model_bad = True
            # uv：只在兩邊 material_instance 同屬單貼圖（#1_*）時比座標
            for face, g_face in g_cube.get("uv", {}).items():
                o_face = o_cube.get("uv", {}).get(face)
                if not o_face:
                    continue
                uv_single_total += 1
                if vclose(g_face["uv"], o_face["uv"]) and vclose(g_face["uv_size"], o_face["uv_size"]):
                    uv_single_ok += 1
        if model_bad:
            mismatched_models.append(name)

    def pct(a, b):
        return f"{(100.0 * a / b):.2f}%" if b else "n/a"

    print(f"\n=== 幾何比對（交集 {len(common)} 模型，{total_cubes} cube）===")
    print(f"origin 吻合: {origin_ok}/{total_cubes} = {pct(origin_ok, total_cubes)}")
    print(f"size   吻合: {size_ok}/{total_cubes} = {pct(size_ok, total_cubes)}")
    print(f"uv     吻合: {uv_single_ok}/{uv_single_total} = {pct(uv_single_ok, uv_single_total)}  （含多貼圖，atlas 排版差異會拉低）")
    if mismatched_models:
        print(f"\n有差異的模型（{len(mismatched_models)}）：")
        for m in mismatched_models[:15]:
            print("  ", m)


if __name__ == "__main__":
    main()
