# Agent 实现模块

本目录包含各种专用Agent的实现，对应 learn-claude-code 的分阶段学习。

## Agent类型

### s01 - 基础 Agent循环
- `thesis_agent.py` - 论文主Agent
- 实现基础的消息循环和工具调度

### s02 - 多工具支持
- 增强Agent支持更多论文相关工具

### s03 - 任务规划
- TodoManager集成，支持多步骤任务规划

### s04 - 子Agent支持
- 支持生成子Agent处理特定任务
- 如"框架Agent"、"大纲Agent"等

### s05 - 技能库加载
- 动态加载 PAPER_ANALYSIS.md、FRAMEWORK.md等
- 按需注入学科知识

### s06+ 高级特性
- 上下文压缩
- 后台任务处理
- 多Agent协作
- 工作目录隔离

## 使用方式

```bash
# 运行主Agent
python -m agents.thesis_agent

# 运行具体类型Agent
python -m agents.research_agent
```

## 开发路线

- [ ] 框架生成Agent
- [ ] 大纲生成Agent
- [ ] 文献管理Agent
- [ ] 格式检查Agent
- [ ] AIGC检测Agent
- [ ] 内容扩写Agent
