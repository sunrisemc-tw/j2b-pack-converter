# Java → Bedrock Resource Pack Converter — 技術規格（逆推自 Rainbow 真實 I/O）

> 目標：把 Minecraft Java 版材質包**全部內容**轉成 Bedrock 版 + Geyser custom item mappings，
> 讓基岩玩家（經 Geyser/Floodgate）看到與 Java 玩家一致的自訂模型/貼圖/手持/GUI/字體。
> **全自動、純 Python、不需 Minecraft runtime、跨版本。**

## 背景與既有成果（務必先讀，別重造輪子）

- 已驗證：Geyser 官方**不轉** Java 包給基岩；要獨立產 Bedrock `.mcpack` + `custom_mappings/`。
- 本專案 `tests/golden/` 內有一組**真值對照**：
  - `java_input/` = 日出 Java 包（QualityArmory 槍械 177 模型 + IceTea 冰茶 + RoastDuck 烤鴨物品）
  - `rainbow_output/` = 官方工具 Rainbow 對同一包的輸出（**位元級真值**，拿來做迴歸測試）
- **幾何/UV/貼圖轉換公式已由本人逆推並在 1692 個 cube 上驗證**（見下「已解出的公式」）。
  CC 的工作是把公式寫成乾淨、跨版本、涵蓋全資產類型的轉換器，並用 golden data 做 diff 驗證。

## Prior art（參考、不照抄）

- **Kas-tle/java2bedrock.sh**（Geyser 社群標準，bash）：做了自訂模型→Geyser mappings、多貼圖 atlas 拼接、
  parent model、2D 物品。缺點：依賴重（jq/imagemagick/nodejs/spritesheet-js）、**3D icon 要手動給 sprite**、
  不做全 vanilla 資產、舊版 `overrides[]` 解析。→ 參考它的 **atlas 拼接策略** 與 **Geyser mappings schema** 細節。
- **GeyserMC/Hydraulic**：伺服器端 mod，非獨立轉換器，不採用。
- 本專案與它們的差異賣點：**純 Python 單一工具 + 3D icon 離屏渲染 + 全資產 + 跨版本輸入/輸出**。

## 已解出的轉換公式（位元級吻合 Rainbow，直接實作）

### 1. 幾何 cube（Java element → Bedrock cube）
Java `element.from=[fx,fy,fz]`, `to=[tx,ty,tz]`（單位：像素，0..16 體素空間）
```
bedrock.origin = [8 - tx, min(fy,ty), fz - 8]
bedrock.size   = [abs(tx-fx), abs(ty-fy), abs(tz-fz)]
```
⚠️ 用 min/abs 處理 Java `from>to` 的反向座標（golden 1692 cube 中有 2 個這種邊角）。

### 2. cube rotation（Java element.rotation → Bedrock cube.rotation）
Java `{angle, axis, origin}`（單軸、angle∈{-45,-22.5,0,22.5,45}）→ Bedrock `rotation:[rx,ry,rz]` + `pivot`
```
axis x: bedrock.rotation = [-angle, 0, 0]
axis y: bedrock.rotation = [0, -angle, 0]   # 待 golden 驗證 y 號（樣本少）
axis z: bedrock.rotation = [0, 0,  angle]
bedrock.pivot = [8 - origin_x, origin_y, origin_z - 8]   # 同座標變換
```
（已確認 x 變號、z 保留；y 軸樣本少，實作後用 golden diff 確認。）

### 3. UV（Java face.uv=[x1,y1,x2,y2] → Bedrock per-face uv+uv_size）
```
一般面:  uv=[x1,y1]           uv_size=[x2-x1, y2-y1]
up/down: uv=[x2,y2]           uv_size=[-(x2-x1), -(y2-y1)]   # 負向翻轉
每面一個 material_instance = "#<texkey>_<face>_<idx>"（如 #1_north_0）
```

### 4. 貼圖
- 單貼圖模型：**直接複製 png**（golden 驗證像素 md5 diff=0，只是 PNG 重壓）。
- 多貼圖模型（golden 中 41/72 槍）：**2D atlas 拼接**（PIL），所有 face 的 texkey 合進一張圖，
  UV 偏移到拼接後座標。產 `_stitched.png`。參考 java2bedrock 的 spritesheet 策略（但用 PIL 自寫）。
- Bedrock 貼圖路徑 remap：`qualityarmory:all/texturedmaterials1` → `textures/all/texturedmaterials1`。

### 5. 固定模板（照 golden 的格式產）
- `geometry.*.geo.json`：format_version "1.21.0"，`minecraft:geometry[0].description`
  （identifier、visible_bounds_*、texture_width/height）+ `bones[0]`（name="bone",
  binding="q.item_slot_to_bone_name(context.item_slot)", pivot, cubes[]）。
- `attachables/*.json`：identifier、materials(default/enchanted)、textures、geometry、
  animations(3rd/1st/head)、scripts.animate、render_controllers=["controller.render.item_default"]。
- `animations/*.animation.json`：format_version "1.8.0"；3 個動畫（hold_third_person/hold_first_person/head）。
  bones.bone 的 rotation/scale 直接取 Java `display.*`；**position 由 display.translation 做座標變換**
  （公式**待 CC 用 golden 多樣本解**：已知 x 變號、z=-translation_z、y 有常數偏移+可能與 rotation 耦合，
  見 `docs/display-to-anim.md` 的樣本表，用最小二乘或幾何推導解出）。
- `sounds/sound_definitions.json`、`manifest.json`（format_version 2）、`item_texture.json`、
  `custom_mappings/geyser_item_mappings.json`（format_version 2，每 entry:
  `{bedrock_identifier, bedrock_options.icon, custom_model_data, type:"legacy"}`）。

### 6. GUI icon（3D 透視縮圖，唯一需渲染）
- golden 的 `textures/gun/*_icon.png`（~60-92px）= **3D 透視渲染**（有角度/景深/陰影），非平面裁切。
- 用 **moderngl 離屏渲染**（EGL headless，不需 X）：
  - 載入 cube mesh（origin/size/rotation）+ 貼圖（nearest filter）。
  - 投影用 Java `display.gui` 的 `{rotation, translation, scale}` 變換 + MC GUI 的正交投影
    （MC item GUI 是正交、固定光照：主光 + 環境光，見 Minecraft `ItemRenderer`/`gui` lighting）。
  - 輸出裁切到模型 bounding box，透明背景。
- 這塊 golden 有真值可比對（結構對不上沒關係，icon 用「視覺接近」驗收，不要求位元級）。

## 跨版本支援（輸入 & 輸出都要）

### 輸入版本（Java pack）
- **新格式（1.21.4+）**：`assets/<ns>/items/<item>.json` 的 `model.type=range_dispatch`,
  `property=custom_model_data`, `entries[].threshold` = CMD int。（golden 就是這個）
- **舊格式（≤1.21.3）**：`assets/minecraft/models/item/<item>.json` 的
  `overrides[].predicate.custom_model_data` + `overrides[].model`。要同時支援。
- `pack.mcmeta` 的 `pack_format` 判斷版本；golden 用 `pack_format:9999, supported_formats:[0,9999]`（萬用）。

### 輸出版本（Bedrock min_engine_version）
- geometry/attachable 的 `format_version` 與 manifest `min_engine_version` 要可配置
  （Geyser custom item API v2 需 Bedrock ≥1.21.x；舊 API v1 不同 schema）。
- Geyser mappings `format_version` v1 vs v2 schema 不同（v2 用 `custom_model_data`/`type:legacy`）；
  預設產 v2，但保留 v1 產出選項。
- ⚠️ **Geyser mappings 是 boot-frozen**（啟動後凍結，改了要重啟 Geyser）——文件要寫清楚。

## 全資產類型覆蓋（不只槍械/自訂模型）

CC 要讓轉換器處理一個**任意** Java 包的所有常見資產，逐類 fallback：
1. **自訂物品模型**（CMD）→ geometry+attachable+mapping（上述公式，核心）。
2. **原版物品/手持貼圖覆蓋**（純 2D 貼圖，無自訂模型）→ 直接複製到 Bedrock 對應路徑
   （需 Java→Bedrock 貼圖路徑對照表，參考 packconverter/java2bedrock 的 vanilla mapping）。
3. **字體 font**（`assets/<ns>/font/*.json` + `textures/font/*.png`）→ Bedrock `font/glyph_*.png`
   atlas（Bedrock 字體走 glyph_E1.png 這類固定 atlas，見 bedrock.dev；需 unicode→glyph 格映射）。
4. **GUI/HUD 貼圖**（`textures/gui/**`）→ Bedrock `textures/ui/**`（路徑+尺寸對照，部分需切圖）。
5. **lang 語言檔**（`lang/*.json`）→ Bedrock `texts/*.lang`（key 格式轉換）。
6. **音效**（已有 `build_bedrock_sound_pack.py` 可併入）→ `sounds/sound_definitions.json`。
7. 不支援/未知資產 → 記進 `report.txt`（哪些沒轉、為什麼），不要靜默丟失。

## 驗收標準（golden 迴歸）

1. `python -m j2b convert tests/golden/java_input -o /tmp/out` 跑完無錯。
2. **幾何位元級**：對每個 golden 有對應的 `.geo.json`，輸出 cube 的 origin/size/uv 與 rainbow_output
   **完全相同**（允許浮點 1e-4）；差異列進測試報告。目標 ≥99% cube 吻合。
3. **mapping 完整**：178 個自訂物品全部在 `geyser_item_mappings.json`，CMD↔identifier 對得上。
4. **貼圖**：單貼圖像素一致；多貼圖 atlas 的 UV 指到正確區域（用 golden 的 stitched 對照）。
5. **icon**：目視接近 golden（可接受差異，但要是能辨識的 3D 槍縮圖，非空白/非純色）。
6. **跨版本**：給一個舊格式（overrides[]）的小測試包也能轉（CC 自造最小測試 fixture）。
7. **CLI**：`j2b convert <pack> -o <out> [--bedrock-version X] [--geyser-api v2] [--no-icons]`，
   產出可直接 `docker cp` 進 Geyser `packs/` + `custom_mappings/` 的目錄結構。

## 專案結構
```
j2b-pack-converter/
  j2b/              # 套件：cli.py, geometry.py, uv.py, textures.py, atlas.py,
                    #        attachable.py, animation.py, mappings.py, icon_render.py,
                    #        vanilla_assets.py（貼圖/字體/GUI/lang）, versions.py, report.py
  tests/
    golden/java_input/      # Java 真值輸入
    golden/rainbow_output/  # Rainbow 真值輸出（迴歸比對）
    test_geometry.py 等
  docs/
    spec.md（本檔）
    display-to-anim.md（display→animation position 樣本表，待解公式）
  scripts/
  README.md
```

## 環境
- Python 3.11，`pip install moderngl pillow numpy`（moderngl 需 EGL headless 渲染 icon）。
- 本機桌面有 llvmpipe（軟體 GL），moderngl 可走 EGL/osmesa backend。
- git: duckducktw / dianasogooda@gmail.com。repo 歸屬：**個人帳號 duckducktw**（烤鴨自用工具），
  要推再問烤鴨 public/private。
