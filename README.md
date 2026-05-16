# ThesisMind

ThesisMind 是一个本地优先的论文辅助工作台，面向工程管理、项目管理、质量管理、风险管理、成本管理、流程优化等方向的硕士论文写作场景。

系统把论文从“选题和项目背景”到“方法论选择、研究框架、章节大纲、引用生成、章节写作、开题材料、盲审风险检查”的流程串成一个可运行的本地 Web 应用，并配套 Python Agent、技能库、知识库索引、文档转换、引用卡片和商业许可证控制。

## 特点

- 本地优先：知识库、草稿、引用卡片、向量索引、导出文件默认都在本机。
- 面向论文流程：不是通用聊天工具，而是围绕工程管理类论文的真实写作路径设计。
- 方法论驱动：按“发现问题 / 解决问题 / 验证问题”组织方法卡片和章节逻辑。
- 知识库增强：支持 PDF、DOCX、Markdown 资料转换、入库、检索和引用卡片生成。
- 页面级技能：不同页面加载对应的写作引导 skill，减少泛泛而谈。
- 商业授权：支持免费试用、基础版、畅想版、VIP 版、管理员版的功能分层。

## 功能概览

| 模块 | 能力 |
| --- | --- |
| 基本配置 | 配置 Anthropic 兼容大模型服务、Base URL、模型名和 API Key |
| 论文信息 | 维护论文题目、研究方向、项目背景、论文思路和项目记忆 |
| 方法论选择 | 扫描本地方法论资料，按三阶段分配研究方法 |
| 研究框架 | 生成论文技术路线图、SVG 框架图和 Mermaid 源码 |
| 章节大纲 | 生成六章式论文目录，支持字数分配和章节调整 |
| 引用生成 | 从本地论文库、引用卡片和 LLM 补充中生成参考文献 |
| 章节写作 | 对章节进行扩写、重写、保存草稿和一致性检查 |
| 增值服务 | 生成开题报告、开题/中期/答辩 PPT、论文表格 |
| VIP 服务 | 盲审风险检查、AIGC 率评估、AIGC 降重 |
| 管理工具 | 知识库初始化、论文入库、许可证管理 |

## 快速开始

建议使用 Python 3.10+。

```bash
cd /Users/Joey/Agents/ThesisMind
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`，配置一个 Anthropic 兼容接口。DeepSeek 兼容端点示例：

```env
LLM_PROVIDER=deepseek
ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
ANTHROPIC_MODEL=deepseek-v4-pro
MODEL_ID=deepseek-v4-pro
ANTHROPIC_AUTH_MODE=api_key
ANTHROPIC_API_KEY=your_api_key_here
```

验证环境：

```bash
python verify.py
```

启动 Web 工作台：

```bash
python src/web_server.py --host 127.0.0.1 --port 8765
```

访问：

```text
http://127.0.0.1:8765
```

命令行 Agent：

```bash
python -m src.agent_loop
```

## 推荐使用流程

1. 在“基本配置”页面配置模型连接，并开始免费试用或激活许可证。
2. 在“论文信息”页面填写论文题目、研究方向、项目背景和论文思路。
3. 在“方法论选择”页面扫描知识库，选择发现、解决、验证阶段的方法。
4. 生成研究框架，确认技术路线图与章节逻辑是否一致。
5. 生成章节大纲，调整章节标题、三级目录和字数分配。
6. 生成参考文献，优先使用本地知识库中可追溯的真实文献。
7. 在“章节写作”页面逐节扩写和重写，并保存草稿。
8. 使用开题报告、PPT、表格、盲审检查、AIGC 检测等扩展能力完成交付材料。

## 项目结构

```text
ThesisMind/
├── src/
│   ├── web_server.py       # 本地 Web 服务和 API
│   ├── agent_loop.py       # 工具调用式论文 Agent
│   ├── tools.py            # 框架、大纲、引用、文件、格式检查等工具
│   ├── license_manager.py  # 许可证签发、验签和功能分层
│   ├── vector_store.py     # SQLite 本地向量库
│   ├── paper_store.py      # 论文和引用卡片结构化存储
│   ├── paper_pipeline.py   # 论文入库流水线
│   ├── document_converter.py
│   ├── skill_loader.py
│   └── ...
├── web/                    # Web 工作台前端
├── skills/                 # Agent 技能和页面引导
├── knowledge_base/         # 本地知识库，默认不提交到 git
├── cards/                  # 方法卡和风险卡源数据，默认不提交到 git
├── assets_enc/             # 加密资产包
├── docs/                   # 架构、产品、商业和许可证文档
├── tools/                  # 绘图等辅助脚本
├── output/                 # 工作区状态、导出文件、临时索引
├── license_cli.py          # 推荐使用的许可证 CLI
├── verify.py               # 环境和基础功能验证
└── requirements.txt
```

## 核心数据

| 路径 | 说明 |
| --- | --- |
| `knowledge_base/references/` | 原始论文、方法论资料和模板资料 |
| `knowledge_base/references/converted/` | 转换后的 Markdown 文本 |
| `knowledge_base/vector_store.sqlite3` | 本地向量索引 |
| `knowledge_base/papers.sqlite3` | 论文元数据和引用卡片数据库 |
| `knowledge_base/cards.sqlite3` | 方法卡和风险卡数据库 |
| `output/workspace.sqlite3` | Web 工作台状态、项目和草稿 |
| `output/` | 导出的 docx、pdf、pptx、svg、报告等文件 |

`knowledge_base/`、`cards/`、`output/` 包含用户资料或核心资产，默认由 `.gitignore` 忽略。

## Skills

`skills/` 下的 Markdown 文件由 `src/skill_loader.py` 解析，可注入 Agent 或页面助手。

| Skill | 作用 |
| --- | --- |
| `PAPER_ANALYSIS.md` | 论文结构、章节写作、学术规范 |
| `FRAMEWORK.md` | 研究框架、技术路线、流程模式 |
| `CITATION.md` | 引用规范、文献筛选、参考文献格式 |
| `DIAGRAM_DESIGN.md` | 框架图版式和 Mermaid 美化 |
| `DOCUMENT_CONVERSION.md` | PDF/DOCX 转 Markdown 的入库规则 |
| `PAGE_*.md` | Web 页面级引导 |
| `problem-diagnosis.md` | 现状诊断章节的问题识别方法 |

## 知识库初始化

Web 页面中可以通过“知识库初始化”触发完整流程，也可以用 Python 调用底层能力：

```bash
python -c "from src.vector_store import build_index; print(build_index(source_dirs=['knowledge_base', 'skills'], reset=True))"
```

知识库流程大致为：

```text
原始 PDF/DOCX/Markdown
    -> 文档转换与清洗
    -> 分类和元数据提取
    -> 方法论/引用/章节结构识别
    -> SQLite 结构化存储
    -> 本地向量索引
    -> 写作和引用生成时检索
```

扫描版 PDF 当前不会自动 OCR。没有可提取文本时，应先进行 OCR 再入库。

## 许可证

当前代码实现 5 级授权：

| 等级 | 标识 | 有效期 | 权限 |
| --- | --- | --- | --- |
| 免费试用 | `trial/free` | 3 天 | 基础工作流 |
| 基础版 | `basic` | 1 年 | 01-07 基础论文流程 |
| 畅想版 | `pro` | 2 年 | 基础流程 + 开题/PPT/表格等增值服务 |
| VIP 版 | `vip` | 2 年 | 全部用户功能 |
| 管理员版 | `admin` | 10 年 | 全部功能 + 知识库初始化 + 许可证管理 |

常用命令：

```bash
python license_cli.py status
python license_cli.py trial-start
python license_cli.py trial-check
python license_cli.py activate "TM-..."
python license_cli.py validate "TM-..."
python license_cli.py remove
```

许可证使用 Ed25519 非对称签名：

- 客户端只配置 `THESISMIND_LICENSE_PUBLIC_KEY`，用于离线验签。
- 签发环境才配置 `THESISMIND_LICENSE_PRIVATE_KEY`，用于生成 License Code。
- 不要把私钥放进客户机器、源码仓库、`.env.example` 或交付包。
- 旧版 HMAC 兼容仅在显式设置 `THESISMIND_LICENSE_KEY` 时启用，默认没有源码内置密钥。

签发示例：

```bash
export THESISMIND_LICENSE_PRIVATE_KEY="base64url_raw_private_key"
python license_cli.py generate --type basic --email user@example.com
python license_cli.py generate --type vip --email user@example.com --machine-id 123456789
```

客户端验签配置：

```bash
export THESISMIND_LICENSE_PUBLIC_KEY="base64url_raw_public_key"
```

更多细节见 [License Code 系统](docs/license/LICENSE_CODE_SYSTEM.md)。

## 加密资产

明文知识库和卡片是核心资产。交付时可以用 `encrypt_assets.py` 生成加密资产包：

```bash
python encrypt_assets.py --secret your_asset_key
```

运行时 `src.asset_crypto.AssetStore` 会从 `assets_enc/manifest.json` 读取密文清单，并把资产解密到临时目录。默认密钥来源：

1. `THESISMIND_ASSET_KEY`
2. 机器 ID 派生值

正式分发建议使用独立资产密钥，并配合许可证状态控制资产解密。

## 开发与验证

语法检查：

```bash
python -m py_compile src/license_manager.py src/web_server.py src/agent_loop.py
```

系统验证：

```bash
python verify.py
```

本地 API smoke test：

```bash
python src/web_server.py --host 127.0.0.1 --port 8765
curl http://127.0.0.1:8765/api/config
```

`src/tools.py` 中的 `run_command` 默认关闭。只有显式设置下面的变量后，Agent 才能使用少量白名单命令：

```bash
ENABLE_RUN_COMMAND=true
```

## 安全注意

- `.env` 可能保存真实 API Key，已经被 `.gitignore` 忽略，不要提交。
- 本地 Web 服务默认绑定 `127.0.0.1`；暴露到局域网或公网前，应增加认证、TLS 和反向代理访问控制。
- 服务端已对已映射的 `/api/` 功能接口做许可证校验，前端菜单隐藏不是唯一边界。
- 本地离线许可证无法阻止用户直接修改源码。强商业部署应叠加服务端激活、吊销列表、设备限额、发布包完整性校验。
- `knowledge_base/` 和 `cards/` 默认是明文资产目录，交付包应优先使用 `assets_enc/`。

## 已知改进方向

- `src/web_server.py` 仍是单文件服务，后续应拆分为路由层、服务层、存储层和 LLM 适配层。
- `docs/license/LICENSE_COMMERCIAL.md` 中仍有早期商业条款口径，技术授权以 `LICENSE_CODE_SYSTEM.md` 和当前代码为准。
- 自动化测试还需要覆盖 license 验签、API gating、知识库流水线、Web 前端关键流程。
- 当前向量索引是轻量本地实现，生产部署可替换为 bge、gte、text2vec 等本地 embedding 模型。

## 文档入口

- [架构设计](docs/architecture/ARCHITECTURE.md)
- [项目目录结构](docs/architecture/PROJECT_STRUCTURE.md)
- [数据结构](docs/architecture/DATA_STRUCTURES.md)
- [快速开始](docs/product/QUICKSTART.md)
- [License Code 系统](docs/license/LICENSE_CODE_SYSTEM.md)
- [商业许可协议](docs/license/LICENSE_COMMERCIAL.md)

