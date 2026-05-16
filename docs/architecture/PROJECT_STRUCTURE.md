# ThesisMind 项目目录结构

```
ThesisMind/                          # 项目根目录
│
├── 📄 README.md                     # 项目概述
├── 📄 ARCHITECTURE.md               # 系统架构设计文档
├── 📄 QUICKSTART.md                 # 快速开始指南
├── 📄 DEVELOPMENT_PLAN.md           # 开发路线图和计划
├── 📄 DATA_STRUCTURES.md            # 核心数据结构文档
├── 📄 PROJECT_STRUCTURE.md          # 本文件
│
├── 📄 requirements.txt              # Python依赖包列表
├── 📄 .env.example                  # 环境变量示例
├── 📄 .gitignore                    # Git忽略文件
├── 📄 init.py                       # 项目初始化脚本
├── 📄 verify.py                     # 系统验证脚本
│
│
├── 📁 src/                          # 核心源码目录
│   ├── __init__.py                  # 模块初始化
│   ├── agent_loop.py                # 主Agent循环实现 (s01)
│   ├── tools.py                     # 工具集实现 (s02)
│   └── utils/                       # 工具函数目录
│       ├── __init__.py
│       ├── file_utils.py            # 文件操作工具
│       ├── format_utils.py          # 格式化工具
│       └── text_utils.py            # 文本处理工具
│
│
├── 📁 agents/                       # Agent实现目录 (s01-s12)
│   ├── __init__.py
│   ├── README.md                    # Agent实现说明
│   ├── thesis_agent.py              # 主论文Agent (s01)
│   ├── research_agent.py            # 研究Agent (s04-s05)
│   ├── writer_agent.py              # 内容写作Agent (后续)
│   ├── review_agent.py              # 质量审查Agent (后续)
│   └── subagents/                   # 子Agent目录
│       ├── __init__.py
│       ├── framework_generator.py   # 框架生成子Agent
│       ├── outline_generator.py     # 大纲生成子Agent
│       └── citation_manager.py      # 文献管理子Agent
│
│
├── 📁 skills/                       # 技能库目录 (s05)
│   ├── PAPER_ANALYSIS.md            # 论文分析技能
│   │   └── 包含: 论文结构规范、章节写作指南、学术规范等
│   ├── FRAMEWORK.md                 # 框架生成技能
│   │   └── 包含: 框架模式、Mermaid示例、多学科模板等
│   ├── CITATION.md                  # 文献管理技能
│   │   └── 包含: 引用格式、搜索策略、最佳实践等
│   ├── FORMAT_CHECK.md              # 格式检查技能 (后续)
│   └── AIGC_DETECTION.md            # AIGC检测知识库 (后续)
│
│
├── 📁 knowledge_base/               # 知识库数据存储
│   │
│   ├── 📁 papers/                   # 论文库元数据
│   │   ├── metadata.json            # 论文库索引
│   │   ├── cs_papers.json           # 计算机科学论文库
│   │   ├── medical_papers.json      # 医学论文库
│   │   └── ...
│   │
│   ├── 📁 templates/                # 模板库
│   │   ├── thesis_template.docx     # 学位论文模板
│   │   ├── conference_template.docx # 会议论文模板
│   │   ├── outline_template.md      # 大纲模板
│   │   └── frameworks/              # 框架模板集
│   │
│   └── 📁 references/               # 参考文献库
│       ├── references.bib           # BibTeX文献库
│       ├── citations.json           # JSON格式文献库
│       └── citation_styles/         # 引用格式定义
│
│
├── 📁 tools/                        # 工具模块目录
│   ├── __init__.py
│   ├── document_tools.py            # 文档处理工具 (Word, PDF)
│   ├── graph_tools.py               # 图表生成工具 (Mermaid, PlantUML)
│   ├── citation_tools.py            # 文献管理工具 (格式化、搜索)
│   ├── format_checker.py            # 格式检查工具
│   └── aigc_detector.py             # AIGC检测工具 (后续)
│
│
├── 📁 templates/                    # 输出模板目录
│   ├── thesis_outline_template.md   # 论文大纲Markdown模板
│   ├── mermaid_templates/           # Mermaid图模板库
│   │   ├── flowchart.mmd
│   │   ├── mindmap.mmd
│   │   └── ...
│   └── docx_templates/              # Word文档模板库
│       ├── thesis_structure.xml
│       └── formatting_styles.xml
│
│
├── 📁 output/                       # 输出文件目录
│   │
│   ├── 📁 frameworks/               # 生成的研究框架
│   │   ├── *.svg                    # SVG格式框架图
│   │   ├── *.png                    # PNG格式框架图
│   │   └── *.mmd                    # Mermaid源文件
│   │
│   ├── 📁 outlines/                 # 生成的论文大纲
│   │   ├── *.docx                   # Word大纲
│   │   ├── *.xmind                  # XMind思维导图
│   │   └── *.md                     # Markdown大纲
│   │
│   ├── 📁 papers/                   # 生成或处理的论文
│   │   ├── *.docx
│   │   ├── *.pdf
│   │   └── *.md
│   │
│   ├── 📁 citations/                # 生成的引文列表
│   │   ├── *.bib
│   │   └── *.json
│   │
│   └── 📁 reports/                  # 质量检查报告
│       ├── format_check_*.json
│       └── aigc_detection_*.json
│
│
├── 📁 logs/                         # 日志文件目录
│   ├── thesis_mind.log              # 主日志文件
│   └── error.log                    # 错误日志
│
│
├── 📁 docs/                         # 文档目录
│   ├── USER_GUIDE.md                # 用户指南 (后续)
│   ├── DEV_GUIDE.md                 # 开发者指南 (后续)
│   ├── API_REFERENCE.md             # API参考文档 (后续)
│   └── TROUBLESHOOTING.md           # 故障排查指南 (后续)
│
│
├── 📁 tests/                        # 测试目录 (后续)
│   ├── __init__.py
│   ├── test_agent_loop.py           # Agent循环测试
│   ├── test_tools.py                # 工具测试
│   ├── test_framework.py            # 框架生成测试
│   ├── test_outline.py              # 大纲生成测试
│   └── test_integration.py          # 集成测试
│
│
├── 📁 examples/                     # 示例代码目录 (后续)
│   ├── basic_usage.py               # 基础使用示例
│   ├── framework_generation.py      # 框架生成示例
│   ├── outline_generation.py        # 大纲生成示例
│   └── citation_management.py       # 文献管理示例
│
│
└── 📁 .github/                      # GitHub配置 (后续)
    └── workflows/
        └── ci.yml                   # CI/CD工作流
```

## 核心目录说明

### `/src` - 核心源码
- **agent_loop.py** - 实现了learn-claude-code的s01基础Agent循环
- **tools.py** - 实现了s02工具系统，包含所有与论文相关的工具
- **utils/** - 辅助工具函数

### `/agents` - Agent实现
- **thesis_agent.py** - 主论文Assistant，直接继承ThesisAgent类
- **research_agent.py** - 研究子Agent，处理文献和框架
- **writer_agent.py** - 写作子Agent，处理内容生成
- **subagents/** - 特定功能的子Agent实现

### `/skills` - 技能库
实现learn-claude-code的s05机制：
- 每个.md文件是一个"技能"，包含该领域的知识
- 文件使用YAML frontmatter定义元数据
- Agent按需加载，不提前注入

### `/knowledge_base` - 知识库
- **papers/** - 论文库元数据，支持快速查询
- **templates/** - 各类模板集合
- **references/** - 文献库，支持多格式

### `/output` - 输出文件
- **frameworks/** - 生成的研究框架图
- **outlines/** - 生成的论文大纲（多格式）
- **papers/** - 处理或生成的论文文件
- **reports/** - 质量检查和AIGC检测报告

## 关键设计原则

### 1. 模块化 (Modularity)
- 每个目录对应一个功能模块
- 模块间通过清晰的接口通信
- 易于独立测试和维护

### 2. 可扩展性 (Extensibility)
- 添加新Agent：在`agents/`目录创建新文件
- 添加新技能：在`skills/`目录创建新的.md文件
- 添加新工具：在`src/tools.py`添加新函数

### 3. 数据驱动 (Data-Driven)
- 知识库存储在`knowledge_base/`
- 输出文件集中在`output/`
- 便于版本控制和备份

### 4. 分离关注点 (Separation of Concerns)
- 源码逻辑与知识库分离
- 工具实现与调用分离
- Agent协调与具体任务分离

## 文件大小参考

```
src/
├── agent_loop.py      ~200 lines  (Agent循环)
├── tools.py           ~400 lines  (工具实现)
└── utils/
    ├── file_utils.py  ~100 lines
    ├── format_utils.py ~150 lines
    └── text_utils.py  ~100 lines

skills/
├── PAPER_ANALYSIS.md  ~400 lines  (知识库)
├── FRAMEWORK.md       ~500 lines
└── CITATION.md        ~600 lines

agents/
├── thesis_agent.py    ~150 lines  (继承ThesisAgent)
└── research_agent.py  ~200 lines  (子Agent)
```

## 项目初始化流程

```
1. init.py           # 创建所有目录和初始文件
2. verify.py         # 验证环境和依赖
3. -m src.agent_loop # 启动主Agent
```

## 部署和打包

```
# 开发环境
ThesisMind/                 # 上述完整结构

# 生产环境
thesis-mind/
├── src/                    # 核心代码
├── agents/                 # Agent实现
├── skills/                 # 技能库（可选，可从远程加载）
├── knowledge_base/         # 知识库（可选，可从云端同步）
└── config.json            # 配置文件
```

---

**最后更新**: 2026-05-08
**项目状态**: 初始化阶段
**下一步**: 完成Phase 1的所有实现和测试
