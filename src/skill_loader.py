"""
技能加载器 - 对应 learn-claude-code s05 Skills 机制
将 skills/*.md 解析为结构化技能，供 Agent 实时消费
"""

import re
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

FRONTMATTER_RE = re.compile(r"^\s*---\s*\n(.*?)\n\s*---\s*\n", re.DOTALL | re.MULTILINE)
SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


def _parse_frontmatter(raw: str) -> Dict[str, Any]:
    """解析 YAML frontmatter"""
    match = FRONTMATTER_RE.search(raw)
    if not match:
        return {}
    try:
        meta = yaml.safe_load(match.group(1))
        return meta if isinstance(meta, dict) else {}
    except yaml.YAMLError:
        return {}


def _strip_frontmatter(content: str) -> str:
    return FRONTMATTER_RE.sub("", content, count=1)


def _extract_sections(content: str) -> List[Dict[str, Any]]:
    """将 Markdown 内容按 ## 标题拆分为 sections"""
    lines = content.splitlines()
    sections = []
    current: Dict[str, Any] = {"title": "", "level": 0, "content": []}

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            if current["content"] or current["title"]:
                sections.append(current)
            level = 2 if stripped.startswith("## ") else 3
            current = {"title": stripped.lstrip("#").strip(), "level": level, "content": []}
        else:
            current["content"].append(line)

    if current["content"] or current["title"]:
        sections.append(current)

    # 把 content 合并为字符串，过滤空行
    for s in sections:
        s["content"] = "\n".join(s["content"]).strip()
    return sections


class Skill:
    """单个技能对象"""

    def __init__(self, name: str, meta: Dict[str, Any], sections: List[Dict[str, Any]]):
        self.name = name
        self.meta = meta
        self.sections = sections

    @property
    def topics(self) -> List[str]:
        return self.meta.get("topics", [])

    @property
    def tags(self) -> List[str]:
        return self.meta.get("tags", [])

    @property
    def priority(self) -> str:
        return self.meta.get("priority", "normal")

    def get_section(self, title: str) -> Optional[str]:
        """按标题查找 section 内容"""
        for s in self.sections:
            if title.lower() in s["title"].lower():
                return s["content"]
        return None

    def to_prompt(self, section_filter: Optional[List[str]] = None) -> str:
        """将技能格式化为可注入 System Prompt 的文本"""
        lines = [f"# {self.name}\n"]
        for s in self.sections:
            if section_filter and not any(
                kw.lower() in s["title"].lower() for kw in section_filter
            ):
                continue
            if not s["content"]:
                continue
            lines.append(f"## {s['title']}\n{s['content']}\n")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "meta": self.meta,
            "sections": self.sections,
        }


class SkillLoader:
    """技能加载器"""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self._registry: Dict[str, Skill] = {}
        self._topics_index: Dict[str, List[str]] = {}  # topic -> [skill_name, ...]
        self._tags_index: Dict[str, List[str]] = {}
        self._loaded = False

    def load_all(self) -> "SkillLoader":
        """扫描 skills_dir 下所有 .md 文件并解析"""
        if not self.skills_dir.exists():
            return self

        for path in sorted(self.skills_dir.glob("*.md")):
            skill = self._load_skill(path)
            if skill:
                self._register(skill)

        self._loaded = True
        return self

    def _load_skill(self, path: Path) -> Optional[Skill]:
        name = path.stem  # 文件名作为技能名
        try:
            raw = path.read_text(encoding="utf-8")
        except Exception:
            return None

        meta = _parse_frontmatter(raw)
        content = _strip_frontmatter(raw)
        sections = _extract_sections(content)

        return Skill(name=name, meta=meta, sections=sections)

    def _register(self, skill: Skill) -> None:
        self._registry[skill.name] = skill
        for topic in skill.topics:
            self._topics_index.setdefault(topic, []).append(skill.name)
        for tag in skill.tags:
            self._tags_index.setdefault(tag, []).append(skill.name)

    def get(self, name: str) -> Optional[Skill]:
        return self._registry.get(name)

    def get_by_topic(self, topic: str) -> List[Skill]:
        names = self._topics_index.get(topic, [])
        return [self._registry[n] for n in names if n in self._registry]

    def get_by_tag(self, tag: str) -> List[Skill]:
        names = self._tags_index.get(tag, [])
        return [self._registry[n] for n in names if n in self._registry]

    def search(self, query: str) -> List[Skill]:
        """按 query 模糊匹配技能名、topic、tag"""
        query_lower = query.lower()
        results = []
        for name, skill in self._registry.items():
            if query_lower in name.lower():
                results.append(skill)
                continue
            if any(query_lower in t.lower() for t in skill.topics):
                results.append(skill)
                continue
            if any(query_lower in t.lower() for t in skill.tags):
                results.append(skill)
        return results

    def list_all(self) -> List[str]:
        return sorted(self._registry.keys())

    def inject_into_system(
        self, base_system: str, skills: Optional[List[str]] = None
    ) -> str:
        """
        将指定技能内容追加到 system prompt 末尾。

        Args:
            base_system: 原始 system prompt
            skills: None=全部注入, []=不注入, ["x"]=只注入指定技能
        """
        if not self._loaded:
            self.load_all()

        if skills is None:
            names = self.list_all()
        else:
            names = skills

        if not names:
            return base_system

        lines = [base_system.strip(), "\n\n# 可用技能\n"]
        for name in names:
            skill = self.get(name)
            if not skill:
                continue
            lines.append(skill.to_prompt())

        return "\n".join(lines)

    def get_skill_summary(self) -> str:
        """获取所有技能的简洁摘要，用于调试和日志"""
        if not self._loaded:
            self.load_all()

        items = []
        for name in self.list_all():
            skill = self.get(name)
            items.append(f"- **{name}** (priority: {skill.priority})")
            items.append(f"  topics: {', '.join(skill.topics)}")
            items.append(f"  sections: {len(skill.sections)}")
        return "\n".join(items) if items else "No skills loaded"


# ==================== 工具级函数 ====================


_loader: Optional[SkillLoader] = None


def load_skill(skill_name: Optional[str] = None) -> Dict[str, Any]:
    """
    加载单个或全部技能。

    Args:
        skill_name: 单个技能名，为空则加载全部
    """
    global _loader
    if _loader is None:
        _loader = SkillLoader().load_all()

    if skill_name:
        skill = _loader.get(skill_name)
        if not skill:
            return {"error": f"Skill not found: {skill_name}"}
        return skill.to_dict()

    return {
        "skills": _loader.list_all(),
        "summary": _loader.get_skill_summary(),
    }


def inject_skills_to_prompt(
    base_system: str, skill_names: Optional[List[str]] = None
) -> str:
    """将技能内容注入到 system prompt"""
    global _loader
    if _loader is None:
        _loader = SkillLoader().load_all()
    return _loader.inject_into_system(base_system, skill_names)


def search_skills(query: str) -> List[Dict[str, Any]]:
    """搜索技能"""
    global _loader
    if _loader is None:
        _loader = SkillLoader().load_all()

    return [s.to_dict() for s in _loader.search(query)]


def get_skills_for_task(task_keywords: List[str]) -> List[str]:
    """
    根据任务关键词返回最相关的技能名列表。

    Args:
        task_keywords: 如 ["引用", "格式", "APA"]
    """
    global _loader
    if _loader is None:
        _loader = SkillLoader().load_all()

    matched_names: Dict[str, int] = {}
    for kw in task_keywords:
        for skill in _loader.search(kw):
            matched_names[skill.name] = matched_names.get(skill.name, 0) + 1

    # 按匹配次数降序
    return sorted(matched_names, key=lambda n: matched_names[n], reverse=True)


# ==================== 初始化调用 ====================


if __name__ == "__main__":
    loader = SkillLoader().load_all()
    print("Loaded skills:")
    print(loader.get_skill_summary())
    print("\nSkill lookup test:")
    s = loader.get("CITATION")
    if s:
        print(f"  CITATION has {len(s.sections)} sections")
        print(f"  topics: {s.topics}")
