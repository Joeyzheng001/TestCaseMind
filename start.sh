#!/usr/bin/env bash
# ThesisMind 一键启动脚本 (macOS / Linux)
# 用法: bash start.sh [端口号，默认 8222]
set -e

PORT="${1:-8222}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ── 检查虚拟环境 ──
if [ ! -f ".venv/bin/activate" ]; then
    echo -e "${RED}虚拟环境未找到，请先运行: bash setup.sh${NC}"
    exit 1
fi

source .venv/bin/activate

# 国内用户 HuggingFace 镜像（模型下载加速）
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

# ── 检查 .env ──
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo -e "${YELLOW}.env 已从模板创建，如需配置 API Key 请编辑 .env${NC}"
fi

# ── 杀掉占用端口的旧进程 ──
OLD_PID=$(lsof -ti ":$PORT" 2>/dev/null || true)
if [ -n "$OLD_PID" ]; then
    echo -e "${YELLOW}[INFO] 端口 $PORT 被 PID $OLD_PID 占用，正在清理...${NC}"
    kill -9 $OLD_PID 2>/dev/null || true
    sleep 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ThesisMind${NC}"
echo -e "${GREEN}  地址: http://localhost:${PORT}${NC}"
echo -e "${GREEN}  Ctrl+C 停止${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 自动打开浏览器
if command -v open &>/dev/null; then
    open "http://localhost:$PORT"
elif command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:$PORT"
fi

python src/web_server.py --port "$PORT"
