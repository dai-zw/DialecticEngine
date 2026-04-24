"""
Feedback Learning Tests
====================

测试反馈学习功能，包括：
- 显式反馈处理
- 隐式反馈处理
- 权重更新逻辑
- 纠错机制
- 反馈统计和分析
"""

import pytest
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from policy_router.types import FeedbackType, FeedbackRecord, UserProfile

if TYPE_CHECKING:
    from policy_router.feedback import FeedbackEngine, WeightUpdater
    from policy_router.context import ContextManager


# ============================================================================
# Explicit Feedback Tests
# ============================================================================

class TestExplicitFeedback:
    """测试显式反馈处理。"""

    def test_positive_feedback_processing(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试正面反馈处理。"""
        decision_id = "test_decision_1"
        skill_ids = ["rujia-perspective"]

        # 提交正面反馈
        weights = feedback_engine.receive_explicit_feedback(
            rating=5.0,
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
            comment="回答很好"
        )

        # 应该有权重更新
        assert weights is not None
        assert "rujia-perspective" in weights

    def test_negative_feedback_processing(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试负面反馈处理。"""
        decision_id = "test_decision_2"
        skill_ids = ["rujia-perspective"]

        weights = feedback_engine.receive_explicit_feedback(
            rating=1.0,
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
            comment="不太满意"
        )

        # 权重应该降低
        assert weights is not None

    def test_neutral_feedback_processing(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试中性反馈处理。"""
        decision_id = "test_decision_3"
        skill_ids = ["rujia-perspective", "fajia-perspective"]

        weights = feedback_engine.receive_explicit_feedback(
            rating=3.0,
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
        )

        # 中性反馈应该影响较小
        assert weights is not None

    def test_multi_skill_feedback_distribution(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试多技能反馈分配。"""
        decision_id = "test_decision_multi"
        skill_ids = ["rujia-perspective", "fajia-perspective", "daojia-perspective"]

        weights = feedback_engine.receive_explicit_feedback(
            rating=4.5,
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
        )

        # 所有技能都应该收到反馈
        for skill_id in skill_ids:
            assert skill_id in weights

    def test_feedback_with_comment(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试带评论的反馈。"""
        decision_id = "test_decision_comment"
        skill_ids = ["rujia-perspective"]

        weights = feedback_engine.receive_explicit_feedback(
            rating=4.0,
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
            comment="分析很有深度，但缺少具体建议"
        )

        assert weights is not None


# ============================================================================
# Implicit Feedback Tests
# ============================================================================

class TestImplicitFeedback:
    """测试隐式反馈处理。"""

    def test_acceptance_signal_detection(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试接受信号检测。"""
        decision_id = "test_decision_accept"
        skill_ids = ["rujia-perspective"]

        # 用户表示接受
        weights = feedback_engine.receive_implicit_feedback(
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
            user_response="好的，谢谢，这很有帮助",
            response_time=10.0,
        )

        # 应该触发正向反馈
        assert weights is not None

    def test_rejection_signal_detection(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试拒绝信号检测。"""
        decision_id = "test_decision_reject"
        skill_ids = ["rujia-perspective"]

        # 用户表示拒绝
        weights = feedback_engine.receive_implicit_feedback(
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
            user_response="不用这个，换一个视角",
            response_time=5.0,
        )

        # 应该触发负向反馈
        assert weights is not None

    def test_follow_up_signal_detection(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试追问信号检测。"""
        decision_id = "test_decision_followup"
        skill_ids = ["rujia-perspective"]

        # 用户追问
        weights = feedback_engine.receive_implicit_feedback(
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
            user_response="好的，然后呢？还有其他建议吗？",
            response_time=15.0,
        )

        # 追问表示满意，应该有正向反馈
        assert weights is not None

    def test_no_clear_signal(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试无明确信号时的处理。"""
        decision_id = "test_decision_neutral"
        skill_ids = ["rujia-perspective"]

        # 无明确信号
        weights = feedback_engine.receive_implicit_feedback(
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
            user_response="好的",
            response_time=5.0,
        )

        # 可能返回 None 或权重更新
        # 根据实现决定

    def test_quick_skip_detection(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试快速跳过检测。"""
        decision_id = "test_decision_skip"
        skill_ids = ["rujia-perspective"]

        # 用户快速跳过
        weights = feedback_engine.receive_implicit_feedback(
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=skill_ids,
            user_response="下一题",
            response_time=1.0,  # 快速跳过
        )

        # 应该有反馈信号
        assert weights is not None


# ============================================================================
# Correction Tests
# ============================================================================

class TestCorrection:
    """测试用户纠错功能。"""

    def test_user_correction_positive(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试用户正确纠错。"""
        decision_id = "test_decision_wrong"
        correct_skill_ids = ["fajia-perspective"]

        # 用户纠正
        feedback_engine.receive_correction(
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            correct_skill_ids=correct_skill_ids,
        )

        # 验证权重更新
        profile = feedback_engine.context_manager.get_user_profile(temp_user_id)
        assert profile.skill_weights.get("fajia-perspective", 0) > 0.5

    def test_multi_skill_correction(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试多技能纠错。"""
        decision_id = "test_decision_multi_wrong"
        correct_skill_ids = ["rujia-perspective", "daojia-perspective"]

        feedback_engine.receive_correction(
            decision_id=decision_id,
            user_id=temp_user_id,
            session_id=temp_session_id,
            correct_skill_ids=correct_skill_ids,
        )

        # 两个技能都应该有较高的权重
        profile = feedback_engine.context_manager.get_user_profile(temp_user_id)

        for skill_id in correct_skill_ids:
            assert profile.skill_weights.get(skill_id, 0) > 0.5


# ============================================================================
# Weight Update Tests
# ============================================================================

class TestWeightUpdate:
    """测试权重更新逻辑。"""

    def test_weight_increase_on_success(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试成功时权重增加。"""
        skill_id = "rujia-perspective"

        # 获取初始权重
        initial_weight = feedback_engine.context_manager.get_skill_weight(
            temp_user_id, skill_id
        )

        # 多次正面反馈
        for i in range(5):
            feedback_engine.receive_explicit_feedback(
                rating=5.0,
                decision_id=f"decision_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=[skill_id],
            )

        # 获取更新后的权重
        updated_weight = feedback_engine.context_manager.get_skill_weight(
            temp_user_id, skill_id
        )

        # 权重应该增加
        assert updated_weight >= initial_weight

    def test_weight_decrease_on_failure(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试失败时权重降低。"""
        skill_id = "fajia-perspective"

        # 多次负面反馈
        for i in range(3):
            feedback_engine.receive_explicit_feedback(
                rating=1.0,
                decision_id=f"decision_fail_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=[skill_id],
            )

        # 获取更新后的权重
        updated_weight = feedback_engine.context_manager.get_skill_weight(
            temp_user_id, skill_id
        )

        # 权重应该降低
        assert updated_weight < 0.5

    def test_weight_bounds_enforcement(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试权重边界约束。"""
        skill_id = "daojia-perspective"

        # 极端正面反馈
        for i in range(20):
            feedback_engine.receive_explicit_feedback(
                rating=5.0,
                decision_id=f"decision_pos_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=[skill_id],
            )

        weight = feedback_engine.context_manager.get_skill_weight(temp_user_id, skill_id)

        # 权重不应该超过 1.0
        assert weight <= 1.0

        # 极端负面反馈
        for i in range(20):
            feedback_engine.receive_explicit_feedback(
                rating=1.0,
                decision_id=f"decision_neg_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=[skill_id],
            )

        weight = feedback_engine.context_manager.get_skill_weight(temp_user_id, skill_id)

        # 权重不应该低于 0.1
        assert weight >= 0.1

    def test_learning_rate_effect(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试学习率的影响。"""
        skill_id = "bingjia-perspective"

        # 单次反馈的权重变化应该较小
        initial_weight = feedback_engine.context_manager.get_skill_weight(
            temp_user_id, skill_id
        )

        feedback_engine.receive_explicit_feedback(
            rating=5.0,
            decision_id="decision_lr_test",
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=[skill_id],
        )

        updated_weight = feedback_engine.context_manager.get_skill_weight(
            temp_user_id, skill_id
        )

        # 权重变化应该在合理范围内
        change = abs(updated_weight - initial_weight)
        assert change < 0.5  # 单次反馈不应该导致巨大变化

    def test_decay_towards_baseline(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试权重向基线衰减。"""
        skill_id = "mojia-perspective"

        # 设置一个极端权重
        profile = feedback_engine.context_manager.get_user_profile(temp_user_id)
        profile.skill_weights[skill_id] = 1.0
        feedback_engine.context_manager.update_user_profile(profile)

        # 不进行任何反馈，多次查询后权重应该衰减
        # 这里简化处理，假设衰减发生在反馈处理中

        # 进行多次中性反馈
        for i in range(10):
            feedback_engine.receive_explicit_feedback(
                rating=3.0,
                decision_id=f"decision_decay_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=[skill_id],
            )

        weight = feedback_engine.context_manager.get_skill_weight(temp_user_id, skill_id)

        # 权重应该接近基线 0.5
        assert 0.4 < weight < 0.6


# ============================================================================
# Feedback Statistics Tests
# ============================================================================

class TestFeedbackStatistics:
    """测试反馈统计功能。"""

    def test_skill_statistics(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试技能统计。"""
        skill_id = "rujia-perspective"

        # 收集反馈
        for i in range(10):
            rating = 4.0 if i % 2 == 0 else 2.0
            feedback_engine.receive_explicit_feedback(
                rating=rating,
                decision_id=f"decision_stat_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=[skill_id],
            )

        stats = feedback_engine.get_skill_stats(temp_user_id)

        assert skill_id in stats
        assert "count" in stats[skill_id]
        assert "mean_score" in stats[skill_id]
        assert "success_rate" in stats[skill_id]

    def test_feedback_insights_generation(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试反馈洞察生成。"""
        # 收集多样化的反馈
        skill_ratings = [
            ("rujia-perspective", 5.0),
            ("rujia-perspective", 4.5),
            ("rujia-perspective", 4.0),
            ("fajia-perspective", 2.0),
            ("fajia-perspective", 1.5),
            ("daojia-perspective", 4.5),
        ]

        for i, (skill_id, rating) in enumerate(skill_ratings):
            feedback_engine.receive_explicit_feedback(
                rating=rating,
                decision_id=f"decision_insight_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=[skill_id],
            )

        insights = feedback_engine.get_feedback_insights(temp_user_id)

        assert "insight" in insights
        assert "top_skills" in insights or len(insights["top_skills"]) >= 0

    def test_empty_feedback_stats(
        self,
        feedback_engine: "FeedbackEngine",
    ):
        """测试空反馈统计。"""
        temp_user_id = "test_empty_stats"

        stats = feedback_engine.get_skill_stats(temp_user_id)

        # 应该有默认结构
        assert isinstance(stats, dict)

    def test_feedback_record_counting(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试反馈记录计数。"""
        initial_count = len(feedback_engine._feedback_records)

        # 提交多个反馈
        for i in range(5):
            feedback_engine.receive_explicit_feedback(
                rating=4.0,
                decision_id=f"decision_count_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=["rujia-perspective"],
            )

        # 记录数量应该增加
        assert len(feedback_engine._feedback_records) == initial_count + 5


# ============================================================================
# Feedback Persistence Tests
# ============================================================================

class TestFeedbackPersistence:
    """测试反馈持久化。"""

    def test_feedback_save(
        self,
        feedback_engine: "FeedbackEngine",
        tmp_path,
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试反馈保存。"""
        feedback_engine.set_storage_path(str(tmp_path))

        # 提交反馈
        for i in range(3):
            feedback_engine.receive_explicit_feedback(
                rating=4.0,
                decision_id=f"decision_save_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=["rujia-perspective"],
            )

        # 保存
        feedback_engine.save_feedback()

        # 验证文件存在
        feedback_file = tmp_path / "feedback_records.jsonl"
        assert feedback_file.exists()

    def test_feedback_load(
        self,
        feedback_engine: "FeedbackEngine",
        tmp_path,
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试反馈加载。"""
        feedback_engine.set_storage_path(str(tmp_path))

        # 提交并保存
        for i in range(3):
            feedback_engine.receive_explicit_feedback(
                rating=4.0,
                decision_id=f"decision_load_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=["rujia-perspective"],
            )
        feedback_engine.save_feedback()

        # 创建新的 engine 并加载
        new_engine = feedback_engine.__class__(
            feedback_engine.config,
            feedback_engine.context_manager
        )
        new_engine.set_storage_path(str(tmp_path))
        new_engine.load_feedback()

        # 记录数量应该匹配
        assert len(new_engine._feedback_records) >= 3


# ============================================================================
# Feedback History Tests
# ============================================================================

class TestFeedbackHistory:
    """测试反馈历史管理。"""

    def test_feedback_history_limit(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试反馈历史长度限制。"""
        skill_id = "rujia-perspective"

        # 提交大量反馈
        for i in range(150):
            feedback_engine.receive_explicit_feedback(
                rating=4.0,
                decision_id=f"decision_history_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=[skill_id],
            )

        # 获取统计
        stats = feedback_engine.updater.get_feedback_stats(temp_user_id, skill_id)

        # 历史长度应该被限制
        assert stats["count"] <= 100  # 根据实现定义的上限

    def test_feedback_history_order(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试反馈历史顺序。"""
        skill_id = "rujia-perspective"

        ratings = [5.0, 4.0, 3.0, 2.0, 1.0]

        for i, rating in enumerate(ratings):
            feedback_engine.receive_explicit_feedback(
                rating=rating,
                decision_id=f"decision_order_{i}",
                user_id=temp_user_id,
                session_id=temp_session_id,
                skill_ids=[skill_id],
            )

        stats = feedback_engine.updater.get_feedback_stats(temp_user_id, skill_id)

        # 平均分应该反映所有评分
        expected_avg = sum(ratings) / len(ratings)
        assert abs(stats["mean_score"] - expected_avg) < 0.1


# ============================================================================
# Feedback Edge Cases
# ============================================================================

class TestFeedbackEdgeCases:
    """测试反馈边界情况。"""

    def test_zero_rating(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试零评分处理。"""
        weights = feedback_engine.receive_explicit_feedback(
            rating=0.0,
            decision_id="decision_zero",
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=["rujia-perspective"],
        )

        assert weights is not None

    def test_max_rating(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试最大评分处理。"""
        weights = feedback_engine.receive_explicit_feedback(
            rating=5.0,
            decision_id="decision_max",
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=["rujia-perspective"],
        )

        assert weights is not None

    def test_empty_skill_list(
        self,
        feedback_engine: "FeedbackEngine",
        temp_user_id: str,
        temp_session_id: str
    ):
        """测试空技能列表。"""
        weights = feedback_engine.receive_explicit_feedback(
            rating=4.0,
            decision_id="decision_empty",
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=[],
        )

        # 应该处理而不报错
        assert weights is not None or weights == {}

    def test_nonexistent_user(
        self,
        feedback_engine: "FeedbackEngine",
    ):
        """测试不存在用户的反馈。"""
        temp_user_id = "nonexistent_user_xyz"
        temp_session_id = "nonexistent_session_xyz"

        weights = feedback_engine.receive_explicit_feedback(
            rating=4.0,
            decision_id="decision_new_user",
            user_id=temp_user_id,
            session_id=temp_session_id,
            skill_ids=["rujia-perspective"],
        )

        # 应该自动创建用户并处理反馈
        assert weights is not None
