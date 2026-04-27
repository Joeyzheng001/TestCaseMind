# TestCaseMind 🧠

**AI 驱动的测试用例设计智能体**

自动完成需求评审、测试点生成、用例展开、知识积累的完整闭环。越用越准——每次跑完都会提炼通用规则沉淀到知识库，长期记忆持续积累测试经验。

---

## 一、快速安装

### 1. 安装依赖（一次性）

```bash
pip install -r requirements.txt
```

> requirements.txt 包含所有依赖，不会在运行时要求你临时安装。

**系统依赖**（macOS）：
```bash
brew install pandoc   # Word 文档转换（可选，有 python-docx 作为主方案）
```

### 2. 下载嵌入模型（一次性，约 470MB）

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

# 下载其余配置文件
HF_ENDPOINT=https://hf-mirror.com python3 -c "
from huggingface_hub import snapshot_download
import os
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
snapshot_download(
    repo_id='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
    local_dir='./models/paraphrase-multilingual-MiniLM-L12-v2',
    ignore_patterns=['*.h5', '*.ot', 'onnx/*', 'openvino/*'],
)
print('完成')
"
```

### 3. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env 填入：
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxx
# MODEL_ID=claude-sonnet-4-6
# HF_ENDPOINT=https://hf-mirror.com
```

---

## 二、核心使用方式

### 方式一：自然语言驱动（推荐）

通过 Claude Code，用自然语言描述意图，系统自动路由到对应工具：

```
# 生成测试用例
帮我对这个PRD生成测试用例 [上传文件]

# 查询进度
跑完了吗？

# 知识积累
把这次的规则提炼到知识库

# 检查知识库
知识库现在有多少内容，质量怎么样？

# 查看结果
结果在哪，生成了什么文件？
```

Claude Code 会根据 CLAUDE.md 自动判断调用哪个工具，不需要记脚本名。

**注册 MCP（一次性）**：
```bash
claude mcp add test-agent \
  --scope user \
  -- /path/to/python /path/to/TestCaseMind/mcp_server.py
```

### 方式二：命令行直接运行

```bash
# 完整流程（推荐）
python agent.py "需求文档.docx" --kb

# 只生成测试点
python agent.py "需求文档.md" --kb --no-cases

# 只跑指定章节
python agent.py "需求文档.md" --kb --section "结算风控金"

# 中途崩了续跑
python agent.py "需求文档.md" --kb --resume
```

支持直接传 `.docx` 文件，自动转换为 Markdown。

---

## 三、完整工作流

### 第一次使用（准备知识库）

```bash
# 1. 把数据字典/表设计文档加入知识库
python kb_from_excel.py 表设计文档.xlsx       # 表设计文档
python kb_from_design.py 因子设计文档.xlsx    # 因子设计文档（金融场景）

# 2. 把其他设计文档加入知识库
python kb_convert.py 技术设计文档.docx        # Word 文档
# 或直接把 .md 文件放入 knowledge_base/

# 3. 建立向量索引
python kb_rag.py --rebuild

# 4. 检查知识库状态
python kb_check.py
```

### 日常使用（跑 PRD）

```bash
# 1. 生成测试用例
python agent.py "需求文档.docx" --kb

# 2. 把规则提炼到知识库（可选，但推荐）
python kb_distill.py "output/需求名/时间戳/testpoints.json" \
       --req "knowledge_base/需求文档.md"

# 3. 更新索引
python kb_rag.py --rebuild
```

### 定期维护（每月一次）

```bash
# 检查知识库质量
python kb_check.py

# 审核长期记忆，删除低质量条目
python memory_review.py --clean

# 交互式测试检索效果
python kb_check.py --search
```

---

## 四、输出文件

每次运行在 `output/<需求名>/<时间戳>/` 目录下生成：

| 文件 | 说明 |
|------|------|
| `testpoints.json` | 测试点（REQ/KB/RISK 三类标记） |
| `testpoints_xmind.md` | XMind 导入文件 |
| `testcases.json` | 测试用例完整数据 |
| `testcases.xlsx` | Excel（带颜色标记，可直接交付） |
| `report.md` | 测分文档 |

---

## 五、知识库管理

知识库质量决定 KB 来源测试点的质量。只有规范性文档应该入库：

| 应该入库 ✅ | 不应该入库 ❌ |
|-----------|-------------|
| 数据字典枚举值定义 | PRD 原文 |
| 表设计文档（字段约束）| 测试用例本身 |
| 开发设计文档（实现逻辑）| 版本特定的业务规则 |
| 行业/监管规范 | 还在评审中的需求 |

```bash
# 知识提炼（从测试点中提取通用规则）
python kb_distill.py output/xxx/testpoints.json

# 知识库健康检查
python kb_check.py --quick    # 快速检查
python kb_check.py            # 完整检查（含检索测试）
python kb_check.py --search   # 交互式验证关键词

# 长期记忆审核
python memory_review.py --stats   # 查看统计
python memory_review.py --clean   # 清理低质量条目
python memory_review.py --add     # 手动添加经验
```

---

## 六、所有脚本说明

| 脚本 | 功能 | 何时使用 |
|------|------|---------|
| `agent.py` | 主程序，四阶段生成流程 | 每次跑 PRD |
| `mcp_server.py` | Claude Code MCP 集成 | Claude Code 自然语言驱动 |
| `kb_distill.py` | 知识提炼，提炼通用规则入库 | 跑完 PRD 后 |
| `kb_check.py` | 知识库健康检查 | 定期维护 |
| `kb_rag.py` | 向量索引管理 | 知识库更新后 |
| `kb_from_excel.py` | Excel 表设计 → 知识库 | 首次准备 |
| `kb_from_design.py` | 因子设计文档 → 知识库 | 金融场景 |
| `kb_convert.py` | Word/MD → 知识库 | 普通设计文档 |
| `docx2md.py` | Word → 干净的 Markdown | 文档预处理 |
| `memory_review.py` | 长期记忆审核 | 定期维护 |
| `gen_report.py` | 生成测分文档（零token）| 单独生成报告 |
| `regen_excel.py` | 重新生成 Excel（零token）| 调整格式 |
| `regen_md.py` | 重新生成 XMind MD（零token）| 调整格式 |
| `review_cases.py` | 人工用例评审与优化 | 评审已有用例 |

---

## 七、目录结构

```
TestCaseMind/
├── agent.py              # 主程序
├── mcp_server.py         # MCP Server
├── kb_distill.py         # 知识提炼
├── kb_check.py           # 知识库检查
├── kb_rag.py             # 向量检索
├── kb_from_excel.py      # 表设计入库
├── kb_from_design.py     # 因子设计入库
├── kb_convert.py         # 文档转换入库
├── kb_reader.py          # 通用文档读取
├── docx2md.py            # Word → Markdown
├── memory_review.py      # 记忆审核
├── memory_rag.py         # 记忆向量检索
├── memory_store.py       # 记忆存储
├── task_store.py         # 任务持久化
├── gen_report.py         # 测分文档
├── regen_excel.py        # 重生成 Excel
├── regen_md.py           # 重生成 XMind
├── review_cases.py       # 用例评审
├── requirements.txt      # 依赖列表
├── .env.example          # 配置模板
├── CLAUDE.md             # 自然语言指令规范
├── skills/
│   ├── requirement-review/SKILL.md
│   ├── testpoint-gen/SKILL.md
│   └── testcase-gen/SKILL.md
├── knowledge_base/       # 知识库（只存规范文档）
│   ├── 通用规则积累.md   ← kb_distill.py 自动维护
│   ├── design/           ← 因子设计文档
│   └── tables/           ← 表字段说明
├── output/               # 生成的测试用例
├── memory/               # 长期记忆
└── models/               # 嵌入模型（不提交 git）
```

---

## 八、常见问题

| 问题 | 解决 |
|------|------|
| KB=0 RISK=0 | 知识库为空，先跑 kb_from_excel.py 准备知识库 |
| Excel 没有生成 | `pip install openpyxl` |
| 模型下载超时 | 设置 `HF_ENDPOINT=https://hf-mirror.com` 后重试 |
| 需求评审返回 N/A | 正常，有格式修复兜底，不影响后续流程 |
| 章节跳过不对 | 查看 `memory/long_term.json` 的 section_patterns，用 `memory_review.py` 清理 |
| MCP 连接失败 | 用 `which python` 找完整路径，重新注册 MCP |

---

## 九、致谢

基于 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 框架构建，组合 s03/s04/s05/s06/s07/s09/s11 七个 Harness 机制。
