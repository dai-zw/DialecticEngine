"""
Test Fixtures Data
================

提供测试使用的静态数据。
"""

# 所有 21 个 Skill 的完整列表
ALL_SKILLS = [
    "rujia-perspective",        # 儒家
    "fajia-perspective",        # 法家
    "daojia-perspective",       # 道家
    "bingjia-perspective",       # 兵家
    "mojia-perspective",         # 墨家
    "mingjia-perspective",       # 名家
    "zonghengjia-perspective",   # 纵横家
    "yinyangjia-perspective",   # 阴阳家
    "shijia-perspective",        # 史家
    "yijia-perspective",         # 医家
    "fojia-perspective",         # 佛家
    "lixue-perspective",         # 理学
    "xinxue-perspective",        # 心学
    "jingxue-perspective",       # 经学
    "huanglao-perspective",      # 黄老
    "nongjia-perspective",       # 农家
    "xiaoshuojia-perspective",   # 小说家
    "shushujia-perspective",     # 术数家
    "zajia-perspective",         # 杂家
    "xuanxue-perspective",       # 玄学
    "newrujia-perspective",      # 新儒
]

# Skill 到中文名称的映射
SKILL_NAMES = {
    "rujia-perspective": "儒家",
    "fajia-perspective": "法家",
    "daojia-perspective": "道家",
    "bingjia-perspective": "兵家",
    "mojia-perspective": "墨家",
    "mingjia-perspective": "名家",
    "zonghengjia-perspective": "纵横家",
    "yinyangjia-perspective": "阴阳家",
    "shijia-perspective": "史家",
    "yijia-perspective": "医家",
    "fojia-perspective": "佛家",
    "lixue-perspective": "理学",
    "xinxue-perspective": "心学",
    "jingxue-perspective": "经学",
    "huanglao-perspective": "黄老",
    "nongjia-perspective": "农家",
    "xiaoshuojia-perspective": "小说家",
    "shushujia-perspective": "术数家",
    "zajia-perspective": "杂家",
    "xuanxue-perspective": "玄学",
    "newrujia-perspective": "新儒",
}

# Skill 到领域的映射
SKILL_DOMAINS = {
    "rujia-perspective": ["ethics", "relationships", "self_cultivation"],
    "fajia-perspective": ["governance", "management", "law"],
    "daojia-perspective": ["metaphysics", "self_cultivation", "nature"],
    "bingjia-perspective": ["strategy", "military", "competition"],
    "mojia-perspective": ["logic", "ethics", "rhetoric"],
    "mingjia-perspective": ["logic", "epistemology"],
    "zonghengjia-perspective": ["diplomacy", "rhetoric", "strategy"],
    "yinyangjia-perspective": ["metaphysics", "nature", "medicine"],
    "shijia-perspective": ["history", "education"],
    "yijia-perspective": ["medicine", "health", "nature"],
    "fojia-perspective": ["metaphysics", "ethics", "self_cultivation"],
    "lixue-perspective": ["metaphysics", "epistemology", "self_cultivation"],
    "xinxue-perspective": ["metaphysics", "ethics", "self_cultivation"],
    "jingxue-perspective": ["education", "literature", "ethics"],
    "huanglao-perspective": ["governance", "metaphysics", "law"],
    "nongjia-perspective": ["economics", "governance", "agriculture"],
    "xiaoshuojia-perspective": ["literature", "rhetoric"],
    "shushujia-perspective": ["metaphysics", "nature"],
    "zajia-perspective": ["general", "eclectic"],
    "xuanxue-perspective": ["metaphysics", "literature"],
    "newrujia-perspective": ["ethics", "modernization", "governance"],
}

# 对立配对（用于辩论模式测试）
OPPOSING_PAIRS = [
    ("rujia-perspective", "fajia-perspective"),  # 德治 vs 法治
    ("daojia-perspective", "fajia-perspective"),  # 无为 vs 有为
    ("rujia-perspective", "daojia-perspective"),  # 积极 vs 消极
    ("mojia-perspective", "rujia-perspective"),   # 兼爱 vs 别亲
    ("lixue-perspective", "xinxue-perspective"),  # 理学 vs 心学
]

# 核心测试查询（每个 skill 至少一个）
CORE_TEST_QUERIES = {
    "rujia-perspective": [
        "什么是仁",
        "如何修身",
        "五伦关系怎么处理",
        "中庸之道是什么",
    ],
    "fajia-perspective": [
        "如何设计绩效考核制度",
        "赏罚分明的管理原则",
        "法治vs人治",
    ],
    "daojia-perspective": [
        "无为而治的含义",
        "道法自然是什么意思",
        "如何做到不争",
    ],
    "bingjia-perspective": [
        "知己知彼百战不殆",
        "奇正之道",
        "竞争策略",
    ],
    "mojia-perspective": [
        "兼爱是什么意思",
        "逻辑推理的方法",
        "如何辩论",
    ],
}

# 复杂场景测试数据
COMPLEX_SCENARIOS = [
    {
        "name": "德治与法治之争",
        "query": "国家治理应该以德治国还是依法治国？为什么？",
        "expected_debate": True,
        "potential_skills": ["rujia-perspective", "fajia-perspective", "huanglao-perspective"],
    },
    {
        "name": "理想与现实之辩",
        "query": "追求理想重要还是现实生存重要？",
        "expected_debate": True,
        "potential_skills": ["rujia-perspective", "daojia-perspective", "fojia-perspective"],
    },
    {
        "name": "个人与集体",
        "query": "个人利益和集体利益冲突时应该怎么选择？",
        "expected_debate": True,
        "potential_skills": ["mojia-perspective", "rujia-perspective", "fajia-perspective"],
    },
    {
        "name": "管理风格选择",
        "query": "企业管理应该严格制度化管理还是人性化管理？",
        "expected_debate": True,
        "potential_skills": ["fajia-perspective", "rujia-perspective", "daojia-perspective"],
    },
    {
        "name": "传统与现代",
        "query": "传统文化思想对现代企业管理有参考价值吗？",
        "expected_debate": False,
        "potential_skills": ["shijia-perspective", "zajia-perspective", "newrujia-perspective"],
    },
]

# 情绪分类测试数据
EMOTION_TEST_QUERIES = {
    "anxious": [
        "我最近特别焦虑，工作压力很大，该怎么办？",
        "事情太多做不完，我快崩溃了",
    ],
    "angry": [
        "我对老板特别不满，他太不公平了",
        "有人总是针对我，我很生气",
    ],
    "sad": [
        "我失去了重要的人，很悲伤",
        "努力了很久还是失败了，很失落",
    ],
    "confused": [
        "我不知道该怎么选择，两个选项各有利弊",
        "人生的意义是什么，我很迷茫",
    ],
    "hopeful": [
        "我对未来充满期待，该如何规划？",
        "看到了希望，但不知道如何把握",
    ],
}

# 意图分类测试数据
INTENT_TEST_QUERIES = {
    "ethical_dilemma": [
        "朋友找我借钱但我不想借，该怎么拒绝？",
        "诚实和伤人之间的平衡",
    ],
    "decision_analysis": [
        "我有两个选择，该如何分析？",
        "投资还是储蓄，哪个更合理？",
    ],
    "relationship": [
        "和父母观念不同，总是有矛盾",
        "如何处理同事之间的关系？",
    ],
    "organization": [
        "如何建立有效的管理制度？",
        "团队执行力不强怎么办？",
    ],
    "self_cultivation": [
        "如何提升自己的修养？",
        "怎样才能成为更好的人？",
    ],
    "strategy": [
        "竞争对手很强，如何应对？",
        "如何制定有效的战略？",
    ],
}
