"""
DialecticEngine - Multi-Dimension Skill Scorer
==============================================
对所有skill进行多维度打分，包括：
1. Semantic Score - embedding相似度
2. Rule Bias Score - 规则标签匹配
3. Context Score - 上下文匹配
4. Feedback Score - 历史表现反馈

Design:
- 支持自定义权重
- 提供可解释的分数分解
- 支持批量评分
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .types import (
    FeatureVector,
    SkillMetadata,
    SkillScore,
    DomainTag,
    IntentType,
    RouterConfig,
    TraceStep,
)
from .context import ContextManager, ContextAggregator
from .registry_adapter import RegistryAdapter


# ============================================================================
# SCORE COMPONENTS
# ============================================================================


@dataclass
class SemanticScorer:
    """Computes semantic similarity between query and skill.

    当前使用关键词匹配作为占位符。
    实际实现应使用embedding模型。
    """

    # 儒家/法家/道家/兵家相关关键词
    # 扩展关键词覆盖，提升语义匹配准确性
    SCHOOL_KEYWORDS = {
        "rujia-perspective": [
            "仁", "义", "礼", "智", "信", "忠", "恕", "孝", "悌",
            "修身", "五伦", "君子", "中庸", "名实", "经权",
            "伦理", "关系", "道德", "责任", "角色",
            "人情", "情面", "和谐", "长辈", "领导", "下属",
            "忠恕", "恭敬", "教化", "德行", "品行",
        ],
        "fajia-perspective": [
            "法", "术", "势", "赏罚", "刑德", "制度", "规则",
            "激励", "监督", "权责", "执行", "法治",
            "管理", "组织", "绩效", "合规", "激励相容",
            "考核", "KPI", "规范", "约束", "奖惩",
            "条例", "规章", "规定", "条文", "标准",
        ],
        "daojia-perspective": [
            "道", "无为", "自然", "柔弱", "虚静", "逍遥",
            "齐物", "反者道之动", "知足", "不争",
            "无用", "心斋", "顺势", "内耗", "焦虑",
            "放下", "顺其自然", "不强求", "淡定", "从容",
            "淡泊", "宁静", "超脱", "看淡", "平常心",
        ],
        "bingjia-perspective": [
            "兵", "战", "谋", "势", "奇正", "虚实", "战略",
            "竞争", "博弈", "知己知彼", "全胜", "伐谋",
            "对手", "竞争者", "策略", "战术", "布局",
            "进攻", "防守", "攻防", "谋略", "计策",
        ],
        "mojia-perspective": [
            "兼爱", "非攻", "尚贤", "节用", "逻辑",
            "功利", "墨辩", "推理", "辩论", "判断",
            "分析", "论证", "推理", "逻辑", "道理",
            "公正", "公平", "客观", "理性", "权衡",
        ],
        "mingjia-perspective": [
            "名", "实", "辩论", "逻辑", "白马",
            "离坚白", "合同异", "概念", "定义", "本质",
            "名实", "表象", "实质", "真相", "核实",
            "验证", "辨别", "区分", "澄清", "正名",
        ],
        # 新增其他学派的关键词
        "zonghengjia-perspective": [
            "合纵", "连横", "外交", "游说", "权谋", "外交",
            "联盟", "盟友", "联合", "结盟", "谈判",
            "说服", "沟通", "关系", "资源整合", "借力",
        ],
        "yinyangjia-perspective": [
            "阴阳", "五行", "相生", "相克", "平衡", "调和",
            "矛盾", "对立", "统一", "转化", "循环",
            "动态", "调节", "协调", "综合", "折中",
        ],
        "fojia-perspective": [
            "佛", "缘起", "空", "无常", "放下", "慈悲", "觉悟",
            "烦恼", "执念", "痛苦", "解脱", "涅槃",
            "禅", "修行", "因缘", "果报", "中道",
            "心静", "心安", "平和", "超然", "自在",
        ],
        "yijia-perspective": [
            "医", "养生", "调和", "预防", "健康", "调理",
            "身体", "疾病", "治疗", "康复", "保健",
            "身心", "平衡", "气血", "经络", "阴阳",
        ],
        "shijia-perspective": [
            "历史", "借鉴", "得失", "兴衰", "教训", "传统",
            "前人", "古人", "往事", "典故", "往事",
            "经验", "智慧", "规律", "周期", "轮回",
        ],
        "lixue-perspective": [
            "理", "气", "格物", "致知", "天理", "心性",
            "学习", "读书", "经典", "研究", "修养",
            "明理", "穷理", "博文", "约礼", "格致",
        ],
        "xinxue-perspective": [
            "心", "良知", "致良知", "知行合一", "心即理",
            "本心", "真诚", "反省", "内省", "自省",
            "直觉", "初心", "意念", "念头", "心学",
        ],
        "huanglao-perspective": [
            "黄老", "清静", "无为而治", "刑德", "老子",
            "法治", "法术", "道法", "君主", "臣民",
            "治国", "理政", "宽猛", "简约", "清净",
        ],
        "jingxue-perspective": [
            "经", "经典", "注疏", "训诂", "六经", "传注",
            "儒学", "经文", "典籍", "文献", "考证",
            "诠释", "解读", "阐发", "义理", "微言大义",
        ],
        "zajia-perspective": [
            "综合", "博采", "折中", "融通", "务实", "经世",
            "实用", "灵活", "变通", "权变", "制宜",
            "因时", "因地", "制宜", "制宜", "综合分析",
        ],
        "xuanxue-perspective": [
            "玄学", "清谈", "有无", "本末", "老庄", "三玄",
            "义理", "玄虚", "形而上学", "本体", "终极",
            "思辨", "玄奥", "精微", "幽深", "超验",
        ],
        "newrujia-perspective": [
            "新儒", "理学", "心学", "宋明", "道统", "复兴",
            "传统", "现代化", "转型", "创新", "融合",
            "儒学", "返本开新", "中学为体", "西学为用",
        ],
    }

    def score(
        self,
        query: str,
        skill: SkillMetadata,
        features: FeatureVector,
    ) -> float:
        """Compute semantic similarity score.

        Args:
            query: Original query text
            skill: Skill metadata
            features: Extracted features

        Returns:
            Score in [0.0, 1.0]
        """
        query_lower = query.lower()
        skill_keywords = self.SCHOOL_KEYWORDS.get(
            skill.slug,
            list(skill.tags)[:10]  # fallback到tags
        )

        # 关键词匹配计数
        matches = 0
        total_keywords = len(skill_keywords)

        for keyword in skill_keywords:
            if keyword.lower() in query_lower:
                matches += 1

        # 同时检查description匹配
        desc_matches = sum(
            1 for kw in skill_keywords
            if kw in skill.description.lower()
        )

        # 综合得分
        keyword_score = matches / max(1, total_keywords)
        desc_score = desc_matches / max(1, total_keywords) * 0.3  # description权重较低

        raw_score = keyword_score + desc_score
        normalized = min(1.0, raw_score)

        # 如果query中有该school的明确指示词，加权提升
        if any(kw in query_lower for kw in ["儒家", "法家", "道家", "兵家", "墨家"]):
            school_mentioned = {
                "儒家": "rujia",
                "法家": "fajia",
                "道家": "daojia",
                "兵家": "bingjia",
                "墨家": "mojia",
            }
            for mention, slug in school_mentioned.items():
                if mention in query_lower and skill.slug == f"{slug}-perspective":
                    normalized = min(1.0, normalized + 0.3)
                    break

        return normalized


@dataclass
class RuleBiasScorer:
    """Computes rule-based matching score using skill tags and domains."""

    def score(
        self,
        features: FeatureVector,
        skill: SkillMetadata,
    ) -> float:
        """Compute rule-based bias score.

        Args:
            features: Extracted features
            skill: Skill metadata

        Returns:
            Score in [0.0, 1.0]
        """
        scores: list[float] = []

        # 1. Intent匹配
        if self._intent_matches(features.intent, skill):
            scores.append(0.4)  # intent权重40%
        else:
            scores.append(0.1)

        # 2. Domain匹配
        domain_score = self._domain_match_score(features.domains, skill.domains)
        scores.append(domain_score * 0.35)  # domain权重35%

        # 3. 问题维度匹配
        dimension_score = self._dimension_score(features, skill)
        scores.append(dimension_score * 0.25)  # 维度权重25%

        return sum(scores)

    def _intent_matches(self, intent: IntentType, skill: SkillMetadata) -> bool:
        """Check if intent matches skill's primary domain."""
        intent_domain_map = {
            IntentType.CONFUCIAN: ["rujia"],
            IntentType.LEGALIST: ["fajia"],
            IntentType.DAOIST: ["daojia"],
            IntentType.ETHICAL_DILEMMA: ["rujia", "mojia", "fajia"],
            IntentType.DECISION_ANALYSIS: ["fajia", "rujia", "daojia"],
            IntentType.RELATIONSHIP: ["rujia"],
            IntentType.ORGANIZATION: ["fajia"],
            IntentType.SELF_CULTIVATION: ["rujia", "daojia"],
            IntentType.STRATEGY: ["bingjia", "fajia"],
            IntentType.GENERAL: [],  # 通用匹配所有
        }

        matching_slugs = intent_domain_map.get(intent, [])
        return any(slug in skill.slug for slug in matching_slugs)

    def _domain_match_score(
        self,
        query_domains: frozenset[DomainTag],
        skill_domains: frozenset[DomainTag],
    ) -> float:
        """Compute domain overlap score."""
        if not query_domains or not skill_domains:
            return 0.3  # 默认分数

        # Jaccard相似度
        intersection = len(query_domains.intersection(skill_domains))
        union = len(query_domains.union(skill_domains))

        return intersection / union if union > 0 else 0.0

    def _dimension_score(
        self,
        features: FeatureVector,
        skill: SkillMetadata,
    ) -> float:
        """Compute score based on problem dimensions."""
        score = 0.5  # 基础分

        skill_slug = skill.slug

        # 伦理维度
        if features.has_ethical_dimension:
            if "rujia" in skill_slug or "mojia" in skill_slug:
                score += 0.15
            elif "fajia" in skill_slug:
                score += 0.05

        # 组织维度
        if features.has_organizational_dimension:
            if "fajia" in skill_slug:
                score += 0.2

        # 个人维度
        if features.has_personal_dimension:
            if "daojia" in skill_slug:
                score += 0.15
            elif "rujia" in skill_slug:
                score += 0.1

        return min(1.0, score)


@dataclass
class ContextScorer:
    """Computes context-based matching score using user/session history."""

    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        self.aggregator = ContextAggregator()

    def score(
        self,
        skill: SkillMetadata,
        context: dict[str, Any],
    ) -> float:
        """Compute context matching score.

        Args:
            skill: Skill metadata
            context: Context dict from ContextManager

        Returns:
            Score in [0.0, 1.0]
        """
        # 使用aggregator进行加权聚合
        return self.aggregator.aggregate_context_score(
            skill_domains=skill.domains,
            skill_id=skill.skill_id,
            context=context,
        )


@dataclass
class FeedbackScorer:
    """Computes score based on historical feedback."""

    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager

    def score(
        self,
        skill_id: str,
        user_id: str,
    ) -> float:
        """Compute feedback-based score.

        基于用户对该skill的历史使用和反馈。
        成功率高 -> 分数高
        使用次数少 -> 分数趋近0.5（不确定）

        Args:
            skill_id: Skill identifier
            user_id: User identifier

        Returns:
            Score in [0.0, 1.0]
        """
        # 获取用户对该skill的成功率
        success_rate = self.context_manager.get_skill_success_rate(
            user_id, skill_id
        )

        # 获取动态权重
        weight = self.context_manager.get_skill_weight(user_id, skill_id)

        # 综合得分
        # success_rate是[0.0, 1.0]
        # weight是[0.5, 1.0]
        # 综合两者，给予适度偏向成功率高的一侧
        raw_score = (success_rate * 0.7) + (weight * 0.3)

        # 如果使用次数过少（<3），分数回归0.5
        # 这可以通过context manager获取使用次数
        # 此处简化处理
        return raw_score


# ============================================================================
# MULTI-DIMENSION SKILL SCORER
# ============================================================================


class MultiDimensionScorer:
    """Main scorer that combines all dimensions.

    Pipeline:
    1. Semantic scoring (embedding similarity)
    2. Rule bias scoring (tag/domain matching)
    3. Context scoring (user/session history)
    4. Feedback scoring (historical performance)

    Final score = weighted sum of all dimensions
    """

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
        context_manager: Optional[ContextManager] = None,
        registry_adapter: Optional[RegistryAdapter] = None,
    ):
        self.config = config or RouterConfig()
        self.context_manager = context_manager or ContextManager(config=self.config)
        self.registry_adapter = registry_adapter

        # 初始化各维度scorer
        self.semantic_scorer = SemanticScorer()
        self.rule_scorer = RuleBiasScorer()
        self.context_scorer = ContextScorer(self.context_manager)
        self.feedback_scorer = FeedbackScorer(self.context_manager)

    def score_all_skills(
        self,
        query: str,
        features: FeatureVector,
        user_id: str,
        session_id: str,
    ) -> dict[str, SkillScore]:
        """Score all available skills.

        Args:
            query: User query text
            features: Extracted features
            user_id: User identifier
            session_id: Session identifier

        Returns:
            Dict mapping skill_id to SkillScore
        """
        # 获取上下文
        context = self.context_manager.get_context_for_scorer(user_id, session_id)

        # 获取所有skill
        if self.registry_adapter:
            skills = self.registry_adapter.get_skills_for_scoring()
        else:
            # 简化fallback：只包含预设的几种
            skills = []

        # 对每个skill打分
        scores: dict[str, SkillScore] = {}
        weights = self.config.scoring_weights

        for skill in skills:
            # 各维度打分
            semantic = self.semantic_scorer.score(query, skill, features)
            rule_bias = self.rule_scorer.score(features, skill)
            context_score = self.context_scorer.score(skill, context)
            feedback = self.feedback_scorer.score(skill.skill_id, user_id)

            # 创建SkillScore对象
            skill_score = SkillScore(
                skill_id=skill.skill_id,
                skill_name=skill.name,
                semantic_score=semantic,
                rule_bias_score=rule_bias,
                context_score=context_score,
                feedback_score=feedback,
                weights=weights,
            )

            # 计算加权总分
            skill_score.compute_total()

            # 生成可解释的breakdown
            skill_score.breakdown = self._generate_breakdown(
                skill, features, semantic, rule_bias, context_score, feedback
            )

            # 生成explanation
            skill_score.explanation = self._generate_explanation(
                skill, skill_score
            )

            scores[skill.skill_id] = skill_score

        return scores

    def score_single_skill(
        self,
        skill_id: str,
        query: str,
        features: FeatureVector,
        user_id: str,
        session_id: str,
    ) -> Optional[SkillScore]:
        """Score a single skill.

        Args:
            skill_id: Skill identifier
            query: User query text
            features: Extracted features
            user_id: User identifier
            session_id: Session identifier

        Returns:
            SkillScore or None if skill not found
        """
        if self.registry_adapter:
            skill = self.registry_adapter.get_skill_metadata(skill_id)
        else:
            skill = None

        if not skill:
            return None

        context = self.context_manager.get_context_for_scorer(user_id, session_id)

        semantic = self.semantic_scorer.score(query, skill, features)
        rule_bias = self.rule_scorer.score(features, skill)
        context_score = self.context_scorer.score(skill, context)
        feedback = self.feedback_scorer.score(skill.skill_id, user_id)

        skill_score = SkillScore(
            skill_id=skill.skill_id,
            skill_name=skill.name,
            semantic_score=semantic,
            rule_bias_score=rule_bias,
            context_score=context_score,
            feedback_score=feedback,
            weights=self.config.scoring_weights,
        )

        skill_score.compute_total()
        skill_score.breakdown = self._generate_breakdown(
            skill, features, semantic, rule_bias, context_score, feedback
        )
        skill_score.explanation = self._generate_explanation(skill, skill_score)

        return skill_score

    def _generate_breakdown(
        self,
        skill: SkillMetadata,
        features: FeatureVector,
        semantic: float,
        rule_bias: float,
        context_score: float,
        feedback: float,
    ) -> dict[str, Any]:
        """Generate detailed breakdown for explanation."""
        return {
            "skill_name": skill.name,
            "skill_slug": skill.slug,
            "dimensions": {
                "semantic": {
                    "score": round(semantic, 4),
                    "description": "语义相似度（关键词匹配）",
                },
                "rule_bias": {
                    "score": round(rule_bias, 4),
                    "description": "规则标签匹配度",
                    "intent_match": features.intent.value,
                },
                "context": {
                    "score": round(context_score, 4),
                    "description": "上下文匹配度",
                },
                "feedback": {
                    "score": round(feedback, 4),
                    "description": "历史表现反馈",
                },
            },
            "weights": self.config.scoring_weights,
        }

    def _generate_explanation(
        self,
        skill: SkillMetadata,
        score: SkillScore,
    ) -> str:
        """Generate human-readable explanation for the score."""
        parts = []

        # 语义得分说明
        if score.semantic_score > 0.5:
            parts.append(f"query与「{skill.name}」的核心概念高度相关")
        elif score.semantic_score > 0.2:
            parts.append(f"query涉及「{skill.name}」的部分领域")

        # 规则匹配说明
        if score.rule_bias_score > 0.6:
            parts.append("意图与领域匹配度高")
        elif score.rule_bias_score > 0.3:
            parts.append("存在一定程度的领域匹配")

        # 综合评价
        if score.total_score > 0.7:
            conclusion = "非常适合处理此问题"
        elif score.total_score > 0.5:
            conclusion = "可以作为备选视角"
        elif score.total_score > 0.3:
            conclusion = "可作为辅助参考"
        else:
            conclusion = "不太适合此场景"

        if parts:
            return f"{'；'.join(parts)}。综合评估：{conclusion}。"
        return f"「{skill.name}」综合得分{score.total_score:.2f}，{conclusion}。"

    def create_trace_step(
        self,
        query: str,
        scores: dict[str, SkillScore],
        duration_ms: float,
    ) -> TraceStep:
        """Create trace step for debugging."""
        top_skills = sorted(
            scores.items(),
            key=lambda x: x[1].total_score,
            reverse=True
        )[:3]

        return TraceStep(
            step_name="skill_scoring",
            step_order=2,
            input_summary={
                "query": query[:100],
                "skill_count": len(scores),
            },
            output_summary={
                "top_skills": [
                    {"id": sid, "score": s.total_score}
                    for sid, s in top_skills
                ],
                "score_range": [
                    min(s.total_score for s in scores.values()),
                    max(s.total_score for s in scores.values()),
                ] if scores else [0, 0],
            },
            duration_ms=duration_ms,
        )


# ============================================================================
# FACTORY
# ============================================================================


def create_scorer(
    config: Optional[RouterConfig] = None,
    context_manager: Optional[ContextManager] = None,
    registry_adapter: Optional[RegistryAdapter] = None,
) -> MultiDimensionScorer:
    """Factory function to create configured scorer."""
    return MultiDimensionScorer(
        config=config,
        context_manager=context_manager,
        registry_adapter=registry_adapter,
    )
