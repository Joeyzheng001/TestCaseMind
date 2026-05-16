"""
论文Agent主循环
对应 learn-claude-code s01 The Agent Loop
"""

import os
import json
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from anthropic import Anthropic

# 加载环境变量
load_dotenv()

# 导入工具和License管理
from src.tools import TOOLS
from src.license_manager import LicenseManager, TrialLicense
from src.llm_config import load_llm_config
from src.skill_loader import inject_skills_to_prompt
from src.compact import auto_compact, CompactConfig

# ==================== 系统提示词 ====================

BASE_SYSTEM_PROMPT = """你是一个专业的AI论文辅助系统，名叫ThesisMind。

你的职责：
1. 帮助用户进行论文写作和研究
2. 生成研究框架和论文大纲
3. 管理引用文献
4. 检查文档格式
5. 检测AIGC内容
6. 协助内容扩写

当用户提出需求时，使用可用的工具来完成任务。

可用工具：
- read_file: 读取文件
- write_file: 写入文件
- generate_research_framework: 生成研究框架
- generate_outline: 生成论文大纲
- format_citation: 格式化引用
- search_citations: 搜索文献
- build_knowledge_index: 构建本地向量知识库
- search_knowledge_base: 检索本地知识库
- convert_local_document: 转换本地PDF/DOCX为Markdown或文本
- check_document_format: 检查格式

说话风格：
- 学术且专业
- 提供具体建议
- 解释论文写作的最佳实践
- 鼓励原创思维
"""

# ==================== Agent 主类 ====================


class ThesisAgent:
    """论文辅助Agent"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        skip_license_check: bool = False,
        skills: Optional[List[str]] = None,
    ):
        """
        初始化Agent

        Args:
            api_key: Anthropic API key (默认从环境变量读取)
            skip_license_check: 跳过License检查 (仅用于测试)
            skills: 技能名列表。None=加载全部, []=不加载任何, ["x"]=只加载指定技能
        """
        self.llm_config = load_llm_config(api_key=api_key)
        self.api_key = self.llm_config.api_key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        # License检查
        if not skip_license_check:
            self._check_license()

        client_kwargs = {"api_key": self.api_key}
        if self.llm_config.auth_mode == "auth_token" and self.llm_config.auth_token:
            client_kwargs["auth_token"] = self.llm_config.auth_token
        else:
            os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)
        if self.llm_config.base_url:
            client_kwargs["base_url"] = self.llm_config.base_url

        self.client = Anthropic(**client_kwargs)
        self.model = self.llm_config.model
        self.messages = []  # 对话历史
        self.license_manager = LicenseManager()

        # 技能注入: skills=None 加载全部, skills=[] 不注入, skills=["x"] 只注入指定
        if skills is None:
            self.system = inject_skills_to_prompt(BASE_SYSTEM_PROMPT, None)
        elif len(skills) == 0:
            self.system = BASE_SYSTEM_PROMPT
        else:
            self.system = inject_skills_to_prompt(BASE_SYSTEM_PROMPT, skills)
        self._base_system = self.system

        # 上下文压缩配置
        self.compact_config = CompactConfig()

        # 工具调度表 — 一次构建，避免每次 _run_tool 重复创建 lambda
        self._tool_dispatch = self._build_tool_dispatch()

        # 工具 JSON Schema — 一次构建，避免每次 API 调用重复生成
        self._tools_schema = self._build_tools_schema()

    def _check_license(self):
        """检查并验证License"""
        manager = LicenseManager()

        # 首先检查是否有激活的License
        found, license_code, info = manager.load_license()

        if found:
            # 验证License有效性
            is_valid, license_info = manager.validate_license(license_code)
            if is_valid:
                print(f"✓ License activated: {license_info['type']}")
                self.license_info = license_info
                return
            else:
                print(f"✗ License expired or invalid: {license_info.get('error')}")

        # 检查试用License
        trial_valid, trial_info = TrialLicense.check()
        if trial_valid:
            print(f"✓ Using trial license ({trial_info['days_left']} days left)")
            return

        # 都没有有效的License，创建试用
        print("\n" + "=" * 60)
        print("📋 ThesisMind - Commercial License Required")
        print("=" * 60)
        print("\nNo valid license found. Creating trial license...\n")

        success, msg = TrialLicense.start()
        if success:
            print(f"✓ {msg}\n")
            print("To activate with a paid license, use:")
            print("  python -m src.license_cli activate <LICENSE_CODE>\n")
            print("To get your license, visit:")
            print("  https://www.thesismind.com/license\n")
        else:
            print(f"✗ Failed to create trial license: {msg}")
            raise RuntimeError("Cannot continue without a valid license")

    def is_feature_allowed(self, feature: str) -> bool:
        """
        检查功能是否被当前License允许

        Args:
            feature: 功能名称 (basic, advanced, business)

        Returns:
            True如果功能被允许
        """
        allowed, _ = self.license_manager.check_feature(feature)
        return allowed

    def _build_tool_dispatch(self) -> Dict[str, Any]:
        """构建工具调度表 — 每个工具名映射到一个接受 tool_input 的可调用对象"""
        t = TOOLS
        return {
            "read_file": lambda ti: t["read_file"]["handler"](ti.get("file_path", "")),
            "write_file": lambda ti: t["write_file"]["handler"](
                ti.get("file_path", ""), ti.get("content", "")
            ),
            "list_directory": lambda ti: t["list_directory"]["handler"](ti.get("dir_path", "./")),
            "analyze_paper_structure": lambda ti: t["analyze_paper_structure"]["handler"](
                ti.get("paper_content", "")
            ),
            "extract_paper_metadata": lambda ti: t["extract_paper_metadata"]["handler"](
                ti.get("paper_file", "")
            ),
            "generate_research_framework": lambda ti: t["generate_research_framework"]["handler"](
                ti.get("topic", ""), ti.get("discipline", "general")
            ),
            "generate_outline": lambda ti: t["generate_outline"]["handler"](
                ti.get("framework", {}), ti.get("depth", 3)
            ),
            "format_citation": lambda ti: t["format_citation"]["handler"](
                ti.get("author", ""), ti.get("year", ""),
                ti.get("title", ""), ti.get("style", "apa")
            ),
            "search_citations": lambda ti: t["search_citations"]["handler"](
                ti.get("keyword", ""), ti.get("limit", 10)
            ),
            "build_knowledge_index": lambda ti: t["build_knowledge_index"]["handler"](
                ti.get("source_dirs", None), ti.get("db_path", None), ti.get("reset", False)
            ),
            "search_knowledge_base": lambda ti: t["search_knowledge_base"]["handler"](
                ti.get("query", ""), ti.get("limit", 5), ti.get("db_path", None)
            ),
            "convert_local_document": lambda ti: t["convert_local_document"]["handler"](
                ti.get("file_path", ""), ti.get("output_dir", None), ti.get("output_format", "md")
            ),
            "check_document_format": lambda ti: t["check_document_format"]["handler"](
                ti.get("file_path", "")
            ),
            "run_command": lambda ti: t["run_command"]["handler"](
                ti.get("command", ""), ti.get("cwd", None)
            ),
        }

    def _build_tools_schema(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": name,
                "description": tool["description"],
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "file_path": {"type": "string"},
                        "content": {"type": "string"},
                        "topic": {"type": "string"},
                        "framework": {"type": "object"},
                        "author": {"type": "string"},
                        "year": {"type": "string"},
                        "title": {"type": "string"},
                        "style": {"type": "string"},
                        "keyword": {"type": "string"},
                        "limit": {"type": "integer"},
                        "phases": {"type": "array"},
                        "depth": {"type": "integer"},
                        "discipline": {"type": "string"},
                        "dir_path": {"type": "string"},
                        "command": {"type": "string"},
                        "cwd": {"type": "string"},
                        "source_dirs": {"type": "array", "items": {"type": "string"}},
                        "db_path": {"type": "string"},
                        "reset": {"type": "boolean"},
                        "output_dir": {"type": "string"},
                        "output_format": {"type": "string"},
                    },
                    "required": [],
                },
            }
            for name, tool in TOOLS.items()
        ]

    def _run_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        """执行单个工具并返回结果字符串"""
        fn = self._tool_dispatch.get(tool_name)
        if fn is None:
            return f"工具不存在: {tool_name}"
        try:
            return fn(tool_input)
        except Exception as e:
            return f"Error: {str(e)}"

    def run(self, user_message: str) -> str:
        """
        运行Agent循环

        Implements s01: The Agent Loop

        Args:
            user_message: 用户输入

        Returns:
            Agent的最终响应
        """
        # 添加用户消息到历史
        self.messages.append({"role": "user", "content": user_message})

        # s06: 自动上下文压缩检测 — 更新 self.messages 和 self.system
        self.messages, self.system, compaction_summary = auto_compact(
            self.messages, self.system, self.compact_config
        )
        if compaction_summary:
            print(f"  [上下文已压缩: {compaction_summary.compacted_at}]")

        print(f"\n👤 用户: {user_message}")

        # Agent循环
        while True:
            # 调用Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.system,
                messages=self.messages,
                tools=self._tools_schema,
            )

            # 添加助手响应到历史
            self.messages.append({"role": "assistant", "content": response.content})

            # 检查停止原因
            if response.stop_reason == "end_turn":
                # 提取文本响应
                text_response = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text_response += block.text

                print(f"\n🤖 助手: {text_response}")
                return text_response

            elif response.stop_reason == "tool_use":
                # 处理工具调用
                tool_results = []

                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input
                        tool_use_id = block.id

                        print(f"\n🔧 使用工具: {tool_name}")
                        print(
                            f"   参数: {json.dumps(tool_input, ensure_ascii=False, indent=2)}"
                        )

                        # 执行工具
                        output = self._run_tool(tool_name, tool_input)

                        # 将结果转换为字符串
                        if isinstance(output, dict):
                            output_str = json.dumps(
                                output, ensure_ascii=False, indent=2
                            )
                        else:
                            output_str = str(output)

                        print(f"   结果: {output_str[:200]}...")

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": output_str,
                            }
                        )

                # 添加工具结果到消息历史
                self.messages.append({"role": "user", "content": tool_results})
            else:
                # 其他停止原因
                print(f"Unexpected stop reason: {response.stop_reason}")
                break

        return "Agent循环异常结束"

    def clear_history(self):
        """清空对话历史"""
        self.messages = []
        self.system = self._base_system
        print("✓ 对话历史已清空")


# ==================== 交互式CLI ====================


def main():
    """主函数 - 交互式CLI"""
    print("=" * 60)
    print("🎓 ThesisMind - AI论文辅助系统")
    print("=" * 60)
    print("输入 'exit' 退出，输入 'clear' 清空历史\n")

    agent = ThesisAgent()

    while True:
        try:
            user_input = input("\n📝 你: ").strip()

            if not user_input:
                continue

            if user_input.lower() == "exit":
                print("👋 再见!")
                break

            if user_input.lower() == "clear":
                agent.clear_history()
                continue

            # 运行Agent
            agent.run(user_input)

        except KeyboardInterrupt:
            print("\n\n👋 被中断，再见!")
            break
        except Exception as e:
            print(f"❌ 发生错误: {str(e)}")
            continue


if __name__ == "__main__":
    main()
