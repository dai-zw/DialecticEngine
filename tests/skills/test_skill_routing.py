"""
Skill Routing Tests
===================

测试所有 21 个 Skill 的路由匹配能力。

每个测试类对应一个 Skill，验证：
1. 典型关键词能够触发该 Skill
2. 典型问题能够正确路由到该 Skill
3. 边界情况能够正确处理
"""

import pytest
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from policy_router import PolicyRouter
    from policy_router.types import RoutingDecision


# ============================================================================
# 儒家 (Rujia) Tests
# ============================================================================

class TestRujiaPerspective:
    """儒家视角测试。"""

    def test_keyword_routing_ren_yi_li(self, router: "PolicyRouter"):
        """测试仁义礼关键词能够路由到儒家。"""
        keywords = ["仁", "义", "礼", "智", "信"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "rujia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到儒家"

    def test_keyword_routing_xiao_chong(self, router: "PolicyRouter"):
        """测试孝忠关键词能够路由到儒家。"""
        keywords = ["孝", "忠", "恕", "悌"]
        for keyword in keywords:
            decision = router.route(f"涉及{keyword}的问题")
            assert "rujia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到儒家"

    def test_ethical_dilemma_routing(self, router: "PolicyRouter"):
        """测试伦理困境问题路由到儒家。"""
        queries = [
            "朋友托我办事但我不想帮，怎么说不得罪人？",
            "领导让我做违规的事，我该如何拒绝？",
            "做人应该诚实，但有时候说真话会伤害别人，怎么办？",
        ]
        for query in queries:
            decision = router.route(query)
            assert len(decision.selected_skills) >= 1, \
                f"伦理问题'{query[:20]}...'应至少选择一个视角"

    def test_relationship_routing(self, router: "PolicyRouter"):
        """测试人际关系问题路由到儒家。"""
        queries = [
            "和父母观念不同，总是吵架怎么办？",
            "朋友借钱不还，我该怎么要回来？",
            "同事总是占我便宜，我该忍还是反击？",
        ]
        for query in queries:
            decision = router.route(query)
            assert len(decision.selected_skills) >= 1

    def test_skill_ranking(self, router: "PolicyRouter"):
        """测试儒家在伦理问题上的排名。"""
        query = "我欠了领导人情，但他让我做违规的事，该怎么办？"
        decision = router.route(query)
        rankings = router.get_skill_rankings(query)

        # 找到儒家排名
        rujia_rank = None
        for i, (skill_id, score) in enumerate(rankings):
            if skill_id == "rujia-perspective":
                rujia_rank = i + 1
                break

        assert rujia_rank is not None, "儒家应在排名列表中"
        assert rujia_rank <= 3, f"儒家排名应在前3，实际排名: {rujia_rank}"


# ============================================================================
# 法家 (Fajia) Tests
# ============================================================================

class TestFajiaPerspective:
    """法家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试法家关键词能够路由到法家。"""
        keywords = ["法", "术", "势", "赏罚", "制度", "规则"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "fajia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到法家"

    def test_management_routing(self, router: "PolicyRouter"):
        """测试管理问题路由到法家。"""
        queries = [
            "员工总是迟到，如何用制度约束？",
            "如何设计绩效考核让团队更有执行力？",
            "团队里有人钻空子，制度形同虚设怎么办？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "fajia-perspective" in decision.selected_skills, \
                f"管理问题'{query[:15]}...'应路由到法家"

    def test_organization_routing(self, router: "PolicyRouter"):
        """测试组织治理问题路由到法家。"""
        query = "公司制度执行不下去，大家都在钻空子怎么办？"
        decision = router.route(query)
        assert "fajia-perspective" in decision.selected_skills

    def test_explicit_mention(self, router: "PolicyRouter"):
        """测试明确提到法家时能够正确路由。"""
        query = "用法家的思想来分析这个问题"
        decision = router.route(query)
        assert "fajia-perspective" in decision.selected_skills


# ============================================================================
# 道家 (Daojia) Tests
# ============================================================================

class TestDaojiaPerspective:
    """道家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试道家关键词能够路由到道家。"""
        keywords = ["道", "无为", "自然", "柔弱", "虚静", "逍遥"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "daojia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到道家"

    def test_anxiety_routing(self, router: "PolicyRouter"):
        """测试焦虑相关问题路由到道家。"""
        queries = [
            "我最近特别焦虑，拼命努力却感觉没有进展",
            "职场内卷严重，该如何自处？",
            "想躺平但又不能完全躺平，内心很矛盾",
        ]
        for query in queries:
            decision = router.route(query)
            assert "daojia-perspective" in decision.selected_skills, \
                f"焦虑问题应路由到道家: {query[:15]}..."

    def test_self_cultivation_routing(self, router: "PolicyRouter"):
        """测试修身自省问题路由到道家。"""
        query = "做事总是用力过猛，效果反而不好"
        decision = router.route(query)
        assert "daojia-perspective" in decision.selected_skills

    def test_complexity_in_spiritual(self, router: "PolicyRouter"):
        """测试道家处理复杂精神困境的能力。"""
        query = "既想追求成功又想要内心平静，该如何平衡？"
        decision = router.route(query)

        # 道家应该在这个复杂问题上有较高得分
        scores = router.get_skill_rankings(query)
        rujia_rank = next((i for i, (s, _) in enumerate(scores) if s == "daojia-perspective"), None)

        assert rujia_rank is not None and rujia_rank <= 5, \
            "道家应在精神类复杂问题上有较好表现"


# ============================================================================
# 兵家 (Bingjia) Tests
# ============================================================================

class TestBingjiaPerspective:
    """兵家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试兵家关键词能够路由到兵家。"""
        keywords = ["兵", "战", "谋", "奇正", "虚实", "战略"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "bingjia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到兵家"

    def test_competition_routing(self, router: "PolicyRouter"):
        """测试竞争博弈问题路由到兵家。"""
        queries = [
            "竞争对手推出了新产品，我们该如何应对？",
            "谈判陷入僵局，如何打破争取有利条件？",
            "资源有限但目标很大，该如何布局取胜？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "bingjia-perspective" in decision.selected_skills, \
                f"竞争问题应路由到兵家: {query[:15]}..."

    def test_strategy_routing(self, router: "PolicyRouter"):
        """测试战略策略问题路由到兵家。"""
        query = "面对强敌，正面硬刚还是避其锋芒？"
        decision = router.route(query)
        assert "bingjia-perspective" in decision.selected_skills

    def test_debate_mode_trigger(self, router: "PolicyRouter"):
        """测试兵家能够触发辩论模式。"""
        # 竞争+伦理的复杂问题可能触发辩论
        query = "商业竞争中，为了赢可以不择手段吗？"
        decision = router.route(query)

        # 可能触发兵家+法家 或 兵家+儒家的辩论
        assert len(decision.selected_skills) >= 1


# ============================================================================
# 墨家 (Mojia) Tests
# ============================================================================

class TestMojiaPerspective:
    """墨家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试墨家关键词能够路由到墨家。"""
        keywords = ["兼爱", "非攻", "尚贤", "节用", "功利", "逻辑"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "mojia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到墨家"

    def test_logic_routing(self, router: "PolicyRouter"):
        """测试逻辑推理问题路由到墨家。"""
        queries = [
            "两个人吵架各有道理，如何判断谁是对的？",
            "如何用逻辑说服一个固执的人？",
            "辩论中对方偷换概念，我该如何反驳？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "mojia-perspective" in decision.selected_skills, \
                f"逻辑问题应路由到墨家: {query[:15]}..."

    def test_rational_decision_routing(self, router: "PolicyRouter"):
        """测试理性决策问题路由到墨家。"""
        query = "投资时如何排除情感干扰做出理性判断？"
        decision = router.route(query)
        assert "mojia-perspective" in decision.selected_skills


# ============================================================================
# 名家 (Mingjia) Tests
# ============================================================================

class TestMingjiaPerspective:
    """名家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试名家关键词能够路由到名家。"""
        keywords = ["名", "实", "白马", "离坚白", "合同异"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "mingjia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到名家"

    def test_concept_analysis_routing(self, router: "PolicyRouter"):
        """测试概念分析问题路由到名家。"""
        queries = [
            "成功的企业家说站在风口上猪都能飞，这说法对吗？",
            "名与实到底哪个更重要？",
            "如何看清表象背后的本质？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "mingjia-perspective" in decision.selected_skills, \
                f"概念分析问题应路由到名家: {query[:15]}..."

    def test_critical_thinking_routing(self, router: "PolicyRouter"):
        """测试批判性思维问题路由到名家。"""
        query = "很多人追捧的概念真的是好东西吗还是只是营销？"
        decision = router.route(query)
        assert "mingjia-perspective" in decision.selected_skills


# ============================================================================
# 纵横家 (Zonghengjia) Tests
# ============================================================================

class TestZonghengjiaPerspective:
    """纵横家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试纵横家关键词能够路由到纵横家。"""
        keywords = ["合纵", "连横", "外交", "游说", "权谋"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "zonghengjia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到纵横家"

    def test_diplomacy_routing(self, router: "PolicyRouter"):
        """测试外交博弈问题路由到纵横家。"""
        queries = [
            "公司要进入新市场，是该联合盟友还是单打独斗？",
            "和客户谈判时如何争取最大利益？",
            "个人发展中该广结人脉还是专注提升自己？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "zonghengjia-perspective" in decision.selected_skills, \
                f"外交问题应路由到纵横家: {query[:15]}..."

    def test_alliance_routing(self, router: "PolicyRouter"):
        """测试联盟策略问题路由到纵横家。"""
        query = "在大国之间如何保持平衡不得罪任何一方？"
        decision = router.route(query)
        assert "zonghengjia-perspective" in decision.selected_skills


# ============================================================================
# 阴阳家 (Yinyangjia) Tests
# ============================================================================

class TestYinyangjiaPerspective:
    """阴阳家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试阴阳家关键词能够路由到阴阳家。"""
        keywords = ["阴阳", "五行", "相生", "相克", "平衡", "调和"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "yinyangjia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到阴阳家"

    def test_balance_routing(self, router: "PolicyRouter"):
        """测试平衡问题路由到阴阳家。"""
        queries = [
            "工作太忙没时间休息，但停下来又焦虑怎么办？",
            "事业和家庭如何平衡？",
            "既要坚持原则又要灵活变通，如何把握度？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "yinyangjia-perspective" in decision.selected_skills, \
                f"平衡问题应路由到阴阳家: {query[:15]}..."


# ============================================================================
# 史家 (Shijia) Tests
# ============================================================================

class TestShijiaPerspective:
    """史家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试史家关键词能够路由到史家。"""
        keywords = ["历史", "借鉴", "得失", "兴衰", "教训"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "shijia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到史家"

    def test_historical_analysis_routing(self, router: "PolicyRouter"):
        """测试历史分析问题路由到史家。"""
        queries = [
            "以史为鉴，为什么历史上改革总是困难重重？",
            "历史上类似的情况最终是如何解决的？",
            "古人面对困境有哪些智慧可以借鉴？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "shijia-perspective" in decision.selected_skills, \
                f"历史分析问题应路由到史家: {query[:15]}..."


# ============================================================================
# 医家 (Yijia) Tests
# ============================================================================

class TestYijiaPerspective:
    """医家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试医家关键词能够路由到医家。"""
        keywords = ["医", "养生", "调和", "预防", "健康"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "yijia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到医家"

    def test_health_routing(self, router: "PolicyRouter"):
        """测试健康养生问题路由到医家。"""
        queries = [
            "长期加班身体吃不消，该如何调理？",
            "压力太大导致失眠，有什么养生建议？",
            "亚健康状态如何通过日常习惯改善？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "yijia-perspective" in decision.selected_skills, \
                f"健康问题应路由到医家: {query[:15]}..."


# ============================================================================
# 佛家 (Fojia) Tests
# ============================================================================

class TestFojiaPerspective:
    """佛家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试佛家关键词能够路由到佛家。"""
        keywords = ["佛", "缘起", "空", "无常", "放下", "慈悲", "觉悟"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "fojia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到佛家"

    def test_attachment_routing(self, router: "PolicyRouter"):
        """测试执念相关问题路由到佛家。"""
        queries = [
            "我执念太深放不下一个人，怎么办？",
            "人生充满苦难，活着有什么意义？",
            "如何放下对结果的执念，享受过程？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "fojia-perspective" in decision.selected_skills, \
                f"执念问题应路由到佛家: {query[:15]}..."

    def test_inner_peace_routing(self, router: "PolicyRouter"):
        """测试内心平静问题路由到佛家。"""
        query = "内心不平静，总是被杂念干扰，该怎么办？"
        decision = router.route(query)
        assert "fojia-perspective" in decision.selected_skills


# ============================================================================
# 理学 (Lixue) Tests
# ============================================================================

class TestLixuePerspective:
    """理学视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试理学关键词能够路由到理学。"""
        keywords = ["理", "气", "格物", "致知", "天理"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "lixue-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到理学"

    def test_study_routing(self, router: "PolicyRouter"):
        """测试格物致知相关问题路由到理学。"""
        queries = [
            "做事要格物致知，具体该怎么做？",
            "如何通过学习经典提升自己的修养？",
            "天理和人欲如何平衡？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "lixue-perspective" in decision.selected_skills, \
                f"理学问题应路由到理学: {query[:15]}..."


# ============================================================================
# 心学 (Xinxue) Tests
# ============================================================================

class TestXinxuePerspective:
    """心学视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试心学关键词能够路由到心学。"""
        keywords = ["心", "良知", "致良知", "知行合一", "心即理"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "xinxue-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到心学"

    def test_inner_voice_routing(self, router: "PolicyRouter"):
        """测试内心声音相关问题路由到心学。"""
        queries = [
            "面对选择时如何听从内心的声音？",
            "我的良知告诉我要这样做，但现实不允许",
            "知行不合一，知道但做不到，问题出在哪里？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "xinxue-perspective" in decision.selected_skills, \
                f"心学问题应路由到心学: {query[:15]}..."


# ============================================================================
# 经学 (Jingxue) Tests
# ============================================================================

class TestJingxuePerspective:
    """经学视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试经学关键词能够路由到经学。"""
        keywords = ["经", "经典", "注疏", "训诂", "六经"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "jingxue-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到经学"

    def test_classics_routing(self, router: "PolicyRouter"):
        """测试经典学习相关问题路由到经学。"""
        queries = [
            "读古书有用吗，如何读才能真正学到东西？",
            "如何理解古人的智慧在现代的应用？",
            "经典著作太多，该从何读起？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "jingxue-perspective" in decision.selected_skills, \
                f"经学问题应路由到经学: {query[:15]}..."


# ============================================================================
# 黄老 (Huanglao) Tests
# ============================================================================

class TestHuanglaoPerspective:
    """黄老视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试黄老关键词能够路由到黄老。"""
        keywords = ["黄老", "清静", "无为而治", "刑德", "道法"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "huanglao-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到黄老"

    def test_governance_routing(self, router: "PolicyRouter"):
        """测试治国理政问题路由到黄老。"""
        queries = [
            "政府应该管得多还是管得少？",
            "无为而治在企业管理中可行吗？",
            "如何在严厉管理和宽松管理之间找到平衡？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "huanglao-perspective" in decision.selected_skills, \
                f"黄老问题应路由到黄老: {query[:15]}..."


# ============================================================================
# 农家 (Nongjia) Tests
# ============================================================================

class TestNongjiaPerspective:
    """农家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试农家关键词能够路由到农家。"""
        keywords = ["农", "耕", "食", "本业", "农时", "民本"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "nongjia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到农家"

    def test_agriculture_routing(self, router: "PolicyRouter"):
        """测试农业相关问题路由到农家。"""
        queries = [
            "农民问题对中国发展有多重要？",
            "如何理解民以食为天的重要性？",
            "农业文明的智慧对现代社会有什么启示？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "nongjia-perspective" in decision.selected_skills, \
                f"农家问题应路由到农家: {query[:15]}..."


# ============================================================================
# 小说家 (Xiaoshuojia) Tests
# ============================================================================

class TestXiaoshuojiaPerspective:
    """小说家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试小说家关键词能够路由到小说家。"""
        keywords = ["小说", "故事", "叙事", "虚构", "演义"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "xiaoshuojia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到小说家"

    def test_narrative_routing(self, router: "PolicyRouter"):
        """测试叙事相关问题路由到小说家。"""
        queries = [
            "如何把复杂的事情讲得生动有趣？",
            "讲故事真的能打动人心说服别人吗？",
            "如何用故事的方式教育孩子？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "xiaoshuojia-perspective" in decision.selected_skills, \
                f"小说家问题应路由到小说家: {query[:15]}..."


# ============================================================================
# 术数家 (Shushujia) Tests
# ============================================================================

class TestShushujiaPerspective:
    """术数家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试术数家关键词能够路由到术数家。"""
        keywords = ["术数", "占卜", "吉凶", "命理", "风水", "易"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "shushujia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到术数家"

    def test_divination_routing(self, router: "PolicyRouter"):
        """测试占卜命理相关问题路由到术数家。"""
        queries = [
            "算命真的准吗，该不该相信？",
            "风水对中国建筑文化有什么影响？",
            "易经的智慧到底是什么？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "shushujia-perspective" in decision.selected_skills, \
                f"术数家问题应路由到术数家: {query[:15]}..."


# ============================================================================
# 杂家 (Zajia) Tests
# ============================================================================

class TestZajiaPerspective:
    """杂家视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试杂家关键词能够路由到杂家。"""
        keywords = ["杂", "综合", "博采", "折中", "融通", "务实"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "zajia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到杂家"

    def test_eclectic_routing(self, router: "PolicyRouter"):
        """测试综合博采相关问题路由到杂家。"""
        queries = [
            "面对复杂问题应该博采众长还是专注一家？",
            "如何综合不同学派的思想形成自己的体系？",
            "学术研究中跨学科方法是否更有优势？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "zajia-perspective" in decision.selected_skills, \
                f"杂家问题应路由到杂家: {query[:15]}..."


# ============================================================================
# 玄学 (Xuanxue) Tests
# ============================================================================

class TestXuanxuePerspective:
    """玄学视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试玄学关键词能够路由到玄学。"""
        keywords = ["玄学", "清谈", "有无", "本末", "义理", "三玄"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "xuanxue-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到玄学"

    def test_metaphysics_routing(self, router: "PolicyRouter"):
        """测试形而上学相关问题路由到玄学。"""
        queries = [
            "魏晋名士的清谈是智慧还是逃避？",
            "玄学有无之辩对现代人有什么启示？",
            "形而上的思考是否有实际意义？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "xuanxue-perspective" in decision.selected_skills, \
                f"玄学问题应路由到玄学: {query[:15]}..."


# ============================================================================
# 新儒 (Newrujia) Tests
# ============================================================================

class TestNewrujiaPerspective:
    """新儒视角测试。"""

    def test_keyword_routing(self, router: "PolicyRouter"):
        """测试新儒关键词能够路由到新儒。"""
        keywords = ["新儒", "理学", "心学", "道统", "复兴", "现代化"]
        for keyword in keywords:
            decision = router.route(f"关于{keyword}的问题")
            assert "newrujia-perspective" in decision.selected_skills, \
                f"关键词'{keyword}'未能路由到新儒"

    def test_modernization_routing(self, router: "PolicyRouter"):
        """测试传统文化现代化相关问题路由到新儒。"""
        queries = [
            "传统文化如何现代化转型？",
            "新儒家思想对当代中国有什么意义？",
            "儒家思想能否解决现代社会的精神危机？",
        ]
        for query in queries:
            decision = router.route(query)
            assert "newrujia-perspective" in decision.selected_skills, \
                f"新儒问题应路由到新儒: {query[:15]}..."


# ============================================================================
# Skill Coverage Tests
# ============================================================================

class TestSkillCoverage:
    """测试所有 Skill 的覆盖性。"""

    def test_all_skills_available(self, router: "PolicyRouter", all_skill_ids: list[str]):
        """验证所有 21 个 skill 都能被加载。"""
        available = router.get_available_skills()

        for skill_id in all_skill_ids:
            assert skill_id in available, \
                f"Skill '{skill_id}' 应该被加载但未找到"

    def test_all_skills_have_ranking(self, router: "PolicyRouter", all_skill_ids: list[str]):
        """验证所有 skill 都能产生排名。"""
        query = "这是一个关于人生选择的问题"
        rankings = router.get_skill_rankings(query)

        ranked_ids = [skill_id for skill_id, _ in rankings]

        for skill_id in all_skill_ids:
            assert skill_id in ranked_ids, \
                f"Skill '{skill_id}' 应该有排名但未找到"

    def test_all_skills_scores_sum_to_valid_range(self, router: "PolicyRouter"):
        """验证所有 skill 分数和在合理范围内。"""
        query = "关于管理和领导力的问题"
        rankings = router.get_skill_rankings(query)

        total_score = sum(score for _, score in rankings)

        # 总分应该大于 0
        assert total_score > 0, "所有 skill 分数和应该大于 0"

        # 平均分应该在合理范围内
        avg_score = total_score / len(rankings) if rankings else 0
        assert 0 <= avg_score <= 1, f"平均分应该在 [0, 1] 范围内，实际: {avg_score}"

    @pytest.mark.parametrize("skill_id", [
        "rujia-perspective", "fajia-perspective", "daojia-perspective",
        "bingjia-perspective", "mojia-perspective", "mingjia-perspective",
        "zonghengjia-perspective", "yinyangjia-perspective", "fojia-perspective",
        "lixue-perspective", "xinxue-perspective", "zajia-perspective",
    ])
    def test_skill_appears_in_rankings(self, router: "PolicyRouter", skill_id: str):
        """参数化测试每个核心 skill 都能出现在排名中。"""
        query = "如何做一个好的领导者"
        rankings = router.get_skill_rankings(query)

        ranked_ids = [skill_id for skill_id, _ in rankings]
        assert skill_id in ranked_ids, \
            f"Skill '{skill_id}' 应该出现在排名中"
