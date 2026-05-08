# TestCaseMind 系统介绍

## 1. 项目定位

TestCaseMind 是一个面向需求文档的 AI 测试用例设计智能体。它以 PRD、因子规格、表设计、开发设计等文档为输入，自动完成需求质量评审、测试点生成、测试用例展开、Excel 交付物导出、测分报告生成，以及知识库和长期记忆沉淀。

系统基于 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 的 Agent Harness 思路构建，组合落地了 s03、s04、s05、s06、s07、s09、s11 七个机制。与一次性调用大模型不同，TestCaseMind 更像一个带工作流、工具、记忆、任务状态和知识库的测试工程助手：它会先理解需求质量，再分阶段生成测试资产，并把每次运行中的经验反哺给后续任务。

核心目标包括：

- 把需求文档转化为可执行、可交付的测试用例资产。
- 让测试点来源可追溯，区分 `REQ`、`KB`、`RISK` 三类来源。
- 用本地知识库补齐需求未显式描述的枚举、字段约束、开发设计实现逻辑、历史规则和风险场景。
- 用长期记忆沉淀跨项目测试经验，让系统越用越贴近业务域。
- 用任务持久化和容错机制支撑长耗时、多阶段生成流程。

## 2. 总体架构

系统分为六层：

1. 入口层
   - 命令行入口：`scripts/agent.py`
   - MCP 入口：`scripts/mcp_server.py`

2. 工作流编排层
   - 需求评审：`stage1_review`
   - 测试点生成：`stage2_testpoints`
   - 测试用例生成：`stage3_testcases`
   - 本地导出：评审报告 Markdown、问题清单 Excel、XMind Markdown、测试用例 Excel、测分报告

3. Agent Harness 层
   - s03 计划展示：`todo_write`
   - s04 子代理：`run_subagent`
   - s05 技能加载：`load_skill`
   - s06 上下文压缩：`micro_compact`、`auto_compact`
   - s07 任务持久化：`TaskStore`
   - s09 长期记忆：`MemoryStore`、`MemoryRAG`
   - s11 容错降级：异常捕获、重试、空结果继续

4. 知识增强层
   - 文档知识库：`knowledge_base/`
   - 向量索引：`.kb_index/`
   - 检索器：`scripts/kb_rag.py`
   - 知识提炼：`scripts/kb_distill.py`

5. 记忆层
   - 长期记忆：`memory/long_term.json`
   - 需求短期记忆：`memory/<req_stem>.json`
   - 记忆向量索引：`.memory_index/`

6. 交付层
   - `output/<需求名>/<时间戳>/review_report*.md`
   - `output/<需求名>/<时间戳>/review_issues*.xlsx`
   - `output/<需求名>/<时间戳>/review_mindmap*.md`
   - `output/<需求名>/<时间戳>/testpoints_xmind*.md`
   - `output/<需求名>/<时间戳>/testcases*.xlsx`
   - `output/<需求名>/<时间戳>/report*.md`
   - `output/<需求名>/<时间戳>/*.json` 机器可读底层产物

## 3. 关键目录说明

```text
TestCaseMind/
├── scripts/              # 所有 Python 脚本入口与内部模块
├── skills/               # 三个大模型技能说明文件
├── knowledge_base/       # 本地知识库，存放规范性 Markdown 文档
├── memory/               # 长期记忆和需求级短期记忆
├── models/               # 本地 embedding 模型
├── output/               # 每次生成的测试资产
├── .sections/            # --section 模式下提取出的章节临时文件
├── .tasks/               # s07 任务状态文件
├── .mcp_jobs/            # MCP 异步任务状态和日志
├── .kb_index/            # 知识库向量索引
├── .memory_index/        # 长期记忆向量索引
├── config/               # 章节过滤等配置
└── docs/                 # 系统说明文档
```

`scripts/` 中的脚本会把项目根目录作为工作目录，因此移动脚本位置后，知识库、输出、记忆、任务文件仍然读写根目录下的对应文件夹。

## 4. 初始化与安装流程

项目可以直接从 GitHub 下载后本地运行：

```bash
git clone https://github.com/Joeyzheng001/TestCaseMind.git
cd TestCaseMind
```

推荐使用独立 Python 环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果使用 Conda：

```bash
conda create -n testcase-mind python=3.12
conda activate testcase-mind
pip install -r requirements.txt
```

不建议在 `base` 环境中直接运行 TestCaseMind。`base` 环境常常被多个项目共享，其他 agent 或音视频处理工具可能安装 `torchcodec`、`whisperx`、`pyannote-audio` 等依赖。TestCaseMind 的 RAG 只需要文本 embedding，但 `sentence-transformers/transformers` 的导入链可能探测到这些音视频依赖；如果这些依赖的 FFmpeg 动态库版本不匹配，就会导致文本 RAG 初始化失败。

macOS 上建议额外安装 `pandoc`，用于 Word 文档转换兜底：

```bash
brew install pandoc
```

本地 RAG 需要 embedding 模型，首次使用需下载：

```bash
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

复制配置模板并填写模型 API Key：

```bash
cp .env.example .env
```

`.env` 中常用配置：

```text
ANTHROPIC_API_KEY=...
ANTHROPIC_BASE_URL=...
MODEL_ID=...
HF_ENDPOINT=https://hf-mirror.com
```

初始化验证：

```bash
python scripts/agent.py --help
python scripts/kb_check.py --quick
```

如果出现 `401 Authentication Fails, api key is invalid`，优先检查 `.env` 中的 key 是否有效，并确认 shell 中没有残留旧的 `ANTHROPIC_AUTH_TOKEN`：

```bash
unset ANTHROPIC_AUTH_TOKEN
```

## 5. 核心运行流程

### 5.1 输入处理

用户可以传入 `.docx`、`.doc`、`.md`、`.txt` 等需求文档。主程序会先解析命令行参数：

```bash
python scripts/agent.py "需求文档.docx" --kb
python scripts/agent.py "需求文档.md" --kb --section "5.8 ETF退款金"
python scripts/agent.py "需求文档.md" --kb --no-cases
python scripts/agent.py "需求文档.md" --kb --resume
```

当输入是 Word 文档时，系统优先使用 `scripts/docx2md.py` 转为 Markdown，并写入 `knowledge_base/`。如果转换失败，再降级使用 `pandoc`。

除 PRD/需求规格外，系统也支持把开发设计文档作为知识来源。开发设计文档一般不作为本次生成的 `REQ` 主输入，而是进入 `knowledge_base/`，在测试点生成阶段通过 RAG 作为 `KB` 来源补充实现逻辑、数据来源、字段口径、计算细节和异常分支。

当指定 `--section` 时，系统会从文档中提取包含关键词的章节，写入 `.sections/_section_<需求名>_<时间戳>.md` 临时文件，再只针对该章节执行后续流程。

### 5.2 阶段一：需求评审

入口函数是 `stage1_review`。该阶段会启动一个子代理，从测试视角读取需求文档，并加载 `skills/requirement-review/requirement-review.md`。

评审阶段的底层结果是结构化 JSON，同时会在交付阶段导出为 `review_report*.md`、`review_issues*.xlsx` 和 `review_mindmap*.md`。结构化评审结果包含：

- `score`：需求质量分。
- `summary`：整体质量摘要。
- `completeness_issues`：完整性问题。
- `consistency_issues`：一致性问题。
- `untestable_items`：不可测试或模糊描述。
- `risk_flags`：安全、性能、集成等风险标记。
- `testable_features`：后续测试点生成的功能输入。

如果评审失败，s11 容错机制会返回空评审结果继续执行，不让整个任务崩掉。

### 5.3 阶段二：测试点生成

入口函数是 `stage2_testpoints`。它分为两个子阶段。

阶段 A 是需求直出测试点。系统会把 Markdown 按标题拆分为章节，对有实质内容的章节逐段调用大模型生成 `REQ` 来源测试点。每个测试点会包含：

- `testpoint_id`
- `functional_module`
- `test_scenario`
- `source`
- `source_ref`
- `preconditions`
- `test_steps`
- `expected_result`
- `priority`
- `remarks`

阶段 B 是知识库和风险补充。启用 `--kb` 后，系统通过 `KBRetriever` 检索 `knowledge_base/`，把相关段落注入 prompt，让模型生成 `KB` 和 `RISK` 来源测试点。

`KB` 代表知识库补充，常见来源包括枚举值、字段约束、表结构、开发设计实现逻辑、行业规则、历史沉淀规则。`RISK` 代表基于测试经验推断的风险场景，例如并发竞争、数据精度丢失、数据同步延迟、外部依赖失败等。

系统还会额外检索 `knowledge_base/design/` 下的因子设计文档，并使用独立的 `.design_index/` 索引做设计文档增强。

### 5.4 阶段三：测试用例展开

入口函数是 `stage3_testcases`。系统会把测试点按批次切分，默认每批 10 条，最多 3 个并发 worker。每批调用 `stage3_testcases_batch`，加载 `skills/testcase-gen/testcase-gen.md`，把测试点展开为完整测试用例。

测试用例强调可执行性，要求包含：

- 具体前置条件。
- 可落地测试数据。
- 明确操作步骤。
- 公式类场景的计算过程。
- 数据库或接口校验字段。
- 可验证的预期结果。

并行生成时使用 `_wait_rate_limit` 做简单限速，避免多个批次同时打 API 导致 429 或 529。

### 5.5 阶段四：本地导出

用例生成结束后，系统在本地生成交付资产：

- 需求评审报告 Markdown：质量等级、维度评分、问题清单和评审 mindmap。
- 需求评审问题清单 Excel：便于筛选、分派和评审会流转。
- 需求评审 XMind Markdown：可导入 XMind 的评审思维导图。
- 测试点 XMind Markdown：可导入 XMind 的测试点树。
- 测试用例 Excel：带来源颜色和优先级样式，可直接交付。
- 用例库纳入评审：Excel 中包含 `是否纳入用例库` 和 `未纳入原因` 字段，人工评审后可由 `scripts/learn_from_case_review.py` 学习未纳入原因。
- 测分报告 Markdown：由 `scripts/gen_report.py` 本地生成，不额外消耗 token。
- JSON 底层产物：保留评审、测试点、用例和 manifest，供 MCP、续跑、重生成和外部系统读取。

## 6. 七个 Harness 机制落地

### 6.1 s03：计划与进度可视化

实现位置：`scripts/agent.py` 中的 `todo_write` 工具。

需求评审子代理被要求先调用 `todo_write`，输出清晰的执行计划。例如：

```text
1. 列出执行计划
2. 加载 requirement-review 技能
3. 读取需求文档
4. 写入评审结果 JSON
```

这个机制让长任务不再是黑盒，用户能看到 Agent 当前处于哪一步，也方便排查卡点。

### 6.2 s04：子代理机制

实现位置：`run_subagent`。

需求评审阶段不是简单的一次 prompt，而是一个可以调用工具的子代理。子代理拥有以下工具：

- `read_file`：读取项目内文件。
- `bash`：运行受限 shell 命令。
- `write_file`：写入结构化结果。
- `load_skill`：加载技能说明。
- `todo_write`：输出执行计划。

子代理循环处理模型返回的 tool use，直到模型完成任务。它负责把评审过程拆成“读技能、读文档、写结果”的可控步骤。

### 6.3 s05：Skills 技能系统

实现位置：`skills/` 目录和 `load_skill`。

当前有三个技能：

- `requirement-review`：需求质量评审。
- `testpoint-gen`：测试点生成规则。
- `testcase-gen`：测试用例展开规则。
- `case-review-learning`：根据人工评审后的用例库纳入/未纳入结果，总结未纳入原因并沉淀为后续生成规则。

技能文件以 Markdown 描述任务、原则、关键规则和 JSON 输出格式。它们把测试工程经验从代码中抽离出来，成为可维护、可迭代的提示资产。

这个设计有两个好处：

- 改规则不用改主流程代码。
- 不同阶段可以加载不同技能，降低 prompt 混杂。

### 6.4 s06：上下文压缩

实现位置：`micro_compact` 和 `auto_compact`。

子代理多轮调用工具时，上下文会不断增长。系统做了两层控制：

- `micro_compact`：压缩历史工具结果，只保留最近几个重要结果。
- `auto_compact`：当估算 token 超过阈值时，调用模型把历史对话总结成中文摘要。

同时，`read_file` 这类关键工具结果会被保留，避免压缩掉需求原文等重要信息。

### 6.5 s07：任务持久化与续跑

实现位置：`scripts/task_store.py`。

系统把完整流程拆成四个阶段：

```text
review -> testpoints -> testcases -> export
```

每个阶段都有状态：

```text
pending -> running -> done | failed
```

状态文件保存在 `.tasks/<req_stem>_<ts>.json`。当使用 `--resume` 时，系统会查找该需求最近未完成任务，已完成阶段直接跳过，从失败或未完成阶段继续。

这个机制解决了长任务常见问题：中途断网、模型超时、Excel 导出失败时，不需要从头消耗 token 重跑。

### 6.6 s09：长期记忆系统

实现位置：

- `scripts/memory_store.py`
- `scripts/memory_rag.py`
- `memory/long_term.json`
- `memory/<req_stem>.json`

记忆分为两层：

1. 长期记忆：跨需求复用的规律。
   - `domain_patterns`
   - `quality_signals`
   - `testpoint_hints`
   - `risk_patterns`
   - `section_patterns`

2. 短期记忆：当前需求文档相关的经验。
   - 上次评审分。
   - 上次评审问题。
   - 已知功能点。
   - 已知因子模块。
   - 测试点数量。

系统会在评审后保存质量经验，在测试点生成后保存风险模式和模块信息。`MemoryRAG` 会把长期记忆向量化，只检索与当前需求最相关的历史经验，避免把全部记忆塞进 prompt。

### 6.7 s11：容错与降级

实现位置分布在 `run_subagent`、`stage1_review`、`stage2_testpoints`、`stage3_testcases` 和主流程中。

典型容错策略包括：

- 429/529 自动等待重试。
- 需求评审失败时返回空评审结果继续。
- JSON 解析失败时尝试提取 JSON 块或调用格式修复。
- RAG 检索失败时跳过知识库补充，保留 REQ 测试点。
- 单个测试用例批次失败时跳过该批，不影响其他批次。
- Excel 或报告生成失败时只提示 warning，不抹掉已生成 JSON。

这让系统更适合真实工作流：局部失败不会轻易吞掉整次运行。

## 7. 知识库机制

知识库目录是 `knowledge_base/`。它只应该保存稳定、可复用的规范性资料，例如：

- 数据字典。
- 表结构设计。
- 字段约束。
- 开发设计文档，包括实现逻辑、数据来源、计算口径、异常分支和接口/表字段映射。
- 因子设计文档。
- 通用测试规则。

不建议把 PRD 原文、一次性业务需求、还在评审中的规则、测试用例本身直接加入知识库。

### 7.1 知识入库

相关脚本：

- `scripts/kb_from_excel.py`：从表设计 Excel 提取表字段知识。
- `scripts/kb_from_design.py`：从因子设计 Excel 生成因子设计 Markdown。
- `scripts/kb_convert.py`：把知识库中的 Word 文档转换为 Markdown。
- `scripts/docx2md.py`：高质量 Word 到 Markdown 转换。

开发设计文档有两种入库方式：

- 普通 Word/Markdown 开发设计文档：放入 `knowledge_base/` 后用 `scripts/kb_convert.py` 转换或整理成 Markdown。
- 因子类 Excel 开发设计文档：使用 `scripts/kb_from_design.py` 拆分为 `knowledge_base/design/` 下的按因子组织的 Markdown，并生成 `00_因子索引.md`。

开发设计文档进入知识库后，生成测试点时会作为 `KB` 来源参与检索。它主要补充 PRD 中经常缺失的实现级信息，例如取数表、字段名、枚举映射、计算公式、数据优先级、默认值、空值处理、异常兜底和导出/展示字段口径。

### 7.2 向量检索

`KBRetriever` 会把知识库 Markdown 切分为段落，建立 ChromaDB 向量索引。切分策略优先按 Markdown 标题拆分，长段落再按行切分，并保留一定重叠，避免公式或字段说明上下文断裂。

索引会根据文件名、mtime、大小、首尾内容抽样计算 hash，知识库变化后自动重建。

检索结果会做两层控制：

- 相关度阈值过滤，默认过滤低相关段落。
- 字符预算控制，避免 prompt 过大。

### 7.3 知识提炼

`knowledge_base/通用规则积累.md` 已预置一版基础测试规则，覆盖枚举值、字段约束、计算边界、数据来源、异常兜底、并发风险、展示导出等通用场景。`scripts/kb_distill.py` 会从已经生成的测试点中继续提炼通用规则，主要关注 `KB` 和 `RISK` 来源测试点。它会判断哪些场景具有跨 PRD 复用价值，并追加到：

```text
knowledge_base/通用规则积累.md
```

写入后会尝试自动重建知识库索引，让新规则在后续任务中可检索。手工编辑该文件后，也应运行 `python scripts/kb_rag.py --rebuild` 更新索引。

## 8. MCP 自然语言入口

`scripts/mcp_server.py` 把系统封装为 Claude Code 可调用的 MCP Server。它的设计重点是异步任务：耗时生成流程不会阻塞 Claude Code，而是立刻返回 `job_id`，后台线程继续执行。

主要工具包括：

- `run_test_agent`：启动完整生成流程。
- `get_job_status`：查询任务进度、日志尾部和输出文件。
- `cancel_job`：取消运行中的任务。
- `convert_kb_docx`：把 Word 文档转换为 Markdown 并加入知识库。
- `save_to_knowledge_base`：把需求文档和风险经验沉淀到知识库和记忆。
- `list_outputs`：列出已有输出结果。
- `distill_knowledge`：异步 dry-run 知识提炼。
- `check_knowledge_base`：检查知识库健康状态。
- `review_memory`：查看长期记忆统计或导出。
- `rebuild_index`：异步重建知识库索引。

MCP 任务状态写入 `.mcp_jobs/`，每个任务包含 JSON 状态文件和日志文件。

### 8.1 MCP Server 的优化价值

MCP Server 是后续最值得重点优化的对象之一。原因是它处在用户自然语言入口和底层生成工作流之间，决定了系统是否能从“命令行工具”升级为“可持续协作的测试智能体”。

当前实现已经具备几个关键基础：

- 任务异步化：`run_test_agent` 立刻返回 `job_id`，后台线程继续执行。
- 状态可查询：`get_job_status` 可以读取任务状态、日志尾部和输出文件。
- 任务可取消：`cancel_job` 可以终止正在运行的子进程。
- 工具聚合：知识库转换、知识提炼、索引重建、记忆查看都通过 MCP 暴露给 Claude Code。
- 文件化状态：`.mcp_jobs/` 中保存任务 JSON 和日志，便于恢复和排查。

但它目前仍然是“轻量异步封装”，还不是完整的任务调度系统。后续可以重点优化以下方向：

1. 任务状态更细粒度

   现在的状态主要是 `pending/running/done/failed`，进度来自日志尾部。后续可以把 `review/testpoints/testcases/export` 四个阶段结构化写入 MCP job，使 Claude Code 能准确回答“现在跑到哪一步”“已生成多少测试点”“哪一批用例失败”。

2. 输出结果结构化

   已经加入初版 `manifest.json`。`agent.py` 会在测试点阶段和完整导出阶段写入标准运行清单，例如：

   ```text
   output/<需求名>/<时间戳>/manifest.json
   ```

   MCP 会优先读取 manifest，返回测试点数量、用例数量、文件路径、来源统计、评审分和告警信息。后续仍可以继续增强 manifest 的阶段明细、错误分类和耗时统计。

3. 任务生命周期管理

   后续可以增加任务队列、并发限制、超时策略、重试策略和历史任务清理策略，避免多个大文档同时运行时互相抢模型 API、embedding 模型或磁盘资源。

4. 错误分类与可恢复建议

   MCP 可以把常见失败分类为认证失败、模型限流、RAG 依赖失败、Word 转换失败、JSON 解析失败、Excel 导出失败等，并返回明确修复建议，而不是只暴露 `log_tail`。

5. 与 s07 任务系统打通

   当前 MCP 的 `.mcp_jobs/` 和 Agent 的 `.tasks/` 是两套状态。理想形态是 MCP job 能引用 `.tasks/` 的阶段状态，甚至直接触发 `--resume`，让自然语言入口天然支持断点续跑。

6. 产物预览与二次操作

   `get_job_status` 完成后可以返回可读摘要，例如评审分、REQ/KB/RISK 数量、Excel 路径、报告路径。进一步可以增加工具支持“只重新生成 Excel”“只重跑某个章节”“基于现有测试点补充 KB/RISK”“对已有用例做人工评审优化”。

7. 更安全的环境变量处理

   当前运行时容易受外部环境变量影响，例如旧的 `ANTHROPIC_AUTH_TOKEN` 会覆盖 `.env` 中的新 key。MCP 层可以在启动任务前做脱敏环境检查，发现冲突时直接返回提示，减少用户反复试错。

如果把 TestCaseMind 看作长期使用的测试平台，MCP Server 就是最适合沉淀“交互体验”和“运行稳定性”的地方。底层 `agent.py` 负责把一次任务跑完，MCP 则负责让用户能自然地启动、观察、追问、恢复、重跑和管理这些任务。

## 9. 数据流概览

```text
需求文档
  |
  | docx2md / pandoc
  v
Markdown 需求文档
  |
  | knowledge_base RAG 可同时检索数据字典、表设计、开发设计文档、因子设计文档
  |
  | stage1_review + requirement-review skill + memory
  v
需求评审 JSON
  |
  | export_review_markdown / export_review_issues_excel / export_review_mindmap
  v
评审报告 MD / 问题清单 Excel / 评审 XMind Markdown
  |
  | stage2_testpoints + testpoint-gen skill
  | + knowledge_base RAG
  | + design RAG
  v
测试点 JSON / 测试点 XMind Markdown
  |
  | stage3_testcases + testcase-gen skill
  v
测试用例 JSON
  |
  | export_excel + gen_report
  v
测试用例 Excel / 测分报告
  |
  | 人工填写“是否纳入用例库/未纳入原因”
  | learn_from_case_review + case-review-learning skill
  v
用例评审学习报告 / 长期记忆 testpoint_hints
  |
  | MemoryStore / kb_distill
  v
长期记忆 / 通用规则知识库
```

## 10. 输出资产说明

每次运行会在 `output/<需求名>/<时间戳>/` 下生成独立目录，避免覆盖历史结果。文件名中会带模型名和时间戳，例如：

```text
review_report_deepseek-v4-pro_1778203231.md
review_issues_deepseek-v4-pro_1778203231.xlsx
review_mindmap_deepseek-v4-pro_1778203231.md
testpoints_xmind_deepseek-v4-pro_1778203231.md
testcases_deepseek-v4-pro_1778203231.xlsx
report_deepseek-v4-pro_1778203231.md
review_deepseek-v4-pro_1778203231.json
testpoints_deepseek-v4-pro_1778203231.json
testcases_deepseek-v4-pro_1778203231.json
manifest.json
```

人工查看优先使用 Markdown、Excel 和 XMind Markdown：`review_report*.md` 看评审结论，`review_issues*.xlsx` 跟踪问题，`review_mindmap*.md` 和 `testpoints_xmind*.md` 导入 XMind，`testcases*.xlsx` 作为测试用例交付物。

JSON 仍会保留为机器可读底层产物，主要服务 MCP、续跑、重生成和外部系统集成。测试点 JSON 中包含 `meta.by_source`，用于统计 `REQ`、`KB`、`RISK` 三类来源数量。Excel 会用不同颜色区分来源，便于评审时识别哪些用例来自需求原文、哪些来自知识库和风险推断。`manifest.json` 是标准运行清单，面向 MCP 和外部工具，记录本次运行状态、评审摘要、测试点/用例数量、产物路径和告警信息。

## 11. 配置和运行注意事项

`.env` 中主要配置：

```text
ANTHROPIC_API_KEY=...
ANTHROPIC_BASE_URL=...
MODEL_ID=...
HF_ENDPOINT=...
```

主程序使用 `load_dotenv(..., override=True)`，以当前仓库 `.env` 为准，避免 shell 中残留的旧变量覆盖项目配置。尤其要注意 `ANTHROPIC_AUTH_TOKEN`：如果外部环境里存在旧 token，Anthropic SDK 可能优先读取它，导致认证失败。可以清理旧变量：

```bash
unset ANTHROPIC_AUTH_TOKEN
```

RAG 检索依赖本地 embedding 模型和 ChromaDB。若复用 `base` 环境，可能被其他项目安装的 `torchcodec`、`whisperx`、`pyannote-audio` 等音视频依赖影响，出现 FFmpeg 动态库版本冲突。推荐用独立 `.venv` 或 `testcase-mind` conda 环境只安装 `requirements.txt` 中声明的依赖。即使 RAG 依赖异常，系统也会跳过知识库补充，继续生成 REQ 来源测试点和测试用例。

## 12. 当前实现特点

TestCaseMind 的特点不是只“调用一次大模型生成测试用例”，而是把测试设计拆成了可控流程：

- 先评审需求质量，再生成测试资产。
- 测试点和测试用例分阶段生成，减少上下文污染。
- 通过 Skills 固化测试规范，让输出更稳定。
- 通过 RAG 引入本地知识，不依赖模型凭空记忆。
- 通过 Memory 记录跨项目经验，形成长期改进。
- 通过 TaskStore 支持续跑和阶段跳过。
- 通过 MCP 支持自然语言驱动和后台任务管理。
- 通过 s11 容错让局部失败不影响整体交付。

从工程形态上看，它是一个“测试用例生成工作流系统”，而不是一个单脚本 demo。它把 learn-claude-code 中的多个 Harness 机制组合到了真实业务场景里，让 AI 生成更可追踪、更可恢复、更可维护，也更贴近测试工程师的日常工作方式。
