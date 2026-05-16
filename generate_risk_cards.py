#!/usr/bin/env python3
"""生成盲审风险卡片 — LLM 生成 cards/risks/risk_*.md，然后 build_risks 入库。"""
from __future__ import annotations

import json, sys, time, re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

from anthropic import Anthropic
from llm_config import load_llm_config

PROJECT_ROOT = Path(__file__).resolve().parent
CARDS_RISKS = PROJECT_ROOT / "cards" / "risks"

RISKS = [
    # (name, severity, category, check_stage)
    ("方法堆砌缺乏论证", "critical", "methodology", "post_generation"),
    ("AHP缺少一致性检验", "critical", "methodology", "post_generation"),
    ("问卷调查样本量不足", "high", "methodology", "post_generation"),
    ("德尔菲法专家信息缺失", "high", "methodology", "post_generation"),
    ("方法选择缺乏理由", "medium", "methodology", "post_generation"),
    ("章节逻辑断裂", "critical", "structure", "post_generation"),
    ("创新点空泛缺乏具体贡献", "critical", "structure", "post_generation"),
    ("问题-方法-方案脱节", "high", "structure", "post_generation"),
    ("引用陈旧缺乏近年文献", "high", "academic_quality", "post_generation"),
    ("英文文献严重不足", "medium", "academic_quality", "post_generation"),
    ("参考文献格式混乱", "medium", "academic_quality", "post_generation"),
    ("缺少数据支撑空谈结论", "high", "evidence", "post_generation"),
    ("图表不规范缺少编号标题", "medium", "evidence", "post_generation"),
    ("案例代表性不足", "high", "evidence", "post_generation"),
    ("摘要要素不完整", "medium", "writing", "post_generation"),
    ("关键词选取不当", "low", "writing", "post_generation"),
    ("论文格式不符合学校模板", "low", "writing", "post_generation"),
    ("研究范围过大缺乏聚焦", "high", "structure", "post_generation"),
    ("文献综述缺乏评述只有罗列", "high", "academic_quality", "post_generation"),
    ("对策建议空泛缺乏可操作性", "medium", "structure", "post_generation"),
]

SKIP_EXISTING = True


def safe_id(name: str) -> str:
    eng = re.findall(r"[A-Za-z0-9]+", name)
    if eng:
        return "_".join(e.lower() for e in eng[:3])
    slug_map = {
        "方": "fang", "法": "fa", "堆": "dui", "砌": "qi", "缺": "que",
        "乏": "fa2", "论": "lun", "证": "zheng", "一": "yi", "致": "zhi",
        "性": "xing", "检": "jian", "验": "yan", "问": "wen", "卷": "juan",
        "调": "diao", "查": "cha", "样": "yang", "本": "ben", "量": "liang",
        "不": "bu", "足": "zu", "德": "de", "尔": "er", "菲": "fei",
        "专": "zhuan", "家": "jia", "信": "xin", "息": "xi",
        "选": "xuan", "择": "ze", "理": "li", "由": "you",
        "章": "zhang", "节": "jie", "逻": "luo", "辑": "ji",
        "断": "duan", "裂": "lie", "创": "chuang", "新": "xin",
        "点": "dian", "空": "kong", "泛": "fan", "具": "ju", "体": "ti",
        "贡": "gong", "献": "xian", "脱": "tuo",
        "引": "yin", "用": "yong", "陈": "chen", "旧": "jiu",
        "近": "jin", "年": "nian", "文": "wen", "献": "xian",
        "英": "ying", "严": "yan2", "重": "zhong",
        "参": "can", "考": "kao", "格": "ge", "式": "shi",
        "混": "hun", "乱": "luan", "数": "shu", "据": "ju",
        "支": "zhi", "撑": "cheng", "空": "kong", "谈": "tan",
        "结": "jie", "图": "tu", "表": "biao", "规": "gui",
        "范": "fan", "编": "bian", "号": "hao", "标": "biao",
        "案": "an", "例": "li", "代": "dai", "摘": "zhai",
        "要": "yao", "素": "su", "完": "wan", "整": "zheng",
        "关": "guan", "键": "jian", "词": "ci", "取": "qu",
        "当": "dang", "学": "xue", "校": "xiao", "模": "mo",
        "板": "ban", "研": "yan", "究": "jiu", "围": "wei",
        "过": "guo", "大": "da", "聚": "ju", "焦": "jiao",
        "综": "zong", "述": "shu", "评": "ping", "罗": "luo",
        "对": "dui", "策": "ce", "建": "jian2", "议": "yi",
        "操": "cao", "作": "zuo",
    }
    return "".join(slug_map.get(c, "") for c in name[:8]) or f"risk_{hash(name) % 10000:04d}"


def build_frontmatter(name: str, card_id: str, severity: str, category: str, check_stage: str) -> str:
    now = time.strftime("%Y-%m-%d")
    return f"""---
id: {card_id}
type: risk_card
name: {name}
severity: {severity}
category: {category}
check_stage: {check_stage}
disciplines:
  - mem
  - mba
applicable_chapters:
  - chapter_3_problem_analysis
  - chapter_4_solution_design
  - chapter_5_validation
trigger_conditions: []
check_questions: []
fix_strategy: []
related_method_tags: []
inject_policy:
  stages: ["post_generation"]
  max_tokens: 800
  inject_sections: ["risk_scan"]
source_type: builtin
scope: platform
status: draft
version: 1.0.0
embedding_fields:
  - name
  - body
created_at: {now}
updated_at: {now}
---
"""


def generate_card(client, model: str, name: str, severity: str, category: str) -> str:
    prompt = f"""你是一位工程管理（MEM）硕士论文盲审专家。请为盲审风险「{name}」生成完整的风险检查卡片。

严重程度：{severity}
风险类别：{category}

请严格按照以下部分输出，每部分用"## 部分名"开头：

## 风险定位
一句话说明该风险在论文盲审中的位置和影响。

## 严重程度
说明为什么被定为 {severity} 级别，盲审被拒的可能性。

## 触发条件
列出5-8个触发该风险的具体条件，每条件以"- "开头。使用可被程序检测的明确信号（如关键词、句式、数量阈值）。

## 检查问题
列出4-6个盲审专家会问的问题，每问题以"- "开头。

## 修复策略
给出3-5条可操作的修复建议，每条含具体怎么做，以"- "开头。

## 可配合的风险检查
列举2-3个可以配合检查的相关风险名称，简要说明搭配方式。

## 示例表达
提供一段200字左右的论文中触发该风险的典型错误写法示例，以及对应的修改后正确写法。

## 生成约束
论文生成时必须遵守的规则，3-5条。"""

    resp = client.messages.create(
        model=model,
        max_tokens=2000,
        thinking={"type": "disabled"},
        system="你是盲审风险专家，输出结构化、可操作的风险检查卡片。触发条件必须具体、可检测。修复策略必须可执行。",
        messages=[{"role": "user", "content": prompt}],
    )
    parts = []
    for block in resp.content:
        if getattr(block, "type", "") == "text":
            parts.append(block.text)
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("LLM 未返回正文")
    return text


def main():
    config = load_llm_config()
    if not config.api_key:
        print("错误: 未配置 API Key")
        sys.exit(1)

    client = Anthropic(api_key=config.api_key, base_url=config.base_url, timeout=60)
    CARDS_RISKS.mkdir(parents=True, exist_ok=True)

    generated = skipped = failed = 0

    for name, severity, category, check_stage in RISKS:
        card_id = f"risk_{safe_id(name)}"
        card_path = CARDS_RISKS / f"{card_id}.md"

        if SKIP_EXISTING and card_path.exists():
            print(f"  [跳过] {name} → {card_id}.md (已存在)")
            skipped += 1
            continue

        print(f"  [生成中] {name} ({severity})...", end=" ", flush=True)
        try:
            body = generate_card(client, config.model, name, severity, category)
            content = build_frontmatter(name, card_id, severity, category, check_stage) + "\n" + body
            card_path.write_text(content, encoding="utf-8")
            print(f"→ {card_id}.md ({len(body)} 字)")
            generated += 1
        except Exception as e:
            print(f"✗ 失败: {e}")
            failed += 1

    print(f"\n生成完成: {generated} 新建, {skipped} 跳过, {failed} 失败")

    if generated > 0:
        print("\n构建风险卡片数据库...")
        try:
            from card_builder import build_risks
            result = build_risks()
            print(f"  {result.get('status')}: {result.get('risks_processed', result.get('cards_processed', '?'))} 张风险卡")
            if result.get("errors"):
                for e in result["errors"][:5]:
                    print(f"    错误: {e}")
        except Exception as e:
            print(f"  构建失败: {e}")


if __name__ == "__main__":
    main()
