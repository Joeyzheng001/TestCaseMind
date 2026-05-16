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
pip install -r requirements.txt -q
echo -e "${GREEN}✓ 依赖安装完成${NC}"

# ── 资产解密 ──
echo ""
if [ -d "assets_enc" ]; then
    echo -e "${YELLOW}提示: 检测到加密资产包 (assets_enc/)${NC}"
    echo "资产将在首次启动服务时自动解密"
else
    echo -e "${YELLOW}提示: 未找到加密资产包，系统将以受限模式运行${NC}"
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
