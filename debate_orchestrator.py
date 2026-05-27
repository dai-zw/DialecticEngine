"""
辩论主持引擎：大脑（主持人）调度流派发言人，发言人仅发言不总结。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# 发言人禁止输出的章节标题（由主持人综合）
FORBIDDEN_SPEAKER_SECTIONS = (
    "综上所述",
    "最终建议",
    "最终结论",
    "综合建议",
    "辩证综合",
    "给用户的建议",
)


@dataclass
class DebateTurn:
    """单条发言/申辩记录"""

    skill_id: str
    phase: str  # speak | rebuttal_defense | rebuttal_reply | floor
    host_instruction: str
    context_brief: str
    speech: str
    host_summary: str = ""


@dataclass
class DebateSession:
    """整场辩论状态（仅主持人维护摘要链）"""

    user_query: str
    ordered_skills: list[str]
    turns: list[DebateTurn] = field(default_factory=list)
    host_brief_for_next: str = ""
    rebuttal_rounds: int = 0
    search_context: str = ""
    opening_analysis: str = ""


class DebateOrchestrator:
    """
    大脑主持模型：
    - 主持人：派单、阶段总结、检测异议、安排申辩、最终综合
    - 发言人：只按主持人指令发言，不做全场总结
    """

    MAX_OBJECTION_THREADS = 3
    MAX_REBUTTAL_PER_THREAD = 2
    MAX_TOTAL_REBUTTAL_ROUNDS = 6

    def __init__(
        self,
        llm: Any,
        load_skill_context: Callable[[list[str]], str],
        get_skill_display_name: Callable[[str], str],
        get_skill_focus: Callable[[str], str],
        all_skill_ids: Optional[list[str]] = None,
    ):
        self.llm = llm
        self.load_skill_context = load_skill_context
        self.get_skill_display_name = get_skill_display_name
        self.get_skill_focus = get_skill_focus
        self.all_skill_ids = all_skill_ids or []

    def run(
        self,
        user_query: str,
        ordered_skills: list[str],
        skill_weights: dict[str, float],
        memory_context: str = "",
        search_context: str = "",
        mode: str = "multi",
        callback: Optional[Callable[[str], None]] = None,
    ) -> dict[str, Any]:
        session = DebateSession(user_query=user_query, ordered_skills=ordered_skills)
        session.search_context = search_context

        self._emit(callback, f"### 【主持人】开场安排\n\n")
        opening = self._host_opening_plan(session, memory_context, callback)
        session.opening_analysis = opening
        self._emit(callback, f"{opening}\n\n---\n\n")

        # 主发言轮次：每位发言后由主持人总结，下一位只收摘要
        for index, skill_id in enumerate(ordered_skills):
            name = self.get_skill_display_name(skill_id)
            self._emit(callback, f"### {name}（第 {index + 1} 轮·发言）\n\n")

            instruction = self._host_instruction_for_speaker(
                session, skill_id, index, memory_context
            )
            speech = self._speaker_speak(
                session, skill_id, instruction, session.host_brief_for_next, callback
            )
            speech = self._strip_forbidden_sections(speech)

            self._emit(callback, f"\n\n---\n\n### 【主持人】第 {index + 1} 轮阶段小结\n\n")
            host_summary = self._host_summarize_turn(
                session, skill_id, speech, index, memory_context, callback
            )

            turn = DebateTurn(
                skill_id=skill_id,
                phase="speak",
                host_instruction=instruction,
                context_brief=session.host_brief_for_next,
                speech=speech,
                host_summary=host_summary,
            )
            session.turns.append(turn)
            session.host_brief_for_next = self._host_build_cumulative_brief(session)
            self._emit(callback, f"{host_summary}\n\n---\n\n")

        # 检测异议并安排申辩（带全局轮次限制与收敛检测）
        # 主持人也可在此阶段召唤额外流派
        seen_objection_pairs: set[tuple[str, str]] = set()
        summoned_skills: list[str] = []
        for _ in range(self.MAX_OBJECTION_THREADS):
            if session.rebuttal_rounds >= self.MAX_TOTAL_REBUTTAL_ROUNDS:
                self._emit(callback, "### 【主持人】辩论轮次已达上限，进入最终综合。\n\n")
                break

            objections, new_skills = self._host_detect_objections(session, memory_context)

            for summon_info in new_skills:
                skill_id = summon_info["skill_id"] if isinstance(summon_info, dict) else summon_info
                reason = summon_info.get("reason", "") if isinstance(summon_info, dict) else ""
                if skill_id not in session.ordered_skills and skill_id not in summoned_skills:
                    summoned_skills.append(skill_id)
                    session.ordered_skills.append(skill_id)
                    name = self.get_skill_display_name(skill_id)
                    reason_text = f"\n\n> 召唤理由：{reason}\n\n" if reason else "\n\n"
                    self._emit(callback, f"### 【主持人】召唤额外流派：{name}{reason_text}")
                    summon_instruction = self._host_instruction_for_summoned(
                        session, skill_id, memory_context
                    )
                    self._emit(callback, f"### {name}（受邀发言）\n\n")
                    speech = self._speaker_speak(
                        session, skill_id, summon_instruction,
                        session.host_brief_for_next, callback
                    )
                    speech = self._strip_forbidden_sections(speech)

                    self._emit(callback, f"\n\n---\n\n### 【主持人】{name} 发言小结\n\n")
                    host_summary = self._host_summarize_turn(
                        session, skill_id, speech, len(session.turns), memory_context, callback
                    )

                    turn = DebateTurn(
                        skill_id=skill_id,
                        phase="summoned",
                        host_instruction=summon_instruction,
                        context_brief=session.host_brief_for_next,
                        speech=speech,
                        host_summary=host_summary,
                    )
                    session.turns.append(turn)
                    session.host_brief_for_next = self._host_build_cumulative_brief(session)
                    self._emit(callback, f"{host_summary}\n\n---\n\n")

            if not objections:
                break

            # 过滤掉已经辩论过的 skill 对（避免循环）
            new_objections = []
            for obj in objections:
                pair = (obj["from_skill"], obj["target_skill"])
                if pair not in seen_objection_pairs:
                    new_objections.append(obj)
                    seen_objection_pairs.add(pair)

            if not new_objections:
                self._emit(callback, "### 【主持人】现有分歧已充分讨论，进入最终综合。\n\n")
                break

            for obj in new_objections[:1]:  # 每轮只处理一个异议，避免爆发
                if session.rebuttal_rounds >= self.MAX_TOTAL_REBUTTAL_ROUNDS:
                    break
                self._run_rebuttal_thread(session, obj, memory_context, callback)

        self._emit(callback, "### 辩证综合（主持人）\n\n")
        synthesis = self._host_final_synthesis(session, memory_context, callback)

        transcript = self._format_transcript(session, opening)
        final_response = f"{transcript}\n\n---\n\n### 辩证综合（主持人）\n\n{synthesis}"

        skill_outputs = [
            {
                "skill_id": t.skill_id,
                "response": t.speech,
                "weight": skill_weights.get(t.skill_id, 0),
                "phase": t.phase,
            }
            for t in session.turns
        ]

        return {
            "skill_ids": ordered_skills,
            "mode": mode,
            "response": final_response,
            "skill_outputs": skill_outputs,
            "chain_history": [
                {
                    "skill_id": t.skill_id,
                    "response": t.speech,
                    "host_summary": t.host_summary,
                    "phase": t.phase,
                }
                for t in session.turns
            ],
            "synthesis": synthesis,
            "host_opening": opening,
        }

    def _emit(self, callback: Optional[Callable[[str], None]], text: str) -> None:
        if callback:
            callback(text)

    def _llm_invoke(self, prompt: str) -> str:
        try:
            response = self.llm.invoke(prompt)
            return response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            logger.warning("主持人/发言人 LLM 调用失败: %s", e)
            return f"[调用失败: {str(e)[:80]}]"

    def _llm_stream(
        self, prompt: str, callback: Optional[Callable[[str], None]]
    ) -> str:
        full = ""
        try:
            for chunk in self.llm.stream(prompt):
                text = chunk.content if hasattr(chunk, "content") else str(chunk)
                full += text
                self._emit(callback, text)
        except Exception as e:
            logger.warning("流式调用失败: %s", e)
            full = f"[调用失败: {str(e)[:80]}]"
            self._emit(callback, full)
        return full

    def _llm(
        self, prompt: str, callback: Optional[Callable[[str], None]]
    ) -> str:
        if callback:
            return self._llm_stream(prompt, callback)
        return self._llm_invoke(prompt)

    @staticmethod
    def _parse_json_object(text: str) -> dict[str, Any]:
        text = text.strip()
        fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if fence:
            text = fence.group(1).strip()
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    def _host_opening_plan(
        self,
        session: DebateSession,
        memory_context: str,
        callback: Optional[Callable[[str], None]],
    ) -> str:
        names = [self.get_skill_display_name(s) for s in session.ordered_skills]
        all_names = [self.get_skill_display_name(s) for s in self.all_skill_ids]
        all_skills_info = "\n".join(
            f"- {self.get_skill_display_name(s)}（{self.get_skill_focus(s)}）"
            for s in self.all_skill_ids
        )
        prompt = f"""你是本场辩论的**主持人（大脑）**，负责调度发言人，自己不持流派立场。

【用户问题】
{session.user_query}

【已确定发言顺序】
{chr(10).join(f"{i+1}. {n}" for i, n in enumerate(names))}

【系统可用流派全览】
{all_skills_info}

重要：在辩论过程中，如果你认为当前发言的流派不足以覆盖问题的某个重要维度，你可以在异议检测阶段**召唤额外流派**加入讨论。例如：若辩论涉及"战略博弈"但当前无兵家视角，你可以召唤兵家；若涉及"身心健康"但无医家视角，你可以召唤医家。召唤后该流派将作为新发言人加入辩论。

请用 Markdown 输出以下内容：

## 用户问题核心分析
**必须忠实于用户表述，不要用自己的理解替换用户的问题。**
- 逐字或近乎逐字地复述用户明确提出的核心问题或核心矛盾（如果用户说了"讨论的核心是X"，就写X，不要改成Y）
- 列出用户问题中涉及的具体事实条件（数字、时间节点、人名、机构名等）
- 指出用户当前信息中哪些是确定的、哪些是不确定的

## 本场安排
- 简要说明辩论推进顺序
- 提醒各发言人必须围绕用户真正想讨论的问题发言，不要偏离到用户未提及的方向

## 对各发言人的首轮指令要点
- 每位发言人只需告知：用户的核心问题是什么、此前发言的要点（如有）
- **不要替发言人决定应该回应哪些维度、从什么角度切入**——这是学派自主判断的领域
- 仅提醒：必须紧扣用户问题的具体情境，禁止泛泛而谈
- 禁止发言人做「全场总结」或「最终建议」

## 辩论规则提醒（发言人只做发言，由你总结）

不要代替发言人发言，不要给出最终建议。"""
        if memory_context:
            prompt += f"\n【历史参考】\n{memory_context}\n"
        return self._llm(prompt, callback)

    def _host_instruction_for_speaker(
        self,
        session: DebateSession,
        skill_id: str,
        turn_index: int,
        memory_context: str,
    ) -> str:
        name = self.get_skill_display_name(skill_id)
        focus = self.get_skill_focus(skill_id)
        prompt = f"""你是辩论**主持人（大脑）**。请为下一位发言人生成简要指令，不要自己发言。

【用户问题】
{session.user_query}

【本轮发言人】{name}（第 {turn_index + 1} 位，核心关注：{focus}）

【此前主持人掌握的摘要】
{session.host_brief_for_next or "（尚无，本场第一位发言人）"}

要求：
- 简要告知发言人用户的核心问题是什么，让发言人自行决定从其流派视角如何切入
- **不要替发言人指定应回应哪些维度、从什么角度论证**——学派有自己的思想体系，应自主选择切入点
- 若 turn_index > 0，仅提醒发言人注意前述发言中的分歧点，但不要指定如何回应
- 明确禁止发言人做「全场总结」或「最终建议」
- 指令控制在3条以内，保持简洁
"""
        if memory_context:
            prompt += f"\n【历史参考】\n{memory_context}\n"
        return self._llm_invoke(prompt)

    def _speaker_speak(
        self,
        session: DebateSession,
        skill_id: str,
        host_instruction: str,
        context_brief: str,
        callback: Optional[Callable[[str], None]],
    ) -> str:
        name = self.get_skill_display_name(skill_id)
        skill_context = self.load_skill_context([skill_id])
        focus = self.get_skill_focus(skill_id)

        if not context_brief.strip():
            task = f"""你是**{name}**发言人。请基于你的流派思想体系，对用户问题进行独立立论。

【主持人提供的用户核心问题】
{host_instruction}

要求：
- 从你的流派核心思想出发，自主选择最合适的切入角度和论证结构
- 必须紧扣用户问题的具体情境，用你流派的智慧回应用户的真实困惑
- 可以自由组织你的论证结构，不必拘泥于固定格式
- 禁止：综合建议、最终结论、替用户做决定、总结其他流派。"""
        else:
            task = f"""你是**{name}**发言人。此前已有其他流派发言，请基于你的流派思想体系进行回应。

【主持人提供的用户核心问题】
{host_instruction}

【此前发言摘要】
{context_brief}

要求：
- 从你的流派核心思想出发，自主选择回应的角度和方式
- 你可以赞同、质疑或补充前述发言，但必须基于你流派自身的理论逻辑
- 必须紧扣用户问题的具体情境，不要偏离到用户未提及的方向
- 可以自由组织你的论证结构，不必拘泥于固定格式
- 禁止：全场总结、最终建议、综合各派观点、替用户做决定。"""

        prompt = f"""【用户问题】
{session.user_query}

【你的流派】{name}（核心关注：{focus}）

【流派知识】
{skill_context}
"""
        if session.search_context:
            prompt += f"""
【联网搜索结果（作为事实补充，以哲学视角为核心）】
{session.search_context}
"""

        prompt += f"""
【你的任务】
{task}
"""
        return self._llm(prompt, callback)

    def _host_summarize_turn(
        self,
        session: DebateSession,
        skill_id: str,
        speech: str,
        turn_index: int,
        memory_context: str,
        callback: Optional[Callable[[str], None]],
    ) -> str:
        name = self.get_skill_display_name(skill_id)
        prompt = f"""你是辩论**主持人（大脑）**。请对刚结束的发言做阶段小结，供后续发言人使用。

【用户问题】
{session.user_query}

【刚结束的发言人】{name}
【发言内容】
{speech}

请用 Markdown 输出：
## 本轮要点摘要（客观，300字内）
## 遗留分歧
## 给下一位发言人的关注点

不要站队，不要给用户的最终建议。
"""
        if memory_context:
            prompt += f"\n【历史参考】\n{memory_context}\n"
        return self._llm(prompt, callback)

    def _host_build_cumulative_brief(self, session: DebateSession) -> str:
        parts = [f"【用户问题】{session.user_query}\n"]
        if session.opening_analysis:
            parts.append(f"【主持人开场核心分析】\n{session.opening_analysis}\n")
        for i, turn in enumerate(session.turns):
            name = self.get_skill_display_name(turn.skill_id)
            parts.append(
                f"### 第{i+1}位 {name} 主持人摘要\n{turn.host_summary}\n"
            )
        return "\n".join(parts)

    def _host_detect_objections(
        self, session: DebateSession, memory_context: str
    ) -> tuple[list[dict[str, Any]], list[str]]:
        summaries = self._host_build_cumulative_brief(session)
        rebuttal_info = f"已进行 {session.rebuttal_rounds} 轮申辩。"
        if session.rebuttal_rounds >= self.MAX_TOTAL_REBUTTAL_ROUNDS:
            return [], []

        all_skills_info = "\n".join(
            f"- {self.get_skill_display_name(s)}（{self.get_skill_focus(s)}）"
            for s in self.all_skill_ids
        )
        current_skills = json.dumps(session.ordered_skills, ensure_ascii=False)
        available_to_summon = [
            s for s in self.all_skill_ids if s not in session.ordered_skills
        ]
        summonable_info = "\n".join(
            f"- {self.get_skill_display_name(s)}（{self.get_skill_focus(s)}）"
            for s in available_to_summon
        ) if available_to_summon else "（无额外可用流派）"

        prompt = f"""你是辩论主持人。根据以下阶段摘要，判断是否存在需要安排**申辩回合**的异议，以及是否需要**召唤额外流派**加入讨论。

【用户问题】
{session.user_query}

【阶段摘要】
{summaries}

【当前辩论状态】
{rebuttal_info}
最多允许 {self.MAX_TOTAL_REBUTTAL_ROUNDS} 轮申辩。

【当前已参与流派】
{current_skills}

【可召唤的额外流派】
{summonable_info}

重要规则：
- 如果已经辩论多轮（≥{self.MAX_TOTAL_REBUTTAL_ROUNDS // 2} 轮），或现有分歧已在前面回合中充分展开，**请不要提出新异议**。
- 只关注**真正重要且尚未充分讨论**的分歧。
- 避免让相同的两个流派反复争论同一问题。
- 如果当前流派无法覆盖问题的某个重要维度（如涉及战略但无兵家、涉及身心但无医家），你可以召唤额外流派。召唤的流派将作为新发言人加入辩论，提供其独特视角。
- 召唤流派时要给出充分理由，说明为什么现有流派无法覆盖该维度。

请**只**输出 JSON，格式：
{{
  "objections": [
    {{
      "from_skill": "skill_id",
      "target_skill": "skill_id",
      "points": ["异议点1", "异议点2"]
    }}
  ],
  "summon_skills": [
    {{
      "skill_id": "skill_id",
      "reason": "召唤理由"
    }}
  ]
}}

objections 中的 skill_id 必须从当前已参与流派选择：{current_skills}
summon_skills 中的 skill_id 必须从可召唤流派选择：{json.dumps(available_to_summon, ensure_ascii=False)}
若无实质异议，objections 为空数组。若不需要召唤额外流派，summon_skills 为空数组。
"""
        if memory_context:
            prompt += f"\n【历史参考】\n{memory_context}\n"

        raw = self._llm_invoke(prompt)
        data = self._parse_json_object(raw)
        objections = data.get("objections", [])
        summon_requests = data.get("summon_skills", [])

        if not isinstance(objections, list):
            objections = []
        if not isinstance(summon_requests, list):
            summon_requests = []

        valid_ids = set(session.ordered_skills)
        cleaned_objections = []
        for obj in objections:
            if not isinstance(obj, dict):
                continue
            f_id = obj.get("from_skill", "")
            t_id = obj.get("target_skill", "")
            points = obj.get("points", [])
            if f_id in valid_ids and t_id in valid_ids and f_id != t_id and points:
                cleaned_objections.append(
                    {
                        "from_skill": f_id,
                        "target_skill": t_id,
                        "points": points[:5],
                    }
                )

        valid_summon_ids = set(available_to_summon)
        cleaned_summons = []
        for req in summon_requests:
            if not isinstance(req, dict):
                continue
            s_id = req.get("skill_id", "")
            reason = req.get("reason", "")
            if s_id in valid_summon_ids and reason:
                cleaned_summons.append({"skill_id": s_id, "reason": reason})

        return cleaned_objections, cleaned_summons

    def _run_rebuttal_thread(
        self,
        session: DebateSession,
        objection: dict[str, Any],
        memory_context: str,
        callback: Optional[Callable[[str], None]],
    ) -> None:
        challenger = objection["from_skill"]
        defender = objection["target_skill"]
        points = objection.get("points", [])
        c_name = self.get_skill_display_name(challenger)
        d_name = self.get_skill_display_name(defender)
        points_text = "\n".join(f"- {p}" for p in points)

        self._emit(
            callback,
            f"### 【主持人】异议登记：{c_name} 对 {d_name}\n\n{points_text}\n\n",
        )

        # 被质疑方申辩
        self._emit(callback, f"### {d_name}（申辩·回应 {c_name}）\n\n")
        defense_instruction = self._host_rebuttal_instruction(
            session, defender, challenger, points_text, role="defense", memory_context=memory_context
        )
        defense_speech = self._speaker_rebuttal(
            session, defender, defense_instruction, points_text, callback
        )
        defense_speech = self._strip_forbidden_sections(defense_speech)
        session.turns.append(
            DebateTurn(
                skill_id=defender,
                phase="rebuttal_defense",
                host_instruction=defense_instruction,
                context_brief=points_text,
                speech=defense_speech,
            )
        )
        session.rebuttal_rounds += 1

        self._emit(callback, f"\n\n---\n\n### 【主持人】申辩小结\n\n")
        rebuttal_summary = self._host_summarize_rebuttal(
            session, defender, challenger, defense_speech, memory_context, callback
        )
        session.turns[-1].host_summary = rebuttal_summary
        session.host_brief_for_next = self._host_build_cumulative_brief(session)
        self._emit(callback, f"{rebuttal_summary}\n\n---\n\n")

        # 质疑方再回应
        if session.rebuttal_rounds < self.MAX_OBJECTION_THREADS * self.MAX_REBUTTAL_PER_THREAD:
            self._emit(callback, f"### {c_name}（再回应·{d_name} 的申辩）\n\n")
            reply_instruction = self._host_rebuttal_instruction(
                session, challenger, defender, defense_speech[:1500], role="reply", memory_context=memory_context
            )
            reply_speech = self._speaker_rebuttal(
                session, challenger, reply_instruction, defense_speech[:1500], callback
            )
            reply_speech = self._strip_forbidden_sections(reply_speech)
            session.turns.append(
                DebateTurn(
                    skill_id=challenger,
                    phase="rebuttal_reply",
                    host_instruction=reply_instruction,
                    context_brief=defense_speech[:800],
                    speech=reply_speech,
                )
            )
            session.rebuttal_rounds += 1
            self._emit(callback, "\n\n---\n\n")

        # 第三位发言人可介入讨论
        others = [
            s for s in session.ordered_skills if s not in (challenger, defender)
        ]
        if others and session.rebuttal_rounds < self.MAX_OBJECTION_THREADS * self.MAX_REBUTTAL_PER_THREAD:
            third_id = others[0]
            t_name = self.get_skill_display_name(third_id)
            self._emit(callback, f"### {t_name}（介入讨论）\n\n")
            floor_instruction = self._host_floor_instruction(
                session, third_id, challenger, defender, memory_context
            )
            floor_speech = self._speaker_rebuttal(
                session, third_id, floor_instruction, session.host_brief_for_next, callback
            )
            floor_speech = self._strip_forbidden_sections(floor_speech)
            session.turns.append(
                DebateTurn(
                    skill_id=third_id,
                    phase="floor",
                    host_instruction=floor_instruction,
                    context_brief=session.host_brief_for_next,
                    speech=floor_speech,
                )
            )
            session.rebuttal_rounds += 1
            self._emit(callback, "\n\n---\n\n")

    def _host_instruction_for_summoned(
        self,
        session: DebateSession,
        skill_id: str,
        memory_context: str,
    ) -> str:
        name = self.get_skill_display_name(skill_id)
        focus = self.get_skill_focus(skill_id)
        prompt = f"""你是辩论主持人。主持人根据辩论进展，认为需要 {name} 的视角来补充讨论。

【用户问题】
{session.user_query}

【被召唤的流派】{name}（核心关注：{focus}）

【当前辩论摘要】
{session.host_brief_for_next}

请为 {name} 生成简要发言指令（不超过3条），要求：
- 告知 {name} 用户的核心问题是什么，以及当前讨论中缺少 {name} 视角的哪些方面
- 不要替 {name} 决定应如何论证，让其自主选择切入点
- 禁止做全场总结或最终建议。
"""
        if memory_context:
            prompt += f"\n【历史参考】\n{memory_context}\n"
        return self._llm_invoke(prompt)

    def _host_rebuttal_instruction(
        self,
        session: DebateSession,
        speaker_id: str,
        opponent_id: str,
        issue_text: str,
        role: str,
        memory_context: str,
    ) -> str:
        s_name = self.get_skill_display_name(speaker_id)
        o_name = self.get_skill_display_name(opponent_id)
        role_desc = "被质疑方申辩" if role == "defense" else "质疑方再回应"
        prompt = f"""你是辩论主持人。请为发言人写简要指令（不超过3条），不要自己发言。

【用户问题】{session.user_query}
【发言人】{s_name}
【对方】{o_name}
【回合类型】{role_desc}
【争议焦点】
{issue_text}

要求：告知发言人争议焦点，让其自主选择如何回应，禁止发言人做全场总结。
"""
        return self._llm_invoke(prompt)

    def _host_floor_instruction(
        self,
        session: DebateSession,
        speaker_id: str,
        party_a: str,
        party_b: str,
        memory_context: str,
    ) -> str:
        name = self.get_skill_display_name(speaker_id)
        a_name = self.get_skill_display_name(party_a)
        b_name = self.get_skill_display_name(party_b)
        prompt = f"""你是辩论主持人。{name} 将介入 {a_name} 与 {b_name} 的争议讨论。

【现场摘要】
{session.host_brief_for_next}

请写简要指令（不超过3条），告知 {name} 争议焦点和用户核心问题，让其从本派立场自主评论，禁止做最终综合。
"""
        return self._llm_invoke(prompt)

    def _speaker_rebuttal(
        self,
        session: DebateSession,
        skill_id: str,
        host_instruction: str,
        issue_context: str,
        callback: Optional[Callable[[str], None]],
    ) -> str:
        name = self.get_skill_display_name(skill_id)
        skill_context = self.load_skill_context([skill_id])
        prompt = f"""你是**{name}**发言人（子角色），正在申辩/回应回合。

【用户问题】{session.user_query}

【主持人指令】
{host_instruction}

【争议上下文】
{issue_context}

【流派知识】
{skill_context}

请用 Markdown，仅输出：
## 针对争议点的回应
## 本派立场重申

禁止：全场总结、最终建议、替用户做决定。
"""
        return self._llm(prompt, callback)

    def _host_summarize_rebuttal(
        self,
        session: DebateSession,
        defender: str,
        challenger: str,
        defense_speech: str,
        memory_context: str,
        callback: Optional[Callable[[str], None]],
    ) -> str:
        d_name = self.get_skill_display_name(defender)
        c_name = self.get_skill_display_name(challenger)
        prompt = f"""你是主持人。请总结 {d_name} 与 {c_name} 的申辩回合（200字内），并列出仍未解决的分歧。

【申辩内容】
{defense_speech}

不要给最终建议。
"""
        return self._llm(prompt, callback)

    def _host_final_synthesis(
        self,
        session: DebateSession,
        memory_context: str,
        callback: Optional[Callable[[str], None]],
    ) -> str:
        brief = self._host_build_cumulative_brief(session)
        speeches = []
        for t in session.turns:
            n = self.get_skill_display_name(t.skill_id)
            speeches.append(f"### {n}（{t.phase}）\n{t.speech}")

        prompt = f"""你是辩论**主持人（大脑）**。全场发言已结束，请做**唯一**的最终综合。

【用户问题】
{session.user_query}

【主持人阶段摘要】
{brief}

【发言人实录（参考）】
{chr(10).join(speeches)}

请用 Markdown 输出：
## 辩论回顾
## 各方共识
## 核心分歧（仍未统一之处）
## 给用户的综合建议
（至少 2 条路径，标明主要源自哪一派；不得只采信最后一位发言人）

只有你能做最终综合，发言人未授权做此总结。
"""
        if memory_context:
            prompt += f"\n【历史参考】\n{memory_context}\n"
        return self._llm(prompt, callback)

    def _format_transcript(self, session: DebateSession, opening: str) -> str:
        parts = [f"### 【主持人】开场安排\n\n{opening}"]
        speak_index = 0
        for turn in session.turns:
            name = self.get_skill_display_name(turn.skill_id)
            if turn.phase == "speak":
                speak_index += 1
                parts.append(
                    f"\n\n---\n\n### {name}（第 {speak_index} 轮·发言）\n\n{turn.speech}"
                )
                parts.append(
                    f"\n\n---\n\n### 【主持人】阶段小结\n\n{turn.host_summary}"
                )
            elif turn.phase == "rebuttal_defense":
                parts.append(f"\n\n---\n\n### {name}（申辩）\n\n{turn.speech}")
            elif turn.phase == "rebuttal_reply":
                parts.append(f"\n\n---\n\n### {name}（再回应）\n\n{turn.speech}")
            elif turn.phase == "floor":
                parts.append(f"\n\n---\n\n### {name}（介入讨论）\n\n{turn.speech}")
            elif turn.phase == "summoned":
                parts.append(f"\n\n---\n\n### {name}（受邀发言）\n\n{turn.speech}")
        return "".join(parts)

    @staticmethod
    def _strip_forbidden_sections(text: str) -> str:
        """移除发言人越权写出的总结性章节（粗略过滤）"""
        lines = text.split("\n")
        out: list[str] = []
        skip = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                skip = any(k in title for k in FORBIDDEN_SPEAKER_SECTIONS)
            if not skip:
                out.append(line)
        return "\n".join(out).strip()
