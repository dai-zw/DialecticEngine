"""
DialecticEngine - Policy Router Core
====================================
系统级Policy Router主入口，协调所有模块完成路由决策。

Routing Pipeline:
1. Feature Extraction    - 提取query特征
2. Context Load         - 加载上下文状态
3. Skill Scoring        - 对所有skill打分
4. Decision Fusion      - 融合决策
5. Feedback Hook        - 反馈学习钩子
6. Return Result        - 返回路由结果

Usage:
    from policy_router import PolicyRouter, RouterConfig

    config = RouterConfig(
        skills_base_path="skills",
        top_k=3,
    )
    router = PolicyRouter(config)
    result = router.route(
        query="我的领导对我有恩，但他的决策明显错误，我该直言吗？",
        user_id="user_123",
        session_id="session_abc",
    )
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .types import (
    RouterConfig,
    FeatureVector,
    RoutingDecision,
    ExecutionMode,
    TraceStep,
    SkillScore,
)
from .features import FeatureExtractor, create_extractor
from .context import ContextManager, create_context_manager
from .registry_adapter import (
    SkillRegistry,
    RegistryAdapter,
    create_registry,
    create_adapter,
)
from .scorer import MultiDimensionScorer, create_scorer
from .fusion import DecisionFusionEngine, create_fusion_engine
from .feedback import FeedbackEngine, create_feedback_engine

# 长期记忆（延迟导入，避免循环依赖）
_long_term_memory = None

def _get_long_term_memory():
    """获取长期记忆模块（延迟导入）"""
    global _long_term_memory
    if _long_term_memory is None:
        try:
            from milvus_DB.long_term_memory import get_memory, init_memory
            _long_term_memory = init_memory()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"长期记忆模块初始化失败: {e}")
            return None
    return _long_term_memory


# ============================================================================
# ROUTING TRACE LOGGER
# ============================================================================


class RoutingTraceLogger:
    """Logs routing decisions for debugging and analysis."""

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path) if log_path else None
        self._trace_buffer: list[dict[str, Any]] = []

    def log(self, decision: RoutingDecision, features: FeatureVector) -> None:
        """Log a routing decision."""
        entry = {
            "decision_id": decision.decision_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "query_preview": decision.query_preview,
            "selected_skills": decision.selected_skills,
            "execution_mode": decision.execution_mode.value,
            "confidence": decision.confidence,
            "features": features.to_dict(),
            "all_scores": {
                sid: score.to_dict()
                for sid, score in decision.skill_scores.items()
            },
            "trace": decision.trace,
        }

        self._trace_buffer.append(entry)

        # 如果有日志路径，写入文件
        if self.log_path:
            self._write_to_file(entry)

    def _write_to_file(self, entry: dict[str, Any]) -> None:
        """Write entry to log file."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_trace(self, decision_id: str) -> Optional[dict[str, Any]]:
        """Get trace for a specific decision."""
        for entry in self._trace_buffer:
            if entry["decision_id"] == decision_id:
                return entry
        return None

    def get_recent_traces(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent traces."""
        return self._trace_buffer[-limit:]

    def clear(self) -> None:
        """Clear trace buffer."""
        self._trace_buffer.clear()


# ============================================================================
# SKILL IMPORTANCE HEATMAP
# ============================================================================


class SkillImportanceHeatmap:
    """Generates skill importance heatmap data.

    用于可视化skill在历史决策中的重要性分布。
    """

    def __init__(self):
        self._importance_scores: dict[str, list[float]] = {}

    def record(
        self,
        decision: RoutingDecision,
        features: FeatureVector,
    ) -> None:
        """Record skill importance from a decision."""
        for skill_id, score in decision.skill_scores.items():
            if skill_id not in self._importance_scores:
                self._importance_scores[skill_id] = []
            self._importance_scores[skill_id].append(score.total_score)

    def get_heatmap_data(
        self,
        window_size: int = 100,
    ) -> dict[str, dict[str, Any]]:
        """Get heatmap data for visualization.

        Returns:
            Dict with skill_id -> {avg_score, count, recent_scores}
        """
        result = {}

        for skill_id, scores in self._importance_scores.items():
            # 使用滑动窗口
            recent = scores[-window_size:]

            result[skill_id] = {
                "avg_score": sum(recent) / len(recent) if recent else 0.0,
                "count": len(recent),
                "scores": recent[-20:],  # 最近20个分数用于可视化
                "peak": max(recent) if recent else 0.0,
                "trough": min(recent) if recent else 0.0,
            }

        return result

    def get_domain_distribution(
        self,
    ) -> dict[str, float]:
        """Get domain distribution of skill usage.

        Returns:
            Dict with domain -> total importance score
        """
        distribution: dict[str, float] = {}

        for skill_id, scores in self._importance_scores.items():
            # 从skill_id推断domain（简化实现）
            domain = skill_id.split("-")[0] if "-" in skill_id else "general"
            total = sum(scores)
            distribution[domain] = distribution.get(domain, 0.0) + total

        return distribution


# ============================================================================
# POLICY ROUTER (MAIN CLASS)
# ============================================================================


class PolicyRouter:
    """System-level Policy Router.

    主入口类，协调所有模块完成从query到routing decision的转换。

    Example:
        router = PolicyRouter()

        decision = router.route(
            query="我和老板意见不合，但他对我有恩，我该直言吗？",
            user_id="user_123",
            session_id="session_abc",
        )

        print(decision.selected_skills)  # ['rujia-perspective']
        print(decision.explanation)       # 生成的自然语言解释
    """

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        storage_path: Optional[str] = None,
    ):
        """Initialize PolicyRouter.

        Args:
            config: Router configuration. If None, uses defaults.
            storage_path: Path for persisting user profiles and feedback.
        """
        self.config = config or RouterConfig()
        self.storage_path = Path(storage_path) if storage_path else None

        # 初始化各模块
        self._init_modules()

        # 调试工具
        self.trace_logger: Optional[RoutingTraceLogger] = None
        self.heatmap: Optional[SkillImportanceHeatmap] = None

        if self.config.enable_trace:
            log_path = self.config.trace_log_path
            self.trace_logger = RoutingTraceLogger(log_path)
            self.heatmap = SkillImportanceHeatmap()

    def _init_modules(self) -> None:
        """Initialize all sub-modules."""
        # Feature Extractor
        self.feature_extractor: FeatureExtractor = create_extractor(self.config)

        # Context Manager
        self.context_manager: ContextManager = create_context_manager(
            config=self.config,
            storage_path=str(self.storage_path) if self.storage_path else None,
        )

        # Skill Registry
        self.registry: SkillRegistry = create_registry(config=self.config)

        # Registry Adapter
        self.registry_adapter: RegistryAdapter = create_adapter(
            registry=self.registry,
            config=self.config,
        )

        # Scorer
        self.scorer: MultiDimensionScorer = create_scorer(
            config=self.config,
            context_manager=self.context_manager,
            registry_adapter=self.registry_adapter,
        )

        # Fusion Engine
        self.fusion_engine: DecisionFusionEngine = create_fusion_engine(
            config=self.config,
        )

        # Feedback Engine
        self.feedback_engine: FeedbackEngine = create_feedback_engine(
            config=self.config,
            context_manager=self.context_manager,
        )

        # 长期记忆模块
        self._long_term_memory = None
        
        # 扫描skills
        self.registry.scan()

    # -------------------------------------------------------------------------
    # MAIN ROUTING METHOD
    # -------------------------------------------------------------------------

    def route(
        self,
        query: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> RoutingDecision:
        """Route a query to appropriate skills.

        Main pipeline:
        1. Feature Extraction
        2. Context Load
        3. Skill Scoring (all skills)
        4. Decision Fusion
        5. Feedback Hook
        6. Return Routing Result

        Args:
            query: User's query text
            user_id: User identifier for personalization
            session_id: Session identifier. Auto-generated if None.
            context: Optional pre-extracted context

        Returns:
            RoutingDecision with selected skills, scores, and reasoning
        """
        start_time = time.time()
        session_id = session_id or str(uuid.uuid4())

        # 创建trace steps列表
        trace_steps: list[TraceStep] = []

        # =====================================================================
        # STEP 1: Feature Extraction
        # =====================================================================
        step1_start = time.time()
        features = self.feature_extractor.extract(query, context)
        trace_steps.append(self.feature_extractor.create_trace_step(
            "feature_extraction", features,
            (time.time() - step1_start) * 1000
        ))

        # =====================================================================
        # STEP 2: Context Load
        # =====================================================================
        step2_start = time.time()
        session = self.context_manager.get_or_create_session(session_id, user_id)
        user_context = self.context_manager.get_context_for_scorer(user_id, session_id)
        
        # 长期记忆检索
        memory_context = self._get_memory_context(query)
        
        trace_steps.append(TraceStep(
            step_name="context_load",
            step_order=1,
            input_summary={"user_id": user_id, "session_id": session_id},
            output_summary={
                "recent_skills": session.last_skills_used[-5:],
                "turn_count": session.turn_count,
                "memory_results": len(memory_context.get("similar_memories", [])),
            },
            duration_ms=(time.time() - step2_start) * 1000,
        ))

        # =====================================================================
        # STEP 3: Skill Scoring (all skills)
        # =====================================================================
        step3_start = time.time()
        all_scores = self.scorer.score_all_skills(
            query=query,
            features=features,
            user_id=user_id,
            session_id=session_id,
        )
        trace_steps.append(self.scorer.create_trace_step(
            query, all_scores,
            (time.time() - step3_start) * 1000
        ))

        # =====================================================================
        # STEP 4: Decision Fusion
        # =====================================================================
        step4_start = time.time()
        decision = self.fusion_engine.fuse(
            scores=all_scores,
            features=features,
        )
        trace_steps.append(self.fusion_engine.create_trace_step(
            decision,
            (time.time() - step4_start) * 1000
        ))

        # =====================================================================
        # STEP 5: Feedback Hook
        # =====================================================================
        # 记录到heatmap（用于可视化）
        if self.heatmap:
            self.heatmap.record(decision, features)

        # =====================================================================
        # STEP 6: Session Update & Finalize
        # =====================================================================
        # 更新session
        session.add_turn(
            query=query,
            skill_ids=decision.selected_skills,
            features=features,
        )
        self.context_manager.update_session(session)

        # 添加trace和query preview
        decision.query_preview = query[:100]

        # 合并所有trace steps
        for i, step in enumerate(trace_steps):
            step.step_order = i
        decision.trace = {
            "steps": [s.to_dict() for s in trace_steps],
            "total_duration_ms": (time.time() - start_time) * 1000,
        }
        
        # 将长期记忆上下文添加到决策中
        decision.memory_context = memory_context

        # =====================================================================
        # STEP 7: Logging
        # =====================================================================
        if self.trace_logger:
            self.trace_logger.log(decision, features)

        return decision

    # -------------------------------------------------------------------------
    # FEEDBACK METHODS
    # -------------------------------------------------------------------------

    def submit_explicit_feedback(
        self,
        rating: float,
        decision_id: str,
        user_id: str,
        session_id: str,
        skill_ids: list[str],
        comment: Optional[str] = None,
    ) -> dict[str, float]:
        """Submit explicit user feedback.

        Args:
            rating: User rating [1.0, 5.0]
            decision_id: Decision ID from route() response
            user_id: User identifier
            session_id: Session identifier
            skill_ids: Skills that were selected
            comment: Optional user comment

        Returns:
            Updated weights dict
        """
        return self.feedback_engine.receive_explicit_feedback(
            rating=rating,
            decision_id=decision_id,
            user_id=user_id,
            session_id=session_id,
            skill_ids=skill_ids,
            comment=comment,
        )

    def submit_implicit_feedback(
        self,
        decision_id: str,
        user_id: str,
        session_id: str,
        skill_ids: list[str],
        user_response: str,
        response_time: float = 5.0,
    ) -> Optional[dict[str, float]]:
        """Submit implicit feedback from user behavior.

        Returns:
            Updated weights dict if clear signal, None otherwise
        """
        return self.feedback_engine.receive_implicit_feedback(
            decision_id=decision_id,
            user_id=user_id,
            session_id=session_id,
            skill_ids=skill_ids,
            user_response=user_response,
            response_time=response_time,
        )

    def submit_correction(
        self,
        decision_id: str,
        user_id: str,
        session_id: str,
        correct_skill_ids: list[str],
    ) -> None:
        """Submit user correction (wrong skill selected).

        Args:
            decision_id: The wrong decision ID
            user_id: User identifier
            session_id: Session identifier
            correct_skill_ids: Skills user thinks should have been selected
        """
        self.feedback_engine.receive_correction(
            decision_id=decision_id,
            user_id=user_id,
            session_id=session_id,
            correct_skill_ids=correct_skill_ids,
        )

    def get_feedback_insights(self, user_id: str) -> dict[str, Any]:
        """Get feedback insights for a user.

        Returns:
            Dict with insights about user's skill preferences
        """
        return self.feedback_engine.get_feedback_insights(user_id)

    # -------------------------------------------------------------------------
    # DEBUG & VISUALIZATION
    # -------------------------------------------------------------------------

    def get_all_scores(
        self,
        query: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
    ) -> dict[str, SkillScore]:
        """Get scores for all skills (for debugging).

        Returns:
            Dict of skill_id -> SkillScore for all registered skills
        """
        session_id = session_id or str(uuid.uuid4())
        features = self.feature_extractor.extract(query)

        return self.scorer.score_all_skills(
            query=query,
            features=features,
            user_id=user_id,
            session_id=session_id,
        )

    def get_skill_rankings(
        self,
        query: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
    ) -> list[tuple[str, float]]:
        """Get ranked list of skills for a query.

        Returns:
            List of (skill_id, total_score) sorted by score descending
        """
        scores = self.get_all_scores(query, user_id, session_id)
        return sorted(
            [(sid, s.total_score) for sid, s in scores.items()],
            key=lambda x: x[1],
            reverse=True
        )

    def explain_decision(
        self,
        decision: RoutingDecision,
    ) -> dict[str, Any]:
        """Generate detailed explanation for a decision.

        Returns:
            Dict with structured explanation data
        """
        return {
            "decision_id": decision.decision_id,
            "selected_skills": decision.selected_skills,
            "mode": decision.execution_mode.value,
            "confidence": decision.confidence,
            "reasoning": decision.reasoning,
            "explanation": decision.explanation,
            "score_breakdowns": {
                sid: score.breakdown
                for sid, score in decision.skill_scores.items()
                if sid in decision.selected_skills
            },
            "execution_plan": decision.execution_plan,
        }

    def get_heatmap(self) -> Optional[dict[str, Any]]:
        """Get skill importance heatmap data.

        Returns:
            Heatmap data or None if not enabled
        """
        if not self.heatmap:
            return None

        return {
            "skill_importance": self.heatmap.get_heatmap_data(),
            "domain_distribution": self.heatmap.get_domain_distribution(),
        }

    def get_trace_log(self) -> list[dict[str, Any]]:
        """Get recent routing traces.

        Returns:
            List of recent trace entries
        """
        if not self.trace_logger:
            return []
        return self.trace_logger.get_recent_traces()

    def reload_skills(self) -> None:
        """Force reload skills from disk.

        Use when skills have been updated without restarting.
        """
        self.registry.reload()

    # -------------------------------------------------------------------------
    # UTILITY METHODS
    # -------------------------------------------------------------------------

    def get_available_skills(self) -> list[str]:
        """Get list of all available skill IDs."""
        skills = self.registry.get_all_skills()
        return [s.skill_id for s in skills]

    def get_skill_info(self, skill_id: str) -> Optional[dict[str, Any]]:
        """Get information about a specific skill."""
        skill = self.registry.get_skill(skill_id)
        if not skill:
            return None
        return skill.to_dict()

    def set_preferred_skills(self, user_id: str, skill_ids: list[str]) -> None:
        """Set user's preferred skills."""
        self.context_manager.set_preferred_skills(user_id, skill_ids)

    def set_avoided_skills(self, user_id: str, skill_ids: list[str]) -> None:
        """Set user's avoided skills."""
        self.context_manager.set_avoided_skills(user_id, skill_ids)

    # -------------------------------------------------------------------------
    # LONG-TERM MEMORY METHODS
    # -------------------------------------------------------------------------

    def _get_memory_context(self, query: str) -> dict[str, Any]:
        """
        获取长期记忆上下文
        
        用于在路由决策时参考历史相似决策。
        
        Args:
            query: 用户问题
        
        Returns:
            包含相似记忆的上下文字典
        """
        # 延迟初始化长期记忆
        if self._long_term_memory is None:
            try:
                from milvus_DB.long_term_memory import init_memory
                self._long_term_memory = init_memory()
            except Exception:
                return {}
        
        if not self._long_term_memory.is_connected():
            return {}
        
        try:
            # 检索相似记忆
            results = self._long_term_memory.search(
                query=query,
                top_k=self.config.top_k,
            )
            
            if not results:
                return {}
            
            # 构建上下文
            similar_skills = []
            avg_confidence = 0.0
            
            for result in results:
                similar_skills.append({
                    "skill_id": result.record.selected_skills[0] if result.record.selected_skills else "",
                    "skills": result.record.selected_skills,
                    "confidence": result.record.confidence,
                    "similarity": result.similarity,
                    "reasoning": result.record.reasoning,
                })
                avg_confidence += result.similarity
            
            avg_confidence /= len(results) if results else 1
            
            return {
                "similar_memories": similar_skills,
                "memory_count": len(results),
                "avg_similarity": avg_confidence,
                "has_memory_context": True,
            }
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"长期记忆检索失败: {e}")
            return {}

    def get_similar_decisions(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """
        获取相似历史决策
        
        Args:
            query: 用户问题
            top_k: 返回数量
        
        Returns:
            相似决策列表
        """
        # 延迟初始化长期记忆
        if self._long_term_memory is None:
            try:
                from milvus_DB.long_term_memory import init_memory
                self._long_term_memory = init_memory()
            except Exception:
                return []
        
        if not self._long_term_memory:
            return []
        
        try:
            results = self._long_term_memory.search(query, top_k=top_k)
            return [
                {
                    "record_id": r.record.record_id,
                    "query": r.record.query,
                    "skills": r.record.selected_skills,
                    "confidence": r.record.confidence,
                    "similarity": r.similarity,
                    "reasoning": r.record.reasoning,
                }
                for r in results
            ]
        except Exception:
            return []

    def store_decision_to_memory(
        self,
        query: str,
        selected_skills: list[str],
        skill_scores: dict[str, float],
        confidence: float,
        reasoning: str,
        response: str = "",
        user_id: str = "default",
    ) -> Optional[str]:
        """
        将路由决策存储到长期记忆
        
        Args:
            query: 用户问题
            selected_skills: 选中的技能
            skill_scores: 技能得分
            confidence: 决策置信度
            reasoning: 决策理由
            response: 生成的回答
            user_id: 用户 ID
        
        Returns:
            record_id 或 None
        """
        # 延迟初始化长期记忆
        if self._long_term_memory is None:
            try:
                from milvus_DB.long_term_memory import init_memory
                self._long_term_memory = init_memory()
            except Exception:
                return None
        
        if not self._long_term_memory:
            return None
        
        try:
            return self._long_term_memory.store(
                query=query,
                selected_skills=selected_skills,
                skill_scores=skill_scores,
                confidence=confidence,
                reasoning=reasoning,
                response=response,
                user_id=user_id,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"存储记忆失败: {e}")
            return None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def create_router(
    skills_path: str = "skills",
    storage_path: Optional[str] = None,
    top_k: int = 3,
    enable_trace: bool = True,
) -> PolicyRouter:
    """Convenience function to create a configured router.

    Example:
        router = create_router(
            skills_path="skills",
            storage_path="./router_storage",
            top_k=3,
        )
    """
    config = RouterConfig(
        skills_base_path=skills_path,
        top_k=top_k,
        enable_trace=enable_trace,
        trace_log_path=f"{storage_path}/traces.jsonl" if storage_path else None,
    )

    return PolicyRouter(config=config, storage_path=storage_path)


def quick_route(
    query: str,
    user_id: str = "default",
    session_id: Optional[str] = None,
) -> RoutingDecision:
    """Quick routing without configuration.

    Uses all defaults. Suitable for simple use cases.
    """
    router = PolicyRouter()
    return router.route(
        query=query,
        user_id=user_id,
        session_id=session_id,
    )


# ============================================================================
# DEMO / EXAMPLE
# ============================================================================


def demo():
    """Demo of the Policy Router."""
    print("=" * 60)
    print("DialecticEngine Policy Router Demo")
    print("=" * 60)

    # 创建router
    router = create_router(
        skills_path="skills",
        top_k=3,
    )

    # 测试query
    queries = [
        # 儒家场景
        "我和老板意见不合，但他对我有恩，我该直言吗？",
        # 法家场景
        "公司的绩效考核制度执行不下去，大家都在钻空子怎么办？",
        # 道家场景
        "我最近特别焦虑，拼命努力却感觉没有进展，该怎么办？",
        # 兵家场景
        "竞争对手推出了一个很有竞争力的产品，我们该如何应对？",
        # 复杂场景（可能触发多skill）
        "我既想追求个人理想，又要对家人负责，该如何平衡？",
    ]

    print(f"\n发现 {len(router.get_available_skills())} 个可用skills")
    print()

    for i, query in enumerate(queries, 1):
        print(f"\n{'='*60}")
        print(f"Query {i}: {query}")
        print("-" * 40)

        decision = router.route(query, user_id="demo_user")

        print(f"执行模式: {decision.execution_mode.value}")
        print(f"选择Skills: {', '.join(decision.selected_skills)}")
        print(f"置信度: {decision.confidence:.2%}")
        print(f"决策理由: {decision.reasoning[:100]}...")
        print(f"\n解释: {decision.explanation}")

        # 显示top-3得分
        top3 = sorted(
            decision.skill_scores.items(),
            key=lambda x: x[1].total_score,
            reverse=True
        )[:3]

        print("\nTop-3 Scores:")
        for sid, score in top3:
            print(f"  {sid}: {score.total_score:.4f}")
            print(f"    - semantic: {score.semantic_score:.3f}")
            print(f"    - rule_bias: {score.rule_bias_score:.3f}")
            print(f"    - context: {score.context_score:.3f}")
            print(f"    - feedback: {score.feedback_score:.3f}")


if __name__ == "__main__":
    demo()
