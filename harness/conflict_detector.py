"""
DialecticEngine - Conflict Detector
================================
检测多个 skill 输出的建议是否互相矛盾。

简单实现版本：
- 基于关键词匹配检测矛盾
- 支持建议极端性检测

Usage:
    from harness.conflict_detector import ConflictDetector
    
    detector = ConflictDetector()
    result = detector.detect(skill_outputs)
    
    if result["has_conflict"]:
        print(f"检测到冲突: {result['reason']}")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================================
# 冲突模式定义
# ============================================================================

# 矛盾关键词对：当两者同时出现时认为是冲突
CONTRADICTION_PAIRS = [
    # 行动方向矛盾
    (["继续", "坚持", "推进", "执行"], ["停止", "放弃", "中止", "终止"]),
    (["扩张", "进攻", "激进"], ["收缩", "防守", "保守"]),
    (["外包", "外购"], ["自研", "内部", "自主"]),
    
    # 态度矛盾
    (["应该", "必须", "一定要"], ["不应该", "不必", "不需要"]),
    (["积极", "主动", "大胆"], ["消极", "被动", "谨慎"]),
    
    # 优先级矛盾
    (["短期", "眼前", "当下"], ["长期", "长远", "未来"]),
    (["效率", "速度", "快"], ["质量", "稳妥", "慢"]),
    
    # 方式矛盾
    (["强硬", "强硬手段", "强制"], ["柔和", "软着陆", "协商"]),
    (["对抗", "竞争", "硬碰硬"], ["合作", "共赢", "妥协"]),
]

# 极端立场关键词
EXTREME_POSITIVE = [
    "完全", "彻底", "必须", "一定", "绝对", "毫无", "坚决",
]

EXTREME_NEGATIVE = [
    "完全不行", "绝对不能", "绝不可能", "毫无意义", "彻底失败",
]

# 模糊/无建设性关键词
VAGUE_KEYWORDS = [
    "视情况", "看情况", "需要更多信息", "很难说", "不确定",
    "不一定", "可能", "也许", "大概", "差不多",
]


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class ConflictDetail:
    """冲突详情"""
    
    type: str           # "contradiction" | "extreme" | "vague"
    conflicting_skills: list[str]
    evidence: list[str]  # 证据片段
    severity: float      # 0.0 - 1.0


# ============================================================================
# Conflict Detector
# ============================================================================

class ConflictDetector:
    """
    Skill 输出冲突检测器
    
    检测类型：
    1. 方向矛盾：建议完全相反的行动
    2. 极端立场：建议过于极端
    3. 模糊无结论：建议模糊无建设性
    """
    
    def __init__(
        self,
        contradiction_threshold: float = 0.5,
        extreme_threshold: float = 0.6,
    ):
        """
        初始化
        
        Args:
            contradiction_threshold: 矛盾检测阈值
            extreme_threshold: 极端立场阈值
        """
        self.contradiction_threshold = contradiction_threshold
        self.extreme_threshold = extreme_threshold
    
    def detect(
        self,
        skill_outputs: list[dict],
        threshold: float = 0.6,
    ) -> dict:
        """
        检测冲突
        
        Args:
            skill_outputs: skill 输出列表，每个元素包含：
                - skill_id: skill 标识
                - suggestion: 建议内容
                - conclusion: 结论
                - stance: 立场（可选）
            threshold: 冲突判定阈值
        
        Returns:
            {
                "has_conflict": bool,
                "conflict_score": float,      # 0.0 - 1.0
                "conflict_type": str,       # "contradiction" | "extreme" | "vague" | None
                "conflicting_skills": list[str],
                "reason": str,
                "details": list[ConflictDetail],
            }
        """
        if len(skill_outputs) < 2:
            return self._no_conflict_result()
        
        suggestions = [s.get("suggestion", "") or s.get("conclusion", "") for s in skill_outputs]
        skill_ids = [s.get("skill_id", s.get("skill", f"skill_{i}")) for i, s in enumerate(skill_outputs)]
        
        # 1. 方向矛盾检测
        contradiction_result = self._detect_contradiction(suggestions, skill_ids)
        
        # 2. 极端立场检测
        extreme_result = self._detect_extreme(suggestions, skill_ids)
        
        # 3. 模糊无结论检测
        vague_result = self._detect_vague(suggestions, skill_ids)
        
        # 汇总结果
        all_conflicts = [contradiction_result, extreme_result, vague_result]
        
        # 取最严重的冲突
        max_severity = max(c["severity"] for c in all_conflicts)
        worst_conflict = max(all_conflicts, key=lambda x: x["severity"])
        
        has_conflict = max_severity >= threshold
        
        result = {
            "has_conflict": has_conflict,
            "conflict_score": max_severity,
            "conflict_type": worst_conflict["type"] if has_conflict else None,
            "conflicting_skills": worst_conflict.get("conflicting_skills", []),
            "reason": worst_conflict.get("reason", "无冲突") if has_conflict else "未检测到冲突",
            "details": all_conflicts,
        }
        
        logger.debug(f"冲突检测结果: has_conflict={has_conflict}, score={max_severity:.2f}")
        
        return result
    
    def _detect_contradiction(
        self,
        suggestions: list[str],
        skill_ids: list[str],
    ) -> dict:
        """
        检测方向矛盾
        
        例如："继续做" vs "停止/放弃"
        """
        severity = 0.0
        conflicting_pairs = []
        evidence = []
        
        for pos_keywords, neg_keywords in CONTRADICTION_PAIRS:
            pos_found = []
            neg_found = []
            
            for i, suggestion in enumerate(suggestions):
                # 检查正面词
                for kw in pos_keywords:
                    if kw in suggestion:
                        pos_found.append((skill_ids[i], kw))
                        break
                
                # 检查负面词
                for kw in neg_keywords:
                    if kw in suggestion:
                        neg_found.append((skill_ids[i], kw))
                        break
            
            # 发现了矛盾对
            if pos_found and neg_found:
                conflicting_pairs.append({
                    "positive": pos_found,
                    "negative": neg_found,
                })
                
                evidence.append(
                    f"{skill_ids[pos_found[0][0]]} 建议：{pos_found[0][1]}，"
                    f"{skill_ids[neg_found[0][0]]} 建议：{neg_found[0][1]}"
                )
        
        # 计算严重度
        if conflicting_pairs:
            severity = min(1.0, len(conflicting_pairs) * 0.4)
            
            conflicting_skills = list(set(
                skill for pair in conflicting_pairs
                for skills in [pair["positive"], pair["negative"]]
                for skill, _ in skills
            ))
            
            return {
                "type": "contradiction",
                "severity": severity,
                "conflicting_skills": conflicting_skills,
                "reason": f"检测到 {len(conflicting_pairs)} 对矛盾建议",
                "evidence": evidence[:3],
            }
        
        return {
            "type": "contradiction",
            "severity": 0.0,
            "conflicting_skills": [],
            "reason": "未检测到方向矛盾",
            "evidence": [],
        }
    
    def _detect_extreme(
        self,
        suggestions: list[str],
        skill_ids: list[str],
    ) -> dict:
        """
        检测极端立场
        
        例如：建议过于激进或过于保守
        """
        extreme_count = 0
        extreme_skills = []
        evidence = []
        
        for i, suggestion in enumerate(suggestions):
            extreme_score = 0.0
            
            # 检查极端正面词
            for kw in EXTREME_POSITIVE:
                if kw in suggestion:
                    extreme_score += 0.3
                    break
            
            # 检查极端负面词
            for kw in EXTREME_NEGATIVE:
                if kw in suggestion:
                    extreme_score += 0.4
                    break
            
            if extreme_score >= self.extreme_threshold:
                extreme_count += 1
                extreme_skills.append(skill_ids[i])
                evidence.append(f"{skill_ids[i]}: {suggestion[:50]}...")
        
        # 计算严重度：多个 skill 都极端时更严重
        if extreme_count >= 2:
            severity = min(1.0, extreme_count * 0.4)
        elif extreme_count == 1:
            severity = 0.3
        else:
            severity = 0.0
        
        return {
            "type": "extreme",
            "severity": severity,
            "conflicting_skills": extreme_skills,
            "reason": f"检测到 {extreme_count} 个极端立场建议" if extreme_count else "未检测到极端立场",
            "evidence": evidence,
        }
    
    def _detect_vague(
        self,
        suggestions: list[str],
        skill_ids: list[str],
    ) -> dict:
        """
        检测模糊无结论
        
        多个 skill 都给出模糊回答时，认为缺乏有效分析
        """
        vague_count = 0
        vague_skills = []
        evidence = []
        
        for i, suggestion in enumerate(suggestions):
            vague_score = 0.0
            
            for kw in VAGUE_KEYWORDS:
                if kw in suggestion:
                    vague_score += 0.2
                    break
            
            if vague_score >= 0.3:
                vague_count += 1
                vague_skills.append(skill_ids[i])
                evidence.append(f"{skill_ids[i]}: {suggestion[:50]}...")
        
        # 计算严重度：超过一半 skill 都模糊时严重
        if len(suggestions) >= 2:
            ratio = vague_count / len(suggestions)
            severity = ratio if ratio >= 0.5 else 0.0
        else:
            severity = 0.0
        
        return {
            "type": "vague",
            "severity": severity,
            "conflicting_skills": vague_skills,
            "reason": f"检测到 {vague_count} 个模糊回答" if vague_count else "未检测到模糊回答",
            "evidence": evidence,
        }
    
    def _no_conflict_result(self) -> dict:
        """无冲突结果"""
        return {
            "has_conflict": False,
            "conflict_score": 0.0,
            "conflict_type": None,
            "conflicting_skills": [],
            "reason": "skill 数量不足，无法检测冲突",
            "details": [],
        }
    
    # =========================================================================
    # 便捷方法
    # =========================================================================
    
    def check_single_extreme(self, suggestion: str) -> dict:
        """
        检查单条建议是否极端
        
        Args:
            suggestion: 建议内容
        
        Returns:
            {"is_extreme": bool, "reasons": []}
        """
        reasons = []
        
        for kw in EXTREME_POSITIVE + EXTREME_NEGATIVE:
            if kw in suggestion:
                reasons.append(f"包含极端词: {kw}")
        
        return {
            "is_extreme": len(reasons) > 0,
            "reasons": reasons,
        }
    
    def get_stance_polarity(self, suggestion: str) -> float:
        """
        获取建议的立场极性
        
        Returns:
            -1.0 到 1.0，负数表示消极，正数表示积极
        """
        positive_words = ["应该", "建议", "积极", "主动", "鼓励", "支持", "肯定"]
        negative_words = ["不应该", "避免", "反对", "批评", "否定", "停止", "禁止"]
        
        pos_score = sum(1 for w in positive_words if w in suggestion) / len(positive_words)
        neg_score = sum(1 for w in negative_words if w in suggestion) / len(negative_words)
        
        return pos_score - neg_score


# ============================================================================
# 便捷函数
# ============================================================================

def quick_detect(skill_outputs: list[dict]) -> dict:
    """
    快速冲突检测
    """
    detector = ConflictDetector()
    return detector.detect(skill_outputs)
