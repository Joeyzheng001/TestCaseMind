#!/usr/bin/env bash
# 构建 ThesisMind 发行版 zip 包
# 用法: bash build_release.sh [版本号]
set -e

VERSION="${1:-$(date +%Y%m%d)}"
RELEASE_NAME="ThesisMind-v${VERSION}"
BUILD_DIR="build/${RELEASE_NAME}"
ZIP_FILE="build/${RELEASE_NAME}.zip"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ThesisMind 发行版打包${NC}"
echo -e "${GREEN}  版本: ${VERSION}${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ── 清理旧的构建目录 ──
rm -rf "${BUILD_DIR}" "${ZIP_FILE}"
mkdir -p "${BUILD_DIR}"

# ── 1. Python 源码 ──
echo "复制 Python 源码..."
cp -r src "${BUILD_DIR}/src"

# ── 2. Web 前端（不含 admin 文件） ──
echo "复制 Web 前端..."
mkdir -p "${BUILD_DIR}/web"
cp web/app.js web/index.html web/styles.css "${BUILD_DIR}/web/"
# 复制静态资源（logo 等）
cp web/*.png web/*.svg web/*.ico web/*.json 2>/dev/null "${BUILD_DIR}/web/" || true

# ── 3. 知识库数据库 ──
echo "复制知识库数据库..."
mkdir -p "${BUILD_DIR}/knowledge_base"
for f in cards.sqlite3 papers.sqlite3; do
    if [ -f "knowledge_base/${f}" ]; then
        cp "knowledge_base/${f}" "${BUILD_DIR}/knowledge_base/"
        echo "  ✓ knowledge_base/${f}"
    else
        echo -e "  ${RED}✗ knowledge_base/${f} 不存在${NC}"
    fi
done

# templates
if [ -d "knowledge_base/templates" ]; then
    cp -r knowledge_base/templates "${BUILD_DIR}/knowledge_base/"
    echo "  ✓ knowledge_base/templates/"
fi

# outlines (if any)
if [ -d "knowledge_base/outlines" ] && [ "$(ls -A knowledge_base/outlines 2>/dev/null)" ]; then
    cp -r knowledge_base/outlines "${BUILD_DIR}/knowledge_base/"
    echo "  ✓ knowledge_base/outlines/"
fi

# ── 4. 离线依赖包 ──
echo "下载 Python 依赖包（离线安装用）..."
WHEELS_DIR="${BUILD_DIR}/wheels"
mkdir -p "${WHEELS_DIR}"

# 下载当前构建机器可用的 wheels。跨平台/跨 Python 版本 wheelhouse
# 暂不自动生成；如需离线包，可手动把对应平台的 .whl 放入 wheels/。
pip download -r requirements.txt -d "${WHEELS_DIR}" -q 2>&1 || true

WHEEL_COUNT=$(ls -1 "${WHEELS_DIR}"/*.whl 2>/dev/null | wc -l)
WHEELS_SIZE=$(du -sh "${WHEELS_DIR}" | cut -f1)
echo "  ✓ ${WHEEL_COUNT} 个 wheel 包 (${WHEELS_SIZE})"

# ── 5. 向量索引 ──
if [ -f "knowledge_base/vector_store.sqlite3" ]; then
    VECTOR_SIZE=$(du -h knowledge_base/vector_store.sqlite3 | cut -f1)
    echo "打包向量索引 (${VECTOR_SIZE})..."
    cp knowledge_base/vector_store.sqlite3 "${BUILD_DIR}/knowledge_base/"
    echo "  ✓ vector_store.sqlite3"
else
    echo -e "${YELLOW}  注意: vector_store.sqlite3 不存在，部分功能将受限${NC}"
    echo -e "${YELLOW}  请将向量索引文件放入 knowledge_base/ 后重新打包${NC}"
fi

# ── 6. 配置文件 ──
echo "复制配置文件..."
for f in requirements.txt setup.sh .env.example; do
    if [ -f "$f" ]; then
        cp "$f" "${BUILD_DIR}/"
        echo "  ✓ $f"
    fi
done

# setup.bat + start.bat for Windows
for f in setup.bat start.bat; do
    if [ -f "$f" ]; then
        cp "$f" "${BUILD_DIR}/"
        echo "  ✓ $f"
    fi
done

# ── 7. 清理开发残留 ──
echo "清理开发残留..."
find "${BUILD_DIR}" -type f -name ".DS_Store" -delete
find "${BUILD_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
# 确保没有 admin 文件
rm -f "${BUILD_DIR}/web/admin.js" "${BUILD_DIR}/web/admin.css"
# 确保没有备份/WAL 文件
rm -f "${BUILD_DIR}/knowledge_base/"*_backup_*
rm -f "${BUILD_DIR}/knowledge_base/"*-shm
rm -f "${BUILD_DIR}/knowledge_base/"*-wal

# ── 8. 创建 zip ──
mkdir -p build
echo ""
echo "创建 zip 包..."
cd build
zip -qr "${RELEASE_NAME}.zip" "${RELEASE_NAME}"
cd ..

ZIP_SIZE=$(du -h "${ZIP_FILE}" | cut -f1)

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  打包完成！${NC}"
echo ""
echo "  文件: ${ZIP_FILE}"
echo "  大小: ${ZIP_SIZE}"
echo ""
echo "  用户使用方式:"
echo "    1. 解压 ${RELEASE_NAME}.zip"
echo "    2. cd ${RELEASE_NAME}"
echo "    3. bash setup.sh"
echo "    4. source .venv/bin/activate"
echo "    5. python src/web_server.py --port 8222"
echo -e "${GREEN}========================================${NC}"
