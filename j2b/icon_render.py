"""GUI icon 離屏 3D 渲染（moderngl / EGL headless）。

Java 版物品 GUI 縮圖是把 3D 模型用 display.gui 的 {rotation,translation,scale} 擺好、
以正交投影 + 固定方向光渲染而成。Bedrock 的 custom item icon 需要一張 2D png，
因此對每個自訂模型離屏渲染一張透視縮圖（透明背景）。

關鍵：
- moderngl 須用 create_standalone_context(backend='egl')，否則預設嘗試 X11 會在無頭環境失敗。
- MC item GUI 用正交投影；模型空間 0..16 體素。display.gui 預設把物件旋轉 [30,225,0]
  （等角視角）再套用模型自訂的 gui transform。
- 光照：MC 用兩盞方向光（Lighting.setupFor3DItems），這裡用近似的雙向 diffuse + ambient。
"""

from __future__ import annotations

import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import moderngl
    from PIL import Image
    _HAVE_GL = True
except Exception:  # moderngl 或 GL 不可用
    _HAVE_GL = False


# MC 物品 GUI 的預設視角（vanilla block/item 的 gui display 基準旋轉）。
_GUI_BASE_ROT = (30.0, 225.0, 0.0)
_IMG = 128  # 渲染解析度（之後裁切到 bbox）


def _rot_matrix(rx: float, ry: float, rz: float) -> np.ndarray:
    """XYZ 歐拉角（度）-> 3x3 旋轉矩陣。MC 順序：先 Z 再 Y 再 X 外積，用 X*Y*Z 近似。"""
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]], dtype="f4")
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], dtype="f4")
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]], dtype="f4")
    return mx @ my @ mz


def _cube_faces(origin, size, tex_wh):
    """產生一個 cube 的 6 面三角形頂點 (pos3, normal3, uv2)。

    origin/size 為 Java element from/to（0..16 體素，Java 座標系）。uv 取整張貼圖 0..1
    （icon 只需形狀與大致著色，不追求逐面精準 UV）。
    """
    fx, fy, fz = origin
    sx, sy, sz = size
    x0, y0, z0 = fx, fy, fz
    x1, y1, z1 = fx + sx, fy + sy, fz + sz
    # 8 頂點
    v = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    faces = [
        ([4, 5, 6, 7], (0, 0, 1)),    # south +z
        ([1, 0, 3, 2], (0, 0, -1)),   # north -z
        ([5, 1, 2, 6], (1, 0, 0)),    # east +x
        ([0, 4, 7, 3], (-1, 0, 0)),   # west -x
        ([3, 7, 6, 2], (0, 1, 0)),    # up +y
        ([0, 1, 5, 4], (0, -1, 0)),   # down -y
    ]
    uvq = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    out: List[float] = []
    for idx, normal in faces:
        quad = [v[i] for i in idx]
        tri = [quad[0], quad[1], quad[2], quad[0], quad[2], quad[3]]
        triuv = [uvq[0], uvq[1], uvq[2], uvq[0], uvq[2], uvq[3]]
        for p, uv in zip(tri, triuv):
            out.extend([p[0], p[1], p[2], normal[0], normal[1], normal[2], uv[0], uv[1]])
    return out


_VERT = """
#version 330
in vec3 in_pos;
in vec3 in_norm;
in vec2 in_uv;
uniform mat4 mvp;
uniform mat3 nrm;
out vec3 v_norm;
out vec2 v_uv;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    v_norm = normalize(nrm * in_norm);
    v_uv = in_uv;
}
"""

_FRAG = """
#version 330
in vec3 v_norm;
in vec2 v_uv;
uniform sampler2D tex;
out vec4 f_color;
void main() {
    vec4 base = texture(tex, v_uv);
    if (base.a < 0.01) discard;
    // MC 雙向光近似：主光自左上前、副光自右下後，加環境光。
    vec3 l0 = normalize(vec3(0.2, 1.0, 0.7));
    vec3 l1 = normalize(vec3(-0.2, -1.0, -0.7));
    float d = 0.6 * max(dot(v_norm, l0), 0.0) + 0.3 * max(dot(v_norm, l1), 0.0) + 0.4;
    d = min(d, 1.0);
    f_color = vec4(base.rgb * d, base.a);
}
"""


def _ortho(scale: float) -> np.ndarray:
    """正交投影，把 ~16 體素的模型映射到 NDC。scale 控制視圖大小。"""
    s = 1.0 / scale
    m = np.identity(4, dtype="f4")
    m[0, 0] = s
    m[1, 1] = s
    m[2, 2] = -s * 0.5
    return m


def render_icon(ctx, prog, model_elements, texture_path, display_gui) -> Optional["Image.Image"]:
    """渲染單一模型 icon，回傳裁切後的 PIL Image（透明背景）或 None。"""
    # 準備頂點（模型置中到原點：減去 8,8,8）
    verts: List[float] = []
    for el in model_elements:
        origin = [el["from"][0] - 8.0, el["from"][1] - 8.0, el["from"][2] - 8.0]
        size = [el["to"][i] - el["from"][i] for i in range(3)]
        verts.extend(_cube_faces(origin, size, (16, 16)))
    if not verts:
        return None
    vbo = ctx.buffer(np.array(verts, dtype="f4").tobytes())
    vao = ctx.vertex_array(prog, [(vbo, "3f 3f 2f", "in_pos", "in_norm", "in_uv")])

    # 貼圖
    if texture_path and os.path.exists(texture_path):
        img = Image.open(texture_path).convert("RGBA")
    else:
        img = Image.new("RGBA", (16, 16), (180, 180, 180, 255))
    tex = ctx.texture(img.size, 4, img.tobytes())
    tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
    tex.use(0)
    prog["tex"].value = 0

    # 變換：base 等角視角 + display.gui 自訂
    gui_rot = display_gui.get("rotation", [0, 0, 0]) if display_gui else [0, 0, 0]
    gui_scale = display_gui.get("scale", [1, 1, 1]) if display_gui else [1, 1, 1]
    rot = _rot_matrix(*_GUI_BASE_ROT) @ _rot_matrix(gui_rot[0], gui_rot[1], gui_rot[2])
    model_m = np.identity(4, dtype="f4")
    model_m[:3, :3] = rot * float(gui_scale[0] if gui_scale else 1.0)

    mvp = _ortho(12.0) @ model_m
    prog["mvp"].write(np.ascontiguousarray(mvp.T, dtype="f4").tobytes())
    prog["nrm"].write(np.ascontiguousarray(rot, dtype="f4").tobytes())

    fbo = ctx.framebuffer(color_attachments=[ctx.texture((_IMG, _IMG), 4)])
    fbo.use()
    ctx.enable(moderngl.DEPTH_TEST)
    # 需要 depth buffer
    dbo = ctx.depth_renderbuffer((_IMG, _IMG))
    fbo2 = ctx.framebuffer(color_attachments=[fbo.color_attachments[0]], depth_attachment=dbo)
    fbo2.use()
    ctx.clear(0.0, 0.0, 0.0, 0.0)
    vao.render()

    data = fbo2.read(components=4, dtype="f1")
    out = Image.frombytes("RGBA", (_IMG, _IMG), data).transpose(Image.FLIP_TOP_BOTTOM)
    return _crop_to_content(out)


def _crop_to_content(img: "Image.Image") -> "Image.Image":
    bbox = img.getbbox()
    if bbox is None:
        return img
    return img.crop(bbox)


def render_all(icon_jobs, pack_out: str, assets_root: str) -> int:
    """對所有 icon job 渲染。icon_jobs: [(icon_name, icon_rel, JavaModel, texture_abs), ...]。

    回傳成功渲染數。GL 不可用時回 0（呼叫端已 try/except 包起）。
    """
    if not _HAVE_GL:
        raise RuntimeError("moderngl/PIL 不可用")
    ctx = moderngl.create_standalone_context(backend="egl")
    prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
    rendered = 0
    for icon_name, icon_rel, model, texture_abs in icon_jobs:
        try:
            img = render_icon(ctx, prog, model.elements, texture_abs, model.display.get("gui"))
            if img is None:
                continue
            dst = os.path.join(pack_out, icon_rel + ".png")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            img.save(dst)
            rendered += 1
        except Exception:
            continue
    return rendered
