# j2b-pack-converter

純 Python、全自動、跨版本的 **Minecraft Java 版材質包 → Bedrock 版 + Geyser custom item mappings** 轉換器。

讓基岩玩家（經 Geyser/Floodgate）看到與 Java 玩家一致的自訂模型、貼圖、手持、GUI、字體。

- 不需要 Minecraft runtime（純解析 + 數學 + PIL + moderngl 離屏渲染）。
- 涵蓋：自訂物品模型(CMD)、原版貼圖覆蓋、字體、GUI/HUD、lang、音效、3D GUI icon。
- 跨版本：輸入支援新(1.21.4+ range_dispatch)/舊(overrides[]) CMD 格式；輸出可選 Bedrock/Geyser API 版本。

## 開發狀態

骨架階段。完整技術規格（含逆推自官方工具 Rainbow 的位元級轉換公式）見 **`docs/spec.md`**。

## 真值測試資料

`tests/golden/`：
- `java_input/` — 日出 Java 包（QualityArmory + IceTea + RoastDuck）
- `rainbow_output/` — 官方 Rainbow 工具對同包的輸出（位元級迴歸比對真值）

## 用法（目標）

```bash
pip install moderngl pillow numpy
python -m j2b convert <java_pack_dir> -o <out_dir> [--bedrock-version 1.21.0] [--geyser-api v2] [--no-icons]
# 產出 <out_dir>/pack/（.mcpack 內容）+ <out_dir>/custom_mappings/geyser_item_mappings.json
```

部署：`pack/` → Geyser `packs/<name>/`；`custom_mappings/*.json` → Geyser `custom_mappings/`；重啟 Geyser。
