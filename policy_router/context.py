"""
DialecticEngine - Context State Management
==========================================
负责管理用户profile和session状态，提供上下文感知能力。

State Architecture:
- UserProfile: 长期用户偏好和学习状态
- SessionState: 当前会话状态
- ContextManager: 统一上下文管理器

Design Principles:
- 不可变性优先（ dataclass(frozen=True)）
- 增量更新
- 持久化支持（可选）
"""

from __future__ import annotations

import json
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .types import (
    UserProfile,
    SessionState,
    FeatureVector,
    RouterConfig,
)


# ============================================================================
# CONTEXT MANAGER
# ============================================================================


class ContextManager:
    """Manages user profiles and session states.

    提供统一的上下文访问接口，支持：
    - 用户画像查询
    - 会话状态管理
    - 历史数据持久化
    """

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        storage_path: Optional[str] = None,
    ):
        self.config = config or RouterConfig()
        self.storage_path = Path(storage_path) if storage_path else None

        # 内存中的状态缓存
        self._user_profiles: dict[str, UserProfile] = {}
        self._sessions: dict[str, SessionState] = {}

        # 初始化持久化存储
        if self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # USER PROFILE OPERATIONS
    # -------------------------------------------------------------------------

    def get_user_profile(self, user_id: str) -> UserProfile:
        """Get or create user profile.

        如果用户不存在，创建默认profile。
        """
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = self._load_profile(user_id)
        return self._user_profiles[user_id]

    def update_user_profile(self, profile: UserProfile) -> None:
        """Update user profile in memory and persist."""
        self._user_profiles[profile.user_id] = profile
        self._save_profile(profile)

    def get_skill_success_rate(self, user_id: str, skill_id: str) -> float:
        """Get user's success rate for a specific skill."""
        profile = self.get_user_profile(user_id)
        return profile.skill_success_rate(skill_id)

    def get_skill_weight(self, user_id: str, skill_id: str) -> float:
        """Get user's dynamic weight for a specific skill."""
        profile = self.get_user_profile(user_id)
        return profile.skill_weights.get(skill_id, 1.0)

    def increment_skill_usage(
        self,
        user_id: str,
        skill_id: str,
        success: bool,
    ) -> None:
        """Increment skill usage count and update success rate."""
        profile = self.get_user_profile(user_id)

        # 更新总使用次数
        profile.skill_total_counts[skill_id] = (
            profile.skill_total_counts.get(skill_id, 0) + 1
        )

        # 更新成功次数
        if success:
            profile.skill_success_counts[skill_id] = (
                profile.skill_success_counts.get(skill_id, 0) + 1
            )

        # 更新动态权重（基于成功率）
        rate = profile.skill_success_rate(skill_id)
        profile.skill_weights[skill_id] = 0.5 + (rate * 0.5)  # 映射到 [0.5, 1.0]

        # 更新统计
        profile.total_queries += 1
        profile.last_active = datetime.now(timezone.utc)

        self.update_user_profile(profile)

    def set_preferred_skills(self, user_id: str, skill_ids: list[str]) -> None:
        """Set user's preferred skills."""
        profile = self.get_user_profile(user_id)
        profile.preferred_skills = skill_ids
        self.update_user_profile(profile)

    def set_avoided_skills(self, user_id: str, skill_ids: list[str]) -> None:
        """Set user's avoided skills."""
        profile = self.get_user_profile(user_id)
        profile.avoided_skills = skill_ids
        self.update_user_profile(profile)

    # -------------------------------------------------------------------------
    # SESSION OPERATIONS
    # -------------------------------------------------------------------------

    def get_or_create_session(
        self,
        session_id: str,
        user_id: str,
    ) -> SessionState:
        """Get existing session or create new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(
                session_id=session_id,
                user_id=user_id,
            )
        return self._sessions[session_id]

    def update_session(self, session: SessionState) -> None:
        """Update session state in memory."""
        self._sessions[session.session_id] = session

    def add_turn_to_session(
        self,
        session_id: str,
        query: str,
        skill_ids: list[str],
        features: FeatureVector,
    ) -> SessionState:
        """Add a conversation turn to session."""
        session = self.get_or_create_session(session.session_id, session.user_id)
        session.add_turn(query, skill_ids, features)
        self.update_session(session)
        return session

    def get_session_history(self, session_id: str) -> SessionState:
        """Get session with full history."""
        return self._sessions.get(
            session_id,
            SessionState(session_id=session_id, user_id="default")
        )

    def get_recent_skills(
        self,
        session_id: str,
        max_count: int = 5,
    ) -> list[str]:
        """Get recently used skills in session."""
        session = self.get_session_history(session_id)
        return session.last_skills_used[-max_count:]

    def get_session_context(self, session_id: str) -> dict[str, Any]:
        """Get session context for feature extraction."""
        session = self.get_session_history(session_id)
        return {
            "query_history": session.query_history[-10:],
            "skill_history": session.skill_history[-20:],
            "turn_count": session.turn_count,
            "last_skills_used": session.last_skills_used,
        }

    # -------------------------------------------------------------------------
    # CONTEXT QUERY HELPERS
    # -------------------------------------------------------------------------

    def get_context_for_scorer(
        self,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Get unified context dict for scoring.

        整合用户画像和会话状态，供scorer使用。
        """
        profile = self.get_user_profile(user_id)
        session = self.get_session_history(session_id)

        return {
            "user_id": user_id,
            "session_id": session_id,
            # 用户偏好
            "preferred_skills": profile.preferred_skills,
            "avoided_skills": profile.avoided_skills,
            "preferred_domains": profile.preferred_domains,
            "skill_weights": profile.skill_weights,
            "skill_success_rates": {
                sid: profile.skill_success_rate(sid)
                for sid in set(profile.skill_total_counts.keys())
            },
            # 会话状态
            "recent_skills": session.last_skills_used[-10:],
            "recent_intents": [
                f.intent.value
                for f in session.feature_history[-5:]
            ],
            "query_history": session.query_history[-10:],
            "turn_count": session.turn_count,
            # 统计
            "total_queries": profile.total_queries,
            "total_sessions": profile.total_sessions,
        }

    def get_skill_cooccurrence_matrix(
        self,
        user_id: str,
    ) -> dict[tuple[str, str], int]:
        """Get co-occurrence matrix of skills.

        用于分析用户经常同时使用哪些skill组合。
        """
        profile = self.get_user_profile(user_id)

        # 简化实现：返回空矩阵
        # 实际实现需要追踪skill配对
        return {}

    # -------------------------------------------------------------------------
    # PERSISTENCE
    # -------------------------------------------------------------------------

    def _get_profile_path(self, user_id: str) -> Path:
        """Get file path for user profile."""
        if not self.storage_path:
            raise ValueError("Storage path not configured")
        return self.storage_path / "profiles" / f"{user_id}.json"

    def _load_profile(self, user_id: str) -> UserProfile:
        """Load user profile from disk.

        如果没有配置storage_path或文件不存在，返回默认profile。
        """
        # 如果没有配置storage_path，返回默认profile
        if not self.storage_path:
            return UserProfile(user_id=user_id)

        path = self._get_profile_path(user_id)

        if not path.exists():
            return UserProfile(user_id=user_id)

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return UserProfile(
                user_id=data["user_id"],
                preferred_skills=data.get("preferred_skills", []),
                avoided_skills=data.get("avoided_skills", []),
                preferred_domains=data.get("preferred_domains", []),
                skill_weights=data.get("skill_weights", {}),
                skill_success_counts=data.get("skill_success_counts", {}),
                skill_total_counts=data.get("skill_total_counts", {}),
                total_queries=data.get("total_queries", 0),
                total_sessions=data.get("total_sessions", 0),
            )
        except (json.JSONDecodeError, KeyError):
            return UserProfile(user_id=user_id)

    def _save_profile(self, profile: UserProfile) -> None:
        """Save user profile to disk."""
        if not self.storage_path:
            return

        path = self._get_profile_path(profile.user_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(profile.to_dict(), f, ensure_ascii=False, indent=2)

    def clear_session(self, session_id: str) -> None:
        """Clear session from memory."""
        if session_id in self._sessions:
            del self._sessions[session_id]

    def clear_all_sessions(self) -> None:
        """Clear all sessions from memory."""
        self._sessions.clear()


# ============================================================================
# CONTEXT AGGREGATOR
# ============================================================================


class ContextAggregator:
    """Aggregates contextual signals for scoring.

    将多种上下文信号聚合为统一的上下文向量。
    """

    def __init__(self):
        self.signal_weights = {
            "skill_preference": 0.3,
            "domain_preference": 0.2,
            "session_coherence": 0.25,
            "recent_success": 0.25,
        }

    def aggregate_context_score(
        self,
        skill_domains: frozenset,
        skill_id: str,
        context: dict[str, Any],
    ) -> float:
        """Aggregate multiple context signals into single score.

        Args:
            skill_domains: Domains the skill belongs to
            skill_id: Target skill ID
            context: Context dict from ContextManager

        Returns:
            Aggregated context score [0.0, 1.0]
        """
        scores: list[float] = []

        # 1. Skill preference signal
        preferred = context.get("preferred_skills", [])
        if skill_id in preferred:
            scores.append(1.0)
        elif skill_id in context.get("avoided_skills", []):
            scores.append(0.0)
        else:
            scores.append(0.5)

        # 2. Domain preference signal
        preferred_domains = set(context.get("preferred_domains", []))
        if preferred_domains and skill_domains:
            domain_overlap = len(
                preferred_domains.intersection(
                    {d.name.lower() for d in skill_domains}
                )
            )
            domain_score = min(1.0, domain_overlap / max(1, len(skill_domains)))
            scores.append(domain_score)
        else:
            scores.append(0.5)

        # 3. Session coherence signal
        recent_skills = context.get("recent_skills", [])
        if skill_id in recent_skills[-3:]:
            # 刚刚用过，降低分数避免重复
            scores.append(0.3)
        elif recent_skills and any(
            self._skills_related(skill_id, other)
            for other in recent_skills[-3:]
        ):
            # 相关skill，轻微降低
            scores.append(0.6)
        else:
            scores.append(0.7)

        # 4. Recent success signal
        success_rates = context.get("skill_success_rates", {})
        rate = success_rates.get(skill_id, 0.5)
        scores.append(rate)

        # 加权平均
        weighted_sum = sum(
            score * weight
            for score, (_, weight) in zip(scores, self.signal_weights.items())
        )
        total_weight = sum(self.signal_weights.values())

        return weighted_sum / total_weight

    def _skills_related(self, skill_a: str, skill_b: str) -> bool:
        """Check if two skills are related (simplified)."""
        # 简化实现：通过命名约定判断
        # 实际应该从skill元数据中获取关系信息
        related_pairs = {
            ("rujia-perspective", "yijia-perspective"),
            ("fajia-perspective", "bingjia-perspective"),
            ("daojia-perspective", "xuanxue-perspective"),
        }

        pair = tuple(sorted([skill_a, skill_b]))
        return pair in related_pairs


# ============================================================================
# FACTORY
# ============================================================================


def create_context_manager(
    config: Optional[RouterConfig] = None,
    storage_path: Optional[str] = None,
) -> ContextManager:
    """Factory function to create configured context manager."""
    return ContextManager(config=config, storage_path=storage_path)
