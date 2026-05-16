"""端到端对话测试 — 模拟真实用户交互"""
import sys, os, json, time

from src.agent_loop import ThesisAgent


def run_test(name: str, user_message: str, skills=None):
    print(f"\n{'='*60}")
    print(f"  测试: {name}")
    print(f"{'='*60}")
    agent = ThesisAgent(skip_license_check=True, skills=skills)
    try:
        result = agent.run(user_message)
        print(f"\n📋 返回: {result[:300]}...")
        return agent, result
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return agent, None


print("=" * 60)
print("  ThesisMind 端到端对话测试")
print("=" * 60)

# 1. 框架生成 — 需要工具调用
print("\n\n### 场景1: 生成研究框架 ###")
agent1, r1 = run_test(
    "生成新能源车载系统质量管理研究框架",
    "请帮我生成一个关于新能源车载系统研发质量管理的研究框架，学科背景是计算机科学",
)

# 2. 大纲生成 — 依赖框架结果
if r1:
    print("\n\n### 场景2: 基于框架生成大纲 ###")
    r2 = agent1.run("请基于上面生成的研究框架，生成一份深度3的论文大纲")
    print(f"\n📋 返回: {r2[:300] if r2 else 'None'}...")

# 3. 文献引用
print("\n\n### 场景3: 文献引用管理 ###")
agent3, r3 = run_test(
    "搜索并格式化引用",
    "请帮我搜索关于质量管理和CMMI的引用文献，然后用APA和GB/T 7714两种格式分别格式化 Smith 2020 年的一篇关于软件质量的论文",
)

# 4. 压缩上下文测试 — 多轮对话触发压缩
print("\n\n### 场景4: 多轮对话 + 上下文压缩 ###")
agent4 = ThesisAgent(skip_license_check=True, skills=[])
print(f"初始 system 长度: {len(agent4.system)}")
for i in range(5):
    msg = f"这是第{i+1}轮对话。请简单回复确认你收到了消息{i+1}，用一句话。"
    try:
        r = agent4.run(msg)
        print(f"  第{i+1}轮: system长度={len(agent4.system)}, messages数={len(agent4.messages)}")
    except Exception as e:
        print(f"  第{i+1}轮错误: {e}")
        break

# 5. clear_history 后 system 是否重置
print("\n\n### 场景5: clear_history 后 system 重置 ###")
sys_before = agent4.system
msg_count_before = len(agent4.messages)
agent4.clear_history()
assert agent4.system == agent4._base_system, f"system not reset! {len(agent4.system)} vs {len(agent4._base_system)}"
assert len(agent4.messages) == 0, f"messages not cleared!"
print(f"✅ system 已重置 ({len(agent4.system)} chars), messages 已清空")

print("\n\n" + "=" * 60)
print("  全部端到端测试完成")
print("=" * 60)
