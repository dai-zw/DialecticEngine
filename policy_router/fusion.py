"""
DialecticEngine - Multi-Skill Decision Fusion Engine
====================================================
负责将多个skill的打分融合为最终决策，包括：
1. Top-K Selection - 选择最优的K个skill
2. Mode Decision - 确定执行模式（single/multi/debate）
3. Execution Plan - 生成执行计划
4. Reasoning Generation - 生成决策理由

Design:
- 可配置的阈值和参数
- 支持多种fusion策略
- 输出完整的决策trace
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .types import (
    SkillScore,
    ExecutionMode,
    RoutingDecision,
    FeatureVector,
    RouterConfig,
    TraceStep,
)


# ============================================================================
# FUSION STRATEGIES
# ============================================================================


class FusionStrategy:
    """Base class for fusion strategies."""

    def select(
        self,
        scores: dict[str, SkillScore],
        config: RouterConfig,
    ) -> tuple[list[str], list[SkillScore]]:
        """Select skills based on strategy.

        Returns:
            Tuple of (selected_skill_ids, selected_scores)
        """
        raise NotImplementedError


class TopKFusion(FusionStrategy):
    """Select top-K highest scoring skills."""

    def select(
        self,
        scores: dict[str, SkillScore],
        config: RouterConfig,
    ) -> tuple[list[str], list[SkillScore]]:
        # 按分数排序
        sorted_scores = sorted(
            scores.items(),
            key=lambda x: x[1].total_score,
            reverse=True
        )

        # 选择top-k
        top_k = min(config.top_k, len(sorted_scores))
        selected = sorted_scores[:top_k]

        return [sid for sid, _ in selected], [s for _, s in selected]


class ThresholdFusion(FusionStrategy):
    """Select all skills above minimum threshold."""

    def select(
        self,
        scores: dict[str, SkillScore],
        config: RouterConfig,
    ) -> tuple[list[str], list[SkillScore]]:
        selected = [
            (sid, s) for sid, s in scores.items()
            if s.total_score >= config.min_score_threshold
        ]

        # 也需要top-k限制
        selected.sort(key=lambda x: x[1].total_score, reverse=True)
        selected = selected[:config.top_k]

        return [sid for sid, _ in selected], [s for _, s in selected]


class DiversityFusion(FusionStrategy):
    """Select skills with diversity consideration.

    避免选择过于相似的skill，优先选择来自不同领域的skill。
    """

    def select(
        self,
        scores: dict[str, SkillScore],
        config: RouterConfig,
    ) -> tuple[list[str], list[SkillScore]]:
        sorted_scores = sorted(
            scores.items(),
            key=lambda x: x[1].total_score,
            reverse=True
        )

        selected_ids: list[str] = []
        selected_scores: list[SkillScore] = []
        selected_domains: set[str] = set()

        for sid, score in sorted_scores:
            if len(selected_ids) >= config.top_k:
                break

            # 检查是否与已选skill领域重复
            breakdown = score.breakdown
            skill_domains = breakdown.get("skill_slug", "")

            # 简单策略：每个slug类型只选一个
            if skill_domains not in selected_domains or len(selected_ids) < 2:
                selected_ids.append(sid)
                selected_scores.append(score)
                selected_domains.add(skill_domains)

        return selected_ids, selected_scores


# ============================================================================
# MODE DECIDER
# ============================================================================


class ModeDecider:
    """Decides execution mode based on score distribution."""

    def decide(
        self,
        selected_scores: list[SkillScore],
        features: FeatureVector,
        config: RouterConfig,
    ) -> ExecutionMode:
        """Decide execution mode.

        Decision Logic:
        1. 如果top-1分数远高于top-2，选择SINGLE
        2. 如果top-2分数接近top-1，考虑MULTI
        3. 如果top-2分数非常接近top-1，且存在对立，考虑DEBATE
        4. 如果query复杂或歧义度高，考虑MULTI
        """
        if len(selected_scores) < 2:
            return ExecutionMode.SINGLE

        top1 = selected_scores[0].total_score
        top2 = selected_scores[1].total_score

        # 计算分数差
        score_diff = top1 - top2

        # 如果分数差很大，选择SINGLE
        if score_diff > config.multi_skill_threshold:
            return ExecutionMode.SINGLE

        # 如果query复杂度高或歧义度高，考虑MULTI
        if features.complexity.value >= 3 or features.ambiguity > 0.5:
            # 检查是否适合debate
            if score_diff < config.debate_threshold:
                if self._should_debate(selected_scores):
                    return ExecutionMode.DEBATE
            return ExecutionMode.MULTI

        # 分数接近但不够debate阈值，选择MULTI
        if score_diff < config.multi_skill_threshold:
            return ExecutionMode.MULTI

        return ExecutionMode.SINGLE

    def _should_debate(self, scores: list[SkillScore]) -> bool:
        """Check if scores suggest a debate scenario.

        如果top-2的skill来自对立的学派，则适合debate。
        """
        if len(scores) < 2:
            return False

        # 定义对立关系
        opposing_pairs = [
            ("rujia-perspective", "fajia-perspective"),  # 儒家 vs 法家
            ("daojia-perspective", "fajia-perspective"),  # 道家 vs 法家
            ("rujia-perspective", "daojia-perspective"),  # 儒家 vs 道家
        ]

        top2_slugs = [
            scores[0].breakdown.get("skill_slug", ""),
            scores[1].breakdown.get("skill_slug", ""),
        ]

        # 检查是否是对立pair
        pair = tuple(sorted(top2_slugs))
        return pair in opposing_pairs


# ============================================================================
# EXECUTION PLAN GENERATOR
# ============================================================================


class ExecutionPlanGenerator:
    """Generates execution plan based on decision."""

    def generate(
        self,
        selected_skills: list[str],
        mode: ExecutionMode,
        skill_scores: dict[str, SkillScore],
        features: FeatureVector,
    ) -> tuple[list[dict[str, Any]], Optional[list[tuple[str, str]]]]:
        """Generate execution plan.

        Returns:
            Tuple of (execution_plan, debate_pairs)
        """
        plan: list[dict[str, Any]] = []
        debate_pairs: Optional[list[tuple[str, str]]] = None

        if mode == ExecutionMode.SINGLE:
            # 单skill执行
            skill_id = selected_skills[0]
            skill_score = skill_scores.get(skill_id)
            plan.append({
                "step": 1,
                "action": "invoke_skill",
                "skill_id": skill_id,
                "skill_name": skill_score.skill_name if skill_score else skill_id,
                "weight": 1.0,
                "prompt_additions": self._generate_prompt_additions(
                    skill_id, features
                ),
            })

        elif mode == ExecutionMode.MULTI:
            # 多skill融合
            total_weight = sum(
                skill_scores.get(sid, SkillScore(skill_id=sid, skill_name=sid)).total_score
                for sid in selected_skills
            )

            for i, skill_id in enumerate(selected_skills):
                skill_score = skill_scores.get(skill_id)
                score = skill_score.total_score if skill_score else 0.0
                weight = score / total_weight if total_weight > 0 else 1.0 / len(selected_skills)

                plan.append({
                    "step": i + 1,
                    "action": "invoke_skill",
                    "skill_id": skill_id,
                    "skill_name": skill_score.skill_name if skill_score else skill_id,
                    "weight": weight,
                    "aggregation_method": "weighted_average",
                    "prompt_additions": self._generate_prompt_additions(
                        skill_id, features
                    ),
                })

            # 添加融合步骤
            plan.append({
                "step": len(selected_skills) + 1,
                "action": "aggregate_responses",
                "method": "synthesis",
                "inputs": selected_skills,
            })

        elif mode == ExecutionMode.DEBATE:
            # 辩论模式
            debate_pairs = self._generate_debate_pairs(selected_skills)

            # 为每个skill生成论证步骤
            for i, (side_a, side_b) in enumerate(debate_pairs):
                skill_a = skill_scores.get(side_a)
                skill_b = skill_scores.get(side_b)

                plan.append({
                    "step": i * 2 + 1,
                    "action": "invoke_skill",
                    "skill_id": side_a,
                    "skill_name": skill_a.skill_name if skill_a else side_a,
                    "role": "prosecutor" if i % 2 == 0 else "defendant",
                    "prompt_additions": self._generate_prompt_additions(side_a, features),
                })

                plan.append({
                    "step": i * 2 + 2,
                    "action": "invoke_skill",
                    "skill_id": side_b,
                    "skill_name": skill_b.skill_name if skill_b else side_b,
                    "role": "defendant" if i % 2 == 0 else "prosecutor",
                    "prompt_additions": self._generate_prompt_additions(side_b, features),
                })

            # 添加裁判/综合步骤
            plan.append({
                "step": len(debate_pairs) * 2 + 1,
                "action": "synthesize_debate",
                "debate_pairs": debate_pairs,
                "method": "dialectical_synthesis",
            })

        return plan, debate_pairs

    def _generate_debate_pairs(
        self,
        skills: list[str],
    ) -> list[tuple[str, str]]:
        """Generate debate pairings from skills."""
        pairs: list[tuple[str, str]] = []

        # 简单策略：两两配对
        for i in range(0, len(skills) - 1, 2):
            pairs.append((skills[i], skills[i + 1]))

        return pairs

    def _generate_prompt_additions(
        self,
        skill_id: str,
        features: FeatureVector,
    ) -> dict[str, Any]:
        """Generate additional prompt instructions for skill."""
        additions: dict[str, Any] = {}

        # 基于query特征添加指引
        if features.has_ethical_dimension:
            additions["focus_area"] = "伦理分析"

        if features.has_organizational_dimension:
            additions["focus_area"] = "组织治理"

        if features.has_personal_dimension:
            additions["focus_area"] = "个人成长"

        # 基于情绪添加语气指引
        emotion_map = {
            "anxious": "语气平和舒缓",
            "angry": "语气温和化解",
            "sad": "语气温暖鼓励",
            "confused": "语气清晰引导",
        }

        if features.emotion.value in emotion_map:
            additions["tone_guide"] = emotion_map[features.emotion.value]

        return additions


# ============================================================================
# REASONING GENERATOR
# ============================================================================


class ReasoningGenerator:
    """Generates human-readable reasoning for decisions."""

    def generate(
        self,
        decision: RoutingDecision,
        features: FeatureVector,
    ) -> str:
        """Generate reasoning text."""
        parts = []

        # 执行模式说明
        if decision.execution_mode == ExecutionMode.SINGLE:
            parts.append(f"选择「{decision.selected_skills[0]}」作为唯一分析视角。")
        elif decision.execution_mode == ExecutionMode.MULTI:
            parts.append(f"综合{len(decision.selected_skills)}个视角进行多维分析：")
            for sid in decision.selected_skills:
                score = decision.skill_scores.get(sid)
                if score:
                    parts.append(f"  - 「{score.skill_name}」(权重{score.total_score:.2f})")
        elif decision.execution_mode == ExecutionMode.DEBATE:
            parts.append("通过对立视角的辩论来厘清问题：")
            if decision.debate_pairs:
                for pro, con in decision.debate_pairs:
                    parts.append(f"  - 「{pro}」 vs 「{con}」")

        # 决策依据
        parts.append(f"\n决策依据：{decision.reasoning}")

        # 置信度说明
        if decision.confidence > 0.8:
            parts.append("系统对该决策有较高置信度。")
        elif decision.confidence > 0.5:
            parts.append("系统对该决策有一定置信度，建议结合其他视角审视。")
        else:
            parts.append("系统对该决策置信度较低，建议谨慎参考。")

        return "\n".join(parts)

    def generate_explanation(
        self,
        decision: RoutingDecision,
        features: FeatureVector,
    ) -> str:
        """Generate user-facing explanation."""
        parts = []

        # 选择说明
        if len(decision.selected_skills) == 1:
            skill = decision.skill_scores.get(decision.selected_skills[0])
            if skill:
                parts.append(
                    f"我选择以「{skill.skill_name}」的视角来分析你的问题。"
                )
                parts.append(f"理由：{skill.explanation}")
        else:
            names = [
                decision.skill_scores.get(sid, decision.skill_scores.get(sid))
                for sid in decision.selected_skills
            ]
            names_str = "、".join([
                f"「{n.skill_name if n else sid}」"
                for n, sid in zip(names, decision.selected_skills)
            ])
            parts.append(f"我选择综合{names_str}等多个视角来分析。")

        # 复杂度提示
        if features.complexity.value >= 3:
            parts.append(
                "这个问题比较复杂，单一视角可能不够全面，"
                "所以我采用了多视角分析。"
            )

        return " ".join(parts)


# ============================================================================
# DECISION FUSION ENGINE
# ============================================================================


class DecisionFusionEngine:
    """Main fusion engine coordinating all components."""

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
    ):
        self.config = config or RouterConfig()
        self.mode_decider = ModeDecider()
        self.plan_generator = ExecutionPlanGenerator()
        self.reasoning_generator = ReasoningGenerator()

        # 选择fusion策略
        self.strategy: FusionStrategy
        strategy_name = getattr(self.config, 'fusion_strategy', 'topk')
        if strategy_name == 'threshold':
            self.strategy = ThresholdFusion()
        elif strategy_name == 'diversity':
            self.strategy = DiversityFusion()
        else:
            self.strategy = TopKFusion()

    def fuse(
        self,
        scores: dict[str, SkillScore],
        features: FeatureVector,
    ) -> RoutingDecision:
        """Fuse scores into final routing decision.

        Args:
            scores: All skill scores
            features: Extracted features

        Returns:
            RoutingDecision with selected skills and execution plan
        """
        start_time = time.time()

        # 1. Skill Selection
        selected_ids, selected_scores = self.strategy.select(scores, self.config)

        # 2. Mode Decision
        mode = self.mode_decider.decide(selected_scores, features, self.config)

        # 3. Execution Plan Generation
        plan, debate_pairs = self.plan_generator.generate(
            selected_ids, mode, scores, features
        )

        # 4. Reasoning Generation
        reasoning = self._generate_reasoning(selected_ids, selected_scores, scores, mode)

        # 5. Confidence Calculation
        confidence = self._calculate_confidence(selected_scores, mode)

        # 6. Explanation Generation
        explanation = self.reasoning_generator.generate_explanation(
            RoutingDecision(
                selected_skills=selected_ids,
                skill_scores=scores,
                execution_mode=mode,
                reasoning=reasoning,
                confidence=confidence,
                execution_plan=plan,
                debate_pairs=debate_pairs,
                explanation="",
                trace={},
            ),
            features
        )

        duration = (time.time() - start_time) * 1000

        return RoutingDecision(
            selected_skills=selected_ids,
            skill_scores=scores,
            execution_mode=mode,
            reasoning=reasoning,
            confidence=confidence,
            execution_plan=plan,
            debate_pairs=debate_pairs,
            explanation=explanation,
            trace={
                "selection_duration_ms": duration,
                "strategy": self.strategy.__class__.__name__,
                "mode_decision": mode.value,
            },
            query_preview="",
        )

    def _generate_reasoning(
        self,
        selected_ids: list[str],
        selected_scores: list[SkillScore],
        all_scores: dict[str, SkillScore],
        mode: ExecutionMode,
    ) -> str:
        """Generate detailed reasoning text."""
        parts = []

        # 选择依据
        if selected_scores:
            top_score = selected_scores[0]
            parts.append(
                f"「{top_score.skill_name}」综合得分最高({top_score.total_score:.3f})，"
                f"主要优势：{top_score.explanation}"
            )

            # 分数分解
            parts.append(
                f"分数分解：语义匹配{top_score.semantic_score:.2f}，"
                f"规则匹配{top_score.rule_bias_score:.2f}，"
                f"上下文匹配{top_score.context_score:.2f}，"
                f"历史反馈{top_score.feedback_score:.2f}"
            )

        # 模式选择依据
        if mode == ExecutionMode.SINGLE:
            if len(selected_scores) >= 2:
                diff = selected_scores[0].total_score - selected_scores[1].total_score
                parts.append(
                    f"与其他候选相比，差距为{diff:.3f}，"
                    f"优势明显，选择单一视角。"
                )
        elif mode == ExecutionMode.MULTI:
            parts.append(
                f"多个视角得分接近，采用多视角融合分析，"
                f"以获得更全面的视角。"
            )
        elif mode == ExecutionMode.DEBATE:
            parts.append(
                "候选视角存在张力（对立思想），"
                "采用辩论模式进行辩证分析。"
            )

        return "；".join(parts)

    def _calculate_confidence(
        self,
        selected_scores: list[SkillScore],
        mode: ExecutionMode,
    ) -> float:
        """Calculate decision confidence.
        
        置信度计算策略：
        1. SINGLE 模式：直接使用 top-1 分数
        2. MULTI 模式：计算 top-k 平均值，考虑多样性增益
        3. DEBATE 模式：基于分数接近度，但考虑对立价值的洞察价值
        """
        if not selected_scores:
            return 0.0

        if mode == ExecutionMode.SINGLE:
            # 单一选择，置信度基于 top-1 分数
            # 归一化调整：如果原始分数较低，映射到更合理的置信区间
            raw = selected_scores[0].total_score
            # 将 [0, 0.5] 区间映射到 [0.3, 0.7]，将 [0.5, 1.0] 映射到 [0.7, 1.0]
            if raw < 0.3:
                return 0.3  # 最低置信度
            elif raw < 0.5:
                return 0.3 + (raw - 0.3) * 2.0  # [0.3, 0.5] -> [0.3, 0.7]
            else:
                return 0.7 + (raw - 0.5) * 0.6  # [0.5, 1.0] -> [0.7, 1.0]

        # 多选模式：综合考虑分数和多样性
        top1 = selected_scores[0].total_score
        top2 = selected_scores[1].total_score if len(selected_scores) >= 2 else 0

        if mode == ExecutionMode.MULTI:
            # 多视角分析的优势：多个视角共同支撑，置信度提升
            scores = [s.total_score for s in selected_scores]
            avg_score = sum(scores) / len(scores)
            
            # 考虑多样性：如果 top1 和 top2 接近，说明问题复杂但分析全面
            if len(selected_scores) >= 2 and top2 > 0:
                gap = abs(top1 - top2) / max(top1, top2)
                # 差距小（<20%）说明问题需要多视角，置信度提升
                diversity_bonus = 0.1 if gap < 0.2 else 0
            else:
                diversity_bonus = 0

            # 多视角置信度 = 平均分数 + 多样性增益
            raw_confidence = avg_score + diversity_bonus
            return min(1.0, max(0.5, raw_confidence + 0.15))  # 基础提升

        if mode == ExecutionMode.DEBATE:
            # 辩论模式：虽然分数接近降低单一视角置信度
            # 但辩论本身提供了更高质量的洞察
            if len(selected_scores) >= 2 and top2 > 0:
                gap_ratio = top2 / top1
                # 分数接近 -> 适合辩论 -> 洞察价值高
                insight_bonus = 0.1 if gap_ratio > 0.7 else 0.05
            else:
                insight_bonus = 0

            raw_confidence = top1 * 0.8 + insight_bonus
            return min(1.0, max(0.45, raw_confidence + 0.15))

        return top1

    def create_trace_step(
        self,
        decision: RoutingDecision,
        duration_ms: float,
    ) -> TraceStep:
        """Create trace step for debugging."""
        return TraceStep(
            step_name="decision_fusion",
            step_order=3,
            input_summary={
                "skill_count": len(decision.skill_scores),
                "selected_count": len(decision.selected_skills),
            },
            output_summary={
                "selected_skills": decision.selected_skills,
                "execution_mode": decision.execution_mode.value,
                "confidence": round(decision.confidence, 4),
            },
            duration_ms=duration_ms,
        )


# ============================================================================
# FACTORY
# ============================================================================


def create_fusion_engine(
    config: Optional[RouterConfig] = None,
) -> DecisionFusionEngine:
    """Factory function to create configured fusion engine."""
    return DecisionFusionEngine(config=config)
