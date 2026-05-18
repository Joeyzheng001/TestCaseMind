#!/usr/bin/env bash
# 下载知识库资产（向量索引等大文件）
# 将向量索引文件 URL 或分享链接放入 ASSETS_URL 变量
# 运行: bash download_assets.sh
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

VECTOR_FILE="knowledge_base/vector_store.sqlite3"
VECTOR_SIZE="~300MB"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ThesisMind 知识库资产下载${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ── 检查是否已存在 ──
if [ -f "$VECTOR_FILE" ]; then
    actual_size=$(du -h "$VECTOR_FILE" | cut -f1)
    echo -e "${GREEN}✓ 向量索引已存在 ($actual_size)，跳过下载${NC}"
    exit 0
fi

# ── 获取下载 URL ──
ASSETS_URL="${ASSETS_URL:-}"
if [ -z "$ASSETS_URL" ]; then
    echo -e "${RED}错误: 未设置 ASSETS_URL${NC}"
    echo ""
    echo "请设置环境变量指向向量索引下载地址:"
    echo "  export ASSETS_URL='https://your-server.com/vector_store.sqlite3'"
    echo "  bash download_assets.sh"
    echo ""
    echo "或直接修改本脚本中的 ASSETS_URL 变量。"
    exit 1
fi

echo "下载向量索引 (${VECTOR_SIZE})..."
echo "源地址: ${ASSETS_URL}"
echo "目标位置: ${VECTOR_FILE}"
echo ""

# ── 下载 ──
mkdir -p knowledge_base

if command -v wget &> /dev/null; then
    wget -O "${VECTOR_FILE}" "${ASSETS_URL}" --show-progress
elif command -v curl &> /dev/null; then
    curl -L -o "${VECTOR_FILE}" "${ASSETS_URL}" --progress-bar
else
    echo -e "${RED}错误: 未找到 wget 或 curl${NC}"
    exit 1
fi

if [ -f "$VECTOR_FILE" ]; then
    actual_size=$(du -h "$VECTOR_FILE" | cut -f1)
    echo ""
    echo -e "${GREEN}✓ 向量索引下载完成 ($actual_size)${NC}"
else
    echo -e "${RED}下载失败，请检查 URL 是否正确${NC}"
    exit 1
fi
