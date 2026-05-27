"""
DialecticEngine - 主入口
========================
接收用户输入，调度 policy_router 层进行 skill 路由决策，
并通过 DeepSeek LLM 生成回答。

架构流程:
    用户输入 → PolicyRouter.route() → 选定 Skill → DeepSeek 生成回答

使用方式:
    python main_entry.py

    或作为模块导入:
    from main_entry import DialecticEngine

    engine = DialecticEngine()
    result = engine.chat("我和老板意见不合，该直言吗？")
    print(result["response"])
"""

from __future__ import annotations

import concurrent.futures
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import sys
import os
import logging

import warnings
from dotenv import load_dotenv

load_dotenv()

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from policy_router import PolicyRouter, RouterConfig, create_router, RoutingDecision
from src.utils.integrations.deepseek_integration import DeepSeekChat
from memory_store import MemoryStore

# 长期记忆配置（可选）
LONG_TERM_MEMORY_ENABLED = os.environ.get("LONG_TERM_MEMORY_ENABLED", "false").lower() in ("1", "true", "yes")

# 日志配置
logger = logging.getLogger(__name__)


# ============================================================================
# EXECUTION PLAN EXECUTOR
# ============================================================================


class SkillExecutor:
    """根据 RoutingDecision 的 execution_plan 调用对应 Skill 生成回答。"""

    SKILL_NAME_MAP = {
        "rujia-perspective": "儒家",
        "daojia-perspective": "道家",
        "mingjia-perspective": "名家",
        "fajia-perspective": "法家",
        "mojia-perspective": "墨家",
        "zonghengjia-perspective": "纵横家",
        "yinyangjia-perspective": "阴阳家",
        "shijia-perspective": "史家",
        "yijia-perspective": "医家",
        "fojia-perspective": "佛家",
        "lixue-perspective": "理学",
        "xinxue-perspective": "心学",
        "bingjia-perspective": "兵家",
        "huanglao-perspective": "黄老",
        "jingxue-perspective": "经学",
        "nongjia-perspective": "农家",
        "xiaoshuojia-perspective": "小说家",
        "shushujia-perspective": "术数家",
        "zajia-perspective": "杂家",
        "xuanxue-perspective": "玄学",
        "newrujia-perspective": "新儒",
    }

    def __init__(self, llm: DeepSeekChat):
        self.llm = llm
        self.skills_base = ROOT / "skills"

    def execute(
        self, 
        decision: RoutingDecision, 
        user_query: str,
        memory_context: str = "",
    ) -> dict[str, Any]:
        """根据决策执行一个或多个 Skill。

        Args:
            decision: PolicyRouter 路由决策
            user_query: 原始用户问题
            memory_context: 长期记忆上下文（历史回答参考）

        Returns:
            {
                "skill_ids": [...],
                "mode": "single|multi|debate",
                "response": "LLM 生成的回答",
                "execution_plan": [...],
                "skill_outputs": [...],  # 用于 fallback
                "fusion_result": {...},   # 用于 fallback
            }
        """
        mode = decision.execution_mode.value
        selected = decision.selected_skills

        if not selected:
            return {
                "skill_ids": [],
                "mode": mode,
                "response": "抱歉，系统中没有找到合适的思考视角来处理您的问题。",
                "execution_plan": decision.execution_plan,
                "skill_outputs": [],
                "fusion_result": {"conclusion": "", "options": []},
            }

        # 多视角 / 辩论模式：链式交锋（禁止合并为单一流派回答）
        if self._is_debate_chain_mode(decision):
            return self.execute_chain(decision, user_query, memory_context)

        skill_context = self._load_skills_context(selected)

        prompt = self._build_prompt(
            user_query, 
            decision, 
            skill_context,
            memory_context=memory_context,
        )
        
        try:
            response = self.llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.warning(f"LLM 调用失败: {e}")
            response_text = f"[LLM 调用失败: {str(e)[:100]}] 抱歉，系统暂时无法生成回答。"

        # 构建 skill_outputs（用于 fallback）
        skill_outputs = [
            {
                "skill_id": skill,
                "suggestion": self._extract_suggestion(response_text, skill),
                "conclusion": self._extract_conclusion(response_text),
            }
            for skill in selected
        ]

        # 构建 fusion_result（用于 fallback）
        fusion_result = {
            "conclusion": self._extract_conclusion(response_text),
            "options": self._extract_options(response_text),
            "reasoning": decision.reasoning,
        }

        return {
            "skill_ids": selected,
            "mode": mode,
            "response": response_text,
            "execution_plan": decision.execution_plan,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "skill_outputs": skill_outputs,
            "fusion_result": fusion_result,
        }

    def _is_debate_chain_mode(self, decision: RoutingDecision) -> bool:
        """多个视角时启用顺序辩论链。"""
        return (
            len(decision.selected_skills) > 1
            and decision.execution_mode.value in ("multi", "debate")
        )

    def _get_skill_display_name(self, skill_id: str) -> str:
        return self.SKILL_NAME_MAP.get(skill_id, skill_id.replace("-perspective", ""))

    def _get_ordered_skills(
        self, decision: RoutingDecision
    ) -> tuple[list[str], dict[str, float]]:
        """按 execution_plan 的步骤顺序确定发言先后（而非按权重倒序）。"""
        selected = decision.selected_skills
        weights: dict[str, float] = {}
        ordered: list[str] = []

        if decision.execution_plan:
            steps = sorted(
                [s for s in decision.execution_plan if s.get("action") == "invoke_skill"],
                key=lambda s: s.get("step", 0),
            )
            seen: set[str] = set()
            for step in steps:
                skill_id = step.get("skill_id")
                if not skill_id or skill_id in seen:
                    continue
                ordered.append(skill_id)
                seen.add(skill_id)
                weights[skill_id] = step.get("weight", 1.0 / max(len(selected), 1))

        if not ordered:
            ordered = list(selected)
            default_w = 1.0 / max(len(ordered), 1)
            for skill_id in ordered:
                weights[skill_id] = default_w

        for skill_id in selected:
            if skill_id not in ordered:
                ordered.append(skill_id)
                weights[skill_id] = 1.0 / max(len(selected), 1)

        return ordered, weights

    def _create_debate_orchestrator(self):
        from debate_orchestrator import DebateOrchestrator

        return DebateOrchestrator(
            llm=self.llm,
            load_skill_context=self._load_skills_context,
            get_skill_display_name=self._get_skill_display_name,
            get_skill_focus=self._get_skill_focus,
            all_skill_ids=list(self.SKILL_NAME_MAP.keys()),
        )

    def execute_chain(
        self,
        decision: RoutingDecision,
        user_query: str,
        memory_context: str = "",
    ) -> dict[str, Any]:
        """大脑主持：派单、阶段总结、异议申辩、最终综合。"""
        ordered_skills, skill_weights = self._get_ordered_skills(decision)
        orchestrator = self._create_debate_orchestrator()
        result = orchestrator.run(
            user_query=user_query,
            ordered_skills=ordered_skills,
            skill_weights=skill_weights,
            memory_context=memory_context,
            mode=decision.execution_mode.value,
            callback=None,
        )
        synthesis = result.get("synthesis", "")
        return {
            **result,
            "execution_plan": decision.execution_plan,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "fusion_result": {
                "conclusion": self._extract_conclusion(synthesis or result["response"]),
                "options": self._extract_options(synthesis or result["response"]),
                "reasoning": decision.reasoning,
            },
        }

    def _get_skill_focus(self, skill_id: str) -> str:
        """获取各 skill 的核心关注点描述"""
        focus_map = {
            "rujia-perspective": "仁义礼智、修身齐家、社会秩序",
            "daojia-perspective": "道法自然、无为而治、顺势而为",
            "fajia-perspective": "法治刑赏、君主集权、实用效率",
            "mojia-perspective": "兼爱非攻、实用功利、天志明鬼",
            "mingjia-perspective": "名实相符、逻辑辨析、概念澄清",
            "yinyangjia-perspective": "阴阳调和、五行生克、动态平衡",
            "fojia-perspective": "缘起性空、放下执念、内心平静",
            "xinxue-perspective": "心即理致良知、发明本心、知行合一",
            "newrujia-perspective": "中西会通、批判继承、现代转化",
            "lixue-perspective": "格物致知、存天理灭人欲、理性修养",
            "bingjia-perspective": "战略全局、知己知彼、奇正相生",
            "shijia-perspective": "以史为鉴、古今贯通、历史智慧",
            "zajia-perspective": "兼容并蓄、博采众长、因时制宜",
            "zonghengjia-perspective": "合纵连横、游说权谋、利害权衡",
            "huanglao-perspective": "清静无为、德法并用、守雌贵柔",
            "yijia-perspective": "悬壶济世、身心同治、阴阳调和",
            "jingxue-perspective": "训诂考据、经世致用、守正传承",
            "nongjia-perspective": "耕织为本、务实重农、顺天应时",
            "xiaoshuojia-perspective": "以事寓理、体察人情、见微知著",
            "shushujia-perspective": "象数推演、天人相应、趋吉避凶",
            "xuanxue-perspective": "贵无崇本、得意忘言、名教自然",
        }
        return focus_map.get(skill_id, "独特智慧和洞见")

    def execute_stream(self, decision: RoutingDecision, user_query: str, callback=None, memory_context: str = "", search_context: str = ""):
        """流式执行 Skill，边生成边输出。

        Args:
            decision: PolicyRouter 路由决策
            user_query: 原始用户问题
            callback: 每个 token 输出的回调函数
            memory_context: 长期记忆上下文（历史回答参考）
            search_context: 联网搜索结果上下文

        Returns:
            {
                "skill_ids": [...],
                "mode": "single|multi|debate",
                "execution_plan": [...],
                "skill_outputs": [...],
                "fusion_result": {...},
            }
        """
        mode = decision.execution_mode.value
        selected = decision.selected_skills

        if not selected:
            return {
                "skill_ids": [],
                "mode": mode,
                "response": "抱歉，系统中没有找到合适的思考视角来处理您的问题。",
                "execution_plan": decision.execution_plan,
                "skill_outputs": [],
                "fusion_result": {"conclusion": "", "options": []},
            }

        # 多视角 / 辩论：顺序交锋 + 主持人综合
        if self._is_debate_chain_mode(decision):
            return self.execute_chain_stream(decision, user_query, callback, memory_context, search_context)

        skill_context = self._load_skills_context(selected)

        prompt = self._build_prompt(
            user_query, 
            decision, 
            skill_context,
            memory_context=memory_context,
            search_context=search_context,
        )

        full_response = ""
        try:
            for chunk in self.llm.stream(prompt):
                chunk_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                full_response += chunk_text
                if callback:
                    callback(chunk_text)
        except Exception as e:
            logger.warning(f"LLM 流式调用失败: {e}")
            full_response = f"[LLM 调用失败: {str(e)[:100]}] 抱歉，系统暂时无法生成回答。"

        # 构建 skill_outputs（用于 fallback）
        skill_outputs = [
            {
                "skill_id": skill,
                "suggestion": self._extract_suggestion(full_response, skill),
                "conclusion": self._extract_conclusion(full_response),
            }
            for skill in selected
        ]

        # 构建 fusion_result（用于 fallback）
        fusion_result = {
            "conclusion": self._extract_conclusion(full_response),
            "options": self._extract_options(full_response),
            "reasoning": decision.reasoning,
        }

        return {
            "skill_ids": selected,
            "mode": mode,
            "response": full_response,
            "execution_plan": decision.execution_plan,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "skill_outputs": skill_outputs,
            "fusion_result": fusion_result,
        }

    def execute_chain_stream(
        self,
        decision: RoutingDecision,
        user_query: str,
        callback=None,
        memory_context: str = "",
        search_context: str = "",
    ) -> dict[str, Any]:
        """流式大脑主持辩论。"""
        ordered_skills, skill_weights = self._get_ordered_skills(decision)
        orchestrator = self._create_debate_orchestrator()
        result = orchestrator.run(
            user_query=user_query,
            ordered_skills=ordered_skills,
            skill_weights=skill_weights,
            memory_context=memory_context,
            search_context=search_context,
            mode=decision.execution_mode.value,
            callback=callback,
        )
        synthesis = result.get("synthesis", "")
        return {
            **result,
            "execution_plan": decision.execution_plan,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "fusion_result": {
                "conclusion": self._extract_conclusion(synthesis or result["response"]),
                "options": self._extract_options(synthesis or result["response"]),
                "reasoning": decision.reasoning,
            },
        }

    def _load_skills_context(self, skill_ids: list[str]) -> str:
        """从磁盘加载已选 Skill 的 SKILL.md 内容。"""
        contexts = []
        for sid in skill_ids:
            skill_path = self.skills_base / sid / "SKILL.md"
            if skill_path.exists():
                try:
                    content = skill_path.read_text(encoding="utf-8")
                    contexts.append(f"=== {sid} ===\n{content}")
                except Exception:
                    contexts.append(f"=== {sid} ===\n[无法加载 skill 内容]")
            else:
                contexts.append(f"=== {sid} ===\n[skill 文件不存在]")
        return "\n\n".join(contexts)

    def _build_prompt(
        self,
        user_query: str,
        decision: RoutingDecision,
        skill_context: str,
        memory_context: str = "",
        search_context: str = "",
    ) -> str:
        """构建发送给 LLM 的 prompt。"""
        mode_desc = {
            "single": "单一视角",
            "multi": "多视角融合",
            "debate": "辩论对话",
        }.get(decision.execution_mode.value, "多视角")

        base_prompt = f"""你是一位深谙中国传统哲学与现代思辨方法的思考顾问。

用户问题：
{user_query}

选定的思考视角（{mode_desc}）：
{', '.join(decision.selected_skills)}

以下是选定的思考视角的详细定义：
{skill_context}

决策说明：
{decision.explanation}
"""

        if search_context:
            base_prompt += f"""
{'-' * 40}
联网搜索结果（请结合这些最新信息进行分析，但以哲学视角为核心，搜索结果作为事实补充）：
{search_context}
"""

        if memory_context:
            base_prompt += f"""
{'-' * 40}
历史回答参考（仅供参考，不一定要遵循）：
{memory_context}
"""

        base_prompt += """
请结合选定视角的定义和思维框架，针对用户问题给出深入、有见地的回答。
回答应体现所选视角独特的思维方式和核心价值。"""

        return base_prompt

    def _extract_suggestion(self, response: str, skill_id: str) -> str:
        """从回答中提取指定 skill 的建议"""
        # 简单实现：提取包含 skill 名称或核心概念的部分
        skill_name = skill_id.replace("-perspective", "")
        
        # 尝试提取第一段有实质内容的句子
        lines = response.split("\n")
        for line in lines:
            if len(line) > 20 and not line.startswith("```"):
                return line.strip()[:200]
        
        return response[:200] if response else ""

    def _extract_conclusion(self, response: str) -> str:
        """从回答中提取结论"""
        # 尝试找到结论性语句
        conclusion_indicators = ["综上所述", "总之", "总而言之", "因此", "建议：", "总结："]
        
        for indicator in conclusion_indicators:
            if indicator in response:
                idx = response.index(indicator)
                return response[idx:idx+200].strip()
        
        # 默认返回最后一段
        paragraphs = [p.strip() for p in response.split("\n\n") if p.strip()]
        if paragraphs:
            return paragraphs[-1][:200]
        
        return response[:100] if response else ""

    def _extract_options(self, response: str) -> list[str]:
        """从回答中提取选项/方案"""
        options = []
        
        # 检测编号列表
        import re
        numbered = re.findall(r'^\s*[\d一二三四五六七八九十]+[.、)）]\s*(.+)$', response, re.MULTILINE)
        options.extend(numbered[:5])
        
        # 检测"或者"/"或者可以"
        alternatives = re.findall(r'(?:或者|或者可以|还可以)\s*[:：]?\s*(.+)', response)
        options.extend(alternatives[:3])
        
        return list(dict.fromkeys(options))  # 去重保持顺序


# ============================================================================
# DIALECTIC ENGINE (MAIN CLASS)
# ============================================================================


@dataclass
class ChatMessage:
    """对话消息。"""

    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    skill_ids: list[str] = field(default_factory=list)
    decision_id: Optional[str] = None


@dataclass
class ChatSession:
    """对话会话。"""

    session_id: str
    user_id: str
    messages: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DialecticEngine:
    """DialecticEngine 主入口。

    接收用户输入，调度 policy_router 确定视角，通过 LLM 生成回答。

    Example:
        engine = DialecticEngine()
        result = engine.chat("我和老板意见不合，该直言吗？")
        print(result["response"])
    """

    def __init__(
        self,
        skills_path: str | Path = "skills",
        storage_path: str | Path | None = None,
        top_k: int = 3,
        enable_trace: bool = True,
        llm_model: str = "deepseek-chat",
        llm_temperature: float = 0.7,
        long_term_memory_enabled: bool = None,
        fallback_enabled: bool = True,
    ):
        """
        Args:
            skills_path: skills 目录路径
            storage_path: 用户画像/反馈持久化路径
            top_k: 返回最多 top_k 个 skill
            enable_trace: 是否启用路由 trace
            llm_model: DeepSeek 模型名称
            llm_temperature: LLM 温度参数
            long_term_memory_enabled: 是否启用长期记忆（默认读取环境变量）
            fallback_enabled: 是否启用 fallback 机制
        """
        self.root = ROOT
        self.skills_path = Path(skills_path)
        self.user_id = "default_user"
        self._sessions: dict[str, ChatSession] = {}

        config = RouterConfig(
            skills_base_path=str(self.skills_path),
            top_k=top_k,
            enable_trace=enable_trace,
        )

        self.router: PolicyRouter = PolicyRouter(
            config=config,
            storage_path=str(storage_path) if storage_path else None,
        )

        self.llm = DeepSeekChat(
            model=llm_model,
            temperature=llm_temperature,
            request_timeout=120,  # 120秒超时
        )

        self.executor = SkillExecutor(self.llm)

        # 长期记忆模块
        self._long_term_memory_enabled = (
            long_term_memory_enabled
            if long_term_memory_enabled is not None
            else LONG_TERM_MEMORY_ENABLED
        )
        self._long_term_memory = None
        
        # Fallback 模块
        self._fallback_enabled = fallback_enabled
        self._fallback_manager = None

    # -------------------------------------------------------------------------
    # CORE INTERFACE
    # -------------------------------------------------------------------------

    def route(self, query: str) -> RoutingDecision:
        """路由用户问题，返回决策结果（不生成回答）。"""
        return self.router.route(
            query=query,
            user_id=self.user_id,
        )

    def _get_fallback_manager(self):
        """获取或初始化 Fallback Manager"""
        if self._fallback_manager is None:
            try:
                from harness.fallback_manager import FallbackManager, FallbackConfig
                self._fallback_manager = FallbackManager(
                    llm=self.llm,
                    config=FallbackConfig(
                        low_confidence_threshold=0.4,
                        very_low_confidence_threshold=0.3,
                    )
                )
            except ImportError:
                return None
        return self._fallback_manager

    def _build_session_memory_context(
        self,
        query: str,
        session_id: str,
    ) -> str:
        """
        构建会话级别的记忆上下文：
        1. 加载同一会话的历史摘要
        2. 根据当前 query 智能选择需要获取原文的记忆
        3. 组合摘要 + 原文作为上下文

        Args:
            query: 当前用户问题
            session_id: 当前会话ID

        Returns:
            格式化后的记忆上下文文本
        """
        # 1. 获取历史摘要
        summary_context, referenced = MemoryStore.build_context_from_summaries(
            session_id=session_id,
            max_turns=5,
        )

        if not summary_context:
            return ""

        # 2. 智能判断是否需要原文
        raw_memories = MemoryStore.retrieve_relevant_raw_memories(
            query=query,
            referenced_memories=referenced,
            max_raw=2,
        )

        # 3. 构建原文上下文
        raw_context = MemoryStore.build_raw_context(raw_memories)

        # 4. 组合
        parts = [summary_context]
        if raw_context:
            parts.append(raw_context)

        return "\n".join(parts)

    def _run_with_fallback(
        self,
        query: str,
        session_id: str,
        callback=None,
    ) -> tuple[RoutingDecision, dict[str, Any]]:
        """
        运行 pipeline 并处理 fallback（并行优化版本）

        Args:
            query: 用户问题
            session_id: 会话 ID
            callback: 流式输出的回调函数

        Returns:
            (决策, 执行结果)
        """
        memory_context = ""
        decision = None
        result = None

        # 并行执行：路由决策 + 记忆检索（长期记忆 Milvus + 会话记忆文件）
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            # 提交路由任务
            routing_future = executor.submit(
                self.router.route,
                query=query,
                user_id=self.user_id,
                session_id=session_id,
            )

            # 提交长期记忆检索任务（Milvus）
            ltm_future = None
            if self._long_term_memory_enabled:
                ltm_future = executor.submit(
                    self.get_similar_memories,
                    query,
                    top_k=3,
                )

            # 提交会话记忆检索任务（本地文件）
            session_mem_future = executor.submit(
                self._build_session_memory_context,
                query,
                session_id,
            )

            # 获取路由结果（5秒超时）
            try:
                decision = routing_future.result(timeout=5)
            except concurrent.futures.TimeoutError:
                logger.warning("路由决策超时")
                from policy_router import ExecutionMode
                decision = RoutingDecision(
                    decision_id=str(uuid.uuid4()),
                    selected_skills=[],
                    execution_mode=ExecutionMode.SINGLE,
                    confidence=0.0,
                    reasoning="超时，使用默认决策",
                    skill_scores={},
                    execution_plan=[],
                )
            except Exception as e:
                logger.error(f"路由决策失败: {e}")
                from policy_router import ExecutionMode
                decision = RoutingDecision(
                    decision_id=str(uuid.uuid4()),
                    selected_skills=[],
                    execution_mode=ExecutionMode.SINGLE,
                    confidence=0.0,
                    reasoning=f"错误: {str(e)[:50]}",
                    skill_scores={},
                    execution_plan=[],
                )

            # 获取长期记忆结果（3秒超时）
            ltm_context = ""
            if ltm_future:
                try:
                    similar_memories = ltm_future.result(timeout=3)
                    if similar_memories:
                        ltm_context = self._format_memory_context(similar_memories)
                except concurrent.futures.TimeoutError:
                    logger.warning("长期记忆检索超时，跳过")
                except Exception as e:
                    logger.warning(f"长期记忆检索失败: {e}")

            # 获取会话记忆结果（2秒超时）
            session_context = ""
            try:
                session_context = session_mem_future.result(timeout=2)
            except concurrent.futures.TimeoutError:
                logger.warning("会话记忆检索超时，跳过")
            except Exception as e:
                logger.warning(f"会话记忆检索失败: {e}")

            # 组合记忆上下文：长期记忆 + 会话记忆
            parts = []
            if session_context:
                parts.append(session_context)
            if ltm_context:
                parts.append(ltm_context)
            memory_context = "\n\n".join(parts)
        
        # 执行 LLM 生成（必须等待）
        result = self.executor.execute_stream(
            decision,
            query,
            callback=callback,
            memory_context=memory_context,
        )
        
        # 评估是否需要 fallback
        if not self._fallback_enabled:
            return decision, result
        
        fallback_manager = self._get_fallback_manager()
        if fallback_manager is None:
            return decision, result
        
        # 构建 router_scores
        router_scores = [
            {"skill": sid, "score": score.total_score}
            for sid, score in decision.skill_scores.items()
        ]
        
        # 评估 fallback
        fallback_decision = fallback_manager.evaluate(
            user_input=query,
            router_scores=router_scores,
            skill_outputs=result.get("skill_outputs", []),
            fusion_result=result.get("fusion_result", {}),
        )
        
        if not fallback_decision.need_fallback:
            # 后台存储记忆（不阻塞响应）
            self._store_memory_async(query, decision, result, session_id)
            return decision, result
        
        # 执行 fallback
        logger.info(f"触发 fallback: {fallback_decision.level} - {fallback_decision.reason}")
        
        if fallback_decision.level == "retry":
            # Level 1: 重写问题重试
            rewritten_query = fallback_manager.rewrite_query(query)
            decision = self.router.route(
                query=rewritten_query,
                user_id=self.user_id,
                session_id=session_id,
            )
            result = self.executor.execute_stream(
                decision,
                rewritten_query,
                callback=callback,
                memory_context=memory_context,
            )
            result["rewritten_query"] = rewritten_query
            result["fallback_applied"] = "retry"
            
        elif fallback_decision.level == "reskill":
            # Level 2: 扩大或替换 skill
            action = fallback_decision.action
            new_skills = fallback_manager.expand_skills(
                current_skills=decision.selected_skills,
                router_scores=router_scores,
                expand_top_k=action.get("expand_top_k", 5),
                add_skills=action.get("add_analytical_skills", []),
            )
            
            # 临时替换 selected_skills
            original_skills = decision.selected_skills
            decision.selected_skills = new_skills
            
            result = self.executor.execute_stream(
                decision,
                query,
                callback=callback,
                memory_context=memory_context,
            )
            
            result["original_skills"] = original_skills
            result["fallback_applied"] = "reskill"
        
        # 存储记忆
        self._store_memory_async(query, decision, result, session_id)
        return decision, result

    def chat(self, query: str, session_id: str | None = None) -> dict[str, Any]:
        """同步接口：路由 + 生成回答。"""
        session_id = session_id or str(uuid.uuid4())
        session = self._get_or_create_session(session_id)

        decision, result = self._run_with_fallback(query, session_id)

        session.messages.append(ChatMessage(
            role="user",
            content=query,
            skill_ids=decision.selected_skills,
            decision_id=decision.decision_id,
        ))
        session.messages.append(ChatMessage(
            role="assistant",
            content=result["response"],
            skill_ids=decision.selected_skills,
            decision_id=decision.decision_id,
        ))

        result["session_id"] = session_id
        result["decision_id"] = decision.decision_id
        
        # 注意：记忆存储已在 _run_with_fallback 中通过 _store_memory_async 后台完成
        
        return result

    # -------------------------------------------------------------------------
    # SESSION MANAGEMENT
    # -------------------------------------------------------------------------

    def _get_or_create_session(self, session_id: str) -> ChatSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = ChatSession(
                session_id=session_id,
                user_id=self.user_id,
            )
        return self._sessions[session_id]

    def get_session(self, session_id: str) -> ChatSession | None:
        return self._sessions.get(session_id)

    def get_conversation_history(self, session_id: str) -> list[ChatMessage]:
        session = self._sessions.get(session_id)
        return list(session.messages) if session else []

    # -------------------------------------------------------------------------
    # FEEDBACK
    # -------------------------------------------------------------------------

    def submit_feedback(
        self,
        decision_id: str,
        rating: float,
        comment: str | None = None,
    ) -> dict[str, float]:
        """提交显式反馈（用户评分）。

        Args:
            decision_id: 来自 chat() 返回的 decision_id
            rating: 评分 [1.0, 5.0]
            comment: 可选的用户评论
        """
        session_ids = list(self._sessions.keys())
        session_id = session_ids[-1] if session_ids else "default_session"

        recent_msg = None
        for msg in reversed(self.get_conversation_history(session_id)):
            if msg.decision_id == decision_id and msg.role == "assistant":
                recent_msg = msg
                break

        skill_ids = recent_msg.skill_ids if recent_msg else []

        return self.router.submit_explicit_feedback(
            rating=rating,
            decision_id=decision_id,
            user_id=self.user_id,
            session_id=session_id,
            skill_ids=skill_ids,
            comment=comment,
        )

    def correct(self, decision_id: str, correct_skill_ids: list[str]) -> None:
        """用户纠正：某次路由选错了 skill。"""
        session_ids = list(self._sessions.keys())
        session_id = session_ids[-1] if session_ids else "default_session"

        self.router.submit_correction(
            decision_id=decision_id,
            user_id=self.user_id,
            session_id=session_id,
            correct_skill_ids=correct_skill_ids,
        )

    # -------------------------------------------------------------------------
    # DEBUG & UTILITIES
    # -------------------------------------------------------------------------

    def get_available_skills(self) -> list[str]:
        """返回所有可用 skill ID。"""
        return self.router.get_available_skills()

    def get_skill_rankings(self, query: str) -> list[tuple[str, float]]:
        """返回 query 在所有 skill 上的得分排名。"""
        return self.router.get_skill_rankings(query)

    def get_routing_explanation(self, query: str) -> str:
        """返回 query 的路由决策说明。"""
        decision = self.router.route(query, user_id=self.user_id)
        return decision.explanation

    def reload_skills(self) -> None:
        """重新扫描 skills 目录。"""
        self.router.reload_skills()

    # -------------------------------------------------------------------------
    # LONG-TERM MEMORY
    # -------------------------------------------------------------------------

    def _get_long_term_memory(self):
        """获取长期记忆模块"""
        if self._long_term_memory is not None:
            return self._long_term_memory
        
        if not self._long_term_memory_enabled:
            return None
        
        try:
            from milvus_DB.long_term_memory import init_memory
            self._long_term_memory = init_memory()
            return self._long_term_memory
        except Exception as e:
            import logging
            logger.warning(f"长期记忆模块初始化失败: {e}")
            return None

    def _store_memory_async(
        self,
        query: str,
        decision: RoutingDecision,
        result: dict[str, Any],
        session_id: str = "",
    ) -> None:
        """
        后台异步存储双份记忆（不阻塞响应）
        同时保存到长期记忆(Milvus)和本地文件系统
        """
        def _store():
            try:
                # 1. 存储到本地双文件系统（原文+摘要）
                memory_id = MemoryStore.save(
                    session_id=session_id or str(uuid.uuid4()),
                    user_query=query,
                    selected_skills=decision.selected_skills,
                    execution_mode=decision.execution_mode.value,
                    full_response=result.get("response", ""),
                    turns=result.get("chain_history", []),
                    synthesis=result.get("synthesis", ""),
                    skill_outputs=result.get("skill_outputs", []),
                    confidence=decision.confidence,
                    reasoning=decision.reasoning,
                    metadata={
                        "decision_id": decision.decision_id,
                        "fallback_applied": result.get("fallback_applied"),
                        "rewritten_query": result.get("rewritten_query"),
                    },
                )
                logger.info(f"本地双文件记忆已保存: {memory_id}")

                # 2. 存储到长期记忆(Milvus)
                self._store_to_long_term_memory(
                    query=query,
                    decision=decision,
                    response=result.get("response", ""),
                )
            except Exception as e:
                logger.warning(f"异步存储记忆失败: {e}")

        # 使用后台线程执行，不阻塞响应
        threading.Thread(target=_store, daemon=True).start()

    def _store_to_long_term_memory(
        self,
        query: str,
        decision: RoutingDecision,
        response: str,
    ) -> None:
        """存储决策到 Milvus 长期记忆"""
        memory = self._get_long_term_memory()
        if memory is None:
            return

        try:
            skill_scores = {
                sid: score.total_score
                for sid, score in decision.skill_scores.items()
            }

            memory.store(
                query=query,
                selected_skills=decision.selected_skills,
                skill_scores=skill_scores,
                confidence=decision.confidence,
                reasoning=decision.reasoning,
                response=response,
                user_id=self.user_id,
            )
        except Exception as e:
            logger.warning(f"存储长期记忆失败: {e}")

    def get_similar_memories(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict]:
        """
        获取与当前问题相似的历史记忆
        
        Args:
            query: 用户问题
            top_k: 返回数量
        
        Returns:
            相似记忆列表
        """
        memory = self._get_long_term_memory()
        if memory is None:
            return []
        
        try:
            results = memory.search(query, top_k=top_k)
            return [
                {
                    "query": r.record.query,
                    "skills": r.record.selected_skills,
                    "similarity": r.similarity,
                    "confidence": r.record.confidence,
                    "reasoning": r.record.reasoning,
                    "response": r.record.response[:200] if r.record.response else "",
                }
                for r in results
            ]
        except Exception:
            return []

    def update_memory_feedback(
        self,
        decision_id: str,
        feedback_score: float,
        helpful: bool = False,
    ) -> bool:
        """
        更新记忆的反馈信息
        
        Args:
            decision_id: 决策 ID
            feedback_score: 用户反馈评分
            helpful: 是否被采纳
        
        Returns:
            是否成功
        """
        memory = self._get_long_term_memory()
        if memory is None:
            return False
        
        try:
            # 需要先找到对应的 memory record_id
            # 这里简化处理，假设 decision_id 就是 record_id
            return memory.update_feedback(
                record_id=decision_id,
                feedback_score=feedback_score,
                helpful=helpful,
            )
        except Exception:
            return False

    def _format_memory_context(self, memories: list[dict]) -> str:
        """
        格式化记忆上下文为字符串
        
        Args:
            memories: 记忆列表
        
        Returns:
            格式化的字符串
        """
        if not memories:
            return ""
        
        lines = ["【历史回答参考】"]
        
        for i, mem in enumerate(memories, 1):
            lines.append(f"\n{i}. 相似问题：{mem['query'][:50]}...")
            lines.append(f"   选用技能：{', '.join(mem['skills'])}")
            lines.append(f"   相似度：{mem['similarity']:.0%}")
            if mem.get('response'):
                lines.append(f"   回答：{mem['response'][:150]}...")
        
        return "\n".join(lines)


# ============================================================================
# CONVENIENCE FACTORY
# ============================================================================


def create_engine(
    skills_path: str = "skills",
    top_k: int = 3,
) -> DialecticEngine:
    """快捷创建 DialecticEngine 实例。"""
    return DialecticEngine(
        skills_path=skills_path,
        top_k=top_k,
    )
