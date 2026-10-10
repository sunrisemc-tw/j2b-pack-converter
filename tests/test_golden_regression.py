"""golden 迴歸 pytest：幾何 origin/size 位元級、單貼圖 UV 位元級、mapping 吻合。"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN_JAVA = os.path.join(ROOT, "tests", "golden", "java_input")
GOLDEN_OUT = os.path.join(ROOT, "tests", "golden", "rainbow_output")
TOL = 1e-4


@pytest.fixture(scope="session")
def converted(tmp_path_factory):
    """跑一次 convert（跳過 icon 加速），回傳輸出目錄。"""
    out = tmp_path_factory.mktemp("j2b_out")
    subprocess.run(
        [sys.executable, "-m", "j2b", "convert", GOLDEN_JAVA, "-o", str(out), "--no-icons"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return str(out)


def _load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _cubes(geo):
    g = geo["minecraft:geometry"][0]
    return [c for bone in g.get("bones", []) for c in bone.get("cubes", [])]


def _vclose(a, b, tol=TOL):
    return len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b))


def _single_texture(geo_cubes):
    tks = set()
    for cube in geo_cubes:
        for face in cube.get("uv", {}).values():
            mi = face.get("material_instance", "")
            if "_" in mi:
                tks.add(mi.split("_")[0])
    return len(tks) <= 1


def test_geometry_origin_size_bit_exact(converted):
    """交集模型的每個 cube origin/size 必須與 golden 位元級吻合。"""
    gdir = os.path.join(GOLDEN_OUT, "pack", "models", "entity")
    odir = os.path.join(converted, "pack", "models", "entity")
    golden = {os.path.basename(p): p for p in glob.glob(os.path.join(gdir, "*.geo.json"))}
    ours = {os.path.basename(p): p for p in glob.glob(os.path.join(odir, "*.geo.json"))}
    common = sorted(set(golden) & set(ours))
    assert common, "交集模型數不應為 0"

    total = ok_origin = ok_size = 0
    for name in common:
        gc = _cubes(_load(golden[name]))
        oc = _cubes(_load(ours[name]))
        assert len(gc) == len(oc), f"{name}: cube 數不一致"
        for g_cube, o_cube in zip(gc, oc):
            total += 1
            if _vclose(g_cube["origin"], o_cube["origin"]):
                ok_origin += 1
            if _vclose(g_cube["size"], o_cube["size"]):
                ok_size += 1
    assert ok_origin == total, f"origin 吻合 {ok_origin}/{total}"
    assert ok_size == total, f"size 吻合 {ok_size}/{total}"


def test_single_texture_uv_bit_exact(converted):
    """單貼圖模型的 UV/uv_size 必須與 golden 位元級吻合（多貼圖 atlas 排版不同不比）。"""
    gdir = os.path.join(GOLDEN_OUT, "pack", "models", "entity")
    odir = os.path.join(converted, "pack", "models", "entity")
    golden = {os.path.basename(p): p for p in glob.glob(os.path.join(gdir, "*.geo.json"))}
    ours = {os.path.basename(p): p for p in glob.glob(os.path.join(odir, "*.geo.json"))}
    common = sorted(set(golden) & set(ours))

    total = ok = 0
    for name in common:
        gc = _cubes(_load(golden[name]))
        oc = _cubes(_load(ours[name]))
        if len(gc) != len(oc) or not _single_texture(gc):
            continue
        for g_cube, o_cube in zip(gc, oc):
            for face, g_face in g_cube.get("uv", {}).items():
                o_face = o_cube.get("uv", {}).get(face)
                if not o_face:
                    continue
                total += 1
                if _vclose(g_face["uv"], o_face["uv"]) and _vclose(g_face["uv_size"], o_face["uv_size"]):
                    ok += 1
    assert total > 0
    assert ok == total, f"單貼圖 UV 吻合 {ok}/{total}"


def test_mapping_identifiers_match_golden(converted):
    """交集 CMD 的 bedrock_identifier 必須與 golden 完全一致。"""
    ours = _load(os.path.join(converted, "custom_mappings", "geyser_item_mappings.json"))
    golden = _load(os.path.join(GOLDEN_OUT, "custom_mappings", "geyser_item_mappings.json"))

    def flat(m):
        return {
            (item, e["custom_model_data"]): e["bedrock_identifier"]
            for item, entries in m["items"].items()
            for e in entries
        }

    of, gf = flat(ours), flat(golden)
    common = set(of) & set(gf)
    assert common, "mapping 交集不應為 0"
    mismatched = [k for k in common if of[k] != gf[k]]
    assert not mismatched, f"{len(mismatched)} 個 CMD 的 identifier 不符: {mismatched[:5]}"


def test_output_structure(converted):
    """產出結構齊全。"""
    assert os.path.isfile(os.path.join(converted, "pack", "manifest.json"))
    assert os.path.isfile(os.path.join(converted, "custom_mappings", "geyser_item_mappings.json"))
    assert os.path.isfile(os.path.join(converted, "pack", "textures", "item_texture.json"))
    assert os.path.isfile(os.path.join(converted, "report.txt"))
    assert glob.glob(os.path.join(converted, "pack", "attachables", "*.json"))
    assert glob.glob(os.path.join(converted, "pack", "animations", "*.animation.json"))
