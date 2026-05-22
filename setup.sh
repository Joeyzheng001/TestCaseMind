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
        if [ "$major" -eq 3 ] && [ "$minor" -ge 9 ] && [ "$minor" -le 14 ]; then
            PYTHON=$cmd
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${RED}错误: 未找到 Python 3.9-3.14，请先安装受支持的 Python 版本${NC}"
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
PIP_COMMON=(--disable-pip-version-check --retries 5 --timeout 60 --prefer-binary)
PIP_LOCAL_LINKS=()

if compgen -G "wheels/*.whl" > /dev/null; then
    PIP_LOCAL_LINKS+=(--find-links=wheels)
fi

if compgen -G "*.whl" > /dev/null; then
    PIP_LOCAL_LINKS+=(--find-links=.)
fi

if [ "${#PIP_LOCAL_LINKS[@]}" -gt 0 ]; then
    echo "  检测到本地 wheel，优先使用本地包..."
    pip install --upgrade pip setuptools wheel "${PIP_COMMON[@]}" "${PIP_LOCAL_LINKS[@]}" --no-index || {
        echo -e "${YELLOW}  本地 pip/setuptools/wheel 升级失败，继续安装依赖...${NC}"
    }
else
    pip install --upgrade pip setuptools wheel "${PIP_COMMON[@]}" -i https://pypi.tuna.tsinghua.edu.cn/simple || {
        echo -e "${YELLOW}  pip 升级失败，继续安装依赖...${NC}"
    }
fi

OK=0
if [ "${#PIP_LOCAL_LINKS[@]}" -gt 0 ]; then
    pip install -r requirements.txt "${PIP_COMMON[@]}" "${PIP_LOCAL_LINKS[@]}" --no-index && OK=1 || {
        echo -e "${YELLOW}  本地 wheel 不完整，切换到镜像源补齐缺失依赖...${NC}"
    }
fi

if [ "$OK" -eq 0 ]; then
    pip install -r requirements.txt "${PIP_COMMON[@]}" "${PIP_LOCAL_LINKS[@]}" -i https://pypi.tuna.tsinghua.edu.cn/simple && OK=1 || true
fi
if [ "$OK" -eq 0 ]; then
    pip install -r requirements.txt "${PIP_COMMON[@]}" "${PIP_LOCAL_LINKS[@]}" -i https://mirrors.aliyun.com/pypi/simple && OK=1 || true
fi
if [ "$OK" -eq 0 ]; then
    pip install -r requirements.txt "${PIP_COMMON[@]}" "${PIP_LOCAL_LINKS[@]}" -i https://pypi.org/simple
fi
echo -e "${GREEN}✓ 依赖安装完成${NC}"

# ── 知识库检查 ──
echo ""
if [ -f "knowledge_base/vector_store.sqlite3" ]; then
    echo -e "${GREEN}✓ 知识库向量索引已就绪${NC}"
else
    echo -e "${YELLOW}注意: 未找到向量索引，部分功能（引用推荐、文献检索）可能受限${NC}"
fi

# ── 配置文件 ──
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo -e "${YELLOW}! 配置文件已创建，请编辑 .env 填写 API Key${NC}"
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
echo "    python3 src/web_server.py --port 8765"
echo ""
echo "  然后打开浏览器访问: http://localhost:8765"
echo ""
echo "  首次使用请进入「许可证管理」页面开始免费试用"
echo -e "${GREEN}========================================${NC}"
