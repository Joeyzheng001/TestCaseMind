# ThesisMind 架构设计文档

## 系统架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面层                            │
│              (CLI / Web UI / 集成IDE)                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────────┐
│                    Agent 协调层                              │
│  (Thesis Agent / Research Agent / SubAgents)               │
├─────────────────────────────────────────────────────────────┤
│  功能:                                                      │
│  - 消息循环 (Agent Loop - s01)                             │
│  - 工具调度 (Tool Use - s02)                               │
│  - 任务规划 (Task Planning - s03)                          │
│  - 子Agent管理 (SubAgent - s04)                            │
│  - 技能加载 (Skill Loading - s05)                          │
│  - 上下文管理 (Context Compression - s06)                  │
│  - 多Agent协作 (Team Coordination - s09-s12)               │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────────┐
│                   工具和技能库层                              │
├─────────────────────────────────────────────────────────────┤
│  工具 (Tools):                                              │
│  ├─ 文件操作 (read/write/list)                              │
│  ├─ 论文分析 (analyze/extract)                              │
│  ├─ 框架生成 (generate_framework)                           │
│  ├─ 大纲生成 (generate_outline)                             │
│  ├─ 引用管理 (format/search citations)                      │
│  ├─ 文档转换 (PDF/DOCX -> Markdown/Text)                    │
│  ├─ 本地知识库 (build/search knowledge base)                 │
│  ├─ 格式检查 (check_format)                                 │
│  └─ 命令执行 (run_command)                                  │
│                                                              │
│  技能库 (Skills):                                            │
│  ├─ PAPER_ANALYSIS.md - 论文分析知识                         │
│  ├─ FRAMEWORK.md - 框架生成规则                              │
│  ├─ CITATION.md - 文献管理规范                               │
│  └─ ... 更多领域特定知识                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────────┐
│                   数据存储层                                  │
├─────────────────────────────────────────────────────────────┤
│  知识库 (Knowledge Base):                                   │
│  ├─ knowledge_base/papers/ - 论文库                         │
│  ├─ knowledge_base/templates/ - 模板库                      │
│  └─ knowledge_base/references/ - 文献库                     │
│                                                              │
│  本地向量库:                                                  │
│  └─ knowledge_base/vector_store.sqlite3                      │
│                                                              │
│  项目文件:                                                   │
│  └─ thesis_projects/ - 用户论文项目                         │
│                                                              │
│  输出文件:                                                   │
│  ├─ output/ - 生成的文档                                    │
│  └─ logs/ - 系统日志                                        │
└─────────────────────────────────────────────────────────────┘
```

## 核心组件详解

### 1. Agent 循环 (src/agent_loop.py)

**基于 learn-claude-code s01 模式**:

```python
def agent_loop(messages):
    while True:
        # 1. 调用Claude
        response = client.messages.create(
            model=MODEL,
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=TOOLS
        )
        
        # 2. 检查停止原因
        if response.stop_reason == "end_turn":
            return response.content[0].text
        
        # 3. 处理工具调用
        elif response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output = TOOL_HANDLERS[block.name](**block.input)
                    results.append({...output...})
            
            # 4. 循环继续
            messages.append({"role": "user", "content": results})
```

**特点**:
- 简单而强大的循环
- Agency来自Claude的决策
- Harness（环境）提供工具和知识

### 2. 工具系统 (src/tools.py)

**支持的工具分类**:

```
┌─ 文件操作工具
│  ├─ read_file
│  ├─ write_file
│  └─ list_directory
│
├─ 论文分析工具
│  ├─ analyze_paper_structure
│  └─ extract_paper_metadata
│
├─ 框架生成工具
│  ├─ generate_mermaid_framework
│  └─ generate_research_framework
│
├─ 大纲生成工具
│  └─ generate_outline
│
├─ 引用管理工具
│  ├─ format_citation
│  └─ search_citations
│
├─ 文档转换工具
│  └─ convert_local_document
│
├─ 本地知识库工具
│  ├─ build_knowledge_index
│  └─ search_knowledge_base
│
├─ 格式检查工具
│  └─ check_document_format
│
└─ 系统工具
   └─ run_command
```

**工具设计原则** (基于 learn-claude-code s02):
- 每个工具对应一个原子操作
- 工具输入输出清晰定义
- 工具与工具间正交（尽量减少耦合）

### 3. 本地向量知识库 (src/vector_store.py)

**商业化定位**:
- 客户论文、模板、引用资料默认保存在本机，不依赖第三方知识库
- 支持私有化部署，适合学校、机构、企业内网场景
- SQLite 单文件持久化，便于备份、迁移和按项目隔离
- Embedding 后端可替换：当前为本地哈希向量，后续可接入 bge-m3、gte、text2vec 等本地模型

**默认索引范围**:
```
knowledge_base/
├─ papers/       # 论文库
├─ references/   # 文献库
└─ templates/    # 模板库

skills/
├─ PAPER_ANALYSIS.md
├─ FRAMEWORK.md
└─ CITATION.md
```

**核心流程**:
```python
# 0. 可选：单文件转换，便于检查抽取质量
convert_local_document(
    file_path="knowledge_base/references/example.pdf",
    output_dir="knowledge_base/converted",
    output_format="md"
)

# 1. 构建索引
build_knowledge_index(
    source_dirs=["knowledge_base", "skills"],
    reset=True
)

# 2. 语义检索
search_knowledge_base(
    query="APA引用格式和文献综述写法",
    limit=5
)
```

**数据表**:
- `documents`: 文件路径、标题、内容哈希、元数据
- `chunks`: 文本块、chunk序号、向量、token数量

当前实现是零外部依赖的商业原型，主要目标是把数据所有权和接口边界先定下来。生产环境可以在不改变 Agent 工具接口的前提下替换更强的本地 embedding 模型。

**文档转换**:
- `.md`、`.txt`、`.json`、`.bib`、`.yaml` 直接读取
- `.docx` 通过 `python-docx` 提取标题、段落和表格
- `.pdf` 通过 `pypdf` 或 `PyPDF2` 提取可复制文本
- 扫描版 PDF 需要 OCR 模块，当前不会伪造空文本结果

### 4. 技能库系统 (skills/ 目录)

**基于 learn-claude-code s05 模式**:

```
技能库结构:
├─ PAPER_ANALYSIS.md
│  ├─ 论文结构规范
│  ├─ 章节写作指南
│  ├─ 学术写作规范
│  └─ 常见问题排查
│
├─ FRAMEWORK.md
│  ├─ 框架概念
│  ├─ 框架模式
│  ├─ 学科特定框架
│  └─ Mermaid示例
│
└─ CITATION.md
   ├─ 引用格式（APA、GB/T等）
   ├─ 文献来源
   ├─ 检索策略
   └─ 引用最佳实践
```

**知识加载方式** (s05):
- 按需加载，不提前注入
- 通过 `load_skill()` 函数动态加载
- 作为 tool_result 注入到对话中

### 5. 任务管理 (s07 预留)

```python
# 任务数据结构
class Task:
    id: str
    title: str
    description: str
    status: str  # pending, in_progress, completed
    dependencies: List[str]  # 依赖的任务ID
    assignee: str  # 分配的Agent
    created_at: datetime
    updated_at: datetime
    output: str
```

**持久化**:
- 任务保存到 `tasks.jsonl`
- 支持任务图的遍历和执行

### 6. 多Agent协作 (s09-s12 预留)

```
┌─ Team Coordinator
│  ├─ 任务分配
│  ├─ 进度跟踪
│  └─ 结果聚合
│
├─ Research Agent
│  ├─ 文献检索
│  ├─ 框架设计
│  └─ 方案论证
│
├─ Writing Agent
│  ├─ 大纲生成
│  ├─ 内容扩写
│  └─ 文本润色
│
├─ Review Agent
│  ├─ 格式检查
│  ├─ AIGC检测
│  └─ 质量评估
│
└─ Output Agent
   ├─ Word生成
   ├─ PDF转换
   └─ XMind生成
```

## 数据流

### 场景1: 生成论文框架

```
用户输入
  ↓
┌─ Thesis Agent
│ ├─ 理解用户需求
│ ├─ 调用 generate_research_framework()
│ └─ 获得框架和Mermaid图
│
└─ 生成输出
  ├─ Mermaid 流程图
  ├─ 框架描述
  └─ 章节建议
```

### 场景2: 生成论文大纲

```
用户输入（可包含框架）
  ↓
┌─ Thesis Agent
│ ├─ 读取或生成框架
│ ├─ 加载 PAPER_ANALYSIS.md 技能
│ ├─ 调用 generate_outline()
│ └─ 获得多层级大纲
│
└─ 输出处理
  ├─ 生成 Word .docx
  ├─ 生成 XMind .xmind
  └─ 保存为 Markdown
```

### 场景3: 管理引用文献

```
用户输入（搜索关键词）
  ↓
┌─ Thesis Agent
│ ├─ 加载 CITATION.md 技能
│ ├─ 调用 search_citations()
│ ├─ 检索到相关文献
│ ├─ 调用 format_citation()
│ └─ 格式化为所需风格
│
└─ 输出处理
  ├─ 显示文献列表
  ├─ 一键复制引文
  └─ 保存到项目
```

## 文件组织

```
ThesisMind/
├── src/                           # 核心源码
│   ├── __init__.py
│   ├── agent_loop.py             # 主Agent循环 (s01)
│   ├── tools.py                  # 工具实现 (s02)
│   └── utils/
│       ├── __init__.py
│       ├── file_utils.py
│       └── format_utils.py
│
├── agents/                        # Agent实现
│   ├── __init__.py
│   ├── thesis_agent.py           # 主论文Agent
│   ├── research_agent.py         # 研究Agent
│   ├── writer_agent.py           # 写作Agent (后续)
│   └── review_agent.py           # 评审Agent (后续)
│
├── skills/                        # 技能库
│   ├── PAPER_ANALYSIS.md         # 论文分析技能 (s05)
│   ├── FRAMEWORK.md              # 框架生成技能
│   ├── CITATION.md               # 文献管理技能
│   └── FORMAT_CHECK.md           # 格式检查技能 (后续)
│
├── knowledge_base/               # 知识库数据
│   ├── papers/                   # 论文库
│   │   └── metadata.json
│   ├── templates/                # 模板库
│   │   ├── thesis_template.docx
│   │   └── outline_template.md
│   └── references/               # 文献库
│       └── references.bib
│
├── templates/                     # 输出模板
│   ├── thesis_outline_template.md
│   ├── mermaid_templates/
│   └── docx_templates/
│
├── output/                        # 输出文件
│   ├── frameworks/
│   ├── outlines/
│   ├── papers/
│   └── citations/
│
├── logs/                          # 日志
│   └── thesis_mind.log
│
├── docs/                          # 文档
│   ├── ARCHITECTURE.md           # 本文件
│   ├── USER_GUIDE.md
│   ├── DEV_GUIDE.md
│   └── API_REFERENCE.md
│
├── tests/                         # 测试 (后续)
│   └── test_agent_loop.py
│
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── init.py                       # 项目初始化脚本
└── pyproject.toml               # 项目配置 (后续)
```

## 配置管理

### .env 配置

```env
# API配置
ANTHROPIC_API_KEY=sk-...
ANTHROPIC_MODEL=claude-opus-4-1

# 路径配置
PROJECT_ROOT=./
KNOWLEDGE_BASE_PATH=./knowledge_base
OUTPUT_PATH=./output

# 功能开关
ENABLE_AIGC_DETECTION=true
ENABLE_XMIND_EXPORT=true
ENABLE_PDF_EXPORT=true

# 日志配置
LOG_LEVEL=INFO
```

## 扩展机制

### 添加新工具

1. 在 `src/tools.py` 中实现函数
2. 在 `TOOLS` 字典中注册
3. Agent会自动识别和使用

### 添加新技能

1. 创建 `skills/YOUR_SKILL.md`
2. 按照YAML frontmatter格式定义元数据
3. 编写知识内容
4. Agent可通过 `load_skill()` 加载

### 添加新Agent

1. 继承 `ThesisAgent` 基类
2. 重写 `run()` 或 `process()` 方法
3. 在 `agents/` 目录中实现
4. 通过 `spawn_subagent()` 创建

## 性能考虑

### 上下文管理 (s06)

- **消息历史压缩** - 防止context溢出
- **知识按需加载** - 不提前注入所有知识
- **任务分解** - 大任务拆分为子任务

### 并发处理 (s08-s09)

- 后台任务线程
- 异步工具调用
- 多Agent并行执行

## 安全性

### 权限控制

- 文件操作限制在项目目录
- 命令执行的沙箱隔离
- API密钥环境变量管理

### 数据保护

- 用户论文数据本地保存
- 敏感信息不上传到API
- 日志中不记录密钥

## 测试策略

```
单元测试
├─ 工具函数测试
└─ 技能加载测试

集成测试
├─ Agent循环测试
└─ 完整流程测试

端到端测试
└─ 用户场景模拟
```

## 部署

### 本地运行
```bash
pip install -r requirements.txt
python -m src.agent_loop
```

### Docker容器 (后续)
```bash
docker build -t thesis-mind .
docker run -e ANTHROPIC_API_KEY=sk-... thesis-mind
```

### Web服务 (后续)
- FastAPI + 前端界面
- 支持多用户并发

---

**设计原则总结**:
1. **简化** - 核心仅需Agent循环和工具
2. **模块化** - 技能、工具、Agent都可独立扩展
3. **透明** - 清晰的数据流和决策过程
4. **可扩展** - 易于添加新功能不改动现有代码
5. **学术友好** - 深入理解learn-claude-code框架
