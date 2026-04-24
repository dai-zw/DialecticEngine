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

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from policy_router import PolicyRouter, RouterConfig, create_router, RoutingDecision
from src.utils.integrations.deepseek_integration import DeepSeekChat

# 长期记忆配置（可选）
LONG_TERM_MEMORY_ENABLED = os.environ.get("LONG_TERM_MEMORY_ENABLED", "false").lower() in ("1", "true", "yes")

# 日志配置
logger = logging.getLogger(__name__)


# ============================================================================
# EXECUTION PLAN EXECUTOR
# ============================================================================


class SkillExecutor:
    """根据 RoutingDecision 的 execution_plan 调用对应 Skill 生成回答。"""

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

        # 多视角模式使用链式交互
        if mode == "multi" and len(selected) > 1:
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

    def execute_chain(
        self,
        decision: RoutingDecision,
        user_query: str,
        memory_context: str = "",
    ) -> dict[str, Any]:
        """链式执行多个 Skill，实现真正的跨 skill 交互。
        
        每个 skill 依次发言，后面的 skill 会看到前面 skill 的发言，
        从而实现真正的观点碰撞和融合。
        """
        selected = decision.selected_skills
        
        # 按权重排序（从高到低）
        skill_weights = {}
        if decision.execution_plan:
            for step in decision.execution_plan:
                if step.get("action") == "invoke_skill":
                    skill_id = step.get("skill_id")
                    weight = step.get("weight", 1.0 / len(selected))
                    skill_weights[skill_id] = weight
        
        # 按权重降序排列，确保最重要的 skill 先发言
        sorted_skills = sorted(selected, key=lambda s: skill_weights.get(s, 0), reverse=True)
        
        # 收集链式对话历史
        chain_history: list[dict] = []
        
        for i, skill_id in enumerate(sorted_skills):
            is_last = (i == len(sorted_skills) - 1)
            
            # 构建当前 skill 的 prompt
            prompt = self._build_chain_prompt(
                user_query=user_query,
                decision=decision,
                current_skill=skill_id,
                chain_history=chain_history,
                is_last_skill=is_last,
                memory_context=memory_context,
            )
            
            try:
                response = self.llm.invoke(prompt)
                response_text = response.content if hasattr(response, 'content') else str(response)
            except Exception as e:
                logger.warning(f"LLM 调用失败 ({skill_id}): {e}")
                response_text = f"[LLM 调用失败: {str(e)[:100]}]"
            
            # 添加到对话历史
            chain_history.append({
                "skill_id": skill_id,
                "response": response_text,
                "weight": skill_weights.get(skill_id, 0),
            })
        
        # 合并所有输出为最终响应
        final_response = self._merge_chain_responses(chain_history, sorted_skills)
        
        # 构建 skill_outputs
        skill_outputs = [
            {
                "skill_id": item["skill_id"],
                "response": item["response"],
                "weight": item["weight"],
            }
            for item in chain_history
        ]
        
        return {
            "skill_ids": selected,
            "mode": "multi",
            "response": final_response,
            "execution_plan": decision.execution_plan,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "skill_outputs": skill_outputs,
            "chain_history": chain_history,  # 保存完整链式历史用于调试
            "fusion_result": {
                "conclusion": self._extract_conclusion(final_response),
                "options": self._extract_options(final_response),
                "reasoning": decision.reasoning,
            },
        }

    def _build_chain_prompt(
        self,
        user_query: str,
        decision: RoutingDecision,
        current_skill: str,
        chain_history: list[dict],
        is_last_skill: bool,
        memory_context: str = "",
    ) -> str:
        """构建链式交互的 prompt。
        
        Args:
            user_query: 用户问题
            decision: 路由决策
            current_skill: 当前要执行的 skill
            chain_history: 之前的对话历史
            is_last_skill: 是否是最后一个 skill
            memory_context: 长期记忆上下文
        """
        skill_name_map = {
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
        
        current_skill_name = skill_name_map.get(current_skill, current_skill)
        
        # 加载当前 skill 的上下文
        skill_context = self._load_skills_context([current_skill])
        
        # 构建对话历史部分
        history_section = ""
        if chain_history:
            history_lines = ["\n## 前面的讨论\n"]
            for item in chain_history:
                skill_n = skill_name_map.get(item["skill_id"], item["skill_id"])
                history_lines.append(f"**{skill_n}** 说：\n{item['response']}\n")
            history_section = "\n".join(history_lines)
        
        # 构建指令
        if is_last_skill:
            instruction = f"""你是**{current_skill_name}**视角的代言人。

请综合前面的讨论，从{current_skill_name}的核心立场出发，给出：
1. 对前面各视角观点的评价和回应
2. {current_skill_name}的独特贡献和超越性见解
3. 给用户的具体行动建议

回答要有{current_skill_name}的特色，体现其核心思维方式。"""
        else:
            instruction = f"""你是**{current_skill_name}**视角的代言人。

请从{current_skill_name}的核心立场出发，针对用户问题给出深入的洞察和建议。
{current_skill_name}强调{self._get_skill_focus(current_skill)}。
        
回答要点：
1. {current_skill_name}如何看待这个问题
2. 从{current_skill_name}角度的具体建议
3. 体现{current_skill_name}的智慧和洞见"""
        
        prompt = f"""你是一位深谙中国传统哲学的思考顾问，正在参与一场多视角的思想对话。

【用户问题】
{user_query}

【当前视角】
{current_skill_name}

【{current_skill_name}的思维框架】
{skill_context}

{history_section}

【你的任务】
{instruction}
"""
        
        # 添加长期记忆
        if memory_context:
            prompt += f"""
\n{'='*40}
【历史回答参考】
{memory_context}
"""
        
        return prompt

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
        }
        return focus_map.get(skill_id, "独特智慧和洞见")

    def _merge_chain_responses(
        self,
        chain_history: list[dict],
        sorted_skills: list[str],
    ) -> str:
        """合并链式响应为最终输出"""
        skill_name_map = {
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
        
        parts = []
        for i, item in enumerate(chain_history):
            skill_name = skill_name_map.get(item["skill_id"], item["skill_id"])
            parts.append(f"### {skill_name}视角\n\n{item['response']}")
        
        # 如果最后一个是综合性的（通常是权重最高的），作为压轴
        return "\n\n---\n\n".join(parts)

    def execute_stream(self, decision: RoutingDecision, user_query: str, callback=None, memory_context: str = ""):
        """流式执行 Skill，边生成边输出。

        Args:
            decision: PolicyRouter 路由决策
            user_query: 原始用户问题
            callback: 每个 token 输出的回调函数
            memory_context: 长期记忆上下文（历史回答参考）

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

        # 多视角模式使用链式交互（非流式，因为需要等待前面的响应）
        if mode == "multi" and len(selected) > 1:
            return self.execute_chain_stream(decision, user_query, callback, memory_context)

        skill_context = self._load_skills_context(selected)

        prompt = self._build_prompt(
            user_query, 
            decision, 
            skill_context,
            memory_context=memory_context,
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
    ) -> dict[str, Any]:
        """流式链式执行多个 Skill。
        
        逐个 skill 发言，每个 skill 完成后通过 callback 输出，
        用户可以看到各视角依次发言的过程。
        """
        selected = decision.selected_skills
        
        # 按权重排序
        skill_weights = {}
        if decision.execution_plan:
            for step in decision.execution_plan:
                if step.get("action") == "invoke_skill":
                    skill_id = step.get("skill_id")
                    weight = step.get("weight", 1.0 / len(selected))
                    skill_weights[skill_id] = weight
        
        sorted_skills = sorted(selected, key=lambda s: skill_weights.get(s, 0), reverse=True)
        
        chain_history: list[dict] = []
        skill_name_map = {
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
        
        for i, skill_id in enumerate(sorted_skills):
            is_last = (i == len(sorted_skills) - 1)
            skill_name = skill_name_map.get(skill_id, skill_id)
            
            # 输出当前视角标题
            if callback:
                callback(f"\n### {skill_name}视角\n\n")
            
            prompt = self._build_chain_prompt(
                user_query=user_query,
                decision=decision,
                current_skill=skill_id,
                chain_history=chain_history,
                is_last_skill=is_last,
                memory_context=memory_context,
            )
            
            full_response = ""
            try:
                for chunk in self.llm.stream(prompt):
                    chunk_text = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_response += chunk_text
                    if callback:
                        callback(chunk_text)
            except Exception as e:
                logger.warning(f"LLM 流式调用失败 ({skill_id}): {e}")
                full_response = f"[LLM 调用失败: {str(e)[:100]}]"
                if callback:
                    callback(full_response)
            
            # 分隔线（非最后一个）
            if not is_last and callback:
                callback("\n\n---\n\n")
            
            chain_history.append({
                "skill_id": skill_id,
                "response": full_response,
                "weight": skill_weights.get(skill_id, 0),
            })
        
        final_response = self._merge_chain_responses(chain_history, sorted_skills)
        
        skill_outputs = [
            {
                "skill_id": item["skill_id"],
                "response": item["response"],
                "weight": item["weight"],
            }
            for item in chain_history
        ]
        
        return {
            "skill_ids": selected,
            "mode": "multi",
            "response": final_response,
            "execution_plan": decision.execution_plan,
            "reasoning": decision.reasoning,
            "confidence": decision.confidence,
            "skill_outputs": skill_outputs,
            "chain_history": chain_history,
            "fusion_result": {
                "conclusion": self._extract_conclusion(final_response),
                "options": self._extract_options(final_response),
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
    ) -> str:
        """构建发送给 LLM 的 prompt。"""
        mode_desc = {
            "single": "单一视角",
            "multi": "多视角融合",
            "debate": "辩论对话",
        }.get(decision.execution_mode.value, "多视角")

        # 构建基础 prompt
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
        
        # 如果有长期记忆上下文，添加到 prompt 中
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

    def _run_with_fallback(
        self,
        query: str,
        session_id: str,
        callback=None,
    ) -> dict[str, Any]:
        """
        运行 pipeline 并处理 fallback
        
        Args:
            query: 用户问题
            session_id: 会话 ID
            callback: 流式输出的回调函数
        
        Returns:
            执行结果
        """
                
        # 第一次执行
        decision = self.router.route(
            query=query,
            user_id=self.user_id,
            session_id=session_id,
        )
        
                
        # 获取长期记忆上下文
        memory_context = ""
        if self._long_term_memory_enabled:
            similar_memories = self.get_similar_memories(query, top_k=3)
            if similar_memories:
                memory_context = self._format_memory_context(similar_memories)
        
                
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
        
        # 存储到长期记忆
        if self._long_term_memory_enabled:
            self._store_to_memory(
                query=query,
                decision=decision,
                response=result["response"],
            )
        
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

    def _store_to_memory(
        self,
        query: str,
        decision: RoutingDecision,
        response: str,
    ) -> None:
        """存储决策到长期记忆"""
        memory = self._get_long_term_memory()
        if memory is None:
            return
        
        try:
            # 构建 skill_scores 字典
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
            import logging
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


# ============================================================================
# INTERACTIVE CLI
# ============================================================================


def _print_banner():
    print()
    print("  ┌─────────────────────────────────────────────┐")
    print("  │         DialecticEngine · 主入口             │")
    print("  │     多视角哲学推理 · 智能路由 · DeepSeek LLM  │")
    print("  └─────────────────────────────────────────────┘")
    print()
    print("  输入你的问题，获得多视角哲学分析")
    print("  quit / exit 退出")
    print()


def _safe_print(msg: str = "", end: str = "\n"):
    try:
        print(msg, end=end)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", errors="replace").decode("utf-8"), end=end)


def run_cli():
    """交互式 CLI 入口。"""
    import shutil
    import sys

    # --- Docker 前置检查 ---
    from tools.docker_tools import check_docker_prereqs
    docker_ready = check_docker_prereqs()
    if not docker_ready:
        _safe_print("\n  [INFO] Docker not ready. Long-term memory will be unavailable.")
    else:
        _safe_print("  [OK] Docker ready.")

    # --- Bootstrap Agent 环境诊断 ---
    from milvus_DB.bootstrap import run_interactive
    bootstrap_result = run_interactive()

    # 长期记忆功能需要 Milvus + Embedding 都就绪
    memory_enabled = docker_ready and bootstrap_result.milvus_ready and bootstrap_result.embedding_configured
    if not memory_enabled:
        _safe_print("\n  [INFO] Long-term memory features are disabled due to missing dependencies.")

    cols = shutil.get_terminal_size().columns
    _print_banner()

    engine = DialecticEngine(long_term_memory_enabled=memory_enabled)
    session_id = str(uuid.uuid4())

    while True:
        try:
            user_input = input(">>> ").strip()
        except (KeyboardInterrupt, EOFError):
            _safe_print("\n\n再见！")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            _safe_print("感谢使用 DialecticEngine，再见！")
            break

        try:
            # 使用带 fallback 的流式执行
            def stream_callback(text):
                _safe_print(text, end="")
                sys.stdout.flush()
            
            decision, result = engine._run_with_fallback(user_input, session_id, callback=stream_callback)
        except Exception as e:
            logger.error(f"执行失败: {e}")
            _safe_print(f"\n[系统错误] {str(e)[:200]}\n")
            continue

        mode_map = {
            "single": "单一视角",
            "multi": "多视角融合",
            "debate": "辩论对话",
        }
        skill_name_map = {
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
        mode_text = mode_map.get(decision.execution_mode.value, decision.execution_mode.value)
        skill_names = [skill_name_map.get(s, s) for s in decision.selected_skills]

        # 构建详细的选择理由说明
        reasoning_lines = []
        reasoning_lines.append("─" * min(cols, 80))
        reasoning_lines.append(f"【视角选择分析】")
        reasoning_lines.append(f"")
        reasoning_lines.append(f"选用视角：{', '.join(skill_names)}")
        reasoning_lines.append(f"执行模式：{mode_text}")
        reasoning_lines.append(f"")

        # 显示每个视角的得分和分析
        if decision.selected_skills:
            reasoning_lines.append("视角得分详情：")
            for sid in decision.selected_skills:
                if sid in decision.skill_scores:
                    score = decision.skill_scores[sid]
                    skill_name = skill_name_map.get(sid, sid)
                    reasoning_lines.append(f"  ◆ {skill_name}：总分 {score.total_score:.2f}")
                    reasoning_lines.append(f"      - 语义匹配：{score.semantic_score:.2f}  (关键词/概念相关度)")
                    reasoning_lines.append(f"      - 规则匹配：{score.rule_bias_score:.2f}  (意图/领域相关度)")
                    reasoning_lines.append(f"      - 上下文匹配：{score.context_score:.2f}  (对话连贯性)")
                    reasoning_lines.append(f"      - 历史反馈：{score.feedback_score:.2f}  (用户偏好)")

        reasoning_lines.append(f"")

        # 置信度说明
        conf = decision.confidence
        if conf >= 0.8:
            conf_level = "很高"
            conf_desc = "问题特征与视角高度匹配，分析质量有信心"
        elif conf >= 0.65:
            conf_level = "较高"
            conf_desc = "问题特征与视角匹配较好，分析结果可参考"
        elif conf >= 0.5:
            conf_level = "中等"
            conf_desc = "存在一定不确定性，建议结合实际情况判断"
        else:
            conf_level = "较低"
            conf_desc = "问题特征不够明确，建议谨慎参考或换角度思考"

        reasoning_lines.append(f"【置信度】{conf:.1%} ({conf_level})")
        reasoning_lines.append(f"  {conf_desc}")

        # 选择理由
        reasoning_lines.append(f"")
        reasoning_lines.append(f"【选择理由】")
        reasoning_lines.append(f"  {decision.reasoning}")

        # 执行模式说明
        reasoning_lines.append(f"")
        reasoning_lines.append(f"【执行说明】")
        if decision.execution_mode.value == "single":
            reasoning_lines.append(f"  采用单一视角深入分析")
        elif decision.execution_mode.value == "multi":
            reasoning_lines.append(f"  采用多视角融合分析，综合各学派洞见")
            if decision.execution_plan:
                for step in decision.execution_plan:
                    if step.get("action") == "invoke_skill":
                        skill_n = skill_name_map.get(step.get("skill_id", ""), step.get("skill_id", ""))
                        weight = step.get("weight", 0)
                        reasoning_lines.append(f"    - {skill_n} (权重: {weight:.0%})")
        elif decision.execution_mode.value == "debate":
            reasoning_lines.append(f"  采用辩论对话模式，呈现对立视角的碰撞")
            if decision.debate_pairs:
                for pro, con in decision.debate_pairs:
                    pro_n = skill_name_map.get(pro, pro)
                    con_n = skill_name_map.get(con, con)
                    reasoning_lines.append(f"    - {pro_n} vs {con_n}")

        reasoning_lines.append("")
        _safe_print("\n".join(reasoning_lines))

        # 输出分隔线
        _safe_print("─" * min(cols, 80))
        _safe_print("回答：")
        sys.stdout.flush()

        _safe_print()  # 换行
        _safe_print("─" * min(cols, 80))
        _safe_print()


if __name__ == "__main__":
    run_cli()
