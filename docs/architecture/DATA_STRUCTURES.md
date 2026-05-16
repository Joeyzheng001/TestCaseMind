# 📊 项目核心数据结构

## 1. 论文项目结构

用户创建的每个论文项目包含以下信息:

```json
{
  "project": {
    "id": "thesis_2024_001",
    "name": "深度学习在医学影像中的应用",
    "author": "张三",
    "discipline": "medical",
    "degree": "master",
    "status": "in_progress",
    "created_at": "2024-05-08T10:00:00Z",
    "updated_at": "2024-05-08T15:30:00Z",
    "timeline": {
      "start": "2024-05-08",
      "deadline": "2024-12-31"
    },
    "metadata": {
      "total_words": 0,
      "chapters": 5,
      "citations": 0
    }
  },
  "framework": {
    "topic": "深度学习在医学影像中的应用",
    "phases": [
      "文献回顾",
      "方法设计",
      "实验实施",
      "结果分析",
      "结论讨论"
    ],
    "mermaid_graph": "graph TD ...",
    "visualization": {
      "type": "flowchart",
      "url": "output/frameworks/thesis_2024_001.svg"
    }
  },
  "outline": {
    "chapters": [
      {
        "number": 1,
        "title": "绪论",
        "sections": [
          "1.1 研究背景",
          "1.2 研究意义",
          "1.3 主要内容",
          "1.4 创新点"
        ],
        "word_count": 0,
        "status": "pending"
      }
    ],
    "exports": {
      "docx": "output/outlines/thesis_2024_001.docx",
      "xmind": "output/outlines/thesis_2024_001.xmind",
      "markdown": "output/outlines/thesis_2024_001.md"
    }
  },
  "citations": {
    "total": 0,
    "format": "gb7714",
    "sources": [
      {
        "id": "cite_001",
        "type": "journal",
        "authors": ["Smith, J.", "Johnson, K."],
        "year": 2020,
        "title": "Deep Learning in Medical Imaging",
        "journal": "IEEE TMI",
        "volume": 39,
        "issue": 10,
        "pages": "1234-1245",
        "doi": "10.1109/TMI.2020.2987654",
        "formatted": {
          "apa": "Smith, J., & Johnson, K. (2020). Deep learning in medical imaging. IEEE Transactions on Medical Imaging, 39(10), 1234-1245.",
          "gb7714": "[1] Smith J, Johnson K. Deep learning in medical imaging[J]. IEEE Transactions on Medical Imaging, 2020, 39(10): 1234-1245."
        }
      }
    ]
  },
  "content": {
    "chapters": [
      {
        "id": "ch001",
        "number": 1,
        "title": "绪论",
        "content": "...",
        "versions": [
          {
            "version": 1,
            "timestamp": "2024-05-08T10:00:00Z",
            "content": "...",
            "changes": "初稿"
          }
        ]
      }
    ]
  },
  "format_config": {
    "font": {
      "name": "宋体",
      "size": 12,
      "line_height": 1.5
    },
    "margins": {
      "top": 2.5,
      "bottom": 2.5,
      "left": 2.5,
      "right": 2.5
    },
    "page": {
      "size": "A4",
      "orientation": "portrait"
    }
  },
  "quality": {
    "format_score": 0,
    "originality_score": 0,
    "aigc_detection": {
      "overall_percentage": 0,
      "chapters": {},
      "high_risk_sections": []
    },
    "issues": {
      "format": [],
      "academic": [],
      "citations": []
    }
  }
}
```

## 2. 研究框架数据结构

```json
{
  "framework": {
    "id": "framework_2024_001",
    "topic": "深度学习在医学影像中的应用",
    "discipline": "medical",
    "created_at": "2024-05-08T10:00:00Z",
    "description": "研究框架的总体描述",
    
    "research_phases": [
      {
        "phase_number": 1,
        "name": "文献回顾",
        "duration_weeks": 2,
        "objectives": ["目标1", "目标2"],
        "key_activities": ["活动1", "活动2"],
        "deliverables": ["交付物1", "交付物2"],
        "dependencies": []
      }
    ],
    
    "visualization": {
      "mermaid": "graph TD ...",
      "plantuml": "@startmindmap ...",
      "svg_url": "output/frameworks/...",
      "png_url": "output/frameworks/..."
    },
    
    "related_literature": ["ref_001", "ref_002"],
    "methodology": "quantitative|qualitative|mixed",
    "expected_timeline": "12 months"
  }
}
```

## 3. 论文大纲数据结构

```json
{
  "outline": {
    "id": "outline_2024_001",
    "title": "论文: 深度学习在医学影像中的应用",
    "depth": 3,
    
    "chapters": [
      {
        "level": 1,
        "number": 1,
        "title": "绪论",
        "sections": [
          {
            "level": 2,
            "number": "1.1",
            "title": "研究背景",
            "subsections": [
              {
                "level": 3,
                "number": "1.1.1",
                "title": "医学影像的重要性"
              }
            ]
          }
        ]
      }
    ],
    
    "metadata": {
      "total_chapters": 5,
      "total_sections": 20,
      "estimated_words": 50000,
      "created_at": "2024-05-08"
    }
  }
}
```

## 4. 引用文献数据结构

```json
{
  "citation": {
    "id": "cite_001",
    "source": "arXiv|journal|conference|book|website",
    
    "metadata": {
      "authors": ["Author 1", "Author 2"],
      "year": 2020,
      "title": "Paper Title",
      "journal_or_venue": "Journal Name",
      "volume": 39,
      "issue": 10,
      "pages": "1234-1245",
      "doi": "10.1109/...",
      "url": "https://...",
      "keywords": ["keyword1", "keyword2"]
    },
    
    "relevance": {
      "score": 0.85,
      "category": "foundational|methodology|comparison|application",
      "notes": "Brief relevance description"
    },
    
    "formatted_versions": {
      "apa": "...",
      "chicago": "...",
      "harvard": "...",
      "gb7714": "..."
    }
  }
}
```

## 5. 格式检查结果数据结构

```json
{
  "format_check": {
    "file": "thesis.docx",
    "checked_at": "2024-05-08T15:30:00Z",
    "overall_passed": false,
    "score": 78,
    
    "issues": {
      "font": [
        {
          "severity": "warning",
          "location": "Page 5",
          "problem": "Font mismatch",
          "details": "Found Arial instead of Song Ti",
          "suggestion": "Replace Arial with Song Ti (12pt)"
        }
      ],
      "spacing": [
        {
          "severity": "error",
          "location": "Page 12-15",
          "problem": "Line height incorrect",
          "details": "1.0 倍 instead of 1.5倍",
          "suggestion": "Set line height to 1.5x"
        }
      ],
      "margins": [
        {
          "severity": "warning",
          "location": "All pages",
          "problem": "Right margin incorrect",
          "details": "2.0cm instead of 2.5cm",
          "suggestion": "Set right margin to 2.5cm"
        }
      ]
    },
    
    "recommendations": [
      "统一字体为宋体12pt",
      "调整行距为1.5倍",
      "修正页边距为2.5cm",
      "检查页码格式"
    ]
  }
}
```

## 6. AIGC检测结果数据结构

```json
{
  "aigc_detection": {
    "file": "thesis.docx",
    "analyzed_at": "2024-05-08T15:45:00Z",
    
    "overall": {
      "total_words": 50000,
      "aigc_words": 1600,
      "aigc_percentage": 3.2,
      "confidence": 0.92,
      "originality_score": 96.8
    },
    
    "by_chapter": [
      {
        "chapter": 1,
        "title": "绪论",
        "aigc_percentage": 1.5,
        "confidence": 0.88
      }
    ],
    
    "high_risk_sections": [
      {
        "chapter": 3,
        "section": "3.2",
        "location": "Line 45-67",
        "word_count": 850,
        "aigc_probability": 0.965,
        "confidence": 0.95,
        "suggestions": ["改写该段落", "添加更多个人分析"]
      }
    ],
    
    "analysis": {
      "writing_style_consistency": 0.92,
      "vocabulary_diversity": 0.88,
      "sentence_complexity": 0.85,
      "logical_coherence": 0.91
    }
  }
}
```

## 7. Agent任务数据结构

```json
{
  "task": {
    "id": "task_001",
    "title": "生成论文框架",
    "description": "基于用户需求生成研究框架",
    "status": "in_progress",
    "priority": "high",
    
    "created_by": "user_001",
    "assigned_to": "research_agent",
    "created_at": "2024-05-08T10:00:00Z",
    "deadline": "2024-05-08T12:00:00Z",
    
    "input": {
      "topic": "深度学习在医学影像中的应用",
      "discipline": "medical",
      "requirements": ["requirements_list"]
    },
    
    "dependencies": [],
    "subtasks": [],
    
    "output": {
      "framework_id": "framework_2024_001",
      "artifacts": [
        {
          "type": "mermaid_graph",
          "path": "output/frameworks/..."
        }
      ]
    },
    
    "progress": {
      "percentage": 50,
      "current_step": "Generating framework visualization",
      "estimated_completion": "2024-05-08T11:30:00Z"
    }
  }
}
```

## 8. 技能库条目数据结构

```yaml
---
# YAML Frontmatter
topics: ["论文分析", "学术写作", "研究方法"]
tags: ["writing", "research", "thesis"]
priority: high
version: "1.0"
language: "zh_CN"
---

# 技能标题

## 核心知识

### 小节1

内容...

## 实际应用

示例代码或具体使用方式

---
```

---

**这些数据结构支持以下功能:**

1. ✅ 完整的项目生命周期管理
2. ✅ 多版本和多格式支持
3. ✅ 完整的审计和跟踪
4. ✅ Agent间的数据交换
5. ✅ 持久化和恢复
6. ✅ 版本控制集成
