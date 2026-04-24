"""
Context Management Tests
======================

测试上下文管理功能，包括：
- 用户画像管理
- 会话状态管理
- 上下文信号聚合
- 持久化支持
"""

import pytest
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from policy_router.types import UserProfile, SessionState, FeatureVector, QueryEmbedding, IntentType, DomainTag, ComplexityLevel, EmotionType

if TYPE_CHECKING:
    from policy_router.context import ContextManager


# ============================================================================
# User Profile Tests
# ============================================================================

class TestUserProfile:
    """测试用户画像管理。"""

    def test_profile_creation(self, context_manager: "ContextManager"):
        """测试创建默认用户画像。"""
        user_id = "test_user_profile"

        profile = context_manager.get_user_profile(user_id)

        assert profile is not None
        assert profile.user_id == user_id
        assert profile.preferred_skills == []
        assert profile.avoided_skills == []
        assert profile.skill_weights == {}
        assert profile.total_queries == 0

    def test_profile_persistence(self, context_manager: "ContextManager", tmp_path):
        """测试用户画像持久化。"""
        context_manager.storage_path = tmp_path

        user_id = "test_persist_user"
        profile = context_manager.get_user_profile(user_id)

        # 更新画像
        profile.preferred_skills = ["rujia-perspective"]
        profile.skill_weights["rujia-perspective"] = 0.8
        context_manager.update_user_profile(profile)

        # 重新获取
        profile2 = context_manager.get_user_profile(user_id)

        assert profile2.preferred_skills == ["rujia-perspective"]
        assert profile2.skill_weights.get("rujia-perspective") == 0.8

    def test_profile_preferred_skills(self, context_manager: "ContextManager"):
        """测试设置偏好技能。"""
        user_id = "test_pref_skills"

        context_manager.set_preferred_skills(
            user_id,
            ["rujia-perspective", "daojia-perspective"]
        )

        profile = context_manager.get_user_profile(user_id)
        assert "rujia-perspective" in profile.preferred_skills
        assert "daojia-perspective" in profile.preferred_skills

    def test_profile_avoided_skills(self, context_manager: "ContextManager"):
        """测试设置回避技能。"""
        user_id = "test_avoid_skills"

        context_manager.set_avoided_skills(
            user_id,
            ["fajia-perspective"]
        )

        profile = context_manager.get_user_profile(user_id)
        assert "fajia-perspective" in profile.avoided_skills

    def test_skill_weight_tracking(self, context_manager: "ContextManager"):
        """测试技能权重追踪。"""
        user_id = "test_weight_tracking"

        # 增加使用次数
        context_manager.increment_skill_usage(user_id, "rujia-perspective", success=True)
        context_manager.increment_skill_usage(user_id, "rujia-perspective", success=True)
        context_manager.increment_skill_usage(user_id, "rujia-perspective", success=False)

        profile = context_manager.get_user_profile(user_id)

        # 检查统计数据
        assert profile.skill_total_counts.get("rujia-perspective") == 3
        assert profile.skill_success_counts.get("rujia-perspective") == 2

        # 检查成功率
        rate = profile.skill_success_rate("rujia-perspective")
        assert 0 <= rate <= 1
        assert rate == 2 / 3

    def test_dynamic_weight_update(self, context_manager: "ContextManager"):
        """测试动态权重更新。"""
        user_id = "test_dynamic_weight"

        # 多次成功
        for _ in range(5):
            context_manager.increment_skill_usage(user_id, "rujia-perspective", success=True)

        weight = context_manager.get_skill_weight(user_id, "rujia-perspective")

        # 权重应该在合理范围内
        assert 0 <= weight <= 1
        assert weight > 0.5  # 成功率高应该有较高权重

    def test_multiple_users_isolation(self, context_manager: "ContextManager"):
        """测试多用户数据隔离。"""
        user1 = "user_1"
        user2 = "user_2"

        # 设置不同的偏好
        context_manager.set_preferred_skills(user1, ["rujia-perspective"])
        context_manager.set_preferred_skills(user2, ["daojia-perspective"])

        # 验证隔离
        profile1 = context_manager.get_user_profile(user1)
        profile2 = context_manager.get_user_profile(user2)

        assert "rujia-perspective" in profile1.preferred_skills
        assert "daojia-perspective" in profile2.preferred_skills
        assert "daojia-perspective" not in profile1.preferred_skills
        assert "rujia-perspective" not in profile2.preferred_skills


# ============================================================================
# Session State Tests
# ============================================================================

class TestSessionState:
    """测试会话状态管理。"""

    def test_session_creation(self, context_manager: "ContextManager"):
        """测试创建会话。"""
        session_id = "test_session"
        user_id = "test_user"

        session = context_manager.get_or_create_session(session_id, user_id)

        assert session is not None
        assert session.session_id == session_id
        assert session.user_id == user_id
        assert session.turn_count == 0
        assert session.query_history == []

    def test_add_turn(self, context_manager: "ContextManager"):
        """测试添加对话轮次。"""
        session_id = "test_session_turns"
        user_id = "test_user"

        session = context_manager.get_or_create_session(session_id, user_id)

        # 创建测试特征向量
        feature_vector = FeatureVector(
            query_embedding=QueryEmbedding(),
            intent=IntentType.ETHICAL_DILEMMA,
            domains=frozenset([DomainTag.ETHICS]),
            complexity=ComplexityLevel.MODERATE,
            emotion=EmotionType.NEUTRAL,
            urgency=0.5,
            ambiguity=0.3,
            query_length=20,
            has_ethical_dimension=True,
            has_organizational_dimension=False,
            has_personal_dimension=True,
            historical_topics=frozenset(),
            temporal_markers=frozenset(),
        )

        # 添加轮次
        context_manager.add_turn_to_session(
            session_id=session_id,
            query="测试问题",
            skill_ids=["rujia-perspective"],
            features=feature_vector,
        )

        # 验证
        updated_session = context_manager.get_session_history(session_id)
        assert updated_session.turn_count == 1
        assert "测试问题" in updated_session.query_history
        assert "rujia-perspective" in updated_session.skill_history

    def test_session_history_retrieval(self, context_manager: "ContextManager"):
        """测试获取会话历史。"""
        session_id = "test_history"
        user_id = "test_user"

        # 创建多个轮次
        session = context_manager.get_or_create_session(session_id, user_id)

        for i in range(5):
            session.add_turn(
                query=f"问题{i}",
                skill_ids=[f"skill_{i}"],
                features=FeatureVector(
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
            )
            context_manager.update_session(session)

        # 获取历史
        history = context_manager.get_session_history(session_id)

        assert len(history.query_history) == 5
        assert len(history.skill_history) == 5
        assert history.turn_count == 5

    def test_recent_skills_retrieval(self, context_manager: "ContextManager"):
        """测试获取最近使用的技能。"""
        session_id = "test_recent"
        user_id = "test_user"

        session = context_manager.get_or_create_session(session_id, user_id)

        # 添加多个技能
        skills = ["rujia", "fajia", "daojia", "bingjia", "mojia"]
        for skill in skills:
            session.add_turn(
                query="问题",
                skill_ids=[f"{skill}-perspective"],
                features=FeatureVector(
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
            )
            context_manager.update_session(session)

        # 获取最近 3 个
        recent = context_manager.get_recent_skills(session_id, max_count=3)

        assert len(recent) == 3
        # 最近使用的应该在前面
        assert f"{skills[-1]}-perspective" in recent[0]

    def test_session_clear(self, context_manager: "ContextManager"):
        """测试清除会话。"""
        session_id = "test_clear"
        user_id = "test_user"

        # 创建会话
        context_manager.get_or_create_session(session_id, user_id)

        # 清除
        context_manager.clear_session(session_id)

        # 应该不存在
        assert context_manager.get_session_history(session_id) is not None
        # 但应该是空的
        session = context_manager.get_session_history(session_id)
        assert session.turn_count == 0

    def test_multiple_sessions(self, context_manager: "ContextManager"):
        """测试多会话管理。"""
        sessions = ["session_1", "session_2", "session_3"]
        user_id = "test_user"

        for sid in sessions:
            session = context_manager.get_or_create_session(sid, user_id)
            session.add_turn(
                query=f"Query for {sid}",
                skill_ids=["rujia-perspective"],
                features=FeatureVector(
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
            )
            context_manager.update_session(session)

        # 验证每个会话独立
        for sid in sessions:
            session = context_manager.get_session_history(sid)
            assert session is not None
            assert sid in session.query_history[0]


# ============================================================================
# Context Aggregator Tests
# ============================================================================

class TestContextAggregator:
    """测试上下文信号聚合。"""

    def test_aggregate_skill_preference(self, context_manager: "ContextManager"):
        """测试技能偏好信号聚合。"""
        user_id = "test_agg_pref"
        skill_id = "rujia-perspective"

        # 设置偏好
        context_manager.set_preferred_skills(user_id, [skill_id])

        # 获取上下文
        context = context_manager.get_context_for_scorer(user_id, "test_session")

        assert skill_id in context["preferred_skills"]

    def test_aggregate_domain_preference(self, context_manager: "ContextManager"):
        """测试领域偏好信号聚合。"""
        user_id = "test_agg_domain"

        profile = context_manager.get_user_profile(user_id)
        profile.preferred_domains = ["ethics", "governance"]
        context_manager.update_user_profile(profile)

        context = context_manager.get_context_for_scorer(user_id, "test_session")

        assert "ethics" in context["preferred_domains"]

    def test_aggregate_recent_success(self, context_manager: "ContextManager"):
        """测试近期成功率聚合。"""
        user_id = "test_agg_success"

        # 多次成功使用
        for _ in range(10):
            context_manager.increment_skill_usage(user_id, "rujia-perspective", success=True)

        context = context_manager.get_context_for_scorer(user_id, "test_session")

        # 检查成功率
        rates = context.get("skill_success_rates", {})
        assert "rujia-perspective" in rates

    def test_session_context_for_scorer(self, context_manager: "ContextManager"):
        """测试为 scorer 准备的上下文。"""
        user_id = "test_scorer_context"
        session_id = "test_scorer_session"

        # 准备上下文
        context = context_manager.get_context_for_scorer(user_id, session_id)

        # 验证所有必要字段
        assert "user_id" in context
        assert "session_id" in context
        assert "preferred_skills" in context
        assert "avoided_skills" in context
        assert "skill_weights" in context
        assert "recent_skills" in context
        assert "turn_count" in context


# ============================================================================
# Context Persistence Tests
# ============================================================================

class TestContextPersistence:
    """测试上下文持久化。"""

    def test_profile_save_and_load(self, context_manager: "ContextManager", tmp_path):
        """测试画像保存和加载。"""
        context_manager.storage_path = tmp_path

        user_id = "test_save_load"
        profile = context_manager.get_user_profile(user_id)

        # 修改并保存
        profile.preferred_skills = ["rujia-perspective", "fajia-perspective"]
        profile.skill_weights = {"rujia-perspective": 0.9, "fajia-perspective": 0.7}
        profile.total_queries = 100
        context_manager.update_user_profile(profile)

        # 重新创建 context manager（模拟重启）
        new_manager = context_manager.__class__(context_manager.config, str(tmp_path))

        # 加载
        loaded = new_manager.get_user_profile(user_id)

        assert loaded.preferred_skills == ["rujia-perspective", "fajia-perspective"]
        assert loaded.skill_weights == {"rujia-perspective": 0.9, "fajia-perspective": 0.7}
        assert loaded.total_queries == 100

    def test_corrupted_profile_handling(self, context_manager: "ContextManager", tmp_path):
        """测试损坏的画像文件处理。"""
        context_manager.storage_path = tmp_path

        # 写入损坏的 JSON
        profile_path = tmp_path / "profiles"
        profile_path.mkdir(exist_ok=True)
        corrupted_file = profile_path / "corrupted_user.json"
        corrupted_file.write_text("{ invalid json }")

        # 应该返回默认画像
        profile = context_manager.get_user_profile("corrupted_user")

        assert profile.user_id == "corrupted_user"
        assert profile.preferred_skills == []


# ============================================================================
# Skill Co-occurrence Tests
# ============================================================================

class TestSkillCooccurrence:
    """测试技能共现分析。"""

    def test_cooccurrence_matrix(self, context_manager: "ContextManager"):
        """测试共现矩阵生成。"""
        user_id = "test_cooccur"

        # 使用多个技能组合
        combinations = [
            ["rujia-perspective", "fajia-perspective"],
            ["rujia-perspective", "daojia-perspective"],
            ["rujia-perspective", "fajia-perspective"],
        ]

        session = context_manager.get_or_create_session("cooccur_session", user_id)

        for skills in combinations:
            session.add_turn(
                query="问题",
                skill_ids=skills,
                features=FeatureVector(
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
            )
            context_manager.update_session(session)

        # 获取共现矩阵
        matrix = context_manager.get_skill_cooccurrence_matrix(user_id)

        assert isinstance(matrix, dict)


# ============================================================================
# Context Statistics Tests
# ============================================================================

class TestContextStatistics:
    """测试上下文统计功能。"""

    def test_total_queries_tracking(self, context_manager: "ContextManager"):
        """测试总查询数追踪。"""
        user_id = "test_total_queries"

        initial_profile = context_manager.get_user_profile(user_id)
        initial_count = initial_profile.total_queries

        # 增加使用
        context_manager.increment_skill_usage(user_id, "rujia-perspective", success=True)

        updated_profile = context_manager.get_user_profile(user_id)
        assert updated_profile.total_queries == initial_count + 1

    def test_total_sessions_tracking(self, context_manager: "ContextManager"):
        """测试总会话数追踪。"""
        user_id = "test_total_sessions"

        # 创建多个会话
        for i in range(3):
            context_manager.get_or_create_session(f"session_{i}", user_id)

        profile = context_manager.get_user_profile(user_id)
        assert profile.total_sessions >= 1

    def test_last_active_update(self, context_manager: "ContextManager"):
        """测试最后活跃时间更新。"""
        user_id = "test_last_active"

        profile1 = context_manager.get_user_profile(user_id)
        time1 = profile1.last_active

        # 短暂等待后进行操作
        import time
        time.sleep(0.01)

        context_manager.increment_skill_usage(user_id, "rujia-perspective", success=True)

        profile2 = context_manager.get_user_profile(user_id)

        # 时间应该更新或保持
        assert profile2.last_active >= time1

    def test_session_context_retrieval(self, context_manager: "ContextManager"):
        """测试会话上下文检索。"""
        session_id = "test_context_retrieval"
        user_id = "test_user"

        session = context_manager.get_or_create_session(session_id, user_id)

        # 添加数据
        for i in range(3):
            session.add_turn(
                query=f"Query {i}",
                skill_ids=[f"skill-{i}-perspective"],
                features=FeatureVector(
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
            )
            context_manager.update_session(session)

        # 获取上下文
        context = context_manager.get_session_context(session_id)

        assert "query_history" in context
        assert "skill_history" in context
        assert "turn_count" in context
        assert context["turn_count"] == 3
