# j2b-pack-converter

純 Python、全自動、跨版本的 **Minecraft Java 版材質包 → Bedrock 版 + Geyser custom item mappings** 轉換器。

讓基岩玩家（經 Geyser/Floodgate）看到與 Java 玩家一致的自訂模型、貼圖、手持、GUI、字體。
不需要 Minecraft runtime（純解析 + 數學 + PIL + moderngl 離屏渲染）。

## 用法

```bash
python -m j2b convert <java_pack_dir> -o <out_dir> [--bedrock-version 1.21.0] [--geyser-api v2] [--no-icons]
# 產出 <out_dir>/pack/（.mcpack 內容）+ <out_dir>/custom_mappings/geyser_item_mappings.json + report.txt
```

## 能力

- **自訂物品模型(CMD)** → Bedrock geometry + attachable + animation + Geyser mappings
- **2D sprite 物品**（parent=item/generated，無 elements）→ flat icon + mapping
- **GUI icon** → moderngl EGL 離屏 3D 渲染
- **全 vanilla 資產** → flat 貼圖/字體/GUI/lang/音效 fallback（`vanilla_assets.py`）
- **跨版本**：輸入支援新(1.21.4+ range_dispatch)/舊(overrides[]) CMD 格式；輸出可選 Bedrock/Geyser API 版本

## 已驗證（pytest golden 迴歸 6 passed）

- 幾何 origin/size：2433 cube **100% 位元級吻合** 官方 Rainbow golden
- 單貼圖 UV：7542 面 **100% 吻合**
- Geyser mappings：交集 118 CMD 的 bedrock_identifier **100% 一致**
- 舊格式 overrides[] 解析、參照完整性（mapping→attachable→geometry→texture 零斷鏈）
- icon：moderngl EGL 離屏渲染可用（角度/著色視覺接近 golden）

## 每次 release 自動轉換 pipeline

`scripts/convert-and-deploy-bedrock.sh`：下載 GitHub Java 材質包 → j2b 轉換 → 打包 .mcpack →
scp + docker cp 部署進 Geyser proxy 容器的 `packs/` 與 `custom_mappings/`。

```bash
bash scripts/convert-and-deploy-bedrock.sh            # 轉換+部署，不重啟（預設）
bash scripts/convert-and-deploy-bedrock.sh --no-icons # 跳過 icon 3D 渲染（快）
bash scripts/convert-and-deploy-bedrock.sh --restart  # 轉換+部署+重啟 proxy（即時生效）
```

⚠️ **Geyser custom item mappings 是 boot-frozen**：`geyser reload` 不會重新註冊，
改了 `custom_mappings/` 必須**完整重啟 proxy 容器**才生效（純 sound pack 則 reload 即可）。
搭配既有的 `~/.hermes/skills/minecraft-server-ops/scripts/sync-resourcepack-cdn.sh`
（Java pack → CDN）一起跑，即為「每次 release 同時更新 Java(CDN) 與 Bedrock(Geyser)」。

## 真值測試資料

`tests/golden/`：
- `java_input/` — 日出 Java 包（QualityArmory + IceTea + RoastDuck）
- `rainbow_output/` — 官方 Rainbow 工具對同包的輸出（位元級迴歸比對真值）

## 已知待精修

- GUI icon 投影角度/著色與官方 Rainbow golden 視覺接近但非位元相同（cosmetic，背包縮圖）。
- 多貼圖模型 atlas 排版為自家穩定排版（與 Rainbow 內部排版不同），但 geo↔atlas 自洽、顯示正確。

## 技術規格

完整逆推公式、prior art、各資產轉換判定見 **`docs/spec.md`**；display→animation 樣本見 `docs/display-to-anim.md`。
