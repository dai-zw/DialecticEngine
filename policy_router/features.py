"""
DialecticEngine - Feature Extraction Module
============================================
负责从用户query和上下文中提取结构化特征。

Feature Categories:
1. Embedding - query向量表示
2. Intent - 意图分类
3. Domain - 领域识别
4. Complexity - 复杂度评估
5. Emotion - 情感识别

Design: 可插拔架构，支持多种提取器组合
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

from .types import (
    FeatureVector,
    QueryEmbedding,
    IntentType,
    DomainTag,
    ComplexityLevel,
    EmotionType,
    RouterConfig,
    TraceStep,
)


# ============================================================================
# KEYWORD PATTERNS
# ============================================================================

# 意图关键词映射
INTENT_KEYWORDS: dict[IntentType, list[str]] = {
    IntentType.ETHICAL_DILEMMA: [
        "应该", "该不该", "对错", "道德", "伦理", "正义", "公平",
        "价值观", "选择困难", "两难", "取舍", "是非", "善恶",
        "right or wrong", "ethics", "moral", "should i",
    ],
    IntentType.DECISION_ANALYSIS: [
        "决策", "决定", "分析", "利弊", "权衡", "选择", "方案",
        "计划", "策略", "建议", "怎么做", "如何处理",
        "decision", "choose", "option", "pros cons",
    ],
    IntentType.RELATIONSHIP: [
        "朋友", "同事", "领导", "家人", "关系", "矛盾", "冲突",
        "沟通", "误会", "信任", "合作", "人际",
        "relationship", "colleague", "boss", "family",
    ],
    IntentType.ORGANIZATION: [
        "公司", "组织", "管理", "制度", "流程", "团队", "领导力",
        "激励", "绩效", "制度", "规则", "治理",
        "company", "organization", "management", "team",
    ],
    IntentType.SELF_CULTIVATION: [
        "修身", "成长", "学习", "提升", "焦虑", "迷茫", "心态",
        "情绪", "修养", "反省", "自我", "内心",
        "growth", "anxiety", "self", "mind", "reflect",
    ],
    IntentType.METAPHYSICS: [
        "存在", "本质", "宇宙", "人生意义", "生死", "道", "天道",
        "being", "existence", "meaning", "universe", "dao",
    ],
    IntentType.STRATEGY: [
        "战略", "竞争", "博弈", "布局", "谋略", "兵法", "长期",
        "strategy", "competition", "game theory", "long-term",
    ],
    IntentType.RHETORIC: [
        "辩论", "说服", "表达", "演讲", "写作", "沟通技巧",
        "debate", "persuasion", "speech", "writing",
    ],
    IntentType.NATURE: [
        "自然", "无为", "顺其自然", "天道", "阴阳", "平衡",
        "nature", "natural", "balance", "harmony",
    ],
    IntentType.GENERAL: [],  # 默认
}

# 领域关键词映射
DOMAIN_KEYWORDS: dict[DomainTag, list[str]] = {
    DomainTag.ETHICS: [
        "伦理", "道德", "正义", "公平", "善恶", "义利",
        "ethics", "morality", "justice",
    ],
    DomainTag.GOVERNANCE: [
        "治理", "管理", "制度", "法治", "秩序",
        "governance", "institution",
    ],
    DomainTag.RELATIONSHIPS: [
        "关系", "人际", "社会", "五伦", "朋友", "君臣",
        "relationships", "social",
    ],
    DomainTag.SELF_CULTIVATION: [
        "修身", "内省", "心性", "修养", "格物", "致知",
        "cultivation", "self-improvement",
    ],
    DomainTag.STRATEGY: [
        "战略", "谋略", "兵法", "竞争", "博弈",
        "strategy", "competition", "military",
    ],
    DomainTag.DIALECTICS: [
        "辩证", "对立", "矛盾", "转化", "中庸",
        "dialectics", "contradiction",
    ],
    DomainTag.LOGIC: [
        "逻辑", "推理", "名实", "辩论", "墨辩",
        "logic", "reasoning",
    ],
    DomainTag.NATURE: [
        "自然", "天道", "无为", "阴阳", "五行",
        "nature", "dao", "cosmos",
    ],
    DomainTag.POLITICS: [
        "政治", "权力", "君权", "民本", "王道",
        "politics", "power",
    ],
    DomainTag.METAPHYSICS: [
        "本体", "存在", "心性", "天命", "道",
        "metaphysics", "being",
    ],
    DomainTag.LAW: [
        "法律", "法治", "赏罚", "刑德",
        "law", "legal",
    ],
}

# 儒家相关关键词
CONFUCIAN_KEYWORDS = [
    "仁", "义", "礼", "智", "信", "忠", "恕", "孝", "悌",
    "修身", "齐家", "治国", "平天下", "君子", "小人",
    "五伦", "中庸", "良知", "名实",
]

# 法家相关关键词
LEGALIST_KEYWORDS = [
    "法", "术", "势", "赏罚", "刑德", "制度", "规则",
    "激励", "监督", "权责", "执行", "法治",
    "法不阿贵", "循名责实",
]

# 道家相关关键词
DAOIST_KEYWORDS = [
    "道", "无为", "自然", "柔弱", "虚静", "逍遥",
    "齐物", "反者道之动", "知足", "不争",
    "无用", "心斋", "坐忘",
]

# 兵家相关关键词
MILITARY_KEYWORDS = [
    "兵", "战", "谋", "势", "奇正", "虚实", "知己知彼",
    "不战", "全胜", "伐谋",
]

# 墨家相关关键词
MOHIST_KEYWORDS = [
    "兼爱", "非攻", "尚贤", "节用", "天志", "明鬼",
    "功利", "逻辑", "墨辩",
]


# ============================================================================
# COMPLEXITY PATTERNS
# ============================================================================

COMPLEXITY_INDICATORS = {
    ComplexityLevel.SIMPLE: [
        (5, 50),      # 词数范围
    ],
    ComplexityLevel.MODERATE: [
        (20, 150),
    ],
    ComplexityLevel.COMPLEX: [
        (50, 500),
    ],
    ComplexityLevel.CRITICAL: [],  # 通过其他信号判断
}

# 复杂度提升信号
COMPLEXITY_BOOST_PATTERNS = [
    # 多重关系
    r"(但是|然而|不过|可是).{0,30}(却|也|还)",
    # 道德判断
    r"(应该|不应该|对|错|好|坏|善|恶)",
    # 多方利益
    r"(一方面|另一方面|既.{0,5}又.{0,5}|虽然.{0,10}但是)",
    # 时间跨度
    r"(过去|现在|未来|长期|短期|曾经|将来)",
    # 价值观冲突
    r"(我认为|他觉得|大家说|传统认为|现代观念)",
]


# ============================================================================
# EMOTION PATTERNS
# ============================================================================

EMOTION_PATTERNS: dict[EmotionType, list[str]] = {
    EmotionType.ANXIOUS: [
        "焦虑", "担心", "害怕", "不安", "紧张", "恐慌",
        "怎么办", "怎么办才好", "会不会", "万一",
        "anxious", "worried", "afraid",
    ],
    EmotionType.ANGRY: [
        "生气", "愤怒", "恼火", "讨厌", "怨恨", "不爽",
        "凭什么", "气死了", "太不公平",
        "angry", "frustrated", "hate",
    ],
    EmotionType.SAD: [
        "难过", "伤心", "痛苦", "失望", "沮丧", "绝望",
        "怎么办", "没意义", "不值得",
        "sad", "hurt", "disappointed",
    ],
    EmotionType.CONFUSED: [
        "困惑", "迷茫", "不懂", "不明白", "不知道该怎么",
        "怎么选", "到底", "究竟",
        "confused", "lost", "unclear",
    ],
    EmotionType.HOPEFUL: [
        "希望", "期待", "相信", "应该可以", "有可能",
        "hope", "expect", "believe",
    ],
    EmotionType.DESPERATE: [
        "绝望", "放弃", "没办法", "无路可走", "彻底",
        "desperate", "hopeless", "give up",
    ],
    EmotionType.GUILTY: [
        "内疚", "后悔", "自责", "对不起", "不应该",
        "guilty", "regret", "shouldn't have",
    ],
}


# ============================================================================
# FEATURE EXTRACTOR
# ============================================================================


class FeatureExtractor:
    """Unified feature extraction from query and context."""

    def __init__(self, config: Optional[RouterConfig] = None):
        self.config = config or RouterConfig()
        self._intent_classifier: Optional[Callable] = None
        self._emotion_classifier: Optional[Callable] = None

    def extract(
        self,
        query: str,
        context: Optional[dict] = None,
    ) -> FeatureVector:
        """Extract unified features from query.

        Args:
            query: User query text
            context: Optional context dict with historical info

        Returns:
            FeatureVector with all extracted features
        """
        start_time = time.time()

        # 1. Embedding extraction
        embedding = self._extract_embedding(query)

        # 2. Intent classification
        intent = self._classify_intent(query)

        # 3. Domain recognition
        domains = self._recognize_domains(query)

        # 4. Complexity scoring
        complexity = self._assess_complexity(query)

        # 5. Emotion recognition
        emotion = self._recognize_emotion(query)

        # 6. Additional signals
        urgency = self._assess_urgency(query)
        ambiguity = self._assess_ambiguity(query)
        dimensions = self._extract_dimensions(query)

        # 7. Historical topics
        historical_topics = self._extract_historical_topics(context)

        # 8. Temporal markers
        temporal_markers = self._extract_temporal_markers(query)

        duration = (time.time() - start_time) * 1000

        return FeatureVector(
            query_embedding=embedding,
            intent=intent,
            domains=domains,
            complexity=complexity,
            emotion=emotion,
            urgency=urgency,
            ambiguity=ambiguity,
            query_length=len(query),
            has_ethical_dimension=dimensions["ethical"],
            has_organizational_dimension=dimensions["organizational"],
            has_personal_dimension=dimensions["personal"],
            historical_topics=historical_topics,
            temporal_markers=temporal_markers,
        )

    def _extract_embedding(self, query: str) -> QueryEmbedding:
        """Extract query embedding.

        当前为占位实现。在实际系统中，这里应该调用：
        - OpenAI embedding API
        - Sentence transformers
        - 或本地embedding模型
        """
        return QueryEmbedding.from_text(query)

    def _classify_intent(self, query: str) -> IntentType:
        """Classify query intent using keyword matching + rules."""
        query_lower = query.lower()
        scores: dict[IntentType, int] = {}

        for intent, keywords in INTENT_KEYWORDS.items():
            if intent == IntentType.GENERAL:
                continue
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[intent] = score

        if not scores:
            return IntentType.GENERAL

        # 返回得分最高的意图
        return max(scores, key=scores.get)

    def _recognize_domains(self, query: str) -> frozenset[DomainTag]:
        """Recognize relevant domains from query."""
        query_lower = query.lower()
        domains: set[DomainTag] = set()

        for domain, keywords in DOMAIN_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                domains.add(domain)

        # 特殊处理：儒家/法家/道家/兵家/墨家
        if any(kw in query for kw in CONFUCIAN_KEYWORDS):
            domains.update([DomainTag.ETHICS, DomainTag.RELATIONSHIPS, DomainTag.SELF_CULTIVATION])
        if any(kw in query for kw in LEGALIST_KEYWORDS):
            domains.update([DomainTag.LAW, DomainTag.GOVERNANCE])
        if any(kw in query for kw in DAOIST_KEYWORDS):
            domains.update([DomainTag.NATURE, DomainTag.METAPHYSICS])
        if any(kw in query for kw in MILITARY_KEYWORDS):
            domains.update([DomainTag.STRATEGY])
        if any(kw in query for kw in MOHIST_KEYWORDS):
            domains.update([DomainTag.LOGIC, DomainTag.ETHICS])

        return frozenset(domains) if domains else frozenset({DomainTag.ETHICS})

    def _assess_complexity(self, query: str) -> ComplexityLevel:
        """Assess query complexity level."""
        word_count = len(query)

        # 检查复杂度提升模式
        boost_count = 0
        for pattern in COMPLEXITY_BOOST_PATTERNS:
            if re.search(pattern, query):
                boost_count += 1

        # 基础复杂度基于词数
        if word_count < 15:
            base_level = ComplexityLevel.SIMPLE
        elif word_count < 50:
            base_level = ComplexityLevel.MODERATE
        else:
            base_level = ComplexityLevel.COMPLEX

        # 根据boost模式提升复杂度
        if boost_count >= 3:
            return ComplexityLevel.CRITICAL
        elif boost_count >= 1 and base_level == ComplexityLevel.MODERATE:
            return ComplexityLevel.COMPLEX
        elif boost_count >= 2:
            return ComplexityLevel.COMPLEX

        return base_level

    def _recognize_emotion(self, query: str) -> EmotionType:
        """Recognize emotion from query."""
        query_lower = query.lower()

        for emotion, patterns in EMOTION_PATTERNS.items():
            if any(pat in query_lower for pat in patterns):
                return emotion

        return EmotionType.NEUTRAL

    def _assess_urgency(self, query: str) -> float:
        """Assess query urgency [0.0, 1.0]."""
        urgency_keywords = [
            "紧急", "马上", "立刻", "现在", "尽快",
            " deadline", "urgent", "asap", "immediately",
            "今天", "明天", "本周", "必须", "马上",
        ]
        query_lower = query.lower()

        matches = sum(1 for kw in urgency_keywords if kw in query_lower)
        return min(1.0, matches * 0.3)

    def _assess_ambiguity(self, query: str) -> float:
        """Assess query ambiguity [0.0, 1.0].

        高歧义度意味着query模糊，可能需要多个skill分析。
        """
        ambiguity_indicators = [
            r"\?{2,}",  # 多个问号
            r"怎么.{0,10}好",
            r"到底",
            r"也许.{0,10}也许",
            r"不清楚",
            r"不确定",
            r"都可以",
            r"无所谓",
        ]

        score = 0.0
        for pattern in ambiguity_indicators:
            if re.search(pattern, query):
                score += 0.2

        # 短query往往更模糊
        if len(query) < 10:
            score += 0.2

        return min(1.0, score)

    def _extract_dimensions(self, query: str) -> dict[str, bool]:
        """Extract presence of different problem dimensions."""
        query_lower = query.lower()

        return {
            "ethical": any(kw in query_lower for kw in [
                "应该", "道德", "对错", "公平", "正义", "善恶", "义利"
            ]),
            "organizational": any(kw in query_lower for kw in [
                "公司", "组织", "管理", "制度", "团队", "领导", "员工"
            ]),
            "personal": any(kw in query_lower for kw in [
                "我", "自己", "我的", "内心", "成长", "焦虑", "心态"
            ]),
        }

    def _extract_historical_topics(self, context: Optional[dict]) -> frozenset[str]:
        """Extract historical topic keywords from context."""
        if not context:
            return frozenset()

        topics: set[str] = set()

        # 从历史query中提取话题
        if "query_history" in context:
            for q in context["query_history"][-5:]:  # 最近5条
                topics.update(self._extract_topics_from_text(q))

        # 从skill历史中提取
        if "skill_history" in context:
            topics.update(context["skill_history"][-5:])

        return frozenset(topics)

    def _extract_topics_from_text(self, text: str) -> set[str]:
        """Extract topic keywords from text."""
        # 简化实现：提取所有流派关键词
        topics: set[str] = set()
        all_keywords = {
            "儒家": CONFUCIAN_KEYWORDS,
            "法家": LEGALIST_KEYWORDS,
            "道家": DAOIST_KEYWORDS,
            "兵家": MILITARY_KEYWORDS,
            "墨家": MOHIST_KEYWORDS,
        }

        for topic, keywords in all_keywords.items():
            if any(kw in text for kw in keywords):
                topics.add(topic)

        return topics

    def _extract_temporal_markers(self, query: str) -> frozenset[str]:
        """Extract temporal markers from query."""
        temporal_markers: set[str] = set()
        query_lower = query.lower()

        patterns = {
            "past": ["过去", "以前", "曾经", "曾经", "之前", "历史上", "古人"],
            "present": ["现在", "当前", "如今", "目前", "今天"],
            "future": ["未来", "将来", "以后", "以后", "明天", "长期"],
            "decision": ["决定", "决策", "选择", "取舍"],
        }

        for marker_type, keywords in patterns.items():
            if any(kw in query_lower for kw in keywords):
                temporal_markers.add(marker_type)

        return frozenset(temporal_markers)

    def create_trace_step(
        self,
        step_name: str,
        features: FeatureVector,
        duration_ms: float,
    ) -> TraceStep:
        """Create a trace step for debugging."""
        return TraceStep(
            step_name=step_name,
            step_order=0,
            input_summary={"query_length": features.query_length},
            output_summary={
                "intent": features.intent.value,
                "domains": [d.name for d in features.domains],
                "complexity": features.complexity.value,
                "emotion": features.emotion.value,
            },
            duration_ms=duration_ms,
        )


# ============================================================================
# FACTORY
# ============================================================================


def create_extractor(
    config: Optional[RouterConfig] = None,
    embedding_model: Optional[str] = None,
) -> FeatureExtractor:
    """Factory function to create configured extractor.

    Args:
        config: Router configuration
        embedding_model: Optional embedding model name (for future use)

    Returns:
        Configured FeatureExtractor
    """
    extractor = FeatureExtractor(config)

    # 可以在这里初始化真实的embedding模型
    # if embedding_model == "sentence-transformers":
    #     extractor._embedding_model = load_sentence_transformer()

    return extractor
