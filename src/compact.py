"""
上下文压缩模块 - 对应 learn-claude-code s06 上下文压缩机制
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CompactConfig:
    message_threshold: int = 20
    char_threshold: int = 32000
    max_message_chars: int = 2000
    max_tool_result_chars: int = 800
    keep_recent: int = 4
    max_system_chars: int = 8000


@dataclass
class ConversationSummary:
    conclusions: List[str] = field(default_factory=list)
    current_topic: Optional[str] = None
    artifacts: Dict[str, Any] = field(default_factory=dict)
    last_user_message: Optional[str] = None
    user_requirements: List[str] = field(default_factory=list)
    key_paths: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    open_tasks: List[str] = field(default_factory=list)
    compacted_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ==================== micro_compact ====================


def _extract_key_conclusions(text: str) -> str:
    if not text:
        return ""

    lines = text.splitlines()
    key_lines = []
    json_blocks = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            if len(stripped) > 10:
                json_blocks.append(stripped)
        elif any(
            stripped.startswith(p)
            for p in (
                "结论",
                "因此",
                "所以",
                "核心",
                "关键",
                "主题:",
                "框架:",
                "首先",
                "其次",
                "最后",
                "第1",
                "第2",
                "第3",
                "Summary:",
                "Conclusion:",
                "Key:",
                "First,",
                "Second,",
                "Finally,",
            )
        ):
            key_lines.append(stripped)
        elif len(stripped) < 80 and (
            "GB/T" in stripped or "APA" in stripped or "格式" in stripped
        ):
            key_lines.append(stripped)

    if key_lines:
        seen = set()
        unique = []
        for l in key_lines:
            if l not in seen:
                seen.add(l)
                unique.append(l)
        return "\n".join(unique[:20])

    if json_blocks:
        try:
            merged = json_blocks[0]
            for jb in json_blocks[1:]:
                merged += "\n" + jb
            return f"[结构化数据]\n{merged[:500]}"
        except Exception:
            pass

    if len(text) > 500:
        sentences = re.split(r"(?<=[。！？.!?])", text[:600])
        return "".join(sentences[:3]) + "..."

    return text


def _compact_tool_result(result_str: str, max_chars: int) -> str:
    if len(result_str) <= max_chars:
        return result_str
    try:
        data = json.loads(result_str)
        if isinstance(data, dict):
            compacted = {}
            for key, value in data.items():
                if isinstance(value, str) and len(value) > 200:
                    compacted[key] = value[:200] + "..."
                elif isinstance(value, (int, float, bool)):
                    compacted[key] = value
                elif isinstance(value, list) and len(value) > 5:
                    compacted[key] = f"[{len(value)} items]"
                elif isinstance(value, dict):
                    compacted[key] = f"[dict with {len(value)} keys]"
                else:
                    compacted[key] = value
            return json.dumps(compacted, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        pass
    return result_str[:max_chars] + "..."


def micro_compact_message(
    message: Dict[str, Any], config: Optional[CompactConfig] = None
) -> Dict[str, Any]:
    config = config or CompactConfig()
    result = dict(message)
    content = message.get("content", "")

    if isinstance(content, str):
        if len(content) > config.max_message_chars:
            result["content"] = _extract_key_conclusions(content)
        return result

    if message.get("role") == "assistant" and isinstance(content, list):
        new_blocks = []
        for block in content:
            if not isinstance(block, dict):
                new_blocks.append(block)
                continue
            block_type = block.get("type", "text")
            if block_type == "text":
                text = block.get("text", "")
                if len(text) > config.max_message_chars:
                    new_blocks.append(
                        {"type": "text", "text": _extract_key_conclusions(text)}
                    )
                else:
                    new_blocks.append(block)
            else:
                new_blocks.append(block)
        result["content"] = new_blocks
        return result

    if isinstance(content, list):
        new_content = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                original = item.get("content", "")
                compacted = _compact_tool_result(original, config.max_tool_result_chars)
                new_content.append({**item, "content": compacted})
            else:
                new_content.append(item)
        result["content"] = new_content

    return result


# ==================== auto_compact ====================


_PATH_RE = re.compile(r"(?:[./]?\w+(?:/\w+)+\.\w{1,6})")


def _extract_paths(text: str) -> List[str]:
    return list(dict.fromkeys(_PATH_RE.findall(text)))


def _dedupe(items: List[str], limit: int = 20) -> List[str]:
    seen = set()
    out = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out[:limit]


def _build_summary_from_history(messages: List[Dict[str, Any]]) -> ConversationSummary:
    summary = ConversationSummary()
    all_user_texts: List[str] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            text = " ".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            text = ""

        if role == "user":
            all_user_texts.append(text)
            summary.last_user_message = text

        if not text:
            continue

        paths = _extract_paths(text)
        for p in paths:
            if p not in summary.key_paths:
                summary.key_paths.append(p)

        if role == "assistant":
            if not summary.current_topic:
                m = re.search(r"主题[：:]\s*(.+?)(?:\n|$)", text)
                if m:
                    summary.current_topic = m.group(1).strip()

            for match in re.finditer(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL):
                try:
                    artifact = json.loads(match.group(1))
                    if isinstance(artifact, dict):
                        if "title" in artifact:
                            summary.artifacts.setdefault("last_framework", artifact)
                        elif "chapters" in artifact:
                            summary.artifacts.setdefault("last_outline", artifact)
                except Exception:
                    pass

            for line in text.splitlines():
                stripped = line.strip()
                if any(stripped.startswith(p) for p in ("结论", "因此", "所以", "核心", "关键")):
                    summary.conclusions.append(stripped)
                if any(kw in stripped for kw in ("决定", "确认", "采用", "方案:", "Decision:")):
                    summary.decisions.append(stripped)

    for text in all_user_texts:
        for line in text.splitlines():
            stripped = line.strip()
            if any(stripped.startswith(p) for p in ("请", "帮我", "需要", "要求", "I need", "Please")):
                summary.user_requirements.append(stripped)
        for m in re.finditer(r"(?:待办|TODO|未完成|还需要)[：:]\s*(.+)", text):
            summary.open_tasks.append(m.group(1).strip())

    summary.conclusions = _dedupe(summary.conclusions, 10)
    summary.user_requirements = _dedupe(summary.user_requirements, 20)
    summary.key_paths = _dedupe(summary.key_paths, 20)
    summary.decisions = _dedupe(summary.decisions, 10)
    summary.open_tasks = _dedupe(summary.open_tasks, 10)

    return summary


def _messages_to_prompt(summary: ConversationSummary) -> str:
    lines = [
        "# 对话历史摘要",
        f"压缩时间: {summary.compacted_at}",
        "",
    ]

    if summary.current_topic:
        lines.append(f"当前主题: {summary.current_topic}")

    if summary.user_requirements:
        lines.append("\n## 用户需求")
        for r in summary.user_requirements:
            lines.append(f"- {r}")

    if summary.key_paths:
        lines.append("\n## 涉及文件路径")
        for p in summary.key_paths:
            lines.append(f"- `{p}`")

    if summary.decisions:
        lines.append("\n## 已确认方案")
        for d in summary.decisions:
            lines.append(f"- {d}")

    if summary.open_tasks:
        lines.append("\n## 待完成任务")
        for t in summary.open_tasks:
            lines.append(f"- {t}")

    if summary.artifacts:
        lines.append("\n## 已生成的产物")
        for name, artifact in summary.artifacts.items():
            lines.append(f"### {name}")
            lines.append(json.dumps(artifact, ensure_ascii=False, indent=2)[:500])
            lines.append("")

    if summary.conclusions:
        lines.append("\n## 关键结论")
        for c in summary.conclusions:
            lines.append(f"- {c}")

    if summary.last_user_message:
        lines.append(f"\n最新用户消息: {summary.last_user_message}")

    lines.append("\n---")
    lines.append("上方是历史摘要。请根据摘要中的结论和产物继续工作。")
    lines.append("System prompt 原始内容不受影响，请参考其中的技能规则。")

    return "\n".join(lines)


def _collect_tool_use_ids(messages: List[Dict[str, Any]]) -> set:
    ids = set()
    for msg in messages:
        if msg.get("role") == "user" and isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    tid = block.get("tool_use_id")
                    if tid:
                        ids.add(tid)
    return ids


def _keep_recent_with_tool_pairs(
    messages: List[Dict[str, Any]], keep_recent: int
) -> List[Dict[str, Any]]:
    recent = list(messages[-keep_recent:])
    earlier = messages[:-keep_recent]

    tool_use_ids = _collect_tool_use_ids(recent)
    if not tool_use_ids:
        return recent

    extra = []
    for msg in reversed(earlier):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        msg_ids = set()
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                msg_ids.add(block.get("id"))
        if msg_ids & tool_use_ids:
            extra.insert(0, dict(msg))
            tool_use_ids -= msg_ids
        if not tool_use_ids:
            break

    return extra + recent


def _compact_messages(
    messages: List[Dict[str, Any]], config: CompactConfig
) -> Tuple[List[Dict[str, Any]], ConversationSummary]:
    if len(messages) <= config.keep_recent:
        return list(messages), ConversationSummary()

    recent = _keep_recent_with_tool_pairs(messages, config.keep_recent)
    earlier = messages[: len(messages) - len(recent)]

    compacted_earlier = [micro_compact_message(msg, config) for msg in earlier]

    total_chars = sum(
        len(str(m.get("content", ""))) for m in compacted_earlier + recent
    )
    if total_chars <= config.char_threshold:
        return compacted_earlier + recent, ConversationSummary()

    summary = _build_summary_from_history(messages)
    return recent, summary


def auto_compact(
    messages: List[Dict[str, Any]],
    system: str,
    config: Optional[CompactConfig] = None,
) -> Tuple[List[Dict[str, Any]], str, Optional[ConversationSummary]]:
    config = config or CompactConfig()

    total_chars = sum(len(str(m.get("content", ""))) for m in messages)
    should_compact = (
        len(messages) >= config.message_threshold
        or total_chars >= config.char_threshold
    )

    if not should_compact:
        return messages, system, None

    compacted_messages, summary = _compact_messages(messages, config)

    summary_prompt = _messages_to_prompt(summary)
    updated_system = system + "\n\n" + summary_prompt

    if len(updated_system) > config.max_system_chars:
        available = config.max_system_chars - len(system) - 10
        if available > 200:
            summary_prompt = summary_prompt[:available] + "\n...[截断]"
        else:
            summary_prompt = summary_prompt[: config.max_system_chars - 100]
        updated_system = system + "\n\n" + summary_prompt

    return compacted_messages, updated_system, summary


def compact_history(
    messages: List[Dict[str, Any]],
    system: str,
    force: bool = False,
) -> Tuple[List[Dict[str, Any]], str]:
    if not force:
        compacted, updated_system, _ = auto_compact(messages, system)
    else:
        config = CompactConfig()
        compacted, summary = _compact_messages(messages, config)
        summary_prompt = _messages_to_prompt(summary)
        updated_system = system + "\n\n" + summary_prompt
        if len(updated_system) > config.max_system_chars:
            updated_system = system[: config.max_system_chars] + "\n...[压缩]"

    return compacted, updated_system
