"""
创建项目初始化脚本
"""

import os
import sys
from pathlib import Path


def init_project():
    """初始化项目结构和文件"""

    project_root = Path(__file__).parent

    # 创建必要的目录
    dirs = [
        "src",
        "agents",
        "skills",
        "knowledge_base",
        "knowledge_base/papers",
        "knowledge_base/templates",
        "knowledge_base/references",
        "tools",
        "templates",
        "docs",
        "output",
        "logs",
    ]

    for dir_path in dirs:
        full_path = project_root / dir_path
        full_path.mkdir(exist_ok=True)
        print(f"✓ Created directory: {dir_path}")

    # 创建初始化文件
    init_files = {
        "src/__init__.py": "# ThesisMind 核心模块\n",
        "agents/__init__.py": "# Agent 实现模块\n",
        "skills/__init__.py": "# 技能库模块\n",
        "tools/__init__.py": "# 工具模块\n",
        "templates/__init__.py": "# 模板模块\n",
    }

    for file_path, content in init_files.items():
        full_path = project_root / file_path
        if not full_path.exists():
            full_path.write_text(content, encoding="utf-8")
            print(f"✓ Created file: {file_path}")

    # 创建日志目录
    log_dir = project_root / "logs"
    log_dir.mkdir(exist_ok=True)

    print("\n✨ 项目初始化完成!")
    print(f"📁 项目路径: {project_root}")
    print("\n📝 后续步骤:")
    print("1. 配置环境变量: cp .env.example .env")
    print("2. 填写 ANTHROPIC_API_KEY")
    print("3. 安装依赖: pip install -r requirements.txt")
    print("4. 运行 Agent: python -m src.agent_loop")


if __name__ == "__main__":
    init_project()
