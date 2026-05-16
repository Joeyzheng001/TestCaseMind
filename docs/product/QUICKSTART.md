# ThesisMind 快速开始指南

## 📋 目录

1. [安装](#安装)
2. [配置](#配置)
3. [快速示例](#快速示例)
4. [常见用场景](#常见用场景)
5. [故障排查](#故障排查)

## 安装

### 前置要求

- Python 3.8+
- pip 或 conda
- Anthropic API Key (免费获取: https://console.anthropic.com)

### 步骤1: 克隆项目

```bash
cd /Users/Joey/Agents
```

项目已创建于 `ThesisMind` 目录

### 步骤2: 安装依赖

```bash
cd ThesisMind
pip install -r requirements.txt
```

### 步骤3: 配置环境变量

```bash
cp .env.example .env
```

使用编辑器打开 `.env` 并填入:

```env
ANTHROPIC_API_KEY=your_actual_api_key_here
ANTHROPIC_MODEL=claude-opus-4-1
```

### 步骤4: 初始化项目

```bash
python init.py
```

这会创建所有必要的目录结构。

## 配置

### 基础配置

**项目路径** (.env):
```env
PROJECT_ROOT=./
KNOWLEDGE_BASE_PATH=./knowledge_base
OUTPUT_PATH=./output
```

### 功能开关

```env
# AIGC检测
ENABLE_AIGC_DETECTION=true
AIGC_THRESHOLD=0.7

# 导出格式
ENABLE_XMIND_EXPORT=true
ENABLE_PDF_EXPORT=true

# API接入
ARXIV_API=true
SEMANTICSCHOLAR_API=true
```

### 文献格式

```env
DEFAULT_CITATION_STYLE=apa
CITATION_FORMATS=apa,chicago,harvard,gb7714
```

## 快速示例

### 示例1: 启动交互式Agent

```bash
python -m src.agent_loop
```

输出:
```
============================================================
🎓 ThesisMind - AI论文辅助系统
============================================================
输入 'exit' 退出，输入 'clear' 清空历史

📝 你: 
```

### 示例2: 生成论文框架

**输入**:
```
你: 我要写一篇关于"深度学习在医学影像诊断中的应用"的硕士论文，帮我生成一个研究框架
```

**Agent处理**:
```
🤖 助手: 我来帮你生成这个研究课题的框架。
🔧 使用工具: generate_research_framework
   参数: {
     "topic": "深度学习在医学影像诊断中的应用",
     "discipline": "medical"
   }
   结果: {...}
```

**输出**:
```
✓ 研究框架已生成:

📊 研究阶段:
1. 临床背景分析
2. 文献综述
3. 深度学习方法设计
4. 医学影像数据处理
5. 模型实验与验证
6. 临床应用评估
7. 结论与展望

🎯 关键组件:
- 医学基础知识
- 深度学习基础
- 影像数据处理
- 模型设计与优化
- 临床有效性验证

📈 框架流程图 (Mermaid):
graph TD
    A["研究主题: 深度学习在医学影像诊断中的应用"] --> B["临床背景分析"]
    B --> C["文献综述"]
    ...
```

### 示例3: 生成论文大纲

**输入**:
```
你: 基于这个框架，帮我生成一个详细的论文大纲，导出为Word和XMind两种格式
```

**输出**:
```
✓ 大纲已生成并导出

📝 论文大纲:

第一章 绪论
  1.1 研究背景
  1.2 研究意义
  1.3 主要内容
  1.4 创新点

第二章 文献综述
  2.1 医学影像诊断现状
  2.2 深度学习在医学影像中的应用进展
  2.3 存在的问题和挑战
  2.4 本文改进方向

...

📁 输出文件:
✓ output/outlines/thesis_outline.docx
✓ output/outlines/thesis_outline.xmind
✓ output/outlines/thesis_outline.md
```

### 示例4: 搜索和管理文献

**输入**:
```
你: 帮我搜索和这个主题相关的参考文献，用APA格式列出前10篇
```

**输出**:
```
🔍 搜索相关文献...

📚 找到10篇相关论文:

[1] LeCun, Y., Bengio, Y., & Hinton, G. E. (2015). Deep learning. 
    Nature, 521(7553), 436-444.

[2] Ronneberger, O., Fischer, P., & Brox, T. (2015). U-Net: 
    Convolutional networks for biomedical image segmentation. 
    In International Conference on Medical Image Computing and 
    Computer-Assisted Intervention (pp. 234-241).

[3] He, K., Zhang, X., Ren, S., & Sun, J. (2016). Deep residual 
    learning for image recognition. In Proceedings of the IEEE 
    conference on computer vision and pattern recognition (pp. 770-778).

...

✅ 文献已保存到项目
```

## 常见用场景

### 场景1: 快速开始论文写作

```bash
# 1. 启动Agent
python -m src.agent_loop

# 2. 输入要求
> 帮我生成一篇关于"区块链在供应链管理中的应用"的论文框架

# 3. 获得框架
✓ 框架已生成

# 4. 生成大纲
> 基于框架生成详细大纲，导出Word格式

# 5. 获得文档
✓ 已导出至 output/outlines/

# 6. 管理文献
> 搜索相关文献，GB/T 7714格式

# 7. 开始写作
> 帮我扩写第二章"文献综述"部分
```

### 场景2: 论文格式检查

```bash
> 检查我的论文格式是否规范
> 文件路径: output/my_thesis.docx

✓ 格式检查结果
⚠️ 发现问题:
  - 字体不统一: 第5页使用了Arial
  - 行距不一致: 第12-15页为1.0倍
  - 页边距错误: 右边距为2.0cm，应为2.5cm

✅ 建议:
  - 统一使用 宋体 12pt
  - 设置行距为 1.5倍
  - 调整页边距为上下左右各2.5cm
```

### 场景3: AIGC内容检测

```bash
> 检查我的论文中是否包含AI生成的内容

✓ 检测完成
📊 结果:
  - 总字数: 50000
  - 可能AI生成: 3.2% (1600字)
  - 原创度评分: 96.8/100

⚠️ 高风险段落:
  第3章第2节 第45-67行 (850字) - 96.5% AI生成概率
  第5章第1节 第10-32行 (700字) - 87.3% AI生成概率

💡 建议:
  - 这些段落建议手动改写
  - 添加更多个人分析和见解
  - 增加具体数据和案例支撑
```

## 故障排查

### 问题1: ImportError: No module named 'anthropic'

**解决方案**:
```bash
pip install anthropic>=0.42.0
```

### 问题2: ANTHROPIC_API_KEY not found

**解决方案**:
1. 检查 `.env` 文件是否存在
2. 确认 `ANTHROPIC_API_KEY` 已填写
3. 验证API Key是否有效

```bash
# 测试API
python -c "from anthropic import Anthropic; print('✓ API库正常')"
```

### 问题3: FileNotFoundError: knowledge_base not found

**解决方案**:
```bash
# 重新运行初始化
python init.py
```

### 问题4: 工具执行失败

**查看日志**:
```bash
tail -f logs/thesis_mind.log
```

**常见原因**:
- 文件路径错误
- 权限不足
- 磁盘空间不足

## 高级用法

### 使用特定学科框架

```bash
> 我是医学专业，帮我生成医学论文框架
> 生成计算机科学领域的研究框架
> 社会科学定性研究框架
```

### 批量处理文献

```bash
# 创建 citations.txt，每行一条文献信息
> 批量导入文献并生成参考文献表

# 输出多种格式的参考文献
> 生成APA、GB/T、Chicago三种格式的参考文献表
```

### 自定义输出格式

```bash
> 生成Markdown格式的大纲
> 导出为LaTeX格式
> 生成PDF版本
```

## 更多资源

### 文档
- [架构设计文档](../architecture/ARCHITECTURE.md)
- [API参考](docs/API_REFERENCE.md) (即将推出)
- [技能库文档](skills/)

### 示例
- [使用示例脚本](examples/) (即将推出)
- [学科特定模板](knowledge_base/templates/)

### 社区
- 在GitHub提交Issue
- 参与讨论和贡献

## 下一步

### 基础用法
1. ✓ 环境配置
2. ✓ 运行第一个命令
3. → 生成论文框架
4. → 生成论文大纲
5. → 管理引用文献

### 高级功能 (开发中)
- [ ] 多Agent协作
- [ ] 后台任务处理
- [ ] Web用户界面
- [ ] CLI工具链
- [ ] 数据库集成
- [ ] 批量处理

## 反馈

遇到问题或有建议？

- 📧 Email: support@thesismind.com
- 🐛 Bug报告: GitHub Issues
- 💬 讨论: GitHub Discussions
- ⭐ 如果有帮助，请给个Star!

---

**祝你的论文写作顺利!** 🎓📝
