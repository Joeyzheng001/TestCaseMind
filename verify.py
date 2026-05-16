#!/usr/bin/env python3
"""
ThesisMind 验证脚本
检查环境、依赖和基础功能是否正确配置
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from src.llm_config import load_llm_config


def print_header(text):
    """打印带格式的标题"""
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}\n")


def check_python_version():
    """检查Python版本"""
    print("✓ 检查 Python 版本...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"  ✅ Python {version.major}.{version.minor}.{version.micro} - OK")
        return True
    else:
        print(f"  ❌ Python {version.major}.{version.minor} - 需要 3.8+")
        return False


def check_dependencies():
    """检查依赖包"""
    print("\n✓ 检查依赖包...")
    required_packages = [
        ("anthropic", "Anthropic API"),
        ("dotenv", "Environment variables"),
        ("yaml", "YAML parsing"),
    ]

    all_ok = True
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package} - {description}")
        except ImportError:
            print(f"  ❌ {package} - 未安装")
            all_ok = False

    return all_ok


def check_environment():
    """检查环境变量"""
    print("\n✓ 检查环境变量...")
    load_dotenv()

    config = load_llm_config()
    api_key = config.api_key
    if api_key and api_key != "your_api_key_here":
        masked_key = f"{api_key[:7]}...{api_key[-7:]}"
        print(f"  ✅ ANTHROPIC_API_KEY - {masked_key}")
        print(f"  ✅ Provider - {config.provider}")
        print(f"  ✅ Model - {config.model}")
        if config.base_url:
            print(f"  ✅ Base URL - {config.base_url}")
        print(f"  ✅ Auth Mode - {config.auth_mode}")
        return True
    else:
        print(f"  ❌ ANTHROPIC_API_KEY - 未配置或无效")
        print(f"     请在 .env 文件中设置有效的 API Key")
        return False


def check_project_structure():
    """检查项目结构"""
    print("\n✓ 检查项目结构...")

    required_dirs = [
        "src",
        "agents",
        "skills",
        "knowledge_base",
        "output",
        "logs",
    ]

    required_files = [
        "README.md",
        "docs/architecture/ARCHITECTURE.md",
        "docs/product/QUICKSTART.md",
        "requirements.txt",
        ".env.example",
        "src/agent_loop.py",
        "src/tools.py",
    ]

    project_root = Path(__file__).parent

    all_ok = True
    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print(f"  ✅ 目录 {dir_name}/")
        else:
            print(f"  ❌ 目录 {dir_name}/ - 不存在")
            all_ok = False

    for file_name in required_files:
        file_path = project_root / file_name
        if file_path.exists():
            print(f"  ✅ 文件 {file_name}")
        else:
            print(f"  ❌ 文件 {file_name} - 不存在")
            all_ok = False

    return all_ok


def test_llm_api():
    """测试LLM API连接"""
    print("\n✓ 测试 LLM API 连接...")

    try:
        from anthropic import Anthropic

        config = load_llm_config()
        client_kwargs = {"api_key": config.api_key}
        if config.auth_mode == "auth_token" and config.auth_token:
            client_kwargs["auth_token"] = config.auth_token
        else:
            os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
        if config.base_url:
            client_kwargs["base_url"] = config.base_url

        client = Anthropic(**client_kwargs)

        # 简单的测试请求
        response = client.messages.create(
            model=config.model,
            max_tokens=100,
            messages=[
                {
                    "role": "user",
                    "content": "Say 'ThesisMind setup successful' in exactly these words.",
                }
            ],
        )

        response_text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )

        if "ThesisMind setup successful" in response_text:
            print(f"  ✅ API 连接成功 ({config.provider}, {config.model})")
            return True
        else:
            print(f"  ⚠️  API 响应异常: {response_text[:50]}...")
            return True  # 连接成功，只是响应不符合预期

    except Exception as e:
        print(f"  ❌ API 连接失败: {str(e)}")
        return False


def test_tools():
    """测试基础工具"""
    print("\n✓ 测试基础工具...")

    try:
        from src.tools import (
            build_knowledge_index,
            convert_local_document,
            generate_research_framework,
            generate_outline,
            format_citation,
            search_knowledge_base,
        )

        # 测试框架生成
        framework = generate_research_framework("测试主题", "computer_science")
        if "research_phases" in framework:
            print(f"  ✅ generate_research_framework - OK")
        else:
            print(f"  ⚠️  generate_research_framework - 返回异常")

        # 测试大纲生成
        outline = generate_outline(framework)
        if "chapters" in outline:
            print(f"  ✅ generate_outline - OK")
        else:
            print(f"  ⚠️  generate_outline - 返回异常")

        # 测试引用格式化
        citation = format_citation("Smith", "2020", "Test Paper", "apa")
        if citation:
            print(f"  ✅ format_citation - OK")
        else:
            print(f"  ⚠️  format_citation - 返回异常")

        # 测试本地向量知识库
        test_db_path = "output/verify_vector_store.sqlite3"
        index_info = build_knowledge_index(
            source_dirs=["skills"], db_path=test_db_path, reset=True
        )
        if index_info.get("documents", 0) > 0:
            print(f"  ✅ build_knowledge_index - OK")
        else:
            print(f"  ⚠️  build_knowledge_index - 未索引到文档")

        search_result = search_knowledge_base("论文引用格式", limit=1, db_path=test_db_path)
        if search_result.get("results"):
            print(f"  ✅ search_knowledge_base - OK")
        else:
            print(f"  ⚠️  search_knowledge_base - 未检索到结果")

        if callable(convert_local_document):
            print(f"  ✅ convert_local_document - OK")

        return True

    except Exception as e:
        print(f"  ❌ 工具测试失败: {str(e)}")
        return False


def print_summary(results):
    """打印总结"""
    print_header("验证总结")

    checks = [
        ("Python版本", results["python"]),
        ("依赖包", results["dependencies"]),
        ("环境变量", results["env"]),
        ("项目结构", results["structure"]),
        ("API连接", results["api"]),
        ("基础工具", results["tools"]),
    ]

    passed = sum(1 for _, result in checks if result)
    total = len(checks)

    for name, result in checks:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")

    print(f"\n  总体: {passed}/{total} 检查通过")

    if passed == total:
        print("\n  🎉 所有检查通过！系统已就绪。")
        print("\n  📝 后续步骤:")
        print("     1. python init.py          # 初始化项目")
        print("     2. python -m src.agent_loop # 启动Agent")
        return True
    else:
        print("\n  ⚠️  请解决上述问题后重试")
        return False


def main():
    """主函数"""
    print_header("🎓 ThesisMind 系统验证")

    results = {
        "python": check_python_version(),
        "dependencies": check_dependencies(),
        "env": check_environment(),
        "structure": check_project_structure(),
        "api": False,  # 初始化为False
        "tools": False,
    }

    # 基础工具不需要API Key，先做离线验证
    if results["dependencies"]:
        results["tools"] = test_tools()

    # 只有在依赖和环境OK时才测试API
    if results["dependencies"] and results["env"]:
        results["api"] = test_llm_api()

    # 打印总结
    success = print_summary(results)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
