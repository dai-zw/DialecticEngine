# DialecticEngine Test Suite

## 概述

本测试套件覆盖 DialecticEngine 的所有核心功能，包括：

- **21 个 Skill 的路由匹配测试** (`tests/skills/`)
- **PolicyRouter 管道测试** (`tests/router/`)
- **上下文管理测试** (`tests/context/`)
- **边界情况和异常处理测试** (`tests/router/`)

## 测试文件结构

```
tests/
├── __init__.py
├── conftest.py              # pytest fixtures 和配置
├── pytest.ini                # pytest 配置文件
│
├── skills/                  # Skill 路由测试
│   ├── __init__.py
│   └── test_skill_routing.py  # 21 个 Skill 的路由测试
│
├── router/                  # 路由管道测试
│   ├── __init__.py
│   ├── test_router_pipeline.py  # 完整路由管道测试
│   └── test_edge_cases.py      # 边界情况和异常处理
│
├── context/                 # 上下文和反馈测试
│   ├── __init__.py
│   ├── test_context_management.py  # 上下文管理测试
│   └── test_feedback_learning.py   # 反馈学习测试
│
└── fixtures/               # 测试数据
    ├── __init__.py
    └── test_data.py         # 静态测试数据
```

## 测试覆盖

### Skill 路由测试 (test_skill_routing.py)

覆盖所有 21 个 Skill：

| Skill | 测试关键词 |
|-------|----------|
| 儒家 (rujia-perspective) | 仁义礼智信、忠孝、修身 |
| 法家 (fajia-perspective) | 法术势、赏罚、制度 |
| 道家 (daojia-perspective) | 无为、自然、逍遥 |
| 兵家 (bingjia-perspective) | 兵战谋、奇正、虚实 |
| 墨家 (mojia-perspective) | 兼爱、非攻、尚贤 |
| 名家 (mingjia-perspective) | 名实、白马、离坚白 |
| 纵横家 (zonghengjia-perspective) | 合纵连横、外交 |
| 阴阳家 (yinyangjia-perspective) | 阴阳、五行、平衡 |
| 史家 (shijia-perspective) | 历史、借鉴 |
| 医家 (yijia-perspective) | 养生、调和 |
| 佛家 (fojia-perspective) | 缘起、空、放下 |
| 理学 (lixue-perspective) | 格物致知、天理 |
| 心学 (xinxue-perspective) | 良知、知行合一 |
| 经学 (jingxue-perspective) | 经典、注疏 |
| 黄老 (huanglao-perspective) | 无为而治、刑德 |
| 农家 (nongjia-perspective) | 农耕、食本 |
| 小说家 (xiaoshuojia-perspective) | 故事、叙事 |
| 术数家 (shushujia-perspective) | 占卜、易经 |
| 杂家 (zajia-perspective) | 综合、博采 |
| 玄学 (xuanxue-perspective) | 有无、本末 |
| 新儒 (newrujia-perspective) | 现代化、道统 |

### 路由管道测试 (test_router_pipeline.py)

- 特征提取测试
- 执行模式选择测试 (SINGLE/MULTI/DEBATE)
- 决策融合测试
- 完整管道集成测试
- 多 Skill 协作测试
- 辩论模式测试

### 上下文管理测试 (test_context_management.py)

- 用户画像管理
- 会话状态管理
- 上下文信号聚合
- 持久化支持
- 技能共现分析

### 反馈学习测试 (test_feedback_learning.py)

- 显式反馈处理
- 隐式反馈处理
- 权重更新逻辑
- 纠错机制
- 反馈统计和分析

### 边界情况测试 (test_edge_cases.py)

- 输入验证
- 配置边界
- 并发处理
- 错误恢复
- 资源限制
- 内存管理
- 性能基线

## 运行测试

### 运行所有测试

```bash
cd D:\DialecticEngine
pytest tests/
```

### 运行特定测试模块

```bash
# Skill 路由测试
pytest tests/skills/test_skill_routing.py

# 路由管道测试
pytest tests/router/test_router_pipeline.py

# 上下文管理测试
pytest tests/context/test_context_management.py

# 反馈学习测试
pytest tests/context/test_feedback_learning.py
```

### 使用标记运行测试

```bash
# 只运行 Skill 测试
pytest -m skill

# 只运行单元测试
pytest -m unit

# 跳过慢速测试
pytest -m "not slow"
```

### 运行特定 Skill 的测试

```bash
# 测试儒家路由
pytest tests/skills/test_skill_routing.py::TestRujiaPerspective

# 测试法家路由
pytest tests/skills/test_skill_routing.py::TestFajiaPerspective
```

### 生成覆盖率报告

```bash
pytest tests/ --cov=policy_router --cov-report=html --cov-report=term
```

## 测试数据

测试使用的主要数据来源：

- `conftest.py`: pytest fixtures
- `fixtures/test_data.py`: 静态测试数据
- 各测试文件中的内联测试数据

### 核心测试查询

每个 Skill 都有对应的典型测试查询，例如：

```python
"rujia-perspective": [
    "我和领导意见不合，但他对我有恩，我该直言吗？",
    "朋友找我帮忙但我不想帮，该如何拒绝而不伤感情？",
    "孩子不听话，不尊重长辈，我该怎么办？",
]
```

### 复杂场景测试

测试套件包含触发多 Skill 或辩论模式的复杂场景：

```python
{
    "query": "国家治理应该以德治国还是依法治国？",
    "expected_debate": True,
    "potential_skills": ["rujia-perspective", "fajia-perspective"],
}
```

## 注意事项

1. 测试不执行实际的网络请求或数据库操作
2. 所有测试使用内存中的模拟数据
3. 部分测试需要较长时间运行（标记为 `slow`）
4. 测试套件设计为可以独立运行，不依赖外部服务
