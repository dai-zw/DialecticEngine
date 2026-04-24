# DialecticEngine - Policy Router

> 系统级Policy Router，为多Skill哲学推理系统提供智能路由决策能力

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                        PolicyRouter                             │
│                     (核心调度中心)                               │
└─────────────────────┬───────────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬─────────────┐
        ▼             ▼             ▼             ▼
┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐
│ Features  │  │ Context   │  │  Scorer   │  │  Fusion   │
│(特征提取) │  │(上下文)   │  │(多维打分) │  │(决策融合) │
└─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘
      │              │              │              │
      └──────────────┴──────────────┴──────────────┘
                          │
                    ┌─────┴─────┐
                    │ Feedback  │
                    │(反馈学习) │
                    └───────────┘
```

## 目录结构

```
policy_router/
├── __init__.py           # 包入口，导出核心接口
├── types.py              # 数据结构定义（dataclass）
├── features.py            # 特征提取模块
├── context.py             # 上下文状态管理
├── registry_adapter.py    # Skill注册适配器
├── scorer.py              # 多维度打分
├── fusion.py              # 多Skill决策融合
├── feedback.py            # 反馈学习机制
├── router.py              # 核心Router主入口
└── README.md             # 本文档
```

## 快速开始

### 基础使用

```python
from policy_router import PolicyRouter, RouterConfig

# 方式1: 使用默认配置
router = PolicyRouter()

# 方式2: 自定义配置
config = RouterConfig(
    skills_base_path="skills",       # skills目录路径
    top_k=3,                         # 返回top-k个skill
    multi_skill_threshold=0.15,       # 进入multi-skill的分数差阈值
    enable_trace=True,               # 启用trace
)
router = PolicyRouter(config=config)

# 方式3: 快捷创建
from policy_router import create_router
router = create_router(skills_path="skills", top_k=3)
```

### 路由决策

```python
# 路由query
decision = router.route(
    query="我和老板意见不合，但他对我有恩，我该直言吗？",
    user_id="user_123",
    session_id="session_abc",
)

# 查看结果
print(decision.selected_skills)   # ['rujia-perspective']
print(decision.execution_mode)    # ExecutionMode.SINGLE
print(decision.confidence)        # 0.82
print(decision.explanation)       # 自然语言解释

# 查看详细分数
for skill_id, score in decision.skill_scores.items():
    print(f"{skill_id}: {score.total_score:.4f}")
    print(f"  semantic: {score.semantic_score:.3f}")
    print(f"  rule_bias: {score.rule_bias_score:.3f}")
    print(f"  context: {score.context_score:.3f}")
    print(f"  feedback: {score.feedback_score:.3f}")
```

### 提交反馈

```python
# 显式反馈（用户评分）
router.submit_explicit_feedback(
    rating=4.5,                    # [1.0, 5.0]
    decision_id=decision.decision_id,
    user_id="user_123",
    session_id="session_abc",
    skill_ids=decision.selected_skills,
    comment="分析很有帮助！",
)

# 隐式反馈（系统推断）
router.submit_implicit_feedback(
    decision_id=decision.decision_id,
    user_id="user_123",
    session_id="session_abc",
    skill_ids=decision.selected_skills,
    user_response="好的，我明白了",  # 用户回复
    response_time=5.0,              # 用户思考时间
)

# 用户纠正（选错了skill）
router.submit_correction(
    decision_id=decision.decision_id,
    user_id="user_123",
    session_id="session_abc",
    correct_skill_ids=["fajia-perspective"],  # 用户认为应该选的skill
)
```

## 核心模块

### 1. Feature Extraction (`features.py`)

从用户query中提取结构化特征：

| 特征 | 描述 | 范围 |
|------|------|------|
| `intent` | 意图分类 | 12种意图类型 |
| `domains` | 领域标签 | 18个领域标签 |
| `complexity` | 复杂度等级 | 1-4级 |
| `emotion` | 情感类型 | 8种情感 |
| `urgency` | 紧迫度 | [0.0, 1.0] |
| `ambiguity` | 歧义度 | [0.0, 1.0] |

**关键词识别示例：**

```python
# 儒家关键词
["仁", "义", "礼", "智", "信", "忠", "恕", "孝", "悌",
 "修身", "五伦", "君子", "中庸", "名实", "经权"]

# 法家关键词
["法", "术", "势", "赏罚", "刑德", "制度", "规则",
 "激励", "监督", "权责", "执行", "法治"]

# 道家关键词
["道", "无为", "自然", "柔弱", "虚静", "逍遥",
 "齐物", "反者道之动", "知足", "不争"]
```

### 2. Multi-Dimension Scorer (`scorer.py`)

对所有skill进行四维度打分：

| 维度 | 权重 | 描述 |
|------|------|------|
| `semantic` | 0.35 | 语义相似度（embedding匹配） |
| `rule_bias` | 0.20 | 规则标签匹配 |
| `context` | 0.25 | 上下文匹配（用户历史） |
| `feedback` | 0.20 | 历史表现反馈 |

**分数计算公式：**

```
total_score = semantic * 0.35 + rule_bias * 0.20 + context * 0.25 + feedback * 0.20
```

### 3. Decision Fusion (`fusion.py`)

三种执行模式：

#### SINGLE模式
- top-1分数显著高于top-2
- 单一视角足够清晰

#### MULTI模式
- top-2分数接近top-1
- 问题复杂度高或歧义度高

#### DEBATE模式
- 两个视角存在对立关系
- 如：儒家 vs 法家、道家 vs 法家

**对立关系对：**

```python
opposing_pairs = [
    ("rujia-perspective", "fajia-perspective"),  # 儒家 vs 法家
    ("daojia-perspective", "fajia-perspective"),  # 道家 vs 法家
    ("rujia-perspective", "daojia-perspective"),  # 儒家 vs 道家
]
```

### 4. Feedback Learning (`feedback.py`)

学习机制：

| 反馈类型 | 来源 | 影响 |
|----------|------|------|
| `EXPLICIT` | 用户评分 | 直接更新权重 |
| `IMPLICIT` | 行为推断 | 需要足够样本 |
| `CORRECTION` | 用户纠正 | 大幅降低错误skill权重 |

**权重更新公式：**

```python
weight_new = weight_old + learning_rate * (feedback - baseline)
weight_new = decay_factor * weight_new + (1 - decay_factor) * 0.5
```

### 5. Context Management (`context.py`)

用户画像：

```python
@dataclass
class UserProfile:
    user_id: str
    preferred_skills: list[str]     # 优先skill
    avoided_skills: list[str]       # 回避skill
    skill_weights: dict[str, float]  # 动态权重
    skill_success_counts: dict[str, int]
    skill_total_counts: dict[str, int]
    total_queries: int
    total_sessions: int
```

会话状态：

```python
@dataclass
class SessionState:
    session_id: str
    user_id: str
    query_history: list[str]
    skill_history: list[str]
    feature_history: list[FeatureVector]
    turn_count: int
```

## 配置选项

```python
@dataclass
class RouterConfig:
    # 打分权重
    scoring_weights: dict[str, float] = {
        "semantic": 0.35,
        "rule_bias": 0.20,
        "context": 0.25,
        "feedback": 0.20,
    }

    # 决策参数
    top_k: int = 3                          # 返回top-k
    multi_skill_threshold: float = 0.15      # 多skill阈值
    debate_threshold: float = 0.05          # 辩论模式阈值
    min_score_threshold: float = 0.2         # 最小入选分数

    # 学习参数
    learning_rate: float = 0.1              # 学习率
    decay_factor: float = 0.95              # 衰减因子
    min_feedback_count: int = 3             # 最小反馈数

    # 路径配置
    skills_base_path: str = "skills"
    knowledge_base_path: str = "knowledge"

    # 调试
    enable_trace: bool = True
    enable_heatmap: bool = False
```

## 可视化调试

### 获取所有分数

```python
scores = router.get_all_scores(query="你的问题")
rankings = router.get_skill_rankings(query="你的问题")

# 排名结果
for skill_id, score in rankings:
    print(f"{skill_id}: {score:.4f}")
```

### 获取决策解释

```python
explanation = router.explain_decision(decision)
print(json.dumps(explanation, indent=2, ensure_ascii=False))
```

### Trace日志

```python
traces = router.get_trace_log()
for trace in traces[-5:]:
    print(f"{trace['timestamp']} - {trace['selected_skills']}")
```

### 热力图数据

```python
heatmap = router.get_heatmap()
if heatmap:
    print("Skill重要性分布:")
    for domain, score in heatmap['domain_distribution'].items():
        print(f"  {domain}: {score:.2f}")
```

## 调试输出示例

```
Query: 我的领导对我有恩，但他的决策明显错误，我该直言吗？
──────────────────────────────────────────────────────────────────
执行模式: SINGLE
选择Skills: rujia-perspective
置信度: 82.00%
决策理由: 「儒家」综合得分最高(0.823)，主要优势：query与「儒家」的核心概念高度相关；意图与领域匹配度高。

Top-3 Scores:
  rujia-perspective: 0.8234
    - semantic: 0.680
    - rule_bias: 0.750
    - context: 0.650
    - feedback: 0.700
  fajia-perspective: 0.4521
    - semantic: 0.320
    - rule_bias: 0.450
    - context: 0.550
    - feedback: 0.600
  daojia-perspective: 0.3892
    - semantic: 0.210
    - rule_bias: 0.350
    - context: 0.500
    - feedback: 0.550
```

## RAG增强（规划中）

后续可与 `knowledge/` 目录集成：

```python
# 规划中的RAG接口
knowledge = router.get_knowledge_for_skills(
    skill_ids=["rujia-perspective"],
    query=query,
    top_k=5,
)
# 返回相关的经典语录、案例
```

## 扩展指南

### 添加新的打分维度

1. 在 `types.py` 的 `SkillScore` 中添加新字段
2. 在 `scorer.py` 中创建新的Scorer类
3. 在 `MultiDimensionScorer.score_all_skills()` 中调用

### 添加新的执行模式

1. 在 `types.py` 的 `ExecutionMode` 中添加新模式
2. 在 `fusion.py` 的 `ModeDecider` 中添加判断逻辑
3. 在 `ExecutionPlanGenerator.generate()` 中添加处理

### 集成真实Embedding模型

修改 `features.py` 中的 `_extract_embedding()` 方法：

```python
def _extract_embedding(self, query: str) -> QueryEmbedding:
    # 替换为真实的embedding调用
    response = openai.Embedding.create(
        model="text-embedding-3-small",
        input=query,
    )
    vector = response['data'][0]['embedding']
    return QueryEmbedding(values=tuple(vector))
```

## 性能考虑

- **Skill扫描**：60秒缓存，避免频繁文件IO
- **打分**：所有skill批量打分，一次遍历
- **反馈处理**：异步处理，可配置队列
- **Trace记录**：可选，默认开启，建议生产环境关闭

## License

MIT License
