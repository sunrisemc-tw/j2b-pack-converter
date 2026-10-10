#!/usr/bin/env bash
# convert-and-deploy-bedrock.sh
# 每次日出材質包 release → 自動把 Java pack 轉成 Bedrock + Geyser mappings → 部署到 Geyser proxy 容器。
# 在「桌面」跑（有 j2b venv、到 MC host 的 ssh、到 Pterodactyl 面板的 key）。
#
# 流程：
#   1. 下載 GitHub 日出 Java 材質包 tarball
#   2. 跑 j2b 轉成 Bedrock pack + geyser_item_mappings.json
#   3. 打包 .mcpack，scp 到 MC host，docker cp 進 proxy 容器 packs/ 與 custom_mappings/
#   4. 提示：custom item mappings 是 boot-frozen，需完整重啟 proxy 才生效（不自動重啟）
#
# 用法: bash convert-and-deploy-bedrock.sh [--no-icons] [--restart]
#   --no-icons  跳過 GUI icon 3D 渲染（快很多；icon 之後可補）
#   --restart   轉換+部署後自動重啟 proxy 容器（預設不重啟，交由服主）
set -euo pipefail

# ---- 設定 ----
REPO="sunrisemc-tw/resourcepack"
BRANCH="main"
PACK_SUBDIR="日出伺服器專用材質包"
PROJ="$HOME/Data/Dev/python/j2b-pack-converter"
VENV="$PROJ/.venv"
MC_HOST="user@100.64.0.2"
PROXY_CTN="b176b5b8-746d-4f6c-9724-ff35472a7998"
PANEL="https://mcpanel.gdtw.qzz.io"
PANEL_SHORT="b176b5b8"
PTERO_KEY_FILE="$HOME/.ptero_key"
GEYSER_PACKS="/home/container/plugins/Geyser-Velocity/packs"
GEYSER_MAPPINGS="/home/container/plugins/Geyser-Velocity/custom_mappings"
MCPACK_NAME="sunrise-models.mcpack"

NO_ICONS=""
DO_RESTART=0
for arg in "$@"; do
  case "$arg" in
    --no-icons) NO_ICONS="--no-icons" ;;
    --restart) DO_RESTART=1 ;;
  esac
done

WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

echo "[1/5] 下載 GitHub Java 材質包 ($REPO@$BRANCH)…"
curl -sL --max-time 120 "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH" -o repo.tgz
tar xzf repo.tgz
PACKDIR="$(find . -maxdepth 2 -type d -name "$PACK_SUBDIR" | head -1)"
[ -n "$PACKDIR" ] || { echo "ERROR: 找不到材質包子目錄 $PACK_SUBDIR"; exit 1; }
# j2b 吃的是含 assets/ 的 pack 根；確認 assets 在哪一層
if [ -d "$PACKDIR/assets" ]; then
  PACK_ROOT="$PACKDIR"
else
  PACK_ROOT="$(dirname "$(find "$PACKDIR" -type d -name assets | head -1)")"
fi
[ -d "$PACK_ROOT/assets" ] || { echo "ERROR: pack 根找不到 assets/"; exit 1; }
echo "      pack 根: $PACK_ROOT（$(find "$PACK_ROOT/assets" -type f | wc -l) 檔）"

echo "[2/5] j2b 轉換 → Bedrock pack + Geyser mappings…"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
export PYTHONPATH="$PROJ:${PYTHONPATH:-}"
OUT="$WORK/bedrock_out"
python -m j2b convert "$PACK_ROOT" -o "$OUT" --pack-name sunrisepack $NO_ICONS
[ -f "$OUT/pack/manifest.json" ] || { echo "ERROR: 轉換無輸出"; exit 1; }
[ -f "$OUT/custom_mappings/geyser_item_mappings.json" ] || { echo "ERROR: 無 mappings"; exit 1; }
NITEMS="$(python -c "import json;d=json.load(open('$OUT/custom_mappings/geyser_item_mappings.json'));print(sum(len(v) for v in d['items'].values()))")"
echo "      轉出 $NITEMS 個 custom item mappings"

echo "[3/5] 打包 .mcpack（manifest 在 zip 根）…"
MCPACK="$WORK/$MCPACK_NAME"
( cd "$OUT/pack" && find . -type f | LC_ALL=C sort | zip -q -X "$MCPACK" -@ )
echo "      $MCPACK_NAME = $(stat -c%s "$MCPACK") bytes"

echo "[4/5] 部署到 proxy 容器（scp → docker cp）…"
scp -q "$MCPACK" "$OUT/custom_mappings/geyser_item_mappings.json" "$MC_HOST:/tmp/"
ssh "$MC_HOST" "docker cp /tmp/$MCPACK_NAME $PROXY_CTN:$GEYSER_PACKS/$MCPACK_NAME && docker cp /tmp/geyser_item_mappings.json $PROXY_CTN:$GEYSER_MAPPINGS/geyser_item_mappings.json && rm -f /tmp/$MCPACK_NAME /tmp/geyser_item_mappings.json"
echo "      已部署 pack + mappings 進容器"

echo "[5/5] 生效處理…"
if [ "$DO_RESTART" -eq 1 ]; then
  echo "      完整重啟 proxy 容器（custom mappings boot-frozen，需重啟才註冊）…"
  KEY="$(cat "$PTERO_KEY_FILE")"
  curl -s -X POST "$PANEL/api/client/servers/$PANEL_SHORT/power" \
    -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" -H "Accept: application/json" \
    -d '{"signal":"restart"}' -w "\n      restart HTTP:%{http_code}\n"
  echo "      重啟中；約 30-60s 後 log 應出現 'Registered $NITEMS custom items'"
else
  echo "      ⚠️ custom item mappings 是 boot-frozen：geyser reload 不會註冊，"
  echo "         需完整重啟 proxy 容器 $PANEL_SHORT 才生效（未自動重啟，交由服主）。"
  echo "         要即時生效：重跑本腳本加 --restart，或面板手動 restart。"
fi
echo "[DONE] 轉換+部署完成（$NITEMS items）。"
