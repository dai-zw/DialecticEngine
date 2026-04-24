"""
DialecticEngine - Agent Harness
============================
统一的 Agent 运行框架，支持裁决和质量控制。

Usage:
    from harness.agent_harness import AgentHarness
    
    harness = AgentHarness()
    result = await harness.run("我和老板意见不合...")
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .adjudicator import Adjudicator, Judgement

logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class AgentResult:
    """Agent 执行结果"""
    
    # 原始输入
    user_query: str
    trace_id: str
    
    # 路由结果
    selected_skills: list[str] = field(default_factory=list)
    routing_confidence: float = 0.0
    routing_reasoning: str = ""
    
    # Agent 回答
    response: str = ""
    
    # 评判结果
    judgement: Optional[Judgement] = None
    
    # 元数据
    user_id: str = "default"
    session_id: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "user_query": self.user_query,
            "selected_skills": self.selected_skills,
            "routing_confidence": round(self.routing_confidence, 2),
            "response": self.response,
            "judgement": self.judgement.to_dict() if self.judgement else None,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HarnessConfig:
    """Harness 配置"""
    
    max_steps: int = 5
    enable_judgement: bool = True
    judgement_threshold: float = 0.7  # 低于此分数会触发重新生成
    max_regenerations: int = 2  # 最大重新生成次数
    
    # 裁决配置
    use_llm_judgement: bool = False  # 是否使用 LLM 深度评判
    

# ============================================================================
# Agent Harness
# ============================================================================

class AgentHarness:
    """
    统一 Agent 运行框架
    
    功能：
    - 接收用户输入，调用主系统处理
    - 使用 Adjudicator 评判回答质量
    - 根据评判结果决定是否重新生成
    - 记录完整 trace
    """
    
    def __init__(
        self,
        system: Any,  # DialecticEngine 或类似系统
        config: Optional[HarnessConfig] = None,
    ):
        """
        初始化
        
        Args:
            system: 主系统实例（DialecticEngine）
            config: Harness 配置
        """
        self.system = system
        self.config = config or HarnessConfig()
        self.adjudicator = Adjudicator()
        
        # Trace 存储
        self._traces: dict[str, AgentResult] = {}
    
    async def run(
        self,
        user_input: str,
        user_id: str = "default_user",
        session_id: Optional[str] = None,
    ) -> AgentResult:
        """
        统一入口
        
        Args:
            user_input: 用户输入
            user_id: 用户 ID
            session_id: 会话 ID
        
        Returns:
            AgentResult 包含完整执行结果和评判
        """
        # 基础校验
        if not user_input or not user_input.strip():
            return AgentResult(
                user_query="",
                trace_id="",
                response="请输入有效内容",
            )
        
        trace_id = f"trace_{uuid.uuid4().hex[:12]}"
        session_id = session_id or str(uuid.uuid4())
        
        logger.info(f"[{trace_id}] 开始处理: {user_input[:50]}...")
        
        # 创建结果对象
        result = AgentResult(
            user_query=user_input,
            trace_id=trace_id,
            user_id=user_id,
            session_id=session_id,
        )
        
        try:
            # 1️⃣ 执行主系统
            decision, response = await self._execute_system(
                user_input, user_id, session_id
            )
            
            result.selected_skills = decision.selected_skills
            result.routing_confidence = decision.confidence
            result.routing_reasoning = decision.reasoning
            result.response = response
            
            # 2️⃣ 裁决评判
            if self.config.enable_judgement:
                result.judgement = await self._judge_response(
                    user_input,
                    decision.selected_skills,
                    response,
                )
                
                logger.info(
                    f"[{trace_id}] 评判结果: {result.judgement.verdict} "
                    f"({result.judgement.score:.0%})"
                )
                
                # 3️⃣ 根据评判决定是否重新生成
                if result.judgement.score < self.config.judgement_threshold:
                    result = await self._regenerate_if_needed(result, user_input, user_id)
            
            # 存储 trace
            self._traces[trace_id] = result
            
            return result
            
        except Exception as e:
            logger.error(f"[{trace_id}] 执行异常: {e}")
            result.response = f"[系统异常] {str(e)}"
            return result
    
    async def _execute_system(
        self,
        user_input: str,
        user_id: str,
        session_id: str,
    ):
        """
        执行主系统
        
        Returns:
            (decision, response)
        """
        # 如果主系统是 DialecticEngine
        if hasattr(self.system, 'chat'):
            # 同步调用
            chat_result = self.system.chat(
                query=user_input,
                session_id=session_id,
            )
            
            # 获取决策（需要单独调用 route）
            decision = self.system.router.route(
                query=user_input,
                user_id=user_id,
                session_id=session_id,
            )
            
            return decision, chat_result.get("response", "")
        
        # 如果主系统有 process_streaming 方法
        elif hasattr(self.system, 'process_streaming'):
            response = await self.system.process_streaming(user_input, user_id)
            
            # 尝试获取决策
            decision = getattr(self.system, 'last_decision', None)
            if decision is None:
                # 创建默认决策
                from policy_router.types import RoutingDecision, ExecutionMode
                decision = RoutingDecision(
                    selected_skills=[],
                    skill_scores={},
                    execution_mode=ExecutionMode.SINGLE,
                    reasoning="",
                    confidence=0.0,
                    execution_plan=[],
                    explanation="",
                    trace={},
                )
            
            return decision, response
        
        else:
            raise ValueError("系统不支持，必须有 chat() 或 process_streaming() 方法")
    
    async def _judge_response(
        self,
        query: str,
        skills: list[str],
        response: str,
    ) -> Judgement:
        """
        评判回答
        
        Args:
            query: 用户问题
            skills: 选取的技能
            response: Agent 回答
        
        Returns:
            Judgement 评判结果
        """
        if self.config.use_llm_judgement:
            # 使用 LLM 深度评判
            return self.adjudicator.judge_with_llm(
                user_query=query,
                selected_skills=skills,
                response=response,
            )
        else:
            # 使用规则快速评判
            return self.adjudicator.judge(
                user_query=query,
                selected_skills=skills,
                response=response,
            )
    
    async def _regenerate_if_needed(
        self,
        result: AgentResult,
        user_input: str,
        user_id: str,
    ) -> AgentResult:
        """
        根据评判结果决定是否重新生成
        
        Args:
            result: 当前结果
            user_input: 用户输入
            user_id: 用户 ID
        
        Returns:
            更新后的结果
        """
        regeneration_count = 0
        current_result = result
        
        while (
            current_result.judgement 
            and current_result.judgement.score < self.config.judgement_threshold
            and regeneration_count < self.config.max_regenerations
        ):
            regeneration_count += 1
            logger.info(
                f"[{current_result.trace_id}] 触发重新生成 "
                f"({regeneration_count}/{self.config.max_regenerations})"
            )
            
            # 尝试使用不同视角或调整 prompt
            new_result = await self._try_regeneration(
                current_result,
                user_input,
                user_id,
            )
            
            if new_result:
                current_result = new_result
            
            # 停止条件：分数有明显提升
            if current_result.judgement and current_result.judgement.score >= 0.6:
                break
        
        if regeneration_count > 0:
            logger.info(
                f"[{current_result.trace_id}] 重新生成完成，"
                f"最终分数: {current_result.judgement.score:.0%}"
            )
        
        return current_result
    
    async def _try_regeneration(
        self,
        current: AgentResult,
        user_input: str,
        user_id: str,
    ) -> Optional[AgentResult]:
        """
        尝试重新生成
        
        可以根据评判结果调整策略：
        - 如果视角不恰当，尝试其他视角
        - 如果深度不够，增加 prompt 中的深度要求
        - 如果可操作性差，在 prompt 中强调要给出具体建议
        """
        # 获取当前评判的具体问题
        judgement = current.judgement
        if not judgement:
            return None
        
        # 根据问题类型调整
        prompt_adjustments = []
        
        if judgement.relevance.score < 0.5:
            prompt_adjustments.append("请直接切入问题核心，不要偏离主题")
        
        if judgement.skill_appropriateness.score < 0.5:
            prompt_adjustments.append(
                "选取的视角可能不够恰当，请结合问题的具体语境进行分析"
            )
        
        if judgement.depth.score < 0.5:
            prompt_adjustments.append(
                "请增加更深入的分析，触及问题的本质和根源"
            )
        
        if judgement.actionability.score < 0.5:
            prompt_adjustments.append(
                "请在回答末尾给出具体可操作的建议或步骤"
            )
        
        if not prompt_adjustments:
            return None
        
        # 重新执行（这里简化处理，实际可以修改 prompt 后重新调用）
        try:
            # 简单重新调用
            decision = self.system.router.route(
                query=user_input,
                user_id=user_id,
                session_id=current.session_id,
            )
            
            # 构建调整后的 prompt
            adjusted_prompt = "\n".join(prompt_adjustments)
            
            # 重新生成（实际实现中需要修改 executor 的 prompt 构建逻辑）
            response = self.system.llm.invoke(
                f"{self.system.executor._build_prompt(user_input, decision, self.system.executor._load_skills_context(decision.selected_skills))}\n\n附加要求：\n{adjusted_prompt}"
            )
            
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # 重新评判
            new_judgement = await self._judge_response(
                user_input,
                decision.selected_skills,
                response_text,
            )
            
            # 更新结果
            current.selected_skills = decision.selected_skills
            current.routing_confidence = decision.confidence
            current.routing_reasoning = decision.reasoning
            current.response = response_text
            current.judgement = new_judgement
            
            return current
            
        except Exception as e:
            logger.warning(f"重新生成失败: {e}")
            return None
    
    # =========================================================================
    # Trace 查询
    # =========================================================================
    
    def get_trace(self, trace_id: str) -> Optional[AgentResult]:
        """获取指定 trace"""
        return self._traces.get(trace_id)
    
    def get_recent_traces(self, limit: int = 10) -> list[AgentResult]:
        """获取最近的 traces"""
        traces = sorted(
            self._traces.values(),
            key=lambda x: x.timestamp,
            reverse=True,
        )
        return traces[:limit]
    
    def get_average_score(self) -> float:
        """获取平均评判分数"""
        judged_traces = [
            t for t in self._traces.values() 
            if t.judgement is not None
        ]
        
        if not judged_traces:
            return 0.0
        
        return sum(t.judgement.score for t in judged_traces) / len(judged_traces)


# ============================================================================
# 便捷函数
# ============================================================================

def quick_run(
    system: Any,
    query: str,
) -> AgentResult:
    """
    快速运行（同步版本）
    
    Usage:
        result = quick_run(engine, "我和老板意见不合...")
    """
    import asyncio
    
    harness = AgentHarness(system)
    return asyncio.run(harness.run(query))
