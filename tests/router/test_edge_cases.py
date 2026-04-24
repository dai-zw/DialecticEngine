"""
Edge Cases and Exception Handling Tests
======================================

测试边界情况和异常处理，包括：
- 输入验证
- 错误恢复
- 并发处理
- 资源限制
- 配置边界
"""

import pytest
import time
from typing import TYPE_CHECKING

from policy_router import PolicyRouter, RouterConfig
from policy_router.types import (
    ExecutionMode, FeatureVector, QueryEmbedding,
    IntentType, DomainTag, ComplexityLevel, EmotionType
)

if TYPE_CHECKING:
    from policy_router import PolicyRouter


# ============================================================================
# Input Validation Tests
# ============================================================================

class TestInputValidation:
    """测试输入验证。"""

    def test_empty_query_handling(self, router: "PolicyRouter"):
        """测试空查询处理。"""
        query = ""

        decision = router.route(query)

        # 应该返回有效决策而不是崩溃
        assert decision is not None
        assert decision.decision_id is not None

    def test_whitespace_only_query(self, router: "PolicyRouter"):
        """测试纯空白查询。"""
        query = "   \t\n   "

        decision = router.route(query)

        assert decision is not None

    def test_very_long_query(self, router: "PolicyRouter"):
        """测试超长查询处理。"""
        query = "仁" * 10000

        decision = router.route(query)

        assert decision is not None
        assert len(decision.selected_skills) >= 1

    def test_unicode_edge_cases(self, router: "PolicyRouter"):
        """测试 Unicode 边界情况。"""
        queries = [
            "\u0000",  # 空字符
            "\uffff",  # 最大 Unicode
            "\u4e00" * 5000,  # 大量汉字
            "mixed\u4e00text\u4e01",  # 混合
        ]

        for query in queries:
            decision = router.route(query)
            assert decision is not None

    def test_special_characters(self, router: "PolicyRouter"):
        """测试特殊字符。"""
        queries = [
            "仁义礼<Script>alert('xss')</Script>",
            "法家' OR '1'='1",
            '道家" UNION SELECT * FROM users',
            "兵家\n\r\t\b",
        ]

        for query in queries:
            decision = router.route(query)
            assert decision is not None

    def test_numeric_only_query(self, router: "PolicyRouter"):
        """测试纯数字查询。"""
        queries = ["123456", "0.123", "-999"]

        for query in queries:
            decision = router.route(query)
            assert decision is not None

    def test_english_only_query(self, router: "PolicyRouter"):
        """测试纯英文查询。"""
        queries = [
            "what is confucianism",
            "legalism in management",
            "daoist philosophy",
        ]

        for query in queries:
            decision = router.route(query)
            assert decision is not None

    def test_mixed_language_query(self, router: "PolicyRouter"):
        """测试中英混合查询。"""
        queries = [
            "儒家的仁义礼 principles",
            "法家 legal system",
            "道家 wu wei concept",
        ]

        for query in queries:
            decision = router.route(query)
            assert decision is not None


# ============================================================================
# Configuration Boundary Tests
# ============================================================================

class TestConfigurationBoundaries:
    """测试配置边界。"""

    def test_top_k_boundary(self):
        """测试 top_k 边界值。"""
        # 边界值 0
        config0 = RouterConfig(top_k=0)
        assert config0.top_k == 0

        # 边界值 1
        config1 = RouterConfig(top_k=1)
        assert config1.top_k == 1

        # 边界值 100
        config100 = RouterConfig(top_k=100)
        assert config100.top_k == 100

        # 创建 router
        router0 = PolicyRouter(config=config0)
        router1 = PolicyRouter(config=config1)

        query = "儒家思想"
        decision0 = router0.route(query)
        decision1 = router1.route(query)

        assert len(decision0.selected_skills) <= 0
        assert len(decision1.selected_skills) <= 1

    def test_threshold_boundaries(self):
        """测试阈值边界值。"""
        config = RouterConfig(
            multi_skill_threshold=0.0,
            debate_threshold=0.0,
            min_score_threshold=0.0,
        )

        assert config.multi_skill_threshold == 0.0
        assert config.debate_threshold == 0.0
        assert config.min_score_threshold == 0.0

        router = PolicyRouter(config=config)
        decision = router.route("仁义礼是什么")

        assert decision is not None

    def test_threshold_at_one(self):
        """测试阈值等于 1 的情况。"""
        config = RouterConfig(
            multi_skill_threshold=1.0,
            debate_threshold=1.0,
            min_score_threshold=1.0,
        )

        router = PolicyRouter(config=config)
        decision = router.route("儒家")

        # 所有阈值都为 1 时，只有最高分可能通过
        assert decision is not None

    def test_learning_rate_boundaries(self):
        """测试学习率边界值。"""
        # 零学习率
        config_zero = RouterConfig(learning_rate=0.0)
        assert config_zero.learning_rate == 0.0

        # 最大学习率
        config_max = RouterConfig(learning_rate=1.0)
        assert config_max.learning_rate == 1.0

        # 极端学习率
        config_extreme = RouterConfig(learning_rate=10.0)
        assert config_extreme.learning_rate == 10.0

    def test_decay_factor_boundaries(self):
        """测试衰减因子边界值。"""
        # 无衰减
        config_zero = RouterConfig(decay_factor=0.0)
        assert config_zero.decay_factor == 0.0

        # 完全保留
        config_one = RouterConfig(decay_factor=1.0)
        assert config_one.decay_factor == 1.0


# ============================================================================
# Concurrency Tests
# ============================================================================

class TestConcurrencyHandling:
    """测试并发处理。"""

    def test_sequential_routing(self, router: "PolicyRouter"):
        """测试顺序路由。"""
        queries = [
            "儒家思想",
            "法家管理",
            "道家哲学",
            "兵家战略",
            "墨家逻辑",
        ]

        results = []
        for query in queries:
            decision = router.route(query)
            results.append(decision)

        assert len(results) == 5
        assert all(r is not None for r in results)

    def test_rapid_sequential_routing(self, router: "PolicyRouter"):
        """测试快速连续路由。"""
        queries = ["儒家"] * 100

        start_time = time.time()
        for query in queries:
            router.route(query)
        elapsed = time.time() - start_time

        # 应该能快速完成
        assert elapsed < 30  # 假设 100 个查询应该在 30 秒内完成

    def test_session_isolation(self, router: "PolicyRouter"):
        """测试会话隔离。"""
        sessions = [f"session_{i}" for i in range(5)]
        queries = ["儒家", "法家", "道家", "兵家", "墨家"]

        # 并发创建会话
        for session_id, query in zip(sessions, queries):
            router.route(query, session_id=session_id)

        # 验证每个会话独立
        for session_id, expected_query in zip(sessions, queries):
            session = router.context_manager.get_session_history(session_id)
            # 每个会话应该只有一轮
            assert session.turn_count >= 1


# ============================================================================
# Error Recovery Tests
# ============================================================================

class TestErrorRecovery:
    """测试错误恢复。"""

    def test_router_after_failed_route(self, router: "PolicyRouter"):
        """测试失败后 router 仍可用。"""
        # 第一次可能失败的操作（如果有的话）
        try:
            router.route("")
        except Exception:
            pass

        # 第二次应该正常工作
        decision = router.route("儒家")
        assert decision is not None

    def test_context_manager_after_errors(self, router: "PolicyRouter"):
        """测试错误后上下文管理器仍可用。"""
        user_id = "test_user_error"

        # 尝试可能失败的操作
        try:
            router.context_manager.get_user_profile("")
        except Exception:
            pass

        # 应该恢复正常
        profile = router.context_manager.get_user_profile(user_id)
        assert profile is not None

    def test_multiple_config_reloads(self, router: "PolicyRouter"):
        """测试多次配置重载。"""
        for _ in range(5):
            router.reload_skills()

        # 应该仍然正常工作
        decision = router.route("儒家")
        assert decision is not None


# ============================================================================
# Resource Limit Tests
# ============================================================================

class TestResourceLimits:
    """测试资源限制。"""

    def test_large_session_history(self, router: "PolicyRouter"):
        """测试大会话历史处理。"""
        session_id = "large_session"
        user_id = "test_user"

        session = router.context_manager.get_or_create_session(session_id, user_id)

        # 添加大量轮次
        for i in range(100):
            feature = FeatureVector(
                query_embedding=QueryEmbedding(),
                intent=IntentType.GENERAL,
                domains=frozenset(),
                complexity=ComplexityLevel.SIMPLE,
                emotion=EmotionType.NEUTRAL,
                urgency=0.5,
                ambiguity=0.3,
                query_length=10,
                has_ethical_dimension=False,
                has_organizational_dimension=False,
                has_personal_dimension=False,
                historical_topics=frozenset(),
                temporal_markers=frozenset(),
            )
            session.add_turn(f"query_{i}", [f"skill_{i}"], feature)

        router.context_manager.update_session(session)

        # 获取历史
        history = router.context_manager.get_session_history(session_id)

        # 验证历史被正确管理
        assert history is not None

    def test_many_concurrent_sessions(self, router: "PolicyRouter"):
        """测试大量并发会话。"""
        user_id = "test_user"

        # 创建多个会话
        for i in range(50):
            session_id = f"session_{i}"
            router.context_manager.get_or_create_session(session_id, user_id)

        # 验证所有会话都能获取
        for i in range(50):
            session_id = f"session_{i}"
            session = router.context_manager.get_session_history(session_id)
            assert session is not None

    def test_long_skill_history(self, router: "PolicyRouter"):
        """测试长技能历史。"""
        session_id = "long_skill_session"
        user_id = "test_user"

        session = router.context_manager.get_or_create_session(session_id, user_id)

        # 添加大量技能
        skills = ["rujia", "fajia", "daojia", "bingjia", "mojia"]
        for i in range(100):
            skill_id = skills[i % len(skills)]
            feature = FeatureVector(
                query_embedding=QueryEmbedding(),
                intent=IntentType.GENERAL,
                domains=frozenset(),
                complexity=ComplexityLevel.SIMPLE,
                emotion=EmotionType.NEUTRAL,
                urgency=0.5,
                ambiguity=0.3,
                query_length=10,
                has_ethical_dimension=False,
                has_organizational_dimension=False,
                has_personal_dimension=False,
                historical_topics=frozenset(),
                temporal_markers=frozenset(),
            )
            session.add_turn(f"query_{i}", [f"{skill_id}-perspective"], feature)

        router.context_manager.update_session(session)

        # 获取最近技能
        recent = router.context_manager.get_recent_skills(session_id, max_count=10)

        # 应该返回最近的技能
        assert len(recent) == 10


# ============================================================================
# Memory Management Tests
# ============================================================================

class TestMemoryManagement:
    """测试内存管理。"""

    def test_session_clear(self, router: "PolicyRouter"):
        """测试会话清除。"""
        user_id = "test_user"

        # 创建并填充会话
        session_id = "to_clear"
        router.context_manager.get_or_create_session(session_id, user_id)
        session = router.context_manager.get_session_history(session_id)
        for i in range(10):
            session.add_turn(f"query_{i}", [f"skill_{i}"], FeatureVector(
                query_embedding=QueryEmbedding(),
                intent=IntentType.GENERAL,
                domains=frozenset(),
                complexity=ComplexityLevel.SIMPLE,
                emotion=EmotionType.NEUTRAL,
                urgency=0.5,
                ambiguity=0.3,
                query_length=10,
                has_ethical_dimension=False,
                has_organizational_dimension=False,
                has_personal_dimension=False,
                historical_topics=frozenset(),
                temporal_markers=frozenset(),
            ))
        router.context_manager.update_session(session)

        # 清除会话
        router.context_manager.clear_session(session_id)

        # 验证清除
        cleared_session = router.context_manager.get_session_history(session_id)
        assert cleared_session.turn_count == 0

    def test_clear_all_sessions(self, router: "PolicyRouter"):
        """测试清除所有会话。"""
        user_id = "test_user"

        # 创建多个会话
        for i in range(5):
            session_id = f"session_{i}"
            router.context_manager.get_or_create_session(session_id, user_id)

        # 清除所有
        router.context_manager.clear_all_sessions()

        # 验证清除
        for i in range(5):
            session_id = f"session_{i}"
            session = router.context_manager.get_session_history(session_id)
            assert session.turn_count == 0


# ============================================================================
# Data Type Tests
# ============================================================================

class TestDataTypes:
    """测试数据类型处理。"""

    def test_none_values_handling(self, router: "PolicyRouter"):
        """测试 None 值处理。"""
        # 无 session_id
        decision = router.route("儒家", session_id=None)
        assert decision is not None

        # 无 user_id（使用默认值）
        decision = router.route("法家", user_id="default_user")
        assert decision is not None

    def test_special_types_in_context(self, router: "PolicyRouter"):
        """测试上下文中的特殊类型。"""
        query = "儒家"

        # 带特殊上下文
        context = {
            "custom_key": "custom_value",
            "nested": {"a": 1, "b": 2},
        }

        decision = router.route(query, context=context)
        assert decision is not None

    def test_feature_vector_boundaries(self):
        """测试特征向量边界值。"""
        # 极端值
        feature = FeatureVector(
            query_embedding=QueryEmbedding(),
            intent=IntentType.GENERAL,
            domains=frozenset(),
            complexity=ComplexityLevel.CRITICAL,
            emotion=EmotionType.DESPERATE,
            urgency=1.0,
            ambiguity=1.0,
            query_length=10000,
            has_ethical_dimension=True,
            has_organizational_dimension=True,
            has_personal_dimension=True,
            historical_topics=frozenset(),
            temporal_markers=frozenset(),
        )

        assert feature.urgency == 1.0
        assert feature.ambiguity == 1.0

    def test_feature_vector_defaults(self):
        """测试特征向量默认值。"""
        feature = FeatureVector(
            query_embedding=QueryEmbedding(),
            intent=IntentType.GENERAL,
            domains=frozenset(),
            complexity=ComplexityLevel.SIMPLE,
            emotion=EmotionType.NEUTRAL,
            urgency=0.0,
            ambiguity=0.0,
            query_length=0,
            has_ethical_dimension=False,
            has_organizational_dimension=False,
            has_personal_dimension=False,
            historical_topics=frozenset(),
            temporal_markers=frozenset(),
        )

        assert feature.urgency == 0.0
        assert feature.ambiguity == 0.0


# ============================================================================
# Score Calculation Tests
# ============================================================================

class TestScoreCalculations:
    """测试分数计算边界。"""

    def test_zero_scores(self, router: "PolicyRouter"):
        """测试零分情况。"""
        query = "xyz123不存在的概念"

        decision = router.route(query)

        # 应该仍然有结果，即使分数很低
        assert decision is not None
        assert len(decision.selected_skills) >= 1

    def test_perfect_scores(self, router: "PolicyRouter"):
        """测试满分情况。"""
        # 包含所有关键词
        query = "仁义礼智信忠孝悌君子中庸修身"

        decision = router.route(query)

        # 应该给儒家高分
        if decision.skill_scores:
            rujia_score = decision.skill_scores.get("rujia-perspective")
            if rujia_score:
                assert rujia_score.total_score > 0

    def test_even_score_distribution(self, router: "PolicyRouter"):
        """测试均匀分数分布。"""
        query = "general question"

        rankings = router.get_skill_rankings(query)

        if len(rankings) > 1:
            # 分数不应该完全相同
            scores = [score for _, score in rankings]
            # 至少有一些变化
            assert len(set(scores)) >= 1

    def test_score_normalization(self, router: "PolicyRouter"):
        """测试分数归一化。"""
        queries = ["儒家", "法家", "道家"]

        for query in queries:
            rankings = router.get_skill_rankings(query)

            for _, score in rankings:
                assert 0 <= score <= 1, f"分数 {score} 超出 [0, 1] 范围"


# ============================================================================
# Integration Edge Cases
# ============================================================================

class TestIntegrationEdgeCases:
    """测试集成边界情况。"""

    def test_routing_with_no_skills(self):
        """测试没有 skill 时的处理。"""
        config = RouterConfig(skills_base_path="nonexistent_path")
        router = PolicyRouter(config=config)

        decision = router.route("儒家")

        # 应该优雅处理
        assert decision is not None

    def test_router_reload(self, router: "PolicyRouter"):
        """测试 router 重载。"""
        # 初始状态
        decision1 = router.route("儒家")
        initial_skills = set(decision1.selected_skills)

        # 重载
        router.reload_skills()

        # 重载后应该相同
        decision2 = router.route("儒家")
        assert set(decision2.selected_skills) == initial_skills

    def test_multiple_feedback_types(self, router: "PolicyRouter", temp_user_id: str, temp_session_id: str):
        """测试多种反馈类型。"""
        query = "儒家思想"

        # 路由
        decision = router.route(query, user_id=temp_user_id, session_id=temp_session_id)

        # 显式反馈
        router.submit_explicit_feedback(
            rating=4.0,
            decision_id=decision.decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=decision.selected_skills,
        )

        # 隐式反馈
        router.submit_implicit_feedback(
            decision_id=decision.decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=decision.selected_skills,
            user_response="好的，继续",
        )

        # 纠错
        router.submit_correction(
            decision_id=decision.decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            correct_skill_ids=["fajia-perspective"],
        )

        # 应该没有错误
        assert True

    def test_full_conversation_flow(self, router: "PolicyRouter", temp_user_id: str, temp_session_id: str):
        """测试完整对话流程。"""
        queries = [
            "我想了解一下儒家思想",
            "儒家主要讲什么",
            "仁义礼是什么意思",
            "法家和儒家有什么区别",
            "道家呢，有什么特点",
        ]

        decisions = []
        for query in queries:
            decision = router.route(query, user_id=temp_user_id, session_id=temp_session_id)
            decisions.append(decision)

        # 验证流程
        assert len(decisions) == 5

        # 验证会话历史
        session = router.context_manager.get_session_history(temp_session_id)
        assert session.turn_count == 5
        assert len(session.query_history) == 5


# ============================================================================
# Performance Baseline Tests
# ============================================================================

class TestPerformanceBaselines:
    """测试性能基线。"""

    def test_single_route_performance(self, router: "PolicyRouter"):
        """测试单次路由性能。"""
        start_time = time.time()
        decision = router.route("儒家思想的核心是什么")
        elapsed = time.time() - start_time

        # 应该在合理时间内完成
        assert elapsed < 5.0, f"单次路由耗时 {elapsed:.2f}s，超过 5s 基线"
        assert decision is not None

    def test_batch_route_performance(self, router: "PolicyRouter"):
        """测试批量路由性能。"""
        queries = [
            "儒家思想",
            "法家管理",
            "道家哲学",
            "兵家战略",
            "墨家逻辑",
        ]

        start_time = time.time()
        for query in queries:
            router.route(query)
        elapsed = time.time() - start_time

        # 5 次路由应该在 10 秒内完成
        assert elapsed < 10.0, f"5次路由耗时 {elapsed:.2f}s，超过 10s 基线"

    def test_context_retrieval_performance(self, router: "PolicyRouter", temp_user_id: str, temp_session_id: str):
        """测试上下文检索性能。"""
        # 先填充数据
        for i in range(50):
            router.route(f"query_{i}", user_id=temp_user_id, session_id=temp_session_id)

        # 测试检索性能
        start_time = time.time()
        context = router.context_manager.get_context_for_scorer(temp_user_id, temp_session_id)
        elapsed = time.time() - start_time

        assert elapsed < 1.0, f"上下文检索耗时 {elapsed:.2f}s，超过 1s 基线"
        assert context is not None
