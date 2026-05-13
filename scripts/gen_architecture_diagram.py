#!/usr/bin/env python3
"""生成 TestCaseMind 工程化能力组合图 - 参照云架构风格"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'Arial Unicode MS', 'SimHei']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(1, 1, figsize=(18, 11))
ax.set_xlim(0, 18)
ax.set_ylim(0, 11)
ax.axis('off')

# 背景
fig.patch.set_facecolor('#FFFFFF')

# 颜色定义 - 云架构风格
COLORS = {
    'header': '#1565C0',
    '入口层': '#4A90D9',
    'Skills层': '#7B1FA2',
    '工作流层': '#00897B',
    'Harness层': '#F57C00',
    '知识增强层': '#0D47A1',
    '记忆层': '#C62828',
    '交付层': '#37474F',
    'future': '#78909C',
    'layer_bg': '#F8F9FA',
    'border': '#E0E7EE',
    'separator': '#ECEFF1',
}

def draw_isobox(ax, x, y, width, height, face_color, side_color=None, text='', text_color='white', fontsize=7):
    """绘制3D效果的卡片"""
    if side_color is None:
        side_color = face_color

    # 顶面
    top = FancyBboxPatch(
        (x, y + height * 0.3), width, height * 0.7,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=face_color,
        edgecolor='white',
        linewidth=0.8,
        zorder=3
    )
    ax.add_patch(top)

    # 侧面
    side = FancyBboxPatch(
        (x, y), width, height * 0.35,
        boxstyle="round,pad=0.02,rounding_size=0.05",
        facecolor=side_color,
        edgecolor='white',
        linewidth=0.5,
        zorder=2
    )
    ax.add_patch(side)

    # 文字
    if text:
        ax.text(x + width/2, y + height * 0.65, text,
                ha='center', va='center', fontsize=fontsize,
                fontweight='bold', color=text_color, zorder=4)

def draw_layer_row(ax, y_bottom, y_top, title, items, color, start_x=0.5, row_width=17):
    """绘制一层架构 - 横排风格"""
    height = y_top - y_bottom

    # 背景条
    bg = FancyBboxPatch(
        (start_x, y_bottom), row_width, height,
        boxstyle="round,pad=0.03,rounding_size=0.1",
        facecolor=COLORS['layer_bg'],
        edgecolor=color,
        linewidth=2,
        zorder=1
    )
    ax.add_patch(bg)

    # 标题栏
    title_height = 0.45
    title_rect = FancyBboxPatch(
        (start_x, y_top - title_height), row_width, title_height,
        boxstyle="round,pad=0.02,rounding_size=0.06",
        facecolor=color,
        edgecolor='none',
        zorder=2
    )
    ax.add_patch(title_rect)

    ax.text(start_x + 0.3, y_top - title_height/2, title,
            ha='left', va='center', fontsize=9, fontweight='bold',
            color='white', zorder=3)

    # 子项 - 横排卡片布局
    item_width = (row_width - 0.8) / min(len(items), 4) - 0.15
    item_height = height - title_height - 0.25
    card_height = 0.7

    for i, item in enumerate(items):
        card_x = start_x + 0.3 + i * (item_width + 0.15)
        card_y = y_top - title_height - item_height + (item_height - card_height) / 2

        # 计算卡片颜色 - 渐变效果
        alpha = 0.9 - i * 0.1
        card_color = color

        # 绘制卡片
        card = FancyBboxPatch(
            (card_x, card_y), item_width, card_height,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=card_color,
            edgecolor='white',
            linewidth=0.5,
            alpha=alpha,
            zorder=3
        )
        ax.add_patch(card)

        # 文字
        ax.text(card_x + item_width/2, card_y + card_height/2, item,
                ha='center', va='center', fontsize=6.5,
                color='white', zorder=4, wrap=True)

def draw_separator(ax, y, width=17):
    """绘制分隔线"""
    ax.plot([0.5, 17.5], [y, y], color='#CFD8DC', linewidth=1, linestyle='--', zorder=1)

# ========== 顶部标题区 ==========
title_bg = FancyBboxPatch((0.5, 10.2), 17, 0.7,
                          boxstyle="round,pad=0.02,rounding_size=0.1",
                          facecolor=COLORS['header'],
                          edgecolor='none',
                          zorder=2)
ax.add_patch(title_bg)

ax.text(9, 10.55, 'TestCaseMind 工程化能力组合图',
        ha='center', va='center', fontsize=18, fontweight='bold',
        color='white', zorder=3)

# 副标题
ax.text(9, 10.25, 'AI Native 测试用例智能生成平台 · 七层架构',
        ha='center', va='center', fontsize=10, color='#90CAF9', zorder=3)

# ========== 第一层：入口层 ==========
draw_layer_row(ax, 8.8, 10.0, "1. 入口层", [
    "Claude Code\n自然语言交互",
    "MCP Server\n脚本服务",
    "命令行工具\nagent.py"
], COLORS['入口层'])

# ========== 第二层：Skills层 ==========
draw_layer_row(ax, 7.2, 8.8, "2. Skills 技能层（Agent + RAG）", [
    "requirement-review\n需求评审",
    "testpoint-gen\n测试点生成",
    "testcase-gen\n用例展开",
    "testcase-review\n测试反馈"
], COLORS['Skills层'])

# 添加规划中的skill标注
ax.text(15.5, 8.3, "(规划中)", fontsize=7, color='#B0BEC5', style='italic')
ax.text(15.5, 8.1, "code-review · auto-gen", fontsize=6, color='#B0BEC5', style='italic')

# ========== 分隔 ==========
draw_separator(ax, 7.0)

# ========== 第三层：工作流层 ==========
draw_layer_row(ax, 5.6, 7.0, "3. 工作流编排层", [
    "stage1_review\n需求评审",
    "stage2_testpoints\n测试点生成",
    "stage3_testcases\n用例生成",
    "本地导出\nMD/Excel/XMind"
], COLORS['工作流层'])

# ========== 第四层：Agent Harness ==========
draw_layer_row(ax, 4.0, 5.6, "4. Agent Harness 层（Claude SDK）", [
    "s03 计划展示",
    "s04 子代理",
    "s05 技能加载",
    "s06 上下文压缩",
    "s07 任务持久化",
    "s09 MemoryRAG",
    "s11 容错降级"
], COLORS['Harness层'])

# ========== 分隔 ==========
draw_separator(ax, 3.8)

# ========== 第五层：知识+记忆（双列布局）==========
# 左：知识增强层
kb_bg = FancyBboxPatch((0.5, 2.5), 8, 1.3,
                        boxstyle="round,pad=0.03,rounding_size=0.1",
                        facecolor=COLORS['layer_bg'],
                        edgecolor=COLORS['知识增强层'],
                        linewidth=2,
                        zorder=1)
ax.add_patch(kb_bg)

kb_title = FancyBboxPatch((0.5, 3.55), 8, 0.25,
                           boxstyle="round,pad=0.02,rounding_size=0.05",
                           facecolor=COLORS['知识增强层'],
                           edgecolor='none',
                           zorder=2)
ax.add_patch(kb_title)
ax.text(0.8, 3.67, "5. 知识增强层", ha='left', va='center',
        fontsize=8, fontweight='bold', color='white', zorder=3)

# 知识层卡片
kb_items = ["knowledge_base/\n文档知识库", ".kb_index/\n向量索引", "kb_rag.py\n检索", "kb_distill.py\n提炼"]
for i, item in enumerate(kb_items):
    card = FancyBboxPatch((0.7 + i * 1.95, 2.65), 1.8, 0.75,
                          boxstyle="round,pad=0.02,rounding_size=0.05",
                          facecolor=COLORS['知识增强层'],
                          edgecolor='white', linewidth=0.5,
                          alpha=0.9,
                          zorder=3)
    ax.add_patch(card)
    ax.text(0.7 + i * 1.95 + 0.9, 3.02, item,
            ha='center', va='center', fontsize=6,
            color='white', zorder=4)

# 右：记忆层
mem_bg = FancyBboxPatch((9.0, 2.5), 8, 1.3,
                         boxstyle="round,pad=0.03,rounding_size=0.1",
                         facecolor=COLORS['layer_bg'],
                         edgecolor=COLORS['记忆层'],
                         linewidth=2,
                         zorder=1)
ax.add_patch(mem_bg)

mem_title = FancyBboxPatch((9.0, 3.55), 8, 0.25,
                            boxstyle="round,pad=0.02,rounding_size=0.05",
                            facecolor=COLORS['记忆层'],
                            edgecolor='none',
                            zorder=2)
ax.add_patch(mem_title)
ax.text(9.3, 3.67, "6. 记忆层", ha='left', va='center',
        fontsize=8, fontweight='bold', color='white', zorder=3)

# 记忆层卡片
mem_items = ["memory/\nlong_term.json", "memory/<req>.json\n短期记忆", ".memory_index/\n向量索引"]
for i, item in enumerate(mem_items):
    card = FancyBboxPatch((9.2 + i * 2.6, 2.65), 2.45, 0.75,
                          boxstyle="round,pad=0.02,rounding_size=0.05",
                          facecolor=COLORS['记忆层'],
                          edgecolor='white', linewidth=0.5,
                          alpha=0.9,
                          zorder=3)
    ax.add_patch(card)
    ax.text(9.2 + i * 2.6 + 1.22, 3.02, item,
            ha='center', va='center', fontsize=6,
            color='white', zorder=4)

# ========== 第六层：交付层 ==========
draw_layer_row(ax, 1.1, 2.5, "7. 交付层", [
    "output/<需求>/<时间>/",
    "testpoints.json",
    "testcases.json/xlsx",
    "report.md / manifest"
], COLORS['交付层'])

# ========== 底部：未来扩展 ==========
future_bg = FancyBboxPatch((0.5, 0.2), 17, 0.7,
                           boxstyle="round,pad=0.02,rounding_size=0.08",
                           facecolor='#ECEFF1',
                           edgecolor='#B0BEC5',
                           linewidth=1.5,
                           linestyle='--',
                           zorder=1)
ax.add_patch(future_bg)

ax.text(1.0, 0.55, "未来扩展方向：", ha='left', va='center',
        fontsize=7, fontweight='bold', color='#78909C', zorder=3)

future_items = ["自动化测试执行", "精准测试（代码覆盖率）", "CI/CD 集成", "多模态文档解析", "Code Review"]
for i, item in enumerate(future_items):
    ax.text(3.5 + i * 3.0, 0.55, f"• {item}",
            ha='left', va='center', fontsize=7,
            color='#78909C', zorder=3, style='italic')

# ========== 连接箭头 ==========
# 层间连接
for y in [8.0, 6.5, 5.2, 3.6, 2.3]:
    ax.annotate('', xy=(8.8, y - 0.15), xytext=(8.8, y + 0.15),
               arrowprops=dict(arrowstyle='->', color='#90A4AE', lw=1.2))

plt.tight_layout()
plt.savefig('docs/TestCaseMind工程化能力组合图.png', dpi=180, bbox_inches='tight',
           facecolor='white', edgecolor='none')
plt.savefig('docs/TestCaseMind工程化能力组合图.jpeg', dpi=150, bbox_inches='tight',
           facecolor='white', edgecolor='none')
print("生成成功: docs/TestCaseMind工程化能力组合图.png 和 .jpeg")
