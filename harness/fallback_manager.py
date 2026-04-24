"""
DialecticEngine - Fallback Manager
=================================
多 agent 多 skill 推理流程中的失败处理与策略切换。

设计原则：
- 规则驱动，避免过度设计
- 两层 fallback：retry（重试） → reskill（换策略）
- 可扩展，保留接口

Usage:
    from harness.fallback_manager import FallbackManager, FallbackDecision, FallbackInput
    
    manager = FallbackManager(llm)
    
    # 在 pipeline 执行后评估
    decision = manager.evaluate(
        user_input="...",
        router_scores=[{"skill": "rujia", "score": 0.3}],
        skill_outputs=[...],
        fusion_result={...},
    )
    
    if decision.need_fallback:
        # 执行 fallback
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from .conflict_detector import ConflictDetector

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class FallbackInput:
    """Fallback Manager 输入"""
    
    user_input: str                          # 用户原始问题
    router_scores: list[dict] = field(default_factory=list)  # [{"skill": "...", "score": 0.5}]
    skill_outputs: list[dict] = field(default_factory=list)  # 每个 skill 的结构化输出
    fusion_result: dict = field(default_factory=dict)         # 融合结果


@dataclass
class FallbackDecision:
    """Fallback 决策"""
    
    need_fallback: bool = False
    level: Optional[str] = None  # "retry" | "reskill" | None
    reason: str = ""
    action: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "need_fallback": self.need_fallback,
            "level": self.level,
            "reason": self.reason,
            "action": self.action,
        }


@dataclass
class FallbackConfig:
    """Fallback 配置"""
    
    # 置信度阈值
    low_confidence_threshold: float = 0.4      # 触发 retry 的阈值
    very_low_confidence_threshold: float = 0.3  # 触发 reskill 的阈值
    
    # 冲突阈值
    conflict_threshold: float = 0.6           # 冲突检测阈值
    
    # 重试配置
    max_retries: int = 2
    
    # 是否启用各规则
    enable_low_confidence_rule: bool = True
    enable_conflict_rule: bool = True
    enable_no_conclusion_rule: bool = True


# ============================================================================
# Fallback Manager
# ============================================================================

class FallbackManager:
    """
    Fallback 管理器
    
    在以下情况发生时，自动调整策略或降级输出：
    - router 置信度低
    - skill 结果冲突严重
    - 输出质量差（无明确结论）
    
    Fallback 层级：
    1. Level 1 (retry): 低置信度 → query rewrite + 重新执行
    2. Level 2 (reskill): 冲突检测 / 无明确结论 → 扩大 skill 范围或替换组合
    """
    
    def __init__(
        self,
        llm=None,
        config: Optional[FallbackConfig] = None,
    ):
        """
        初始化
        
        Args:
            llm: LLM 实例（用于 query rewrite）
            config: 配置
        """
        self._llm = llm
        self._config = config or FallbackConfig()
        self._conflict_detector = ConflictDetector()
    
    # =========================================================================
    # 核心评估方法
    # =========================================================================
    
    def evaluate(
        self,
        user_input: str,
        router_scores: list[dict],
        skill_outputs: list[dict],
        fusion_result: dict,
    ) -> FallbackDecision:
        """
        评估是否需要 fallback
        
        Args:
            user_input: 用户问题
            router_scores: router 打分结果
            skill_outputs: skill 输出列表
            fusion_result: 融合结果
        
        Returns:
            FallbackDecision
        """
        logger.info(f"评估 fallback: user_input={user_input[:50]}...")
        
        # 构建输入
        input_obj = FallbackInput(
            user_input=user_input,
            router_scores=router_scores,
            skill_outputs=skill_outputs,
            fusion_result=fusion_result,
        )
        
        # 按优先级检查各规则
        # 规则 1: 低置信度
        if self._config.enable_low_confidence_rule:
            decision = self._check_low_confidence(input_obj)
            if decision.need_fallback:
                logger.info(f"触发 fallback: {decision.reason}")
                return decision
        
        # 规则 2: 冲突检测
        if self._config.enable_conflict_rule:
            decision = self._check_conflict(input_obj)
            if decision.need_fallback:
                logger.info(f"触发 fallback: {decision.reason}")
                return decision
        
        # 规则 3: 无明确结论
        if self._config.enable_no_conclusion_rule:
            decision = self._check_no_conclusion(input_obj)
            if decision.need_fallback:
                logger.info(f"触发 fallback: {decision.reason}")
                return decision
        
        # 无需 fallback
        return FallbackDecision(
            need_fallback=False,
            level=None,
            reason="所有检查通过",
            action={},
        )
    
    # =========================================================================
    # 各规则实现
    # =========================================================================
    
    def _check_low_confidence(self, input_obj: FallbackInput) -> FallbackDecision:
        """
        规则 1: 低置信度检测
        
        - 最高分 < 0.3 → Level 2 reskill（太不确定）
        - 最高分 < 0.4 → Level 1 retry（可能需要重试）
        """
        if not input_obj.router_scores:
            return FallbackDecision(
                need_fallback=True,
                level="reskill",
                reason="无 router 分数，无法评估",
                action={"suggestion": "扩大 skill 选择范围"},
            )
        
        max_score = max(s.get("score", 0) for s in input_obj.router_scores)
        
        if max_score < self._config.very_low_confidence_threshold:
            # 非常低，直接换策略
            return FallbackDecision(
                need_fallback=True,
                level="reskill",
                reason=f"最高置信度 {max_score:.2f} < {self._config.very_low_confidence_threshold}，严重不确定",
                action={
                    "suggestion": "扩大 skill 选择范围",
                    "expand_top_k": 5,
                    "add_analytical_skills": ["mingjia-perspective"],  # 名家用于问题分析
                },
            )
        
        if max_score < self._config.low_confidence_threshold:
            # 偏低，尝试重试
            return FallbackDecision(
                need_fallback=True,
                level="retry",
                reason=f"最高置信度 {max_score:.2f} < {self._config.low_confidence_threshold}",
                action={
                    "suggestion": "重写问题后重新执行",
                },
            )
        
        return FallbackDecision(need_fallback=False)
    
    def _check_conflict(self, input_obj: FallbackInput) -> FallbackDecision:
        """
        规则 2: 冲突检测
        
        检测 skill 输出的建议是否互相矛盾
        """
        if len(input_obj.skill_outputs) < 2:
            return FallbackDecision(need_fallback=False)
        
        # 使用冲突检测器
        conflict_result = self._conflict_detector.detect(
            skill_outputs=input_obj.skill_outputs,
            threshold=self._config.conflict_threshold,
        )
        
        if conflict_result["has_conflict"]:
            return FallbackDecision(
                need_fallback=True,
                level="reskill",
                reason=f"检测到 skill 输出冲突: {conflict_result['reason']}",
                action={
                    "conflict_details": conflict_result,
                    "suggestion": "换用更中性的 skill 组合",
                    "avoid_extreme_skills": conflict_result.get("conflicting_skills", []),
                    "add_balancing_skills": ["yinyangjia-perspective"],  # 阴阳家用于平衡
                },
            )
        
        return FallbackDecision(need_fallback=False)
    
    def _check_no_conclusion(self, input_obj: FallbackInput) -> FallbackDecision:
        """
        规则 3: 无明确结论检测
        
        检查 fusion_result 是否：
        - 没有 options
        - 结论模糊
        - 只是重复问题
        """
        if not input_obj.fusion_result:
            return FallbackDecision(
                need_fallback=True,
                level="reskill",
                reason="融合结果为空",
                action={"suggestion": "重新选择 skill 组合"},
            )
        
        # 检查是否缺少关键字段
        required_fields = ["conclusion", "options", "recommendation"]
        missing_fields = [
            f for f in required_fields
            if f not in input_obj.fusion_result or not input_obj.fusion_result[f]
        ]
        
        if len(missing_fields) >= 2:
            return FallbackDecision(
                need_fallback=True,
                level="reskill",
                reason="融合结果缺少关键信息",
                action={"suggestion": "扩大 skill 选择范围重新分析"},
            )
        
        # 检查结论是否模糊
        conclusion = input_obj.fusion_result.get("conclusion", "")
        vague_indicators = [
            "视情况而定",
            "需要更多信息",
            "很难说",
            "不确定",
            "不一定",
        ]
        
        if any(indicator in conclusion for indicator in vague_indicators):
            # 检查是否只是简单重复问题
            if self._is_just_repeating(input_obj.user_input, conclusion):
                return FallbackDecision(
                    need_fallback=True,
                    level="reskill",
                    reason="结论只是重复问题，没有实质性分析",
                    action={"suggestion": "换用分析性更强的 skill"},
                )
        
        return FallbackDecision(need_fallback=False)
    
    # =========================================================================
    # Fallback 执行
    # =========================================================================
    
    def rewrite_query(self, user_input: str) -> str:
        """
        Query Rewrite
        
        使用 LLM 重写问题，使其更清晰、具体
        
        Args:
            user_input: 原始问题
        
        Returns:
            重写后的问题
        """
        if self._llm is None:
            logger.warning("LLM 未配置，使用原始问题")
            return user_input
        
        try:
            prompt = f"""请将以下问题重写得更清晰、具体，便于多视角分析。

原始问题：
{user_input}

要求：
1. 保留原意
2. 去除歧义
3. 明确问题核心
4. 简短明了

重写后的问题："""
            
            response = self._llm.invoke(prompt)
            rewritten = response.content if hasattr(response, 'content') else str(response)
            
            logger.info(f"Query rewrite: '{user_input[:30]}...' → '{rewritten[:30]}...'")
            return rewritten.strip()
            
        except Exception as e:
            logger.warning(f"Query rewrite 失败: {e}，使用原始问题")
            return user_input
    
    def expand_skills(
        self,
        current_skills: list[str],
        router_scores: list[dict],
        expand_top_k: int = 5,
        add_skills: Optional[list[str]] = None,
    ) -> list[str]:
        """
        扩大或替换 skill 组合
        
        Args:
            current_skills: 当前 skill 列表
            router_scores: router 打分结果
            expand_top_k: 扩展到 top-k
            add_skills: 额外添加的 skill
        
        Returns:
            新的 skill 列表
        """
        new_skills = []
        
        # 添加 top-k skills
        sorted_scores = sorted(router_scores, key=lambda x: x.get("score", 0), reverse=True)
        for item in sorted_scores[:expand_top_k]:
            skill = item.get("skill", "")
            if skill and skill not in new_skills:
                new_skills.append(skill)
        
        # 添加额外 skill
        if add_skills:
            for skill in add_skills:
                if skill not in new_skills:
                    new_skills.append(skill)
        
        # 确保至少有一个
        if not new_skills:
            new_skills = current_skills
        
        logger.info(f"Skill 扩展: {current_skills} → {new_skills}")
        return new_skills
    
    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    def _is_just_repeating(self, query: str, conclusion: str, threshold: float = 0.7) -> bool:
        """
        检查结论是否只是重复问题
        
        Args:
            query: 用户问题
            conclusion: 结论
            threshold: 重复阈值
        
        Returns:
            是否只是重复
        """
        # 简单实现：计算字符重叠率
        query_chars = set(query)
        conclusion_chars = set(conclusion)
        
        if not conclusion_chars:
            return True
        
        overlap = len(query_chars & conclusion_chars) / len(conclusion_chars)
        
        return overlap > threshold


# ============================================================================
# 便捷函数
# ============================================================================

def quick_evaluate(
    user_input: str,
    router_scores: list[dict],
    skill_outputs: list[dict],
    fusion_result: dict,
) -> FallbackDecision:
    """
    快速评估（使用默认配置）
    """
    manager = FallbackManager()
    return manager.evaluate(
        user_input=user_input,
        router_scores=router_scores,
        skill_outputs=skill_outputs,
        fusion_result=fusion_result,
    )
