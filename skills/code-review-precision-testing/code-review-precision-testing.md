---
name: code-review-precision-testing
description: 对 Java Spring Boot B/S 后端执行需求驱动的测试视角 Code Review、接口变更分析、Karate 接口用例骨架生成和 JaCoCo 新增代码覆盖率分析
tags: java, spring-boot, code-review, api-testing, jacoco, precision-testing
---

# Java 精准测试技能

本文件用于兼容 TestCaseMind 当前的技能目录约定。完整执行规范见 [SKILL.md](SKILL.md)。

执行确定性分析：

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

读取 `review-context.json` 后，结合需求文档完成测试视角 Review，并细化自动生成的 Karate 接口用例骨架。
