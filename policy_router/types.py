"""
DialecticEngine - Policy Router Type Definitions
================================================
本模块定义了 Policy Router 系统中使用的所有核心数据结构。

Architecture Principles:
- 不可变数据类优先（使用 dataclass/frozen）
- 所有时间戳使用 UTC
- 所有 ID 使用 UUID
- 分数标准化到 [0.0, 1.0]
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Optional


# ============================================================================
# ENUMS
# ============================================================================


class IntentType(Enum):
    """Query intent classification."""

    ETHICAL_DILEMMA = "ethical_dilemma"           # 伦理困境
    DECISION_ANALYSIS = "decision_analysis"       # 决策分析
    RELATIONSHIP = "relationship"                 # 人际关系
    ORGANIZATION = "organization"                # 组织治理
    SELF_CULTIVATION = "self_cultivation"         # 修身自省
    METAPHYSICS = "metaphysics"                  # 形而上学
    STRATEGY = "strategy"                        # 战略策略
    RHETORIC = "rhetoric"                        # 辩论文辞
    NATURE = "nature"                            # 自然哲学
    CONFUCIAN = "confucian"                      # 儒家相关
    LEGALIST = "legalist"                        # 法家相关
    DAOIST = "daoist"                           # 道家相关
    GENERAL = "general"                          # 通用问题


class DomainTag(Enum):
    """Domain tags for skill matching."""

    ETHICS = auto()
    GOVERNANCE = auto()
    RELATIONSHIPS = auto()
    SELF_CULTIVATION = auto()
    STRATEGY = auto()
    DIALECTICS = auto()
    LOGIC = auto()
    NATURE = auto()
    POLITICS = auto()
    ECONOMICS = auto()
    MEDICINE = auto()
    MILITARY = auto()
    RHETORIC = auto()
    LITERATURE = auto()
    METAPHYSICS = auto()
    EPISTEMOLOGY = auto()
    LAW = auto()
    EDUCATION = auto()


class ExecutionMode(Enum):
    """Multi-skill execution mode."""

    SINGLE = "single"        # 只选择一个最优skill
    MULTI = "multi"         # 选择多个skill进行融合
    DEBATE = "debate"       # 多个skill进行辩论/对立分析


class EmotionType(Enum):
    """Emotion classification for query."""

    NEUTRAL = "neutral"
    ANXIOUS = "anxious"          # 焦虑
    ANGRY = "angry"              # 愤怒
    SAD = "sad"                  # 悲伤
    CONFUSED = "confused"        # 困惑
    HOPEFUL = "hopeful"          # 期待
    DESPERATE = "desperate"      # 绝望
    GUILTY = "guilty"            # 内疚


class FeedbackType(Enum):
    """Feedback source type."""

    EXPLICIT = "explicit"          # 显式反馈（用户明确评价）
    IMPLICIT = "implicit"          # 隐式反馈（行为推断）
    CORRECTION = "correction"      # 用户纠正
    ACCEPTANCE = "acceptance"      # 用户接受
    REJECTION = "rejection"       # 用户拒绝


class ComplexityLevel(Enum):
    """Query complexity level."""

    SIMPLE = 1      # 简单问题，单一维度
    MODERATE = 2    # 中等复杂度
    COMPLEX = 3     # 复杂问题，多维度
    CRITICAL = 4    # 关键决策，高风险


# ============================================================================
# CORE DATA CLASSES
# ============================================================================


@dataclass(frozen=True)
class QueryEmbedding:
    """Query vector representation.

    在实际实现中，这将是一个真实的向量。
    当前为占位符设计，保留接口扩展性。
    """

    values: tuple[float, ...] = field(default_factory=tuple)
    model: str = "placeholder"
    dimension: int = 0

    @classmethod
    def from_text(cls, text: str) -> QueryEmbedding:
        """从文本生成embedding（占位实现）。"""
        return cls(
            values=tuple([0.0] * 768),
            model="placeholder",
            dimension=768
        )

    def cosine_similarity(self, other: QueryEmbedding) -> float:
        """计算余弦相似度（占位实现）。"""
        if not self.values or not other.values:
            return 0.0
        dot = sum(a * b for a, b in zip(self.values, other.values))
        norm_a = sum(a * a for a in self.values) ** 0.5
        norm_b = sum(b * b for b in other.values) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


@dataclass(frozen=True)
class FeatureVector:
    """Unified feature representation for a query."""

    query_embedding: QueryEmbedding
    intent: IntentType
    domains: frozenset[DomainTag]
    complexity: ComplexityLevel
    emotion: EmotionType
    urgency: float          # 紧迫度 [0.0, 1.0]
    ambiguity: float        # 歧义度 [0.0, 1.0]
    query_length: int
    has_ethical_dimension: bool
    has_organizational_dimension: bool
    has_personal_dimension: bool
    historical_topics: frozenset[str]  # 历史话题关键词
    temporal_markers: frozenset[str]   # 时间标记词
    extraction_time: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    feature_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "feature_id": self.feature_id,
            "intent": self.intent.value,
            "domains": [d.name for d in self.domains],
            "complexity": self.complexity.value,
            "emotion": self.emotion.value,
            "urgency": self.urgency,
            "ambiguity": self.ambiguity,
            "query_length": self.query_length,
            "has_ethical_dimension": self.has_ethical_dimension,
            "has_organizational_dimension": self.has_organizational_dimension,
            "has_personal_dimension": self.has_personal_dimension,
            "extraction_time": self.extraction_time.isoformat(),
        }


@dataclass(frozen=True)
class SkillMetadata:
    """Metadata for a registered skill."""

    skill_id: str
    name: str
    slug: str                          # URL-friendly identifier
    tags: frozenset[str]               # 标签集（来自skill定义）
    domains: frozenset[DomainTag]      # 领域标签（从tags映射）
    description: str
    reasoning_style: str                # 推理风格描述
    strengths: tuple[str, ...]          # 擅长的领域
    weaknesses: tuple[str, ...]         # 不擅长的领域
    skill_file_path: str               # SKILL.md 文件路径
    embedding: Optional[QueryEmbedding] = None  # 延迟加载
    version: str = "1.0.0"
    last_updated: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "slug": self.slug,
            "tags": list(self.tags),
            "domains": [d.name for d in self.domains],
            "description": self.description,
            "reasoning_style": self.reasoning_style,
            "strengths": list(self.strengths),
            "weaknesses": list(self.weaknesses),
            "version": self.version,
        }


@dataclass
class SkillScore:
    """Individual skill score with breakdown."""

    skill_id: str
    skill_name: str

    # 四个维度的原始分数
    semantic_score: float = 0.0       # embedding相似度 [0.0, 1.0]
    rule_bias_score: float = 0.0       # 规则标签匹配 [0.0, 1.0]
    context_score: float = 0.0         # 上下文匹配 [0.0, 1.0]
    feedback_score: float = 0.0        # 历史表现反馈 [0.0, 1.0]

    # 加权总分
    total_score: float = 0.0

    # 各维度权重（可配置）
    weights: dict[str, float] = field(default_factory=dict)

    # 可解释性
    explanation: str = ""
    breakdown: dict[str, Any] = field(default_factory=dict)

    # 元数据
    score_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    computed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def compute_total(self) -> float:
        """根据权重计算加权总分。"""
        w = self.weights or {
            "semantic": 0.35,
            "rule_bias": 0.20,
            "context": 0.25,
            "feedback": 0.20,
        }
        self.total_score = (
            self.semantic_score * w.get("semantic", 0.35)
            + self.rule_bias_score * w.get("rule_bias", 0.20)
            + self.context_score * w.get("context", 0.25)
            + self.feedback_score * w.get("feedback", 0.20)
        )
        return self.total_score

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "score_id": self.score_id,
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "semantic_score": round(self.semantic_score, 4),
            "rule_bias_score": round(self.rule_bias_score, 4),
            "context_score": round(self.context_score, 4),
            "feedback_score": round(self.feedback_score, 4),
            "total_score": round(self.total_score, 4),
            "weights": self.weights,
            "explanation": self.explanation,
            "breakdown": self.breakdown,
            "computed_at": self.computed_at.isoformat(),
        }


@dataclass
class SkillUsageRecord:
    """Historical record of skill usage for a user."""

    skill_id: str
    user_id: str
    session_id: str

    # 使用信息
    query_preview: str                # query前50字符
    selected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # 反馈信息
    feedback: Optional[FeedbackType] = None
    feedback_score: Optional[float] = None  # [1.0, 5.0] 用户评分
    feedback_comment: Optional[str] = None

    # 执行信息
    execution_mode: ExecutionMode = ExecutionMode.SINGLE
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None

    # 上下文快照
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class UserProfile:
    """User profile for personalization."""

    user_id: str

    # 偏好设置
    preferred_skills: list[str] = field(default_factory=list)   # 优先skill列表
    avoided_skills: list[str] = field(default_factory=list)      # 回避skill列表
    preferred_domains: list[str] = field(default_factory=list)   # 偏好领域

    # 学习参数
    skill_weights: dict[str, float] = field(default_factory=dict)  # 动态权重
    skill_success_counts: dict[str, int] = field(default_factory=dict)  # 成功次数
    skill_total_counts: dict[str, int] = field(default_factory=dict)    # 总使用次数

    # 统计信息
    total_queries: int = 0
    total_sessions: int = 0
    last_active: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def skill_success_rate(self, skill_id: str) -> float:
        """计算某个skill的成功率。"""
        total = self.skill_total_counts.get(skill_id, 0)
        if total == 0:
            return 0.5  # 默认值
        success = self.skill_success_counts.get(skill_id, 0)
        return success / total

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "user_id": self.user_id,
            "preferred_skills": self.preferred_skills,
            "avoided_skills": self.avoided_skills,
            "preferred_domains": self.preferred_domains,
            "skill_weights": self.skill_weights,
            "skill_success_counts": self.skill_success_counts,
            "skill_total_counts": self.skill_total_counts,
            "total_queries": self.total_queries,
            "total_sessions": self.total_sessions,
            "last_active": self.last_active.isoformat(),
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SessionState:
    """Current session state."""

    session_id: str
    user_id: str

    # 历史记录
    query_history: list[str] = field(default_factory=list)
    skill_history: list[str] = field(default_factory=list)  # skill_id列表
    feature_history: list[FeatureVector] = field(default_factory=list)

    # 当前上下文
    current_query: Optional[str] = None
    current_features: Optional[FeatureVector] = None
    last_skills_used: list[str] = field(default_factory=list)

    # 统计
    turn_count: int = 0
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    last_active: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def add_turn(self, query: str, skill_ids: list[str], features: FeatureVector) -> None:
        """添加一轮对话记录。"""
        self.query_history.append(query)
        self.skill_history.extend(skill_ids)
        self.feature_history.append(features)
        self.current_query = query
        self.current_features = features
        self.last_skills_used = skill_ids
        self.turn_count += 1
        self.last_active = datetime.now(timezone.utc)


@dataclass
class RoutingDecision:
    """Final routing decision output."""

    # 选中的skill (required)
    selected_skills: list[str]           # skill_id列表
    skill_scores: dict[str, SkillScore]   # 完整打分

    # 决策信息 (required)
    execution_mode: ExecutionMode
    reasoning: str                        # 决策理由
    confidence: float                     # 置信度 [0.0, 1.0]

    # 执行计划 (required)
    execution_plan: list[dict[str, Any]]  # 执行步骤
    debate_pairs: Optional[list[tuple[str, str]]]  # 辩论配对 (用于DEBATE模式)

    # 可解释性 (required)
    explanation: str = ""                      # 对用户的解释
    trace: dict[str, Any] = field(default_factory=dict)  # 完整trace

    # 长期记忆上下文 (optional)
    memory_context: dict[str, Any] = field(default_factory=dict)

    # 元数据 (optional with defaults)
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    query_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "decision_id": self.decision_id,
            "selected_skills": self.selected_skills,
            "skill_scores": {k: v.to_dict() for k, v in self.skill_scores.items()},
            "execution_mode": self.execution_mode.value,
            "reasoning": self.reasoning,
            "confidence": round(self.confidence, 4),
            "execution_plan": self.execution_plan,
            "debate_pairs": self.debate_pairs,
            "explanation": self.explanation,
            "trace": self.trace,
            "memory_context": self.memory_context,
            "created_at": self.created_at.isoformat(),
            "query_preview": self.query_preview,
        }


@dataclass
class FeedbackRecord:
    """Feedback record for learning."""

    decision_id: str
    user_id: str
    session_id: str
    skill_id: str

    feedback_type: FeedbackType
    score: Optional[float] = None        # 用户评分 [1.0, 5.0]
    comment: Optional[str] = None
    is_positive: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))


# ============================================================================
# CONFIGURATION
# ============================================================================


@dataclass
class RouterConfig:
    """Router configuration."""

    # 打分权重
    scoring_weights: dict[str, float] = field(default_factory=lambda: {
        "semantic": 0.35,
        "rule_bias": 0.20,
        "context": 0.25,
        "feedback": 0.20,
    })

    # 决策参数
    top_k: int = 3                       # 返回top-k个skill
    multi_skill_threshold: float = 0.15   # 进入multi-skill的分数差阈值
    debate_threshold: float = 0.05        # 进入debate模式的分数差阈值
    min_score_threshold: float = 0.2      # 最小入选分数

    # 学习参数
    learning_rate: float = 0.1           # 权重更新学习率
    decay_factor: float = 0.95            # 历史反馈衰减因子
    min_feedback_count: int = 3          # 触发权重更新的最小反馈数

    # Feature extraction
    intent_rules: dict[str, Any] = field(default_factory=dict)
    domain_keywords: dict[str, list[str]] = field(default_factory=dict)

    # Skills目录路径
    skills_base_path: str = "skills"
    skills_glob_pattern: str = "**/SKILL.md"

    # Knowledge目录路径（用于RAG增强）
    knowledge_base_path: str = "knowledge"
    use_knowledge_rag: bool = True

    # 调试选项
    enable_trace: bool = True
    enable_heatmap: bool = False
    trace_log_path: Optional[str] = None


@dataclass
class TraceStep:
    """Single step in routing trace."""

    step_name: str
    step_order: int
    input_summary: dict[str, Any]
    output_summary: dict[str, Any]
    duration_ms: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_name": self.step_name,
            "step_order": self.step_order,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "duration_ms": round(self.duration_ms, 2),
            "metadata": self.metadata,
        }
