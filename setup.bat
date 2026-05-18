@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ========================================
echo   ThesisMind 论文辅助工作台 - 安装向导
echo ========================================
echo.

:: Python 检测
set PYTHON=
for %%p in (python3 python) do (
    where %%p >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=2 delims=." %%v in ('%%p -c "import sys; print(sys.version_info.minor)"') do (
            set PYTHON=%%p
        )
    )
)

if "%PYTHON%"=="" (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    echo   下载: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python 已检测到

:: 虚拟环境
if not exist ".venv" (
    echo 创建虚拟环境...
    %PYTHON% -m venv .venv
)
call .venv\Scripts\activate.bat
echo [OK] 虚拟环境已激活

:: 依赖安装
echo 安装依赖包...
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo [OK] 依赖安装完成

:: 知识库检查
echo.
if exist "knowledge_base\vector_store.sqlite3" (
    echo [OK] 知识库向量索引已就绪
) else (
    echo [注意] 未找到向量索引，部分功能可能受限
)

:: 完成
echo.
echo ========================================
echo   安装完成！
echo.
echo   启动服务:
echo     .venv\Scripts\activate
echo     python src\web_server.py --port 8222
echo.
echo   然后打开浏览器访问: http://localhost:8222
echo   首次使用请进入「许可证管理」页面开始免费试用
echo ========================================
pause
