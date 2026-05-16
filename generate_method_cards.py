#!/usr/bin/env python3
"""批量生成方法论卡片 — 从 cleaned MD 引用 + LLM 自动生成 cards/methods/"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from anthropic import Anthropic
from llm_config import load_llm_config

PROJECT_ROOT = Path(__file__).resolve().parent
CARDS_METHODS = PROJECT_ROOT / "cards" / "methods"
CLEANED_ROOT = PROJECT_ROOT / "knowledge_base" / "references" / "cleaned" / "methodologies"

# 方法名 → 搜索关键词（用于匹配 cleaned MD 文件夹）
METHODS = [
    ("CMMI 2.0", ["CMMI", "能力成熟度"], "discover"),
    ("PDCA循环", ["PDCA", "戴明环"], "solve"),
    ("文献研究法", ["文献研究"], "discover"),
    ("问卷调查法", ["问卷调查", "问卷"], "discover"),
    ("德尔菲法", ["德尔菲"], "discover"),
    ("层次分析法 AHP", ["层次分析", "AHP"], "discover"),
    ("模糊综合评价 FCE", ["模糊综合", "FCE", "模糊评价"], "validate"),
    ("准实验研究设计", ["准实验", "实验研究设计"], "validate"),
    ("双重差分 DID", ["双重差分", "DID"], "validate"),
    ("Gompertz增长模型", ["Gompertz", "增长模型"], "validate"),
    ("鱼骨图", ["鱼骨图", "因果图", "石川"], "discover"),
    ("5W1H", ["5W1H", "5W"], "discover"),
    ("根因分析法", ["根因分析", "根因"], "discover"),
    ("流程优化法", ["流程优化", "流程改善"], "solve"),
    ("质量管理理论", ["质量管理理论", "质量理论"], "discover"),
    ("标杆分析法", ["标杆分析", "标杆"], "discover"),
    ("案例研究法", ["案例研究"], "discover"),
]

SKIP_EXISTING = True  # 跳过已生成的卡片


def find_context(method_name: str, keywords: list[str]) -> str:
    """从 cleaned MD 中找到相关上下文。"""
    if not CLEANED_ROOT.exists():
        return ""

    snippets = []
    for subdir in sorted(CLEANED_ROOT.iterdir()):
        if not subdir.is_dir():
            continue
        dir_name = subdir.name.lower()
        # 匹配：目录名包含关键词，或方法名
        matched = any(
            kw.lower() in dir_name or kw.lower() in method_name.lower()
            for kw in keywords
        )
        if not matched:
            continue

        for md_file in sorted(subdir.glob("*.md"))[:3]:  # 最多取3篇
            try:
                text = md_file.read_text(encoding="utf-8")
                # 取前 2000 字符作为上下文
                snippets.append(
                    f"### 来源: {md_file.relative_to(PROJECT_ROOT)}\n{text[:2000]}"
                )
            except Exception:
                pass

    return "\n\n---\n\n".join(snippets[:5])  # 最多5段


def safe_id(name: str) -> str:
    """从中文名提取英文 ID。"""
    import re as _re
    eng = _re.findall(r"[A-Za-z0-9]+", name)
    if eng:
        return "_".join(e.lower() for e in eng[:2])
    # 拼音映射
    slug_map = {
        "层": "ceng", "次": "ci", "分": "fen", "析": "xi", "法": "fa",
        "模": "mo", "糊": "hu", "综": "zong", "合": "he", "评": "ping",
        "价": "jia", "问": "wen", "卷": "juan", "调": "diao", "查": "cha",
        "德": "de", "尔": "er", "菲": "fei", "实": "shi", "验": "yan",
        "研": "yan", "究": "jiu", "管": "guan", "理": "li", "质": "zhi",
        "量": "liang", "风": "feng", "险": "xian", "进": "jin", "度": "du",
        "流": "liu", "程": "cheng", "优": "you", "化": "hua",
        "绩": "ji", "效": "xiao", "需": "xu", "求": "qiu",
        "鱼": "yu", "骨": "gu", "图": "tu", "根": "gen", "因": "yin",
        "标": "biao", "杆": "gan", "案": "an", "例": "li",
        "文": "wen", "献": "xian",
    }
    return "".join(slug_map.get(c, "") for c in name[:6]) or f"method_{hash(name) % 10000:04d}"


def generate_card(client, model: str, name: str, keywords: list[str], phase: str) -> str:
    """调用 LLM 生成一张方法卡。"""
    context = find_context(name, keywords)
    has_context = bool(context.strip())

    prompt = f"""你是一位工程管理（MEM）研究方法专家。请为「{name}」生成一份完整的研究方法卡片。

该方法主要用于工程管理硕士论文的「{phase}」阶段。
{chr(10) + '以下是从知识库中检索到的相关学术文献作为参考：' + chr(10) + context[:4000] if has_context else '（知识库中暂无该方法的直接参考文献，请基于你的学术知识生成。）'}

请严格按照以下14个部分输出方法卡内容，每部分用"## 部分名"开头：

## 方法定位
一句话说明该方法在工程管理论文中承担的角色。

## 定义
该方法的学术定义（注明提出者/机构和提出年份，若知识库参考文献中有则优先引用）。

## 适用场景
列举3-5个工程管理论文中的典型使用场景，每条20-40字。

## 不适用场景
说明该方法不适合的情况，列举2-3个。

## 输入数据
该方法需要的输入数据类型（定性/定量，具体有哪些）。

## 输出结果
该方法产出的结果类型。

## 操作步骤
详细列出6-8个操作步骤，每步包含具体做什么。

## 优缺点
各列2-3条，优缺点分开展示。

## 适用章节
在论文哪些章节使用（如第三章问题分析、第四章方案设计等）。

## 常见错误
列举4-6个论文中使用该方法时常见的错误。

## 可搭配方法
与哪些方法可以组合使用，简要说明搭配方式。

## 示例表达
提供一段200字左右的论文中应用该方法的写作示例（模仿真实论文语气）。

## 生成约束
论文中使用该方法必须遵守的规则（3-5条）。

## 参考文献
提供2-4条真实的学术参考文献（如有知识库文献则优先引用其中的）。"""

    response = client.messages.create(
        model=model,
        max_tokens=3000,
        system="你是研究方法论专家，输出结构化、学术化、可操作的方法卡内容。",
        messages=[{"role": "user", "content": prompt}],
    )
    # 提取所有 TextBlock，跳过 ThinkingBlock
    parts = []
    for block in response.content:
        if hasattr(block, "text") and block.type == "text":
            parts.append(block.text)
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("LLM 未返回正文内容")
    return text


def build_frontmatter(name: str, card_id: str, phase: str) -> str:
    """生成 YAML frontmatter。"""
    now = time.strftime("%Y-%m-%d")
    return f"""---
id: {card_id}
type: method_card
name: {name}
short_name: {name[:8]}
aliases:
  - {name}
category: qualitative
phase:
  - {phase}
disciplines:
  - mem
  - mba
domains:
  - quality_management
applicable_sections:
  - chapter_3_problem_analysis
pairs_with: []
requires: []
conflicts_with: []
difficulty: intermediate
data_type: []
outputs: []
risk_tags: []
inject_policy: auto
embedding_fields:
  - name
  - body
source_type: builtin
scope: platform
status: draft
version: 1.0.0
created_at: {now}
updated_at: {now}
---
"""


def main():
    config = load_llm_config()
    if not config.api_key:
        print("错误: 未配置 API Key，请先在页面基本配置中设置。")
        sys.exit(1)

    client_kwargs = {"api_key": config.api_key}
    if config.auth_mode == "auth_token" and config.auth_token:
        client_kwargs["auth_token"] = config.auth_token
    if config.base_url:
        client_kwargs["base_url"] = config.base_url
    client = Anthropic(**client_kwargs)

    CARDS_METHODS.mkdir(parents=True, exist_ok=True)

    generated = 0
    skipped = 0
    failed = 0

    for name, keywords, phase in METHODS:
        card_id = f"method_{safe_id(name)}"
        card_path = CARDS_METHODS / f"{card_id}.md"

        if SKIP_EXISTING and card_path.exists():
            print(f"  [跳过] {name} → {card_id}.md (已存在)")
            skipped += 1
            continue

        print(f"  [生成中] {name} ({phase})...", end=" ", flush=True)
        try:
            body = generate_card(client, config.model, name, keywords, phase)
            content = build_frontmatter(name, card_id, phase) + "\n" + body
            card_path.write_text(content, encoding="utf-8")
            print(f"→ {card_id}.md ({len(body)} 字)")
            generated += 1
        except Exception as e:
            print(f"✗ 失败: {e}")
            failed += 1

    print(f"\n生成完成: {generated} 新建, {skipped} 跳过, {failed} 失败")
    print(f"输出目录: {CARDS_METHODS}")

    # 自动 build cards DB
    if generated > 0:
        print("\n构建卡片数据库...")
        try:
            from card_builder import build_cards
            result = build_cards()
            print(f"  {result.get('status')}: {result.get('cards_processed')} 张卡片")
            if result.get("errors"):
                for e in result["errors"][:5]:
                    print(f"    错误: {e}")
        except Exception as e:
            print(f"  构建失败: {e}")
            print("  可稍后手动运行: python3 -c \"from src.card_builder import build_cards; build_cards()\"")


if __name__ == "__main__":
    main()
