"""
DialecticEngine - Agent Harness 模块
===================================
提供 Agent 运行的统一框架和质量控制。

包含：
- Adjudicator: 裁决 Agent，评判回答质量
- AgentHarness: 统一运行框架，支持自动重试
- FallbackManager: 失败处理与策略切换
- ConflictDetector: Skill 输出冲突检测

Usage:
    # 使用裁决 Agent
    from harness.adjudicator import Adjudicator, quick_judge
    
    result = quick_judge(
        user_query="我和老板意见不合...",
        skills=["rujia-perspective"],
        response="从儒家角度看...",
    )
    print(result.score, result.verdict)
    
    # 使用 Fallback Manager
    from harness.fallback_manager import FallbackManager, FallbackInput
    
    manager = FallbackManager(llm)
    decision = manager.evaluate(
        user_input="...",
        router_scores=[...],
        skill_outputs=[...],
        fusion_result={},
    )
    
    # 使用 Harness 运行
    from harness.agent_harness import AgentHarness
    
    harness = AgentHarness(engine)
    result = await harness.run("我想提升决策质量")
"""

from .adjudicator import (
    Adjudicator,
    Judgement,
    JudgementCriteria,
    DimensionScore,
    quick_judge,
)

from .agent_harness import (
    AgentHarness,
    AgentResult,
    HarnessConfig,
    quick_run,
)

from .fallback_manager import (
    FallbackManager,
    FallbackInput,
    FallbackDecision,
    FallbackConfig,
    quick_evaluate,
)

from .conflict_detector import (
    ConflictDetector,
    quick_detect,
)

__all__ = [
    # Adjudicator
    "Adjudicator",
    "Judgement",
    "JudgementCriteria",
    "DimensionScore",
    "quick_judge",
    # AgentHarness
    "AgentHarness",
    "AgentResult",
    "HarnessConfig",
    "quick_run",
    # Fallback
    "FallbackManager",
    "FallbackInput",
    "FallbackDecision",
    "FallbackConfig",
    "quick_evaluate",
    # Conflict
    "ConflictDetector",
    "quick_detect",
]
