"""
DialecticEngine - Feedback Learning Engine
==========================================
负责收集和处理用户反馈，支持动态调整skill权重。

Feedback Types:
1. Explicit Feedback - 用户明确评价（点赞/点踩/评分）
2. Implicit Feedback - 系统推断的行为反馈
3. Correction - 用户主动纠正router的决策

Learning Mechanism:
- 简单的加权移动平均
- 可扩展为future RLHF (Reinforcement Learning from Human Feedback)

Design Principles:
- 非侵入式：用户无感知
- 可配置的学习率
- 支持回滚和历史追踪
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .types import (
    FeedbackType,
    FeedbackRecord,
    SkillScore,
    RouterConfig,
    TraceStep,
)
from .context import ContextManager


# ============================================================================
# FEEDBACK PROCESSOR
# ============================================================================


class FeedbackProcessor:
    """Processes raw feedback into usable signals."""

    def __init__(self, config: Optional[RouterConfig] = None):
        self.config = config or RouterConfig()

    def process_implicit_feedback(
        self,
        decision_id: str,
        user_response: str,
        response_time: float,
    ) -> Optional[FeedbackRecord]:
        """Process implicit feedback from user behavior.

        隐式反馈推断逻辑：
        - 用户快速跳过 -> 可能不满意（需验证）
        - 用户追问/深入 -> 满意，希望深入
        - 用户要求换视角 -> 不满意当前选择
        - 用户接受并结束 -> 满意

        Args:
            decision_id: Original routing decision ID
            user_response: User's response text
            response_time: Time user spent before responding (seconds)

        Returns:
            FeedbackRecord or None if no clear signal
        """
        response_lower = user_response.lower()

        # 检测显式纠正信号
        correction_signals = [
            "换一个", "不用这个", "换视角",
            "错了", "不对", "不好", "不是这个",
            "wrong", "not this", "change", "different",
        ]

        if any(signal in response_lower for signal in correction_signals):
            return FeedbackRecord(
                decision_id=decision_id,
                user_id="",
                session_id="",
                skill_id="",
                feedback_type=FeedbackType.CORRECTION,
                is_positive=False,
                metadata={"response_length": len(user_response)},
            )

        # 检测接受信号
        acceptance_signals = [
            "好的", "可以", "谢谢", "明白了",
            "ok", "thanks", "great", "perfect",
        ]

        if any(signal in response_lower for signal in acceptance_signals):
            # 检查是否有深入追问
            follow_up = any(signal in response_lower for signal in [
                "然后", "所以", "还有", "further", "more", "also"
            ])

            return FeedbackRecord(
                decision_id=decision_id,
                user_id="",
                session_id="",
                skill_id="",
                feedback_type=FeedbackType.ACCEPTANCE,
                is_positive=True,
                score=4.0 if follow_up else 5.0,
                metadata={
                    "is_follow_up": follow_up,
                    "response_time": response_time,
                },
            )

        # 无明确信号
        return None

    def process_explicit_rating(
        self,
        rating: float,
        decision_id: str,
        user_id: str,
        session_id: str,
        skill_id: str,
        comment: Optional[str] = None,
    ) -> FeedbackRecord:
        """Process explicit user rating.

        Args:
            rating: User rating [1.0, 5.0]
            decision_id: Original routing decision ID
            user_id: User identifier
            session_id: Session identifier
            skill_id: Skill that was selected
            comment: Optional user comment

        Returns:
            FeedbackRecord
        """
        is_positive = rating >= 3.5

        return FeedbackRecord(
            decision_id=decision_id,
            user_id=user_id,
            session_id=session_id,
            skill_id=skill_id,
            feedback_type=FeedbackType.EXPLICIT,
            score=rating,
            comment=comment,
            is_positive=is_positive,
        )

    def infer_skill_feedback(
        self,
        feedback: FeedbackRecord,
        skill_ids: list[str],
    ) -> list[tuple[str, float]]:
        """Infer feedback for individual skills from decision feedback.

        当用户对整个决策给出反馈时，需要将其分配给各个skill。

        Args:
            feedback: The feedback record
            skill_ids: Skills involved in the decision

        Returns:
            List of (skill_id, feedback_score) tuples
        """
        if not feedback.score:
            return []

        base_score = feedback.score / 5.0  # 归一化到 [0, 1]

        # 如果是修正反馈，降低所有skill的分数
        if feedback.feedback_type == FeedbackType.CORRECTION:
            return [(sid, base_score * 0.3) for sid in skill_ids]

        # 如果是接受反馈，给予正向反馈
        if feedback.feedback_type == FeedbackType.ACCEPTANCE:
            return [(sid, base_score) for sid in skill_ids]

        # 默认：均匀分配
        return [(sid, base_score) for sid in skill_ids]


# ============================================================================
# WEIGHT UPDATER
# ============================================================================


class WeightUpdater:
    """Updates skill weights based on feedback.

    Learning Algorithm:
    当前使用简单的指数加权移动平均 (EWMA)。

    weight_new = weight_old + learning_rate * (feedback - baseline)

    未来可以扩展为：
    - A/B testing support
    - Bandit algorithms (Thompson Sampling, UCB)
    - RLHF with reward model
    """

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        context_manager: Optional[ContextManager] = None,
    ):
        self.config = config or RouterConfig()
        self.context_manager = context_manager or ContextManager(config=self.config)

        # 追踪每个user-skill对的反馈历史
        self._feedback_history: dict[str, list[FeedbackRecord]] = defaultdict(list)

    def update_weights(
        self,
        user_id: str,
        skill_feedback_pairs: list[tuple[str, float]],
    ) -> dict[str, float]:
        """Update skill weights based on feedback.

        Args:
            user_id: User identifier
            skill_feedback_pairs: List of (skill_id, feedback_score) tuples

        Returns:
            Updated weights dict
        """
        updated_weights = {}
        learning_rate = self.config.learning_rate
        decay_factor = self.config.decay_factor

        for skill_id, feedback_score in skill_feedback_pairs:
            # 获取当前权重
            current_weight = self.context_manager.get_skill_weight(user_id, skill_id)

            # 计算反馈与baseline的差
            baseline = 0.5  # 中性基准
            delta = feedback_score - baseline

            # 指数加权更新
            # w_new = w_old + lr * delta
            new_weight = current_weight + learning_rate * delta

            # 应用衰减（使极端反馈逐渐回归）
            new_weight = decay_factor * new_weight + (1 - decay_factor) * 0.5

            # 限制在 [0.1, 1.0]
            new_weight = max(0.1, min(1.0, new_weight))

            updated_weights[skill_id] = new_weight

        return updated_weights

    def should_update(self, user_id: str, skill_id: str) -> bool:
        """Check if enough feedback has been collected to update.

        Args:
            user_id: User identifier
            skill_id: Skill identifier

        Returns:
            True if should update weights
        """
        history = self._feedback_history.get(f"{user_id}:{skill_id}", [])
        return len(history) >= self.config.min_feedback_count

    def record_feedback(self, feedback: FeedbackRecord) -> None:
        """Record feedback for future analysis."""
        key = f"{feedback.user_id}:{feedback.skill_id}"
        self._feedback_history[key].append(feedback)

        # 限制历史长度
        if len(self._feedback_history[key]) > 100:
            self._feedback_history[key] = self._feedback_history[key][-100:]

    def get_feedback_stats(
        self,
        user_id: str,
        skill_id: str,
    ) -> dict[str, Any]:
        """Get feedback statistics for a user-skill pair."""
        history = self._feedback_history.get(f"{user_id}:{skill_id}", [])

        if not history:
            return {
                "count": 0,
                "mean_score": 0.5,
                "positive_ratio": 0.5,
            }

        scores = [f.score for f in history if f.score is not None]
        positive = sum(1 for f in history if f.is_positive)

        return {
            "count": len(history),
            "mean_score": sum(scores) / len(scores) if scores else 0.5,
            "positive_ratio": positive / len(history),
        }


# ============================================================================
# FEEDBACK ENGINE
# ============================================================================


class FeedbackEngine:
    """Main feedback engine coordinating all components.

    Provides unified interface for:
    - Receiving feedback
    - Updating weights
    - Analyzing feedback patterns
    """

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        context_manager: Optional[ContextManager] = None,
    ):
        self.config = config or RouterConfig()
        self.context_manager = context_manager or ContextManager(config=self.config)
        self.processor = FeedbackProcessor(config)
        self.updater = WeightUpdater(config, self.context_manager)

        # 反馈存储（可选持久化）
        self.storage_path: Optional[Path] = None
        self._feedback_records: list[FeedbackRecord] = []

    def receive_explicit_feedback(
        self,
        rating: float,
        decision_id: str,
        user_id: str,
        session_id: str,
        skill_ids: list[str],
        comment: Optional[str] = None,
    ) -> dict[str, float]:
        """Receive and process explicit feedback.

        Args:
            rating: User rating [1.0, 5.0]
            decision_id: Original routing decision ID
            user_id: User identifier
            session_id: Session identifier
            skill_ids: Skills involved in the decision
            comment: Optional user comment

        Returns:
            Updated weights dict
        """
        # 处理显式反馈
        feedback = self.processor.process_explicit_rating(
            rating=rating,
            decision_id=decision_id,
            user_id=user_id,
            session_id=session_id,
            skill_id=skill_ids[0] if skill_ids else "",
            comment=comment,
        )

        # 推断各skill的反馈
        skill_feedback = self.processor.infer_skill_feedback(feedback, skill_ids)

        # 更新权重
        updated_weights = self.updater.update_weights(user_id, skill_feedback)

        # 应用权重更新到context manager
        profile = self.context_manager.get_user_profile(user_id)
        for skill_id, weight in updated_weights.items():
            profile.skill_weights[skill_id] = weight
        self.context_manager.update_user_profile(profile)

        # 更新使用统计
        is_success = rating >= 3.5
        for skill_id in skill_ids:
            self.context_manager.increment_skill_usage(
                user_id=user_id,
                skill_id=skill_id,
                success=is_success,
            )

        # 记录反馈
        self.updater.record_feedback(feedback)
        self._feedback_records.append(feedback)

        return updated_weights

    def receive_implicit_feedback(
        self,
        decision_id: str,
        user_id: str,
        session_id: str,
        skill_ids: list[str],
        user_response: str,
        response_time: float = 5.0,
    ) -> Optional[dict[str, float]]:
        """Receive and process implicit feedback.

        Args:
            decision_id: Original routing decision ID
            user_id: User identifier
            session_id: Session identifier
            skill_ids: Skills involved in the decision
            user_response: User's response text
            response_time: Time user spent before responding

        Returns:
            Updated weights dict if clear signal, None otherwise
        """
        feedback = self.processor.process_implicit_feedback(
            decision_id=decision_id,
            user_response=user_response,
            response_time=response_time,
        )

        if feedback is None:
            return None

        # 填充用户信息
        feedback.user_id = user_id
        feedback.session_id = session_id

        # 推断各skill的反馈
        skill_feedback = self.processor.infer_skill_feedback(feedback, skill_ids)

        # 检查是否应该更新（需要足够的历史数据）
        for skill_id, _ in skill_feedback:
            if not self.updater.should_update(user_id, skill_id):
                self.updater.record_feedback(feedback)
                return None

        # 更新权重
        updated_weights = self.updater.update_weights(user_id, skill_feedback)

        # 应用权重更新
        profile = self.context_manager.get_user_profile(user_id)
        for skill_id, weight in updated_weights.items():
            profile.skill_weights[skill_id] = weight
        self.context_manager.update_user_profile(profile)

        # 更新使用统计
        for skill_id in skill_ids:
            self.context_manager.increment_skill_usage(
                user_id=user_id,
                skill_id=skill_id,
                success=feedback.is_positive,
            )

        # 记录反馈
        self.updater.record_feedback(feedback)
        self._feedback_records.append(feedback)

        return updated_weights

    def receive_correction(
        self,
        decision_id: str,
        user_id: str,
        session_id: str,
        correct_skill_ids: list[str],
    ) -> None:
        """Receive user correction (user explicitly tells us what was wrong).

        Args:
            decision_id: Original routing decision ID
            user_id: User identifier
            session_id: Session identifier
            correct_skill_ids: Skills user thinks should have been selected
        """
        # 创建修正反馈
        feedback = FeedbackRecord(
            decision_id=decision_id,
            user_id=user_id,
            session_id=session_id,
            skill_id=",".join(correct_skill_ids),
            feedback_type=FeedbackType.CORRECTION,
            is_positive=False,
            comment=f"User corrected to: {correct_skill_ids}",
        )

        # 获取之前选择的skill
        # 这里需要从之前的决策中获取
        # 简化处理：假设skill_ids包含之前的选择
        wrong_skills = []  # 应该从历史中获取

        # 降低错误skill的权重
        wrong_feedback = [(sid, 0.1) for sid in wrong_skills]
        self.updater.update_weights(user_id, wrong_feedback)

        # 提高正确skill的权重
        correct_feedback = [(sid, 0.9) for sid in correct_skill_ids]
        self.updater.update_weights(user_id, correct_feedback)

        # 更新使用统计
        for skill_id in wrong_skills:
            self.context_manager.increment_skill_usage(
                user_id=user_id,
                skill_id=skill_id,
                success=False,
            )

        for skill_id in correct_skill_ids:
            self.context_manager.increment_skill_usage(
                user_id=user_id,
                skill_id=skill_id,
                success=True,
            )

        self.updater.record_feedback(feedback)
        self._feedback_records.append(feedback)

    def get_skill_stats(self, user_id: str) -> dict[str, dict[str, Any]]:
        """Get feedback statistics for all skills used by a user."""
        profile = self.context_manager.get_user_profile(user_id)
        stats = {}

        for skill_id in profile.skill_total_counts.keys():
            stats[skill_id] = self.updater.get_feedback_stats(user_id, skill_id)
            stats[skill_id]["success_rate"] = profile.skill_success_rate(skill_id)
            stats[skill_id]["total_uses"] = profile.skill_total_counts.get(skill_id, 0)
            stats[skill_id]["current_weight"] = profile.skill_weights.get(skill_id, 0.5)

        return stats

    def get_feedback_insights(self, user_id: str) -> dict[str, Any]:
        """Get aggregated feedback insights.

        Returns:
            Dict with insights about user's skill preferences
        """
        stats = self.get_skill_stats(user_id)

        if not stats:
            return {
                "insight": "No feedback data yet.",
                "top_skills": [],
                "underperforming_skills": [],
            }

        # 找出表现最好和最差的skill
        sorted_stats = sorted(
            stats.items(),
            key=lambda x: x[1].get("success_rate", 0.5),
            reverse=True
        )

        top = [sid for sid, _ in sorted_stats[:3] if _["total_uses"] >= 3]
        bottom = [
            sid for sid, _ in sorted_stats[-3:]
            if _["total_uses"] >= 3 and _["success_rate"] < 0.4
        ]

        return {
            "insight": self._generate_insight(stats, top, bottom),
            "top_skills": top,
            "underperforming_skills": bottom,
            "total_feedback_count": len(self._feedback_records),
        }

    def _generate_insight(
        self,
        stats: dict[str, dict[str, Any]],
        top: list[str],
        bottom: list[str],
    ) -> str:
        """Generate natural language insight from stats."""
        if not top and not bottom:
            return "系统正在学习你的偏好，请继续提供反馈。"

        parts = []
        if top:
            parts.append(f"「{top[0]}」表现最好，适合处理你的问题。")
        if bottom:
            parts.append(f"「{bottom[0]}」可能不太适合你的场景。")

        return " ".join(parts)

    def create_trace_step(
        self,
        feedback_type: FeedbackType,
        updated_weights: Optional[dict[str, float]],
        duration_ms: float,
    ) -> TraceStep:
        """Create trace step for debugging."""
        return TraceStep(
            step_name="feedback_learning",
            step_order=5,
            input_summary={
                "feedback_type": feedback_type.value,
                "has_update": updated_weights is not None,
            },
            output_summary={
                "updated_skills": list(updated_weights.keys()) if updated_weights else [],
                "total_records": len(self._feedback_records),
            },
            duration_ms=duration_ms,
        )

    # -------------------------------------------------------------------------
    # PERSISTENCE
    # -------------------------------------------------------------------------

    def set_storage_path(self, path: str) -> None:
        """Set path for feedback persistence."""
        self.storage_path = Path(path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def save_feedback(self) -> None:
        """Save feedback records to disk."""
        if not self.storage_path:
            return

        path = self.storage_path / "feedback_records.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for record in self._feedback_records:
                f.write(json.dumps(record.__dict__, ensure_ascii=False) + "\n")

    def load_feedback(self) -> None:
        """Load feedback records from disk."""
        if not self.storage_path:
            return

        path = self.storage_path / "feedback_records.jsonl"
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    record = FeedbackRecord(**data)
                    self._feedback_records.append(record)


# ============================================================================
# FACTORY
# ============================================================================


def create_feedback_engine(
    config: Optional[RouterConfig] = None,
    context_manager: Optional[ContextManager] = None,
) -> FeedbackEngine:
    """Factory function to create configured feedback engine."""
    return FeedbackEngine(config=config, context_manager=context_manager)
