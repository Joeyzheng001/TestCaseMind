"""
src/__init__.py
ThesisMind 核心模块初始化
"""

__version__ = "0.1.0"
__author__ = "ThesisMind Team"
__description__ = "AI论文辅助工具 - 基于learn-claude-code框架"

from src.agent_loop import ThesisAgent
from src.tools import TOOLS

__all__ = [
    "ThesisAgent",
    "TOOLS",
    "__version__",
]
