"""
DialecticEngine - 裁决 Agent
===========================
用于评判主 Agent 的回复是否与用户问题相关、视角选择是否合理。

功能：
- 评判回答与问题的相关性
- 评判视角选择是否恰当
- 评判回答质量（深度、逻辑性、可操作性）
- 提供改进建议

Usage:
    from harness.adjudicator import Adjudicator, Judgement, JudgementCriteria
    
    adjudicator = Adjudicator()
    
    # 评判单次回答
    result = adjudicator.judge(
        user_query="我和老板意见不合...",
        selected_skills=["rujia-perspective"],
        response="从儒家角度看...",
    )
    
    print(result.score, result.verdict, result.suggestions)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.utils.integrations.deepseek_integration import DeepSeekChat

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class JudgementCriteria:
    """评判维度"""
    
    relevance_weight: float = 0.3      # 相关性权重
    skill_appropriateness_weight: float = 0.25  # 视角恰当性权重
    depth_weight: float = 0.2          # 深度权重
    logic_weight: float = 0.15         # 逻辑性权重
    actionability_weight: float = 0.1   # 可操作性权重


@dataclass
class DimensionScore:
    """单维度得分"""
    
    name: str
    score: float           # 0.0 - 1.0
    reasoning: str         # 打分理由
    suggestions: list[str] = field(default_factory=list)


@dataclass
class Judgement:
    """评判结果"""
    
    # 综合得分 (0.0 - 1.0)
    score: float
    
    # 评判结论
    verdict: str           # "优秀" | "良好" | "一般" | "不合格"
    summary: str           # 简要总结
    
    # 各维度得分
    relevance: DimensionScore
    skill_appropriateness: DimensionScore
    depth: DimensionScore
    logic: DimensionScore
    actionability: DimensionScore
    
    # 建议
    suggestions: list[str] = field(default_factory=list)
    
    # 元数据
    query_preview: str = ""
    skills_preview: str = ""
    
    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "score": round(self.score, 2),
            "verdict": self.verdict,
            "summary": self.summary,
            "dimensions": {
                "relevance": self._dim_to_dict(self.relevance),
                "skill_appropriateness": self._dim_to_dict(self.skill_appropriateness),
                "depth": self._dim_to_dict(self.depth),
                "logic": self._dim_to_dict(self.logic),
                "actionability": self._dim_to_dict(self.actionability),
            },
            "suggestions": self.suggestions,
        }
    
    def _dim_to_dict(self, dim: DimensionScore) -> dict:
        return {
            "score": round(dim.score, 2),
            "reasoning": dim.reasoning,
            "suggestions": dim.suggestions,
        }


# ============================================================================
# 裁决 Agent
# ============================================================================

class Adjudicator:
    """
    裁决 Agent
    
    评判主 Agent 回答的质量，包括：
    1. 相关性 - 回答是否针对用户问题
    2. 视角恰当性 - 选取的视角是否适合问题
    3. 深度 - 回答是否有足够深度
    4. 逻辑性 - 论证是否清晰合理
    5. 可操作性 - 是否给出可执行的建议
    """
    
    # 得分阈值
    EXCELLENT_THRESHOLD = 0.85
    GOOD_THRESHOLD = 0.70
    ACCEPTABLE_THRESHOLD = 0.50
    
    def __init__(
        self,
        llm: Optional[DeepSeekChat] = None,
        criteria: Optional[JudgementCriteria] = None,
    ):
        """
        初始化
        
        Args:
            llm: DeepSeek LLM 实例（延迟初始化）
            criteria: 评判维度权重
        """
        self._llm = llm
        self._criteria = criteria or JudgementCriteria()
    
    @property
    def llm(self) -> DeepSeekChat:
        """获取 LLM 实例"""
        if self._llm is None:
            self._llm = DeepSeekChat(
                model="deepseek-chat",
                temperature=0.3,  # 裁决用较低温度
            )
        return self._llm
    
    # =========================================================================
    # 主评判方法
    # =========================================================================
    
    def judge(
        self,
        user_query: str,
        selected_skills: list[str],
        response: str,
        context: Optional[str] = None,
    ) -> Judgement:
        """
        评判回答
        
        Args:
            user_query: 用户原始问题
            selected_skills: 选取的技能列表
            response: Agent 生成的回答
            context: 可选的额外上下文
        
        Returns:
            Judgement 评判结果
        """
        logger.info(f"开始评判: {user_query[:50]}...")
        
        # 各维度评判
        relevance = self._judge_relevance(user_query, response)
        skill_appropriateness = self._judge_skill_appropriateness(
            user_query, selected_skills, response
        )
        depth = self._judge_depth(user_query, response)
        logic = self._judge_logic(user_query, response)
        actionability = self._judge_actionability(user_query, response)
        
        # 综合得分
        total_score = (
            relevance.score * self._criteria.relevance_weight
            + skill_appropriateness.score * self._criteria.skill_appropriateness_weight
            + depth.score * self._criteria.depth_weight
            + logic.score * self._criteria.logic_weight
            + actionability.score * self._criteria.actionability_weight
        )
        
        # 判定结论
        verdict = self._determine_verdict(total_score)
        
        # 收集建议
        suggestions = self._collect_suggestions([
            relevance,
            skill_appropriateness,
            depth,
            logic,
            actionability,
        ])
        
        return Judgement(
            score=total_score,
            verdict=verdict,
            summary=self._generate_summary(total_score, verdict, suggestions),
            relevance=relevance,
            skill_appropriateness=skill_appropriateness,
            depth=depth,
            logic=logic,
            actionability=actionability,
            suggestions=suggestions,
            query_preview=user_query[:100],
            skills_preview=", ".join(selected_skills),
        )
    
    def judge_with_llm(
        self,
        user_query: str,
        selected_skills: list[str],
        response: str,
        context: Optional[str] = None,
    ) -> Judgement:
        """
        使用 LLM 进行深度评判
        
        适用于需要更细致分析的场景
        
        Args:
            user_query: 用户原始问题
            selected_skills: 选取的技能列表
            response: Agent 生成的回答
            context: 可选的额外上下文
        
        Returns:
            Judgement 评判结果
        """
        logger.info(f"使用 LLM 深度评判: {user_query[:50]}...")
        
        # 先进行规则评判
        base_judgement = self.judge(
            user_query, selected_skills, response, context
        )
        
        # 构建 LLM 评判 prompt
        prompt = self._build_llm_judgement_prompt(
            user_query, selected_skills, response, context
        )
        
        try:
            # 调用 LLM
            llm_response = self.llm.invoke(prompt)
            
            # 解析 LLM 评判结果
            parsed = self._parse_llm_judgement(llm_response.content)
            
            if parsed:
                # 融合规则评判和 LLM 评判
                return self._merge_judgements(base_judgement, parsed)
            
        except Exception as e:
            logger.warning(f"LLM 评判失败: {e}，使用规则评判结果")
        
        return base_judgement
    
    # =========================================================================
    # 各维度评判方法
    # =========================================================================
    
    def _judge_relevance(self, query: str, response: str) -> DimensionScore:
        """
        评判相关性：回答是否针对用户问题
        """
        suggestions = []
        score = 0.5
        
        # 检查关键词覆盖率
        query_keywords = self._extract_keywords(query)
        response_lower = response.lower()
        
        # 统计问题中的关键概念在回答中的出现
        matched_concepts = 0
        total_concepts = len(query_keywords)
        
        for kw in query_keywords:
            if kw.lower() in response_lower:
                matched_concepts += 1
        
        if total_concepts > 0:
            keyword_coverage = matched_concepts / total_concepts
            score = 0.3 + keyword_coverage * 0.4
        
        # 检查回答是否回答了问题
        if "?" in query:
            # 是问句，检查回答是否以结论开头
            first_sentence = response.split("。")[0] if "。" in response else response[:50]
            if any(indicator in first_sentence for indicator in ["是", "不是", "建议", "应该", "可以", "需要"]):
                score = min(1.0, score + 0.15)
        
        # 检查是否有答非所问的迹象
        off_topic_indicators = ["这个问题", "关于这个话题", "一般来说", "通常来说"]
        if any(indicator in response[:30] for indicator in off_topic_indicators):
            score -= 0.1
        
        # 建议
        if score < 0.7:
            suggestions.append("建议直接切入问题核心，避免冗长的背景铺垫")
        
        return DimensionScore(
            name="相关性",
            score=min(1.0, max(0.0, score)),
            reasoning=self._format_reasoning(
                "回答与问题相关度",
                score,
                f"关键词覆盖率 {keyword_coverage*100:.0f}%" if total_concepts > 0 else "N/A"
            ),
            suggestions=suggestions,
        )
    
    def _judge_skill_appropriateness(
        self,
        query: str,
        skills: list[str],
        response: str,
    ) -> DimensionScore:
        """
        评判视角恰当性：选取的视角是否适合问题
        """
        suggestions = []
        score = 0.5
        
        if not skills:
            return DimensionScore(
                name="视角恰当性",
                score=0.0,
                reasoning="未选择任何视角",
                suggestions=["应该选择至少一个思考视角"],
            )
        
        # 定义问题类型与视角的映射
        skill_query_mapping = {
            "rujia-perspective": ["关系", "人情", "道德", "责任", "忠", "孝", "领导", "下属", "长辈", "感恩", "人际"],
            "fajia-perspective": ["制度", "规则", "管理", "考核", "绩效", "KPI", "激励", "监督", "法治"],
            "daojia-perspective": ["焦虑", "内耗", "放下", "顺其自然", "不强求", "淡定", "无为", "超脱"],
            "bingjia-perspective": ["竞争", "对手", "策略", "战略", "博弈", "进攻", "防守", "布局"],
            "mojia-perspective": ["公平", "公正", "功利", "分析", "逻辑", "论证", "判断"],
            "mingjia-perspective": ["概念", "定义", "本质", "名实", "验证", "辨别", "正名"],
            "fojia-perspective": ["烦恼", "执念", "痛苦", "解脱", "放下", "觉悟", "慈悲", "无常"],
            "shijia-perspective": ["历史", "古人", "前人", "教训", "借鉴", "兴衰", "得失"],
            "zonghengjia-perspective": ["谈判", "外交", "联盟", "联合", "说服", "游说", "借力"],
            "yinyangjia-perspective": ["平衡", "矛盾", "对立", "转化", "调和", "动态", "协调"],
        }
        
        # 检查问题是否匹配选取的视角
        query_lower = query.lower()
        matched_skills = []
        
        for skill in skills:
            keywords = skill_query_mapping.get(skill, [])
            if any(kw in query_lower for kw in keywords):
                matched_skills.append(skill)
        
        if matched_skills:
            coverage = len(matched_skills) / len(skills)
            score = 0.4 + coverage * 0.5
        else:
            # 没有明确匹配，检查是否有间接关联
            score = 0.4
        
        # 检查回答中是否体现了选取的视角
        skill_mentions = 0
        for skill in skills:
            skill_name = skill.replace("-perspective", "")
            if skill_name in response or skill.replace("-", "") in response:
                skill_mentions += 1
        
        if skills:
            mention_ratio = skill_mentions / len(skills)
            score = score * 0.7 + mention_ratio * 0.3
        
        # 建议
        if len(skills) == 1 and score < 0.6:
            suggestions.append("建议考虑多视角分析，单一视角可能不够全面")
        if score < 0.5:
            suggestions.append("选取的视角与问题关联度不高，建议重新选择")
        
        return DimensionScore(
            name="视角恰当性",
            score=min(1.0, max(0.0, score)),
            reasoning=self._format_reasoning(
                "视角选取与问题匹配度",
                score,
                f"匹配 {len(matched_skills)}/{len(skills)} 个视角"
            ),
            suggestions=suggestions,
        )
    
    def _judge_depth(self, query: str, response: str) -> DimensionScore:
        """
        评判深度：回答是否有足够的思想深度
        """
        suggestions = []
        score = 0.5
        
        # 统计回答长度
        response_length = len(response)
        min_expected_length = 100
        
        if response_length < min_expected_length:
            score -= 0.2
            suggestions.append("回答过于简短，建议增加分析和论证")
        
        # 检查是否引用了选取视角的核心概念
        depth_indicators = [
            "核心", "本质", "根本", "第一性", "原理",
            "为什么", "如何", "怎样", "应该", "不应该",
            "因为", "所以", "然而", "但是", "不过",
        ]
        
        indicator_count = sum(1 for ind in depth_indicators if ind in response)
        depth_score = min(1.0, indicator_count / 5)
        score = score * 0.5 + depth_score * 0.5
        
        # 检查是否有具体例子或引用
        has_examples = any(marker in response for marker in ["比如", "例如", "比如", "如", "案例"])
        has_quotes = any(marker in response for marker in ["说：", "言：", "曰：", "云：", "《", "》"])
        
        if has_examples:
            score = min(1.0, score + 0.1)
        if has_quotes:
            score = min(1.0, score + 0.1)
        
        # 检查是否有多层次分析
        has_multiple_layers = (
            ("首先" in response or "第一" in response) and
            ("其次" in response or "第二" in response) and
            ("最后" in response or "第三" in response)
        )
        
        if has_multiple_layers:
            score = min(1.0, score + 0.1)
        
        # 建议
        if indicator_count < 3:
            suggestions.append("建议增加更多深度分析，而不仅是表面描述")
        if not has_examples:
            suggestions.append("建议添加具体案例或实例来支撑观点")
        
        return DimensionScore(
            name="思想深度",
            score=min(1.0, max(0.0, score)),
            reasoning=self._format_reasoning(
                "回答深度",
                score,
                f"字数 {response_length}，深度指标 {indicator_count} 个"
            ),
            suggestions=suggestions,
        )
    
    def _judge_logic(self, query: str, response: str) -> DimensionScore:
        """
        评判逻辑性：论证是否清晰合理
        """
        suggestions = []
        score = 0.5
        
        # 检查逻辑连接词
        logic_connectors = {
            "递进": ["而且", "并且", "更重要的是", "此外", "同时"],
            "转折": ["但是", "然而", "不过", "然而", "可是"],
            "因果": ["因为", "所以", "因此", "导致", "致使", "由于"],
            "举例": ["比如", "例如", "如", "案例"],
            "总结": ["总之", "总而言之", "综上所述", "综上所述"],
        }
        
        connector_count = 0
        for category, connectors in logic_connectors.items():
            connector_count += sum(1 for c in connectors if c in response)
        
        logic_score = min(1.0, connector_count / 8)
        score = score * 0.4 + logic_score * 0.6
        
        # 检查是否有前后矛盾
        contradiction_pairs = [
            ("应该", "不应该"),
            ("可以", "不可以"),
            ("必须", "不必"),
            ("重要", "不重要"),
        ]
        
        has_contradiction = False
        for pos, neg in contradiction_pairs:
            if pos in response and neg in response:
                has_contradiction = True
                break
        
        if has_contradiction:
            score -= 0.2
            suggestions.append("注意检查论证中是否存在前后矛盾")
        
        # 检查是否结构清晰
        structure_markers = ["第一", "第二", "第三", "首先", "其次", "最后"]
        structure_count = sum(1 for m in structure_markers if m in response)
        
        if structure_count >= 3:
            score = min(1.0, score + 0.1)
        
        # 建议
        if connector_count < 3:
            suggestions.append("建议使用更多逻辑连接词，使论证更连贯")
        
        return DimensionScore(
            name="逻辑清晰",
            score=min(1.0, max(0.0, score)),
            reasoning=self._format_reasoning(
                "论证逻辑性",
                score,
                f"逻辑连接词 {connector_count} 个"
            ),
            suggestions=suggestions,
        )
    
    def _judge_actionability(self, query: str, response: str) -> DimensionScore:
        """
        评判可操作性：是否给出可执行的建议
        """
        suggestions = []
        score = 0.5
        
        # 检查是否包含可操作的建议
        action_indicators = [
            "建议", "可以", "应该", "不妨", "尝试",
            "第一步", "第二部", "具体做法", "操作步骤",
            "方法", "方案", "策略", "行动",
        ]
        
        indicator_count = sum(1 for ind in action_indicators if ind in response)
        action_score = min(1.0, indicator_count / 4)
        score = score * 0.5 + action_score * 0.5
        
        # 检查是否有具体数字或步骤
        has_numbers = any(char.isdigit() for char in response)
        has_steps = any(f"{i}、" in response or f"{i}." in response for i in range(1, 6))
        
        if has_numbers:
            score = min(1.0, score + 0.1)
        if has_steps:
            score = min(1.0, score + 0.15)
        
        # 检查问题是否需要可操作性
        needs_action = any(kw in query for kw in ["怎么办", "怎么处理", "如何做", "该怎么做", "下一步"])
        
        if needs_action and indicator_count == 0:
            score -= 0.2
            suggestions.append("问题询问具体做法，建议给出可操作的建议")
        
        # 建议
        if indicator_count == 0:
            suggestions.append("建议在回答末尾添加具体可行的行动建议")
        
        return DimensionScore(
            name="可操作性",
            score=min(1.0, max(0.0, score)),
            reasoning=self._format_reasoning(
                "建议可操作性",
                score,
                f"行动指标 {indicator_count} 个"
            ),
            suggestions=suggestions,
        )
    
    # =========================================================================
    # 辅助方法
    # =========================================================================
    
    def _extract_keywords(self, text: str, max_count: int = 10) -> list[str]:
        """提取关键词"""
        stopwords = {
            "的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
            "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
            "你", "会", "着", "没有", "看", "好", "自己", "这", "那",
            "什么", "怎么", "如何", "为什么", "是不是", "能不能",
        }
        
        keywords = []
        for i in range(len(text) - 1):
            word = text[i:i+2]
            if word not in stopwords and len(word) == 2 and word not in keywords:
                keywords.append(word)
                if len(keywords) >= max_count:
                    break
        
        return keywords
    
    def _format_reasoning(self, aspect: str, score: float, detail: str) -> str:
        """格式化理由"""
        return f"{aspect}得分 {score:.0%}，{detail}"
    
    def _determine_verdict(self, score: float) -> str:
        """根据得分确定评判结论"""
        if score >= self.EXCELLENT_THRESHOLD:
            return "优秀"
        elif score >= self.GOOD_THRESHOLD:
            return "良好"
        elif score >= self.ACCEPTABLE_THRESHOLD:
            return "一般"
        else:
            return "不合格"
    
    def _generate_summary(
        self,
        score: float,
        verdict: str,
        suggestions: list[str],
    ) -> str:
        """生成评判总结"""
        parts = [f"综合得分 {score:.0%}，评判结果：{verdict}。"]
        
        if suggestions:
            parts.append(f"主要建议：{suggestions[0]}")
        
        return "".join(parts)
    
    def _collect_suggestions(self, dimensions: list[DimensionScore]) -> list[str]:
        """收集所有维度的建议"""
        all_suggestions = []
        for dim in dimensions:
            if dim.suggestions:
                all_suggestions.extend(dim.suggestions)
        
        # 去重并限制数量
        seen = set()
        unique = []
        for s in all_suggestions:
            if s not in seen:
                seen.add(s)
                unique.append(s)
                if len(unique) >= 3:
                    break
        
        return unique
    
    def _build_llm_judgement_prompt(
        self,
        query: str,
        skills: list[str],
        response: str,
        context: Optional[str],
    ) -> str:
        """构建 LLM 评判 prompt"""
        return f"""你是一位专业的 AI 回答质量评审专家。请对以下回答进行深度评判。

【用户问题】
{query}

【选取的视角】
{', '.join(skills)}

【Agent 回答】
{response}

{context or ''}

请从以下维度对回答进行评判，并给出 0-1 的分数和理由：

1. **相关性 (0.3)**：回答是否针对用户问题，是否抓住了核心
2. **视角恰当性 (0.25)**：选取的视角是否适合问题，视角是否得到充分体现
3. **思想深度 (0.2)**：分析是否有足够深度，是否触及本质
4. **逻辑清晰 (0.15)**：论证是否连贯，有无前后矛盾
5. **可操作性 (0.1)**：是否给出可执行的建议

请用以下 JSON 格式返回评判结果：
{{
    "relevance": {{"score": 0.0-1.0, "reasoning": "...", "suggestions": []}},
    "skill_appropriateness": {{"score": 0.0-1.0, "reasoning": "...", "suggestions": []}},
    "depth": {{"score": 0.0-1.0, "reasoning": "...", "suggestions": []}},
    "logic": {{"score": 0.0-1.0, "reasoning": "...", "suggestions": []}},
    "actionability": {{"score": 0.0-1.0, "reasoning": "...", "suggestions": []}},
    "overall_score": 0.0-1.0,
    "verdict": "优秀|良好|一般|不合格",
    "summary": "简要总结"
}}"""
    
    def _parse_llm_judgement(self, content: str) -> Optional[dict]:
        """解析 LLM 返回的评判结果"""
        import json
        import re
        
        # 尝试提取 JSON
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        return None
    
    def _merge_judgements(
        self,
        base: Judgement,
        llm: dict,
    ) -> Judgement:
        """融合规则评判和 LLM 评判"""
        # LLM 评判权重
        LLM_WEIGHT = 0.4
        BASE_WEIGHT = 0.6
        
        def merge_dim(
            base_dim: DimensionScore,
            llm_dim: dict,
            weight: float,
        ) -> DimensionScore:
            llm_score = llm_dim.get("score", base_dim.score)
            return DimensionScore(
                name=base_dim.name,
                score=base_dim.score * BASE_WEIGHT + llm_score * LLM_WEIGHT,
                reasoning=llm_dim.get("reasoning", base_dim.reasoning),
                suggestions=llm_dim.get("suggestions", base_dim.suggestions) or base_dim.suggestions,
            )
        
        weights = self._criteria
        total_score = (
            merge_dim(base.relevance, llm.get("relevance", {}), LLM_WEIGHT).score * weights.relevance_weight
            + merge_dim(base.skill_appropriateness, llm.get("skill_appropriateness", {}), LLM_WEIGHT).score * weights.skill_appropriateness_weight
            + merge_dim(base.depth, llm.get("depth", {}), LLM_WEIGHT).score * weights.depth_weight
            + merge_dim(base.logic, llm.get("logic", {}), LLM_WEIGHT).score * weights.logic_weight
            + merge_dim(base.actionability, llm.get("actionability", {}), LLM_WEIGHT).score * weights.actionability_weight
        )
        
        verdict = llm.get("verdict", self._determine_verdict(total_score))
        summary = llm.get("summary", base.summary)
        
        suggestions = list(set(
            base.suggestions + 
            llm.get("relevance", {}).get("suggestions", []) +
            llm.get("depth", {}).get("suggestions", [])
        ))[:3]
        
        return Judgement(
            score=total_score,
            verdict=verdict,
            summary=summary,
            relevance=merge_dim(base.relevance, llm.get("relevance", {}), LLM_WEIGHT),
            skill_appropriateness=merge_dim(base.skill_appropriateness, llm.get("skill_appropriateness", {}), LLM_WEIGHT),
            depth=merge_dim(base.depth, llm.get("depth", {}), LLM_WEIGHT),
            logic=merge_dim(base.logic, llm.get("logic", {}), LLM_WEIGHT),
            actionability=merge_dim(base.actionability, llm.get("actionability", {}), LLM_WEIGHT),
            suggestions=suggestions,
            query_preview=base.query_preview,
            skills_preview=base.skills_preview,
        )


# ============================================================================
# 便捷函数
# ============================================================================

def quick_judge(
    query: str,
    skills: list[str],
    response: str,
) -> Judgement:
    """
    快速评判（使用默认配置）
    
    Usage:
        result = quick_judge(
            "我和老板意见不合...",
            ["rujia-perspective"],
            "从儒家角度看..."
        )
    """
    adjudicator = Adjudicator()
    return adjudicator.judge(query, skills, response)
