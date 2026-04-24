"""
Pytest Configuration and Fixtures
==================================

提供测试所需的公共 fixtures 和配置。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

import pytest

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from policy_router import PolicyRouter, RouterConfig, create_router
from policy_router.context import ContextManager
from policy_router.feedback import FeedbackEngine
from main_entry import DialecticEngine


# ============================================================================
# Configuration Fixtures
# ============================================================================

@pytest.fixture
def router_config() -> RouterConfig:
    """标准路由器配置。"""
    return RouterConfig(
        skills_base_path=str(PROJECT_ROOT / "skills"),
        top_k=3,
        enable_trace=True,
    )


@pytest.fixture
def router(router_config: RouterConfig) -> PolicyRouter:
    """创建 PolicyRouter 实例。"""
    return PolicyRouter(config=router_config)


@pytest.fixture
def context_manager(router_config: RouterConfig) -> ContextManager:
    """创建 ContextManager 实例。"""
    return ContextManager(config=router_config)


@pytest.fixture
def feedback_engine(context_manager: ContextManager) -> FeedbackEngine:
    """创建 FeedbackEngine 实例。"""
    return FeedbackEngine(context_manager=context_manager)


@pytest.fixture
def engine() -> DialecticEngine:
    """创建 DialecticEngine 实例。"""
    return DialecticEngine()


# ============================================================================
# Test Data Fixtures
# ============================================================================

@pytest.fixture
def all_skill_ids() -> list[str]:
    """项目中的所有 21 个 skill ID。"""
    return [
        "rujia-perspective",        # 儒家
        "fajia-perspective",        # 法家
        "daojia-perspective",       # 道家
        "bingjia-perspective",      # 兵家
        "mojia-perspective",        # 墨家
        "mingjia-perspective",      # 名家
        "zonghengjia-perspective",  # 纵横家
        "yinyangjia-perspective",   # 阴阳家
        "shijia-perspective",       # 史家
        "yijia-perspective",        # 医家
        "fojia-perspective",        # 佛家
        "lixue-perspective",        # 理学
        "xinxue-perspective",       # 心学
        "jingxue-perspective",      # 经学
        "huanglao-perspective",     # 黄老
        "nongjia-perspective",      # 农家
        "xiaoshuojia-perspective",  # 小说家
        "shushujia-perspective",    # 术数家
        "zajia-perspective",        # 杂家
        "xuanxue-perspective",      # 玄学
        "newrujia-perspective",     # 新儒
    ]


@pytest.fixture
def skill_keywords() -> dict[str, list[str]]:
    """各 skill 的典型关键词，用于测试语义匹配。"""
    return {
        "rujia-perspective": [
            "仁", "义", "礼", "智", "忠", "孝", "君子", "修身",
            "中庸", "五伦", "人伦", "道德", "责任"
        ],
        "fajia-perspective": [
            "法", "术", "势", "赏罚", "制度", "规则", "法治",
            "管理", "绩效", "激励", "监督", "合规"
        ],
        "daojia-perspective": [
            "道", "无为", "自然", "柔弱", "虚静", "逍遥",
            "齐物", "知足", "不争", "内耗", "焦虑", "顺势"
        ],
        "bingjia-perspective": [
            "兵", "战", "谋", "势", "奇正", "虚实", "战略",
            "竞争", "博弈", "知己知彼", "全胜", "伐谋"
        ],
        "mojia-perspective": [
            "兼爱", "非攻", "尚贤", "节用", "逻辑",
            "功利", "墨辩", "推理", "辩论"
        ],
        "mingjia-perspective": [
            "名", "实", "辩论", "逻辑", "白马",
            "离坚白", "合同异"
        ],
        "zonghengjia-perspective": [
            "纵横", "合纵", "连横", "外交", "游说",
            "权谋", "诸侯", "邦交"
        ],
        "yinyangjia-perspective": [
            "阴阳", "五行", "相生", "相克", "平衡",
            "调和", "变化", "循环"
        ],
        "shijia-perspective": [
            "史", "历史", "借鉴", "得失", "兴衰",
            "传统", "经验", "教训"
        ],
        "yijia-perspective": [
            "医", "养生", "调和", "平衡", "预防",
            "治未病", "调理", "健康"
        ],
        "fojia-perspective": [
            "佛", "缘起", "空", "无常", "放下",
            "慈悲", "觉悟", "禅", "因缘"
        ],
        "lixue-perspective": [
            "理", "气", "格物", "致知", "天理",
            "心性", "修养", "理学"
        ],
        "xinxue-perspective": [
            "心", "良知", "致良知", "知行合一", "心即理",
            "本心", "心学", "陆王"
        ],
        "jingxue-perspective": [
            "经", "经典", "注疏", "训诂", "经学",
            "传注", "六经", "儒学"
        ],
        "huanglao-perspective": [
            "黄老", "清静", "无为而治", "刑德", "老子",
            "黄帝", "法术", "道法"
        ],
        "nongjia-perspective": [
            "农", "耕", "食", "本业", "农家",
            "农时", "土地", "民本"
        ],
        "xiaoshuojia-perspective": [
            "小说", "故事", "叙事", "虚构", "稗官",
            "传说", "演义", "轶事"
        ],
        "shushujia-perspective": [
            "术数", "易", "占卜", "吉凶", "命理",
            "风水", "阴阳宅", "星象"
        ],
        "zajia-perspective": [
            "杂", "综合", "兼收", "博采", "折中",
            "融通", "务实", "经世"
        ],
        "xuanxue-perspective": [
            "玄学", "清谈", "有无", "本末", "老庄",
            "玄虚", "义理", "三玄"
        ],
        "newrujia-perspective": [
            "新儒", "理学", "心学", "宋明", "道统",
            "复兴", "现代化", "新儒学"
        ],
    }


@pytest.fixture
def skill_test_queries() -> dict[str, list[str]]:
    """每个 skill 对应的典型测试问题。"""
    return {
        "rujia-perspective": [
            "我和领导意见不合，但他对我有恩，我该直言吗？",
            "朋友找我帮忙但我不想帮，该如何拒绝而不伤感情？",
            "孩子不听话，不尊重长辈，我该怎么办？",
            "做人应该诚实，但有时候说真话会伤害别人，怎么办？",
        ],
        "fajia-perspective": [
            "公司的绩效考核制度执行不下去，大家都在钻空子怎么办？",
            "团队成员总是迟到早退，制度约束不了怎么办？",
            "如何设计一个激励制度让员工主动提高效率？",
            "公司有规则但领导自己破坏规则，该怎么办？",
        ],
        "daojia-perspective": [
            "我最近特别焦虑，拼命努力却感觉没有进展，该怎么办？",
            "职场中总是内卷，我该如何自处？",
            "想躺平但又不能完全躺平，内心很矛盾怎么办？",
            "做事总是用力过猛，效果反而不好，该怎么调整？",
        ],
        "bingjia-perspective": [
            "竞争对手推出了一个很有竞争力的产品，我们该如何应对？",
            "谈判陷入僵局，如何打破僵局争取有利条件？",
            "资源有限但目标很大，该如何布局取胜？",
            "面对强敌正面硬刚还是避其锋芒？",
        ],
        "mojia-perspective": [
            "两个人吵架各有道理，我该如何判断谁是对的？",
            "如何用逻辑说服一个固执的人？",
            "投资决策时如何排除情感干扰做出理性判断？",
            "辩论中对方偷换概念，我该如何反驳？",
        ],
        "mingjia-perspective": [
            "成功的企业家说'站在风口上猪都能飞'，这说法对吗？",
            "名与实到底哪个更重要？",
            "很多人追捧的概念真的是好东西吗还是只是营销？",
            "如何不被表面的说辞迷惑看清本质？",
        ],
        "zonghengjia-perspective": [
            "公司要进入新市场，是该联合盟友还是单打独斗？",
            "和客户谈判时如何争取最大利益？",
            "国际关系中如何在大国之间保持平衡？",
            "个人发展中该广结人脉还是专注提升自己？",
        ],
        "yinyangjia-perspective": [
            "工作太忙没时间休息，但停下来又焦虑怎么办？",
            "事业和家庭如何平衡？",
            "既要坚持原则又要灵活变通，如何把握度？",
            "团队里老实人吃亏但油滑的人得势，怎么看这个问题？",
        ],
        "shijia-perspective": [
            "以史为鉴，为什么历史上改革总是困难重重？",
            "历史上类似的情况最终是如何解决的？",
            "古人面对困境有哪些智慧可以借鉴？",
            "历史告诉我们什么是对的什么是错的？",
        ],
        "yijia-perspective": [
            "长期加班身体吃不消，该如何调理？",
            "压力太大导致失眠，有什么养生建议？",
            "工作拼命但身体越来越差，值不值得？",
            "亚健康状态如何通过日常习惯改善？",
        ],
        "fojia-perspective": [
            "我执念太深放不下一个人，怎么办？",
            "人生充满苦难，活着有什么意义？",
            "如何放下对结果的执念，享受过程？",
            "内心不平静，总是被杂念干扰，该怎么办？",
        ],
        "lixue-perspective": [
            "做事要'格物致知'，具体该怎么做？",
            "如何通过学习经典提升自己的修养？",
            "天理和人欲如何平衡？",
            "在纷繁复杂的世界中如何找到不变的根本道理？",
        ],
        "xinxue-perspective": [
            "面对选择时如何听从内心的声音？",
            "我的良知告诉我要这样做，但现实不允许怎么办？",
            "知行不合一，知道但做不到，问题出在哪里？",
            "如何在忙碌中保持内心的清明和定力？",
        ],
        "jingxue-perspective": [
            "读古书有用吗，如何读才能真正学到东西？",
            "如何理解古人的智慧在现代的应用？",
            "经典著作太多，该从何读起？",
            "皓首穷经研究经典是否值得？",
        ],
        "huanglao-perspective": [
            "政府应该管得多还是管得少？",
            "无为而治在企业管理中可行吗？",
            "法律和道德哪个更重要？",
            "如何在严厉管理和宽松管理之间找到平衡？",
        ],
        "nongjia-perspective": [
            "农民问题对中国发展有多重要？",
            "如何理解'民以食为天'的重要性？",
            "农业文明的智慧对现代社会有什么启示？",
            "在工业社会忽视农业会带来什么问题？",
        ],
        "xiaoshuojia-perspective": [
            "如何把复杂的事情讲得生动有趣？",
            "讲故事真的能打动人心说服别人吗？",
            "历史演义和真实历史有什么区别？",
            "如何用故事的方式教育孩子？",
        ],
        "shushujia-perspective": [
            "算命真的准吗，该不该相信？",
            "风水对中国建筑文化有什么影响？",
            "易经的智慧到底是什么？",
            "如何理性看待传统文化中的命理之学？",
        ],
        "zajia-perspective": [
            "面对复杂问题应该博采众长还是专注一家？",
            "如何综合不同学派的思想形成自己的体系？",
            "学术研究中跨学科方法是否更有优势？",
            "各种观点都有道理，如何形成自己的判断？",
        ],
        "xuanxue-perspective": [
            "魏晋名士的清谈是智慧还是逃避？",
            "玄学'有无之辩'对现代人有什么启示？",
            "如何理解'得意忘言'的境界？",
            "形而上的思考是否有实际意义？",
        ],
        "newrujia-perspective": [
            "传统文化如何现代化转型？",
            "新儒家思想对当代中国有什么意义？",
            "儒家思想能否解决现代社会的精神危机？",
            "如何在中西文化之间找到平衡点？",
        ],
    }


@pytest.fixture
def complex_queries() -> list[dict]:
    """复杂场景测试数据，可能触发多 skill 或 debate 模式。"""
    return [
        {
            "query": "我既想追求个人理想，又要对家人负责，该如何平衡？",
            "expected_intents": ["decision_analysis", "relationship"],
            "potential_skills": ["rujia-perspective", "daojia-perspective"],
            "complexity": "complex",
        },
        {
            "query": "公司要裁员，是应该严格执行KPI还是考虑人情？",
            "query_preview": "公司要裁员，是应该严格执行...",
            "expected_intents": ["ethical_dilemma", "organization"],
            "potential_skills": ["fajia-perspective", "rujia-perspective"],
            "complexity": "critical",
        },
        {
            "query": "创业过程中，道德和利益发生冲突怎么办？",
            "query_preview": "创业过程中，道德和利益发生...",
            "expected_intents": ["ethical_dilemma"],
            "potential_skills": ["rujia-perspective", "fajia-perspective", "mojia-perspective"],
            "complexity": "critical",
        },
        {
            "query": "国家治理应该以德治国还是依法治国？",
            "query_preview": "国家治理应该以德治国还是...",
            "expected_intents": ["organization", "ethics"],
            "potential_skills": ["rujia-perspective", "fajia-perspective", "huanglao-perspective"],
            "complexity": "complex",
        },
        {
            "query": "市场竞争激烈，企业是该狼性文化还是人性化管理？",
            "query_preview": "市场竞争激烈，企业是该狼性...",
            "expected_intents": ["strategy", "organization"],
            "potential_skills": ["bingjia-perspective", "daojia-perspective", "fajia-perspective"],
            "complexity": "complex",
        },
    ]


@pytest.fixture
def user_profiles() -> list[dict]:
    """测试用用户画像数据。"""
    return [
        {
            "user_id": "test_user_1",
            "preferred_skills": ["rujia-perspective"],
            "avoided_skills": [],
            "skill_weights": {"rujia-perspective": 0.8, "fajia-perspective": 0.5},
            "skill_success_counts": {"rujia-perspective": 10, "fajia-perspective": 3},
            "skill_total_counts": {"rujia-perspective": 12, "fajia-perspective": 5},
        },
        {
            "user_id": "test_user_2",
            "preferred_skills": ["daojia-perspective", "fojia-perspective"],
            "avoided_skills": ["fajia-perspective"],
            "skill_weights": {"daojia-perspective": 0.9, "fojia-perspective": 0.7},
            "skill_success_counts": {"daojia-perspective": 8, "fojia-perspective": 5},
            "skill_total_counts": {"daojia-perspective": 10, "fojia-perspective": 6},
        },
    ]


# ============================================================================
# Utility Fixtures
# ============================================================================

@pytest.fixture
def temp_session_id() -> Generator[str, None, None]:
    """生成临时 session ID。"""
    import uuid
    yield f"test_session_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def temp_user_id() -> Generator[str, None, None]:
    """生成临时 user ID。"""
    import uuid
    yield f"test_user_{uuid.uuid4().hex[:8]}"
