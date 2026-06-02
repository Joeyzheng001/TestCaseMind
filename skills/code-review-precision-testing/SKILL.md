---
name: code-review-precision-testing
description: 对 Java Spring Boot B/S 后端执行需求驱动的测试视角 Code Review、接口变更分析、Karate 接口用例骨架生成和 JaCoCo 新增代码覆盖率分析。用户提到代码评审、接口自动化、增量覆盖率、精准测试或回归范围分析时使用。
---

# Java 精准测试

## 目标

围绕需求文档和 Java 代码变更输出可追溯的测试建议：

```text
需求 -> Git Diff -> 受影响 API -> 测试风险 -> Karate 用例 -> JaCoCo 新增代码覆盖率
```

覆盖率表示执行触达，不等同于测试有效性。报告中应明确区分两者。

## 执行步骤

### 1. 准备输入

最少需要：

- Java Git 仓库路径。
- 基线引用，如 `origin/main` 或 `HEAD~1`。
- 需求文档。

优先补充：

- 当前和基线 OpenAPI JSON/YAML；Spring Boot 可从 `/v3/api-docs` 获取。
- 接口用例执行后的 JaCoCo XML。
- 测试环境 URL 和认证配置。

### 2. 生成确定性分析产物

分析已提交代码：

```bash
python scripts/precision_testing.py \
  --repo /path/to/java-service \
  --base-ref origin/main \
  --target-ref HEAD \
  --output output/<需求名>/<时间戳>/precision-testing \
  --openapi-base artifacts/openapi-main.json \
  --openapi-current artifacts/openapi-current.json \
  --jacoco-xml target/site/jacoco/jacoco.xml
```

分析未提交代码时使用：

```bash
python scripts/precision_testing.py \
  --repo /path/to/java-service \
  --base-ref HEAD \
  --target-ref WORKTREE \
  --output output/<需求名>/<时间戳>/precision-testing
```

OpenAPI 和 JaCoCo 参数可省略。缺失时应在报告中说明能力降级。

### 3. 执行测试视角 Review

读取：

- 需求文档。
- `review-context.json`。
- 相关 Java 变更文件。
- `openapi-diff.json`。

输出 `review-report.md` 和 `risk-items.json`。每个风险项必须包含：

```json
{
  "severity": "high|medium|low",
  "requirement_basis": "需求依据",
  "code_location": "文件与代码位置",
  "impacted_api": "METHOD /path",
  "risk": "风险说明",
  "verification": "验证方式",
  "suggested_cases": ["建议用例"]
}
```

重点检查：

- 需求遗漏、实现偏差和超范围实现。
- 参数校验、边界值、非法枚举和组合条件。
- 权限、越权、敏感信息和日志脱敏。
- 状态流转、事务、回滚、并发和幂等。
- 数据库、缓存、消息队列和下游 HTTP 异常。
- OpenAPI 兼容性和响应字段变化。

### 4. 细化接口自动化用例

脚本会生成 `generated-tests/karate/impacted-apis.feature` 骨架。根据需求和风险项补全：

- 请求参数和测试数据。
- 前置数据准备与清理。
- 正向、边界、异常、权限和幂等场景。
- 状态码、响应体和必要的数据落库断言。

不要直接执行带 `@todo` 的骨架作为质量门禁。

### 5. 采集覆盖率并复跑分析

Java 服务通过 JaCoCo Agent 或 Maven/Gradle 插件导出 XML 后，重新执行分析脚本并传入：

```bash
--jacoco-xml target/site/jacoco/jacoco.xml
```

重点查看：

- `coverage/diff-coverage.json`
- `report.md` 中的未覆盖新增代码行
- 风险项是否已有对应接口场景

## 被测服务器接入

- Code Review、OpenAPI Diff 和 Karate 用例生成不需要服务器监听器。
- 采集 Java 覆盖率时，需要在测试环境的 Java 进程启动参数中加载 JaCoCo Agent。
- 默认优先使用 `output=file`，不额外开放监听端口。
- 需要建立“单条用例 -> 代码行”映射时，才使用受控 dump/reset 模式；端口只允许本机或测试网访问。
- 生产环境默认不启用 JaCoCo。
- Keploy 属于二期可选增强，需要额外网络层采集能力，与 JaCoCo 不是同一个组件。

文件导出模式示例：

```bash
java -javaagent:/opt/jacoco/jacocoagent.jar=destfile=/tmp/jacoco.exec,output=file \
  -jar app.jar
```

## 输出产物

```text
precision-testing/
├── review-context.json
├── openapi-diff.json
├── impacted-apis.json
├── report.md
├── risk-items.json                 # Review 后补充
├── review-report.md                # Review 后补充
├── generated-tests/
│   └── karate/
│       └── impacted-apis.feature
└── coverage/
    └── diff-coverage.json
```

## 降级策略

- 没有 OpenAPI：根据 Controller 注解推断 API，并明确提示人工确认 Service 影响范围。
- 没有 JaCoCo XML：先输出 Review 与用例骨架，不给出覆盖率结论。
- 无法识别调用链：加入人工确认项，并采用保守回归范围。
- 需要真实流量录制：将 Keploy 作为可选增强模块，不作为主链路依赖。
