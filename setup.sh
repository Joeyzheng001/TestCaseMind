#!/usr/bin/env bash
# ThesisMind 跨平台安装脚本 (macOS / Linux)
# 使用方法: bash setup.sh
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ThesisMind 论文辅助工作台 - 安装向导${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# ── Python 检测 ──
PYTHON=""
for cmd in python3 python; do
    if command -v $cmd &> /dev/null; then
        ver=$($cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$($cmd -c "import sys; print(sys.version_info.major)")
        minor=$($cmd -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -ge 3 ] && [ "$minor" -ge 9 ]; then
            PYTHON=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}错误: 未找到 Python 3.9+，请先安装 Python${NC}"
    echo "  macOS: brew install python@3.12"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  CentOS/RHEL: sudo dnf install python3 python3-pip"
    exit 1
fi
echo -e "${GREEN}✓ Python: $($PYTHON --version)${NC}"

# ── 虚拟环境 ──
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "创建虚拟环境..."
    $PYTHON -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✓ 虚拟环境已激活${NC}"

# ── 依赖安装 ──
echo "安装依赖包..."
pip install --upgrade pip -q

if [ -d "wheels" ] && [ "$(ls -1 wheels/*.whl 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "  从本地离线包安装..."
    pip install --no-index --find-links=wheels -r requirements.txt -q 2>&1 || {
        echo -e "${YELLOW}  离线包安装失败，切换到清华镜像...${NC}"
        pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q
    }
else
    echo "  离线包不存在，从 PyPI 安装..."
    pip install -r requirements.txt -q 2>&1 || {
        echo -e "${YELLOW}  PyPI 连接失败，尝试清华镜像...${NC}"
        pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple -q
    }
fi
echo -e "${GREEN}✓ 依赖安装完成${NC}"

# ── 知识库检查 ──
echo ""
if [ -f "knowledge_base/vector_store.sqlite3" ]; then
    echo -e "${GREEN}✓ 知识库向量索引已就绪${NC}"
else
    echo -e "${YELLOW}注意: 未找到向量索引，部分功能（引用推荐、文献检索）可能受限${NC}"
fi

# ── 中文字体检测 ──
echo ""
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo -e "${GREEN}✓ macOS: 系统自带中文字体${NC}"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if fc-list :lang=zh 2>/dev/null | grep -q .; then
        echo -e "${GREEN}✓ 检测到中文字体${NC}"
    else
        echo -e "${YELLOW}提示: 建议安装中文字体${NC}"
        echo "  Ubuntu/Debian: sudo apt install fonts-noto-cjk"
        echo "  CentOS/RHEL: sudo dnf install google-noto-cjk-fonts"
    fi
fi

# ── 完成 ──
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  安装完成！${NC}"
echo ""
echo "  启动服务:"
echo "    source .venv/bin/activate"
echo "    python3 src/web_server.py --port 8222"
echo ""
echo "  然后打开浏览器访问: http://localhost:8222"
echo ""
echo "  首次使用请进入「许可证管理」页面开始免费试用"
echo -e "${GREEN}========================================${NC}"
