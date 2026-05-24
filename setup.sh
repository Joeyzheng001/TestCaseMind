#!/usr/bin/env bash
# ThesisMind 跨平台安装脚本 (macOS / Linux)
# 使用方法: bash setup.sh
set -e

# cd to script directory so relative paths work regardless of CWD
cd "$(dirname "$0")"

# Re-exec with bash if invoked via sh/dash/zsh (they lack compgen, arrays, [[ ]])
if [ -z "${BASH_VERSION:-}" ]; then
    if command -v bash >/dev/null 2>&1; then
        exec bash "$0" "$@"
    else
        echo "ERROR: bash is required. Install bash and re-run: bash setup.sh"
        exit 1
    fi
fi

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo()
{
    printf '%s\n' "$*"
}

printf "${GREEN}========================================${NC}\n"
printf "${GREEN}  ThesisMind 论文辅助工作台 - 安装向导${NC}\n"
printf "${GREEN}========================================${NC}\n"
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
    printf "${RED}错误: 未找到 Python 3.9-3.14，请先安装受支持的 Python 版本${NC}\n"
    echo "  macOS: brew install python@3.12"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  CentOS/RHEL: sudo dnf install python3 python3-pip"
    exit 1
fi
printf "${GREEN}✓ Python: %s${NC}\n" "$($PYTHON --version)"

# ── 虚拟环境 ──
VENV_DIR=".venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "创建虚拟环境..."
    $PYTHON -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
printf "${GREEN}✓ 虚拟环境已激活${NC}\n"

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
        printf "${YELLOW}  本地 pip/setuptools/wheel 升级失败，继续安装依赖...${NC}\n"
    }
else
    pip install --upgrade pip setuptools wheel "${PIP_COMMON[@]}" -i https://pypi.tuna.tsinghua.edu.cn/simple || {
        printf "${YELLOW}  pip 升级失败，继续安装依赖...${NC}\n"
    }
fi

OK=0
if [ "${#PIP_LOCAL_LINKS[@]}" -gt 0 ]; then
    pip install -r requirements.txt "${PIP_COMMON[@]}" "${PIP_LOCAL_LINKS[@]}" --no-index && OK=1 || {
        printf "${YELLOW}  本地 wheel 不完整，切换到镜像源补齐缺失依赖...${NC}\n"
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
printf "${GREEN}✓ 依赖安装完成${NC}\n"

# ── 知识库检查 ──
echo ""
if [ -f "knowledge_base/vector_store.sqlite3" ]; then
    printf "${GREEN}✓ 知识库向量索引已就绪${NC}\n"
else
    printf "${YELLOW}注意: 未找到向量索引，部分功能（引用推荐、文献检索）可能受限${NC}\n"
fi

# ── 配置文件 ──
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    printf "${YELLOW}! 配置文件已创建，请编辑 .env 填写 API Key${NC}\n"
fi

# ── 中文字体检测 ──
echo ""
if [[ "$OSTYPE" == "darwin"* ]]; then
    printf "${GREEN}✓ macOS: 系统自带中文字体${NC}\n"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    if fc-list :lang=zh 2>/dev/null | grep -q .; then
        printf "${GREEN}✓ 检测到中文字体${NC}\n"
    else
        printf "${YELLOW}提示: 建议安装中文字体${NC}\n"
        echo "  Ubuntu/Debian: sudo apt install fonts-noto-cjk"
        echo "  CentOS/RHEL: sudo dnf install google-noto-cjk-fonts"
    fi
fi

# ── 完成 ──
echo ""
printf "${GREEN}========================================${NC}\n"
printf "${GREEN}  安装完成！${NC}\n"
echo ""
echo "  启动服务:"
echo "    source .venv/bin/activate"
echo "    python3 src/web_server.py --port 8222"
echo ""
echo "  然后打开浏览器访问: http://localhost:8222"
echo ""
echo "  首次使用请进入「许可证管理」页面开始免费试用"
printf "${GREEN}========================================${NC}\n"
