"""
DialecticEngine - Policy Router
==============================
系统级Policy Router，为多Skill哲学推理系统提供智能路由决策能力。

Quick Start:
    from policy_router import PolicyRouter, create_router, quick_route

    # 方式1: 快捷路由
    decision = quick_route("你和老板意见不合，该直言吗？")

    # 方式2: 自定义配置
    router = create_router(skills_path="skills", top_k=3)
    decision = router.route(query="...", user_id="user_123")

    # 方式3: 完整控制
    from policy_router import RouterConfig
    config = RouterConfig(top_k=5, enable_trace=True)
    router = PolicyRouter(config=config)
    decision = router.route(query="...", user_id="...", session_id="...")
"""

from .types import (
    # Config
    RouterConfig,
    # Enums
    IntentType,
    DomainTag,
    ExecutionMode,
    EmotionType,
    FeedbackType,
    ComplexityLevel,
    # Core Data Classes
    QueryEmbedding,
    FeatureVector,
    SkillMetadata,
    SkillScore,
    SkillUsageRecord,
    UserProfile,
    SessionState,
    RoutingDecision,
    FeedbackRecord,
    TraceStep,
)

from .router import (
    PolicyRouter,
    create_router,
    quick_route,
)

from .features import (
    FeatureExtractor,
    create_extractor,
)

from .context import (
    ContextManager,
    ContextAggregator,
    create_context_manager,
)

from .registry_adapter import (
    SkillRegistry,
    RegistryAdapter,
    create_registry,
    create_adapter,
)

from .scorer import (
    MultiDimensionScorer,
    create_scorer,
)

from .fusion import (
    DecisionFusionEngine,
    create_fusion_engine,
)

from .feedback import (
    FeedbackEngine,
    create_feedback_engine,
)

__version__ = "1.0.0"
__all__ = [
    # Config
    "RouterConfig",
    # Enums
    "IntentType",
    "DomainTag",
    "ExecutionMode",
    "EmotionType",
    "FeedbackType",
    "ComplexityLevel",
    # Core Data Classes
    "QueryEmbedding",
    "FeatureVector",
    "SkillMetadata",
    "SkillScore",
    "SkillUsageRecord",
    "UserProfile",
    "SessionState",
    "RoutingDecision",
    "FeedbackRecord",
    "TraceStep",
    # Main Classes
    "PolicyRouter",
    "FeatureExtractor",
    "ContextManager",
    "SkillRegistry",
    "RegistryAdapter",
    "MultiDimensionScorer",
    "DecisionFusionEngine",
    "FeedbackEngine",
    # Factory Functions
    "create_router",
    "quick_route",
    "create_extractor",
    "create_context_manager",
    "create_registry",
    "create_adapter",
    "create_scorer",
    "create_fusion_engine",
    "create_feedback_engine",
]
