# 测试用例生成 Agent (MVP)

基于 learn-claude-code 框架的最小化实现，组合了 s04 + s05 + s06。

## 快速开始

```bash
# 安装依赖
pip install anthropic python-dotenv pyyaml mammoth

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY

# 用示例需求文档跑一遍
python agent.py example_requirement.md

# 启用知识库（需先转换 Word 文档）
python kb_convert.py         # 把 knowledge_base/*.docx 转成 .md
python agent.py requirements.md --kb
```

## 目录结构

```
test-agent/
├── agent.py                    # 主 Agent
├── kb_convert.py               # 知识库预处理（docx → md）
├── example_requirement.md      # 示例需求文档
├── skills/
│   ├── requirement-review/
│   │   └── SKILL.md            # 评审规则
│   └── testpoint-gen/
│       └── SKILL.md            # 测试点生成规则
├── knowledge_base/             # 放转换后的 .md 知识库文件
└── output/                     # 生成结果（JSON）
```

## 输出说明

生成的 `output/testpoints_<name>_<timestamp>.json` 结构：

```json
{
  "meta": { "total": 25, "by_source": {"REQ": 15, "KB": 5, "RISK": 5} },
  "review": { "score": 85, "risk_flags": [...] },
  "testpoints": [
    {
      "feature": "用户登录",
      "testpoints": [
        { "id": "TP-001", "source": "REQ", ... },
        { "id": "TP-002", "source": "KB",  ... },
        { "id": "TP-003", "source": "RISK", ... }
      ]
    }
  ]
}
```

## 后续优化方向（按优先级）

1. **加 s07 Task System** — 进度持久化，中途崩溃可恢复
2. **加测试用例生成** — 在测试点基础上展开 steps/expected
3. **JSON 转 XMind** — 用 xmindparser 库将 JSON 渲染成思维导图
4. **测分文档生成** — 按模版汇总评审结果 + 测试点统计
