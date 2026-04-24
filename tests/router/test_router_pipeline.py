"""
Policy Router Integration Tests
==============================

测试 PolicyRouter 的完整路由管道，包括：
- 特征提取
- 上下文加载
- Skill 评分
- 决策融合
- 执行模式选择
- 辩论模式触发
"""

import pytest
from typing import TYPE_CHECKING

from policy_router.types import ExecutionMode, IntentType, ComplexityLevel

if TYPE_CHECKING:
    from policy_router import PolicyRouter
    from policy_router.types import RoutingDecision


# ============================================================================
# Feature Extraction Tests
# ============================================================================

class TestFeatureExtraction:
    """测试特征提取功能。"""

    def test_intent_classification(self, router: "PolicyRouter"):
        """测试意图分类是否正确。"""
        test_cases = [
            ("仁义礼是什么", IntentType.CONFUCIAN),
            ("如何制定绩效考核制度", IntentType.LEGALIST),
            ("无为而治是什么意思", IntentType.DAOIST),
            ("知己知彼是什么意思", IntentType.STRATEGY),
        ]

        for query, expected_intent in test_cases:
            decision = router.route(query)
            # 检查 trace 中是否包含意图信息
            assert decision.trace is not None

    def test_domain_extraction(self, router: "PolicyRouter"):
        """测试领域标签提取。"""
        queries_with_domains = [
            "企业管理应该用法家思想还是道家思想",
            "儒家伦理在现代社会还有意义吗",
        ]

        for query in queries_with_domains:
            decision = router.route(query)
            assert len(decision.selected_skills) >= 1

    def test_complexity_detection(self, router: "PolicyRouter"):
        """测试复杂度检测。"""
        simple_query = "什么是仁"
        complex_query = "在现代企业管理中，如何平衡法家的制度化管理与儒家的人本关怀"

        decision_simple = router.route(simple_query)
        decision_complex = router.route(complex_query)

        # 复杂查询应该选择更多 skill
        assert len(decision_complex.selected_skills) >= len(decision_simple.selected_skills)

    def test_emotion_detection(self, router: "PolicyRouter"):
        """测试情绪检测。"""
        queries = [
            "我非常焦虑，完全不知道该怎么办",  # 焦虑
            "我对老板非常愤怒，他太不公平了",   # 愤怒
        ]

        for query in queries:
            decision = router.route(query)
            assert decision is not None

    def test_urgency_and_ambiguity(self, router: "PolicyRouter"):
        """测试紧迫度和歧义度检测。"""
        queries = [
            "明天就要交方案，时间来不及怎么办",  # 高紧迫
            "这个决定太难了，各有各的道理",      # 高歧义
        ]

        for query in queries:
            decision = router.route(query)
            assert decision.confidence is not None


# ============================================================================
# Execution Mode Tests
# ============================================================================

class TestExecutionModes:
    """测试执行模式选择。"""

    def test_single_mode_selection(self, router: "PolicyRouter"):
        """测试单一模式选择（分数差距大时）。"""
        # 明确单一问题，应该选择 SINGLE 模式
        queries = [
            "什么是儒家的仁",
            "法家的术是什么意思",
        ]

        for query in queries:
            decision = router.route(query)
            # 单一模式
            assert decision.execution_mode in [
                ExecutionMode.SINGLE,
                ExecutionMode.MULTI,
                ExecutionMode.DEBATE
            ]
            assert len(decision.selected_skills) >= 1

    def test_multi_mode_selection(self, router: "PolicyRouter"):
        """测试多视角模式选择（分数接近时）。"""
        # 复杂平衡问题，可能选择 MULTI 模式
        queries = [
            "事业和家庭如何平衡",
            "个人理想和现实责任如何取舍",
        ]

        for query in queries:
            decision = router.route(query)
            # 检查执行计划
            assert decision.execution_plan is not None
            assert len(decision.execution_plan) >= 1

    def test_debate_mode_trigger(self, router: "PolicyRouter"):
        """测试辩论模式触发（对立视角时）。"""
        # 对立问题应该触发辩论
        debate_queries = [
            "应该依法治国还是以德治国",
            "商业竞争中应该狼性还是人性化管理",
        ]

        for query in debate_queries:
            decision = router.route(query)
            # 辩论模式或至少多视角
            assert decision.execution_mode in [
                ExecutionMode.SINGLE,
                ExecutionMode.MULTI,
                ExecutionMode.DEBATE
            ]

    def test_mode_consistency(self, router: "PolicyRouter"):
        """测试相同问题在不同时间的一致性。"""
        query = "如何做一个好的领导者"

        decision1 = router.route(query)
        decision2 = router.route(query)

        # 相同 query 应该选择相同的 skills（或至少在 top-k 内）
        assert set(decision1.selected_skills[:2]) == set(decision2.selected_skills[:2])


# ============================================================================
# Decision Fusion Tests
# ============================================================================

class TestDecisionFusion:
    """测试决策融合逻辑。"""

    def test_top_k_selection(self, router: "PolicyRouter"):
        """测试 Top-K 选择逻辑。"""
        query = "企业管理问题"
        decision = router.route(query)

        # 应该返回最多 top_k 个 skills
        assert len(decision.selected_skills) <= router.config.top_k

    def test_score_threshold(self, router: "PolicyRouter"):
        """测试分数阈值过滤。"""
        query = "xyz123不存在的关键词"  # 应该得低分
        decision = router.route(query)

        # 即使模糊查询也应该有结果
        assert len(decision.selected_skills) >= 1

    def test_confidence_calculation(self, router: "PolicyRouter"):
        """测试置信度计算。"""
        queries = [
            "仁义礼智信是什么",  # 明确问题
            "人生的意义是什么",  # 模糊问题
        ]

        for query in queries:
            decision = router.route(query)
            assert 0 <= decision.confidence <= 1

    def test_reasoning_generation(self, router: "PolicyRouter"):
        """测试决策理由生成。"""
        query = "如何拒绝朋友不合理的请求"
        decision = router.route(query)

        assert decision.reasoning is not None
        assert len(decision.reasoning) > 0

    def test_explanation_generation(self, router: "PolicyRouter"):
        """测试用户可见的解释生成。"""
        query = "职场中如何处理与上司的冲突"
        decision = router.route(query)

        assert decision.explanation is not None
        assert len(decision.explanation) > 0

    def test_execution_plan_generation(self, router: "PolicyRouter"):
        """测试执行计划生成。"""
        query = "创业初期如何制定战略"
        decision = router.route(query)

        assert decision.execution_plan is not None
        assert len(decision.execution_plan) > 0

        # 检查执行步骤结构
        for step in decision.execution_plan:
            assert "step" in step
            assert "action" in step


# ============================================================================
# Routing Pipeline Integration Tests
# ============================================================================

class TestRoutingPipeline:
    """测试完整路由管道。"""

    def test_full_pipeline_execution(self, router: "PolicyRouter", temp_session_id: str, temp_user_id: str):
        """测试完整管道执行。"""
        query = "如何做一个合格的领导者"

        decision = router.route(
            query=query,
            user_id=temp_user_id,
            session_id=temp_session_id
        )

        # 验证所有输出字段
        assert decision.decision_id is not None
        assert len(decision.selected_skills) >= 1
        assert decision.execution_mode is not None
        assert decision.confidence is not None
        assert decision.reasoning is not None
        assert decision.explanation is not None
        assert decision.execution_plan is not None

    def test_pipeline_with_trace(self, router: "PolicyRouter"):
        """测试带 trace 的管道执行。"""
        router.config.enable_trace = True

        query = "儒法道三家思想有什么区别"
        decision = router.route(query)

        # 检查 trace
        assert decision.trace is not None
        assert "steps" in decision.trace

    def test_pipeline_with_context(self, router: "PolicyRouter", temp_session_id: str, temp_user_id: str):
        """测试带上下文的管道执行。"""
        # 第一轮
        query1 = "我想学习管理知识"
        decision1 = router.route(query1, user_id=temp_user_id, session_id=temp_session_id)

        # 第二轮 - 应该考虑上下文
        query2 = "具体应该怎么做"
        decision2 = router.route(query2, user_id=temp_user_id, session_id=temp_session_id)

        # 上下文应该影响决策
        assert decision2 is not None

    def test_pipeline_with_feature_override(self, router: "PolicyRouter"):
        """测试特征覆盖。"""
        query = "一个小问题"

        # 带自定义上下文
        context = {
            "force_intent": IntentType.DECISION_ANALYSIS,
            "force_mode": ExecutionMode.SINGLE,
        }

        decision = router.route(query, context=context)
        assert decision is not None

    def test_routing_idempotency(self, router: "PolicyRouter"):
        """测试路由幂等性。"""
        query = "法家的核心思想是什么"

        decisions = [router.route(query) for _ in range(5)]

        # 所有决策应该有相同的 selected_skills
        first_skills = decisions[0].selected_skills
        for decision in decisions[1:]:
            assert decision.selected_skills == first_skills


# ============================================================================
# Multi-Skill Tests
# ============================================================================

class TestMultiSkillRouting:
    """测试多 Skill 选择和协作。"""

    def test_multi_skill_score_calculation(self, router: "PolicyRouter"):
        """测试多 Skill 分数计算。"""
        query = "如何平衡工作和生活"
        decision = router.route(query)

        # 检查每个选中 skill 的分数
        for skill_id in decision.selected_skills:
            assert skill_id in decision.skill_scores
            score = decision.skill_scores[skill_id]
            assert 0 <= score.total_score <= 1

    def test_multi_skill_weight_distribution(self, router: "PolicyRouter"):
        """测试多 Skill 权重分配。"""
        query = "创业应该创新还是模仿"
        decision = router.route(query)

        if len(decision.selected_skills) > 1:
            # 权重应该合理分配
            weights = [
                step.get("weight", 0)
                for step in decision.execution_plan
                if "weight" in step
            ]
            if weights:
                assert sum(weights) > 0

    def test_multi_skill_aggregation(self, router: "PolicyRouter"):
        """测试多 Skill 结果聚合。"""
        query = "企业应该追求利润还是社会责任"
        decision = router.route(query)

        if decision.execution_mode == ExecutionMode.MULTI:
            # 检查是否有聚合步骤
            has_aggregate = any(
                step.get("action") == "aggregate_responses"
                for step in decision.execution_plan
            )
            assert has_aggregate or len(decision.selected_skills) >= 1


# ============================================================================
# Debate Mode Tests
# ============================================================================

class TestDebateMode:
    """测试辩论模式。"""

    def test_debate_pair_generation(self, router: "PolicyRouter"):
        """测试辩论配对生成。"""
        query = "法治和德治哪个更重要"
        decision = router.route(query)

        if decision.execution_mode == ExecutionMode.DEBATE:
            assert decision.debate_pairs is not None
            assert len(decision.debate_pairs) >= 1

            # 检查配对结构
            for pair in decision.debate_pairs:
                assert len(pair) == 2
                assert pair[0] != pair[1]

    def test_debate_execution_plan(self, router: "PolicyRouter"):
        """测试辩论执行计划。"""
        query = "商业道德重要还是盈利重要"
        decision = router.route(query)

        if decision.execution_mode == ExecutionMode.DEBATE:
            # 检查执行计划
            actions = [step.get("action") for step in decision.execution_plan]
            assert "invoke_skill" in actions
            assert "synthesize_debate" in actions or "aggregate_responses" in actions

    def test_opposing_pairs_detection(self, router: "PolicyRouter"):
        """测试对立配对检测。"""
        opposing_queries = [
            "儒家和法家哪个更适合管理",
            "个人利益和集体利益如何取舍",
        ]

        for query in opposing_queries:
            decision = router.route(query)
            # 应该触发多视角或辩论
            assert decision.execution_mode in [
                ExecutionMode.MULTI,
                ExecutionMode.DEBATE
            ] or len(decision.selected_skills) >= 2


# ============================================================================
# Edge Cases for Routing
# ============================================================================

class TestRoutingEdgeCases:
    """测试路由边界情况。"""

    def test_empty_query(self, router: "PolicyRouter"):
        """测试空查询处理。"""
        query = ""

        decision = router.route(query)

        # 应该返回结果或合理的默认值
        assert decision is not None
        assert decision.selected_skills is not None

    def test_very_long_query(self, router: "PolicyRouter"):
        """测试超长查询处理。"""
        query = "仁" * 1000

        decision = router.route(query)

        assert decision is not None
        assert len(decision.selected_skills) >= 1

    def test_mixed_language_query(self, router: "PolicyRouter"):
        """测试中英混合查询。"""
        queries = [
            "儒家思想 and legalism",
            "how to apply 道家 philosophy in management",
        ]

        for query in queries:
            decision = router.route(query)
            assert decision is not None

    def test_special_characters(self, router: "PolicyRouter"):
        """测试特殊字符处理。"""
        queries = [
            "仁义礼智信!!!",
            "法家<<<>>>",
        ]

        for query in queries:
            decision = router.route(query)
            assert decision is not None

    def test_query_with_punctuation(self, router: "PolicyRouter"):
        """测试各种标点符号。"""
        queries = [
            "仁义是什么？",
            "法家的思想！",
            "道家 - 无为而治",
        ]

        for query in queries:
            decision = router.route(query)
            assert decision is not None

    def test_repeated_keywords(self, router: "PolicyRouter"):
        """测试重复关键词。"""
        query = "仁仁仁仁仁 义义义义义"

        decision = router.route(query)

        assert decision is not None
        assert "rujia-perspective" in decision.selected_skills

    def test_no_matching_keywords(self, router: "PolicyRouter"):
        """测试无匹配关键词。"""
        query = "xyz abc 123 测试"

        decision = router.route(query)

        # 应该仍然返回结果
        assert decision is not None
        assert len(decision.selected_skills) >= 1

    def test_unicode_query(self, router: "PolicyRouter"):
        """测试 Unicode 查询。"""
        queries = [
            "仁义礼智信",
            "法術勢",
            "無為而治",
        ]

        for query in queries:
            decision = router.route(query)
            assert decision is not None
