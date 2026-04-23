<div align="center">

# 🧠 TestCaseMind

**AI-Powered Test Case Design Agent | AI 驱动的测试用例设计智能体**

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Anthropic](https://img.shields.io/badge/Powered%20by-Claude-orange.svg)](https://anthropic.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Framework](https://img.shields.io/badge/Framework-learn--claude--code-purple.svg)](https://github.com/shareAI-lab/learn-claude-code)

*从需求文档到完整测试用例，全自动四阶段流程，三类来源标记，RAG 知识库检索*

[快速开始](#-快速开始) · [架构设计](#-架构设计) · [示例输出](#-示例输出) · [Claude Code 集成](#-claude-code-集成)

</div>

---

## 📖 项目背景

### 测试用例设计的三大痛点

在金融、风控等复杂业务系统的测试工作中，测试用例设计面临三个核心难题：

**1. 覆盖不全** — 测试工程师依赖个人经验，容易遗漏枚举边界、数据精度、并发竞争等场景，而这些恰恰是生产环境中最容易出问题的地方。

**2. 编写耗时** — 一份需求文档手工设计测试点需要 2-4 小时，展开成完整用例（含步骤、数据、预期结果）再需要 4-8 小时，人力成本极高。

**3. 知识割裂** — 数据字典、表设计文档、历史测试经验散落在各处，测试工程师每次都要重新查阅，无法系统性复用。

### TestCaseMind 的解法

TestCaseMind 把测试工程师的工作流程抽象为四个自动化阶段，并引入三类来源标记和 RAG 知识库检索：

```
需求文档
   ↓
① 需求评审      → 质量评分、风险识别、可测性分析（自动剔除不可测需求）
   ↓
② 测试点生成    → 两路并行：
                   ▸ 需求文档 → 🔵 REQ 来源测试点
                   ▸ RAG 知识库检索 → 🟡 KB 来源 + 🔴 RISK 来源测试点
   ↓
③ 测试用例展开  → 分批并行处理，P0 自动生成正常流+异常流两条
   ↓
④ 测分文档生成  → 本地零 token，汇总统计+风险清单+测试结论
```

**三类来源标记**让测试结果有据可查，而不是黑盒输出：

| 标记 | 来源 | 含义 |
|------|------|------|
| 🔵 **REQ** | 需求文档 | 能在原文找到对应描述 |
| 🟡 **KB** | 知识库 | 枚举边界/字段约束/行业规范 |
| 🔴 **RISK** | 风险推断 | 并发/精度/外部依赖等测试经验 |

---

## ✨ 核心特性

- **🤖 四阶段全自动**：需求评审 → 测试点 → 测试用例 → 测分文档，一条命令完成
- **🔍 RAG 知识库检索**：ChromaDB + sentence-transformers 向量语义检索，精准匹配，不截断不丢失
- **🧠 长期记忆积累**：向量化跨会话记忆，每次运行自动提炼经验，越跑越准
- **📊 三类来源标记**：REQ/KB/RISK 清晰标注，覆盖来源可追溯
- **⚡ 并行处理**：测试用例分批并行生成（最多4并发），速度提升4倍
- **🔄 崩溃可续跑**：任务进度持久化，中途崩溃从断点继续，不浪费 token
- **🔌 Claude Code 集成**：MCP Server 支持，自然语言一句话触发完整流程
- **💾 零 token 本地工具**：Excel/XMind/测分文档本地生成，不消耗 API 费用

---

## 🏗️ 架构设计

### 技术栈

```
LLM Backend    : Anthropic Claude (claude-sonnet-4-6)
RAG Engine     : ChromaDB + sentence-transformers
Embedding Model: paraphrase-multilingual-MiniLM-L12-v2
Output Formats : JSON / Excel / Markdown(XMind)
MCP Integration: Claude Code MCP Server
```

### Harness 机制组合

基于 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 框架，组合 7 个 Harness 机制：

| Harness | 机制 | 在本项目中的作用 |
|---------|------|-----------------|
| s03 TodoWrite | 子代理先列计划 | 每个子代理强制先写执行步骤，减少遗漏和跑偏 |
| s04 Subagent | 上下文隔离 | 四个阶段各用独立上下文，结果通过文件传递 |
| s05 Skills | 技能按需加载 | 三个 SKILL.md 按需加载，不预埋进系统提示词 |
| s06 Context Compact | 三层压缩 | 防止长文档 token 溢出，支持无限会话 |
| s07 Task System | 进度持久化 | 四阶段状态写入磁盘，崩溃可续跑 |
| s09 Memory System | 跨会话记忆 | 向量化历史经验，每次运行自动注入相关记忆 |
| s11 Error Recovery | 错误恢复 | 529 自动重试，单批失败跳过不影响整体 |

### 知识库体系

```
knowledge_base/
├── 数据字典枚举值.md     ← 所有枚举字段合法值域（来自表设计 Excel）
├── 元数据字段定义.md     ← 字段类型/长度/精度约束
├── 表依赖关系.md         ← 测试数据初始化顺序
├── tables/
│   ├── 00_索引.md        ← Agent 先读这个，按需查找
│   ├── 01_业务模块A.md   ← 按模块拆分，单次检索不超过相关模块
│   └── ...
└── design/
    ├── 00_因子索引.md    ← 因子设计文档索引
    └── 示例因子.md       ← 每个因子的参数值域+元因子取值逻辑
```

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Joeyzheng001/TestCaseMind.git
cd TestCaseMind
```

### 2. 安装依赖

```bash
pip install anthropic python-dotenv pyyaml openpyxl mcp \
            chromadb sentence-transformers pandas

# macOS 安装 pandoc（Word 文档转换用）
brew install pandoc
```

### 3. 下载嵌入模型（约 470MB，仅首次需要）

```bash
HF_ENDPOINT=https://hf-mirror.com python3 -c "
from huggingface_hub import hf_hub_download
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
hf_hub_download(
    repo_id='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
    filename='model.safetensors',
    local_dir='./models/paraphrase-multilingual-MiniLM-L12-v2',
)
print('下载完成')
"
```

### 4. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env`：

```env
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx
MODEL_ID=claude-sonnet-4-6
HF_ENDPOINT=https://hf-mirror.com
```

### 5. 准备知识库（可选，显著提升 KB 来源测试点质量）

```bash
# 从数据库表设计 Excel 提取
python kb_from_excel.py 表设计文档.xlsx

# 从因子开发设计文档提取
python kb_from_design.py 因子设计文档.xlsx

# Word 规范文档批量转 Markdown
python kb_convert.py

# 建立向量索引（首次运行自动建立）
python kb_rag.py
```

### 6. 运行

```bash
# 完整流程（推荐）
python agent.py "需求文档.md" --kb

# 只生成测试点，不展开用例
python agent.py "需求文档.md" --kb --no-cases

# 跳过需求评审
python agent.py "需求文档.md" --kb --skip-review

# 中途崩了，续跑
python agent.py "需求文档.md" --kb --resume
```

---

## 📂 输出文件

每次运行在 `output/<需求文件名>/<时间戳>/` 下生成：

```
output/
└── ARM-RULE-UC00001_持仓数量类因子规格文档/
    └── 1776909806/
        ├── testpoints.json        ← 测试点（含三类来源标记）
        ├── testpoints_xmind.md    ← XMind 思维导图源文件
        ├── testcases.json         ← 测试用例完整数据
        ├── testcases.xlsx         ← Excel（蓝/黄/红颜色标记来源）
        └── report.md              ← 测分文档
```

---

## 📊 示例输出

### 测试点 JSON

```json
{
  "meta": {
    "total": 32,
    "by_source": { "REQ": 24, "KB": 4, "RISK": 4 }
  },
  "testpoints": [
    {
      "testpoint_id": "TP-001",
      "functional_module": "核心计算逻辑",
      "test_scenario": "正常流：输入合法数据时计算结果正确",
      "source": "REQ",
      "source_ref": "需求第3节：计算公式定义",
      "preconditions": "数据库中存在有效的基础数据",
      "test_steps": "1. 准备合法输入数据\n2. 调用计算接口\n3. 验证返回结果",
      "expected_result": "返回值与预期公式计算结果一致",
      "priority": "P0",
      "remarks": ""
    },
    {
      "testpoint_id": "TP-025",
      "functional_module": "数据字典约束",
      "test_scenario": "枚举字段传入非法值时的处理",
      "source": "KB",
      "source_ref": "knowledge_base/数据字典枚举值.md - 字段合法值域定义",
      "preconditions": "输入数据中包含超出枚举范围的值",
      "test_steps": "1. 构造包含非法枚举值的请求\n2. 调用接口",
      "expected_result": "返回参数校验错误，不影响其他合法数据的计算",
      "priority": "P1",
      "remarks": "边界值规范来自数据字典"
    },
    {
      "testpoint_id": "TP-029",
      "functional_module": "并发与数据一致性",
      "test_scenario": "多个并发请求同时触发计算时的数据隔离",
      "source": "RISK",
      "source_ref": "风险推断：需求未明确并发场景下的隔离机制",
      "preconditions": "多个请求同时发起",
      "test_steps": "1. 并发发送多个计算请求\n2. 等待所有响应\n3. 验证各请求结果互不影响",
      "expected_result": "每个请求返回各自正确结果，无数据污染",
      "priority": "P2",
      "remarks": "需确认是否有请求级别的数据隔离"
    }
  ]
}
```

### XMind 导入效果（Markdown 格式）

```markdown
# 示例需求文档
## 概览
### 评审分: 75
### 测试点总数: 32
### REQ需求直出: 24 | KB知识库: 4 | RISK风险: 4
## ⚠ 风险项
### [performance] 未定义接口的并发上限和超时处理机制
### [integration] 依赖外部数据源，未说明数据不可用时的降级方案
## 核心计算逻辑 (12条)
### 🔵[REQ][P0] 正常流：输入合法数据时计算结果正确
### 🔵[REQ][P0] 边界处理：输入值为零时的结果验证
...
## 数据字典约束 (4条)
### 🟡[KB][P1] 枚举字段传入非法值时的处理
...
## 并发与数据一致性 (4条)
### 🔴[RISK][P2] 多个并发请求同时触发计算时的数据隔离
...
```

### 测分文档（report.md 节选）

```markdown
# 测试分析报告

| 项目 | 内容 |
|------|------|
| 需求文档 | example_requirement.md |
| 需求质量 | 🟡 良（75/100）|
| 测试覆盖 | 🟢 完整 |

## 三、测试点统计

| 来源类型 | 数量 | 占比 |
|---------|------|------|
| 🔵 REQ 需求直出 | 24 | 75.0% |
| 🟡 KB 知识库补充 | 4 | 12.5% |
| 🔴 RISK 风险推断 | 4 | 12.5% |

## 五、测试结论

- ✅ 共 8 条 P0 核心测试点，上线前必须全部通过。
- ✅ 共生成 32 条测试用例，可直接导入测试管理工具执行。
- ⚠ 风险推断测试点较少，建议重点关注并发场景和数据精度。
```

---

## 🔌 Claude Code 集成

### 注册 MCP Server

```bash
claude mcp add TestCaseMind \
  --scope user \
  -- /path/to/python /path/to/TestCaseMind/mcp_server.py

# 验证连接
claude mcp list
# 输出: TestCaseMind: ✓ Connected
```

### 可用工具

| 工具 | 功能 |
|------|------|
| `review_requirement` | 需求文档质量评审 |
| `generate_testpoints` | 生成测试点（REQ+KB+RISK） |
| `generate_testcases` | 展开测试用例 |
| `save_to_knowledge_base` | 经验沉淀到知识库 |
| `convert_kb_docx` | Word 文档转 Markdown |
| `get_task_status` | 查询任务进度 |

### 自然语言触发

```
# 注册自定义命令后
/gen-test knowledge_base/需求文档.md

# 或直接说话
用 TestCaseMind 工具对 knowledge_base/需求文档.md 做完整测试，
评审、测试点、用例都要，知识库开启，完成后沉淀到知识库
```

---

## 🛠️ 本地工具（零 token 消耗）

```bash
# 重新生成 XMind Markdown（不调用 API）
python regen_md.py "output/xxx/testpoints.json"

# 重新生成 Excel（调整格式/颜色后直接重跑）
python regen_excel.py "output/xxx/testcases.json"

# 单独生成测分文档
python gen_report.py "output/xxx/testpoints.json" \
       --cases "output/xxx/testcases.json"

# 测试知识库检索效果
python kb_rag.py "持仓数量因子计算" --top-k 5

# 强制重建向量索引
python kb_rag.py --rebuild
```

---

## 📁 项目结构

```
TestCaseMind/
├── agent.py              # 主程序（四阶段流程 + 7个 Harness）
├── task_store.py         # s07 任务持久化
├── memory_store.py       # s09 记忆系统（JSON 存储）
├── memory_rag.py         # s09 记忆向量检索（ChromaDB）
├── kb_rag.py             # 知识库 RAG 检索
├── kb_convert.py         # Word → Markdown 批量转换
├── kb_from_excel.py      # Excel 表设计 → 结构化知识库
├── kb_from_design.py     # 因子设计文档 → 知识库
├── gen_report.py         # 测分文档生成（本地，零 token）
├── regen_md.py           # JSON → XMind Markdown（本地）
├── regen_excel.py        # JSON → Excel（本地）
├── mcp_server.py         # Claude Code MCP Server
├── .env.example          # 环境变量模板
├── skills/
│   ├── requirement-review/SKILL.md   # 需求评审规则
│   ├── testpoint-gen/SKILL.md        # 测试点生成规则
│   └── testcase-gen/SKILL.md         # 测试用例生成规则
└── .claude/
    └── commands/gen-test.md          # Claude Code 自定义命令
```

---

## 📋 命令行参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `--kb` | 启用知识库 RAG 检索 | 关闭 |
| `--no-cases` | 只生成测试点，跳过用例展开 | 生成用例 |
| `--skip-review` | 跳过需求评审，直接生成测试点 | 做评审 |
| `--resume` | 续跑上次未完成的任务 | 新建任务 |

---

## 🔧 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 主运行环境 |
| Anthropic API Key | - | 调用 Claude 模型 |
| pandoc | 任意 | Word 文档转换（可选） |
| 嵌入模型 | 470MB | 首次需下载，之后本地使用 |

---

## 🙏 致谢

本项目基于 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 框架构建，感谢其提供的 Harness 机制设计思路。

---

<div align="center">

如果这个项目对你有帮助，欢迎 ⭐ Star 支持！

</div>
