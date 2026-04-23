对用户指定的需求文档，使用 test-agent MCP 工具按顺序完成完整的测试文档生成，并自动沉淀到知识库。

## 执行步骤

**第一步：需求评审**
调用 review_requirement，传入用户指定的文档路径。
记录返回的 score、risk_flags、testable_features。

**第二步：生成测试点**
调用 generate_testpoints，传入同一文档路径，设置 use_knowledge_base 为 true。
记录返回的 output_file 路径（后续步骤需要用到）。

**第三步：生成测试用例**
用第二步返回结果中的 output_file 路径，调用 generate_testcases。
记录返回的 json_file 和 excel_file 路径。

**第四步：知识库沉淀**
调用 save_to_knowledge_base，传入：
- requirement_path：需求文档路径（同第一步）
- testpoints_file：第二步返回的 output_file 路径
自动完成需求文档归档、风险经验提取、记忆更新。

## 完成后汇总输出

所有步骤完成后，用以下格式告诉我结果：

---
**需求评审**
- 质量分：{score}/100
- 主要风险：{risk_flags 列表，每条一行}

**测试点**
- 总数：{total} 条
- 来源分布：REQ={REQ数} / KB={KB数} / RISK={RISK数}
- 文件：{output_file}
- XMind：{xmind_file}

**测试用例**
- 总数：{total} 条
- Excel：{excel_file}
- JSON：{json_file}

**知识库沉淀**
- {actions 列表，每条一行}
---

## 文档路径

$ARGUMENTS
