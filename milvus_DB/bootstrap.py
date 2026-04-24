"""
DialecticEngine - ReAct Bootstrap Agent

A ReAct-style (Reasoning + Acting) agent that sets up the environment
by iteratively calling an LLM planner and executing tools.

输出格式（中文 ReAct 循环）:
    Thought: Docker daemon 还未运行，需要先检查
    Action: check_docker_daemon
    Observation: Docker daemon 运行中 (v27.x)

    Thought: Docker 已就绪，继续检查 Milvus
    Action: check_milvus
    Observation: Milvus 端口未开放 (19530)

    ...
    Thought: 环境已就绪，可以开始了
    Action: bootstrap_complete
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

from tools import get_registry
from tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Safe print (Windows GBK compat)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _out(msg: str = ""):
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("utf-8", errors="replace").decode("utf-8"))


# ============================================================
# Bootstrap result
# ============================================================

@dataclass
class BootstrapResult:
    platform: str = ""
    docker_desktop_applicable: bool = False
    milvus_ready: bool = False
    milvus_started_by_us: bool = False
    milvus_endpoint: str = "localhost:19530"
    embedding_configured: bool = False
    embedding_model: str = ""
    warnings: list[str] = field(default_factory=list)


# ============================================================
# StuckDetector — the agent uses its own history to detect
# when it is stuck, then self-corrects.
# No external exception handling is involved.
# ============================================================

class StuckDetector:
    """
    简化版 Stuck 检测器。
    记录连续失败次数，超过阈值后标记为 stuck，让 Agent 跳过当前目标。
    """

    def __init__(self, max_attempts: int = 5):
        self.max_attempts = max_attempts
        self._attempts = 0

    def record(self, success: bool) -> bool:
        """记录一次执行结果。返回 True 表示 stuck，需要跳过当前目标。"""
        if success:
            self._attempts = 0
            return False
        self._attempts += 1
        return self._attempts >= self.max_attempts

    def reset(self):
        """重置计数器（切换目标时调用）"""
        self._attempts = 0

    @property
    def attempts(self) -> int:
        return self._attempts


# ============================================================
# LLM client
# ============================================================

def _create_llm():
    """Create the LLM client used by the ReAct agent."""
    from langchain_deepseek import ChatDeepSeek
    import os
    from dotenv import load_dotenv
    load_dotenv()
    return ChatDeepSeek(
        model="deepseek-chat",
        temperature=0.0,
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        request_timeout=60,
    )


# ============================================================
# Prompt templates
# ============================================================

SYSTEM_PROMPT = """你是一个专业的环境诊断与修复 Agent，负责为 DialecticEngine 准备运行时环境。

你的任务：通过观察（Observation）推理下一步行动（Action），直到当前目标达成，才进入下一个目标。

【目标组件】
1. Docker daemon — 必须运行
2. Milvus 服务 — 必须运行（向量数据库，用于长期记忆）
3. Embedding 模型 — 必须可用（用于语义搜索）

【执行顺序】
必须严格按照以下顺序完成：
0. 第一步：调用 check_device_platform 检测当前平台（Windows/Linux/macOS）
1. 第二步：确保 Docker daemon 运行正常
   - 如果环境变量 DIALECTIC_DOCKER_VERIFIED=1（由前置检查设置），表示 Docker 已验证，可以跳过此步骤，直接进入第三步
   - 否则按以下流程检查：
     → 先调用 check_docker_installed() 确认 Docker Desktop 已安装
     → 如已安装但未运行，调用 launch_docker_desktop()
     → 如未安装，调用 ask_user_for_help() 请求人工安装指导
     → Docker daemon 启动后：调用 check_docker_login() 确认已登录（Docker Hub 认证）
       如未登录且 pull 失败，提示用户登录 Docker Desktop
     → 其他系统: 调用 check_docker_installed() 后自行判断
2. 第三步：确保 Milvus 服务运行正常
   - 首先调用 check_milvus() 确认 Milvus 服务正在运行
   - 然后调用 check_milvus_collections() 检查 collections 是否存在
   - **如果 collections 不存在，必须立即调用 create_milvus_collections() 创建**
   - 只有在 collections 存在时才表示此步骤完成
3. 第四步：确保 Embedding 模型可用
   - 首先调用 check_embedding() 检查当前状态
   - **如果返回 "sentence-transformers not installed"，必须立即调用 install_embedding_deps() 安装依赖**
   - 安装完成后重新调用 check_embedding() 确认成功
   - 只有在 check_embedding() 返回 success=true 时才表示此步骤完成
只有在当前步骤确认成功后，才能进入下一步。

【可用工具】
{tool_schemas}

【输出格式（严格遵循）】
每一轮你必须输出以下格式：

--- 目标声明 ---
Thought: <当前目标是什么，例如"我的目标是确保 Docker daemon 运行正常">

--- 行动调用 ---
Action: <工具名称>(<参数，JSON格式，无空格>)
   （如果无参数，写作 Action: <工具名称>()）

--- 结束循环 ---
当所有三个组件都已确认就绪时：
Thought: <总结，描述所有组件状态>
Action: bootstrap_complete

【目标状态判定规则】
你必须根据该轮次的 Observation 中的实际状态来判断目标是否达成：
- 如果 Observation 显示 "Docker: OK"、"success: true" 等，表示目标达成，可以进入下一步
- 如果 Observation 显示 "FAIL"、"not running"、"not available"、"not found" 等，表示目标未达成，必须继续当前步骤
- 重要：不要假设或猜测组件状态，只相信当前 Observation 中的字面内容

【约束】
- 每轮只调用一个工具
- 不要调用不存在于工具列表的工具
- 用中文输出所有 Thought
- **第一步必须先调用 check_device_platform** 检测当前平台，再根据平台决定后续操作
- 如果连续 3 轮同一工具失败，请改用其他策略
- 如果当前步骤无法通过任何工具解决，描述需要什么操作（Python 代码/手动步骤）
- **严格按顺序执行**：先检测平台，再 Docker，再 Milvus，最后 Embedding。不允许跳步。

【Stuck 时的 Rescue 策略（按顺序执行）】
当连续 2 轮同一工具失败时，不要重复调用失败的工具，按以下顺序尝试：

1. 【深度诊断】调用 deep_system_diagnostics() 获取完整系统信息
   → 根据诊断结果修正策略

   如果诊断发现 Docker Desktop 启动失败，立即调用：
   check_docker_desktop_health() 诊断具体原因（WSL2/日志/Hyper-V）

2. 【自动修复】根据诊断结果调用 fix_docker_desktop():
   → wsl_shutdown（WSL2 无响应）
   → update_wsl（WSL 内核过期）
   → reset（Docker Desktop 配置损坏）
   → restart_service（Docker 服务异常）

   如果 Docker pull 失败，检查登录状态：
   → 调用 check_docker_login() 确认 Docker Hub 认证

3. 【网络搜索】如果诊断后仍无法解决，调用 web_search() 搜索错误信息
   → 例如：web_search("Docker Desktop WSL2 not starting Windows 11")
   → 根据搜索结果给出具体解决步骤

4. 【文档查询】调用 check_docs() 查找项目内的配置说明
   → 例如：check_docs("docker setup windows")

5. 【跳步跳过】如果上述均无法解决，调用 skip_bootstrap_step() 并说明原因
   → 然后调用 bootstrap_complete 结束诊断

6. 【Embedding 特殊处理】如果 Embedding 步骤连续失败，检查错误信息：
   → 如果错误提到 "sentence-transformers not installed"，立即调用 install_embedding_deps()
   → 安装后重新调用 check_embedding() 确认

7. 【请求人工】最终调用 ask_user_for_help() 输出结构化求助信息
   → step=具体失败步骤, tried=已尝试的方法, user_action=需要的操作

【StuckDetector 触发时机】
当 StuckDetector 触发时（连续 3 轮无改善），不要慌张，立即执行 Rescue 策略第 1 步。
"""


def _build_user_message(context: list[dict], current_goal: str = "Docker daemon") -> str:
    """Build the user message from the ReAct history."""
    if not context:
        return f"请开始诊断环境状态。\n\n当前目标：确保 {current_goal} 正常运行。"

    lines = []
    for turn in context:
        if turn.get("escalation"):
            lines.append(turn["escalation"])
            lines.append("")
        else:
            if turn.get("thought"):
                lines.append(f"Thought: {turn['thought']}")
            if turn.get("action"):
                lines.append(f"Action: {turn['action']}")
            if turn.get("observation"):
                lines.append(f"Observation: {turn['observation']}")
            lines.append("")
    lines.append(f"请继续完成当前目标：确保 {current_goal} 正常运行。")
    return "\n".join(lines)


# ============================================================
# ReAct Agent
# ============================================================

class ReActBootstrapAgent:
    """
    ReAct-style bootstrap agent.

    The LLM acts as the planner. It outputs Thought → Action calls,
    the agent executes them, feeds back the Observation, and loops
    until the LLM calls bootstrap_complete.

    All errors surface to the agent via history — no silent exception swallowing.
    StuckDetector lets the agent self-correct without external intervention.
    """

    def __init__(
        self,
        llm=None,
        max_iterations: int = 20,
        verbose: bool = True,
    ):
        self.registry = get_registry()
        self.llm = llm or _create_llm()
        self.max_iterations = max_iterations
        self.verbose = verbose
        self.history: list[dict] = []
        self.result: Optional[BootstrapResult] = None

    # --------------------------------------------------------------
    # Tool execution
    # --------------------------------------------------------------

    def _parse_action(self, action_line: str) -> tuple[str, str]:
        """
        Parse 'Action: tool_name(args)' or 'Action: tool_name()'
        Returns (tool_name, args_json_str).
        """
        content = action_line.strip()
        for prefix in ("Action:", "action:", "Action ", "action "):
            if content.startswith(prefix):
                content = content[len(prefix):].strip()
                break

        if not content:
            raise ValueError(f"无法从 Action 行提取工具名: '{action_line}'")

        match = re.match(r"^(\w+)\((.*)\)$", content)
        if match:
            return match.group(1), match.group(2).strip()

        match2 = re.match(r"^(\w+)$", content)
        if match2:
            return match2.group(1), ""

        raise ValueError(f"无法解析 Action 内容: '{content}'")

    def _execute_tool(self, name: str, args_str: str) -> ToolResult:
        """Execute a tool by name with JSON args."""
        tool = self.registry.get(name)
        if tool is None:
            return ToolResult(
                success=False,
                message=f"工具 '{name}' 不存在",
                observation=f"工具 '{name}' 不在工具列表中。可用工具: {', '.join(self.registry.get_names())}",
            )

        kwargs: dict[str, Any] = {}
        if args_str:
            try:
                kwargs = json.loads(args_str)
            except json.JSONDecodeError:
                return ToolResult(
                    success=False,
                    message=f"工具参数解析失败: {args_str}",
                    observation=f"参数格式错误，应为 JSON: {args_str}",
                )

        return tool.execute(**kwargs)

    def _execute_tool_with_timeout(self, name: str, args_str: str, timeout: int = 30) -> ToolResult:
        """Execute a tool in a thread with a timeout."""
        result_holder: list = [None]
        exc_holder: list[Exception] = []

        def _run():
            try:
                result_holder[0] = self._execute_tool(name, args_str)
            except Exception as exc:
                exc_holder.append(exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout=timeout)

        if t.is_alive():
            return ToolResult(
                success=False,
                message=f"工具 '{name}' 执行超时（{timeout}秒）",
                observation=f"工具 '{name}' 执行超过 {timeout} 秒未返回，可能陷入等待循环。"
                            f"请改用其他策略或提供可手动执行的步骤。",
            )

        if exc_holder:
            raise exc_holder[0]

        return result_holder[0]

    def _tool_result_to_observation(self, result: ToolResult, name: str) -> str:
        """Format a ToolResult into a short Chinese observation."""
        if result.success:
            return result.observation or result.message

        hint = result.observation or result.error or result.message

        if name == "check_docker_daemon":
            if "not found" in hint.lower():
                hint += " 请在系统PATH中确认Docker已安装。"
        elif name == "bootstrap_milvus":
            if "docker" in hint.lower():
                hint += " 请确保Docker daemon正在运行。"

        return hint

    # --------------------------------------------------------------
    # Main ReAct loop — all errors surface to the agent via history
    # --------------------------------------------------------------

    def run(self) -> BootstrapResult:
        """
        目标导向的 ReAct bootstrap agent。

        核心逻辑：
        1. 按顺序确定当前目标（Docker → Milvus → Embedding）
        2. 持续调用工具直到当前目标达成
        3. 目标达成后才进入下一个目标
        4. 所有目标完成后调用 bootstrap_complete
        """
        _out()
        _out("=" * 56)
        _out("  DialecticEngine · 环境诊断 Agent")
        _out("=" * 56)
        _out()

        tool_schemas = self.registry.get_schemas()
        tool_schemas_json = json.dumps(tool_schemas, ensure_ascii=False, indent=2)

        from langchain_core.messages import HumanMessage, SystemMessage
        system_msg = SYSTEM_PROMPT.format(tool_schemas=tool_schemas_json)

        self.history = []
        self.result = BootstrapResult()
        stuck = StuckDetector(max_attempts=3)

        # 检查是否已通过前置检查（check_docker_prereqs 已完成 Docker 和 Milvus）
        docker_pre_verified = os.environ.get("DIALECTIC_DOCKER_VERIFIED") == "1"
        
        # 定义目标阶段
        goals = [
            ("平台检测", self._is_platform_checked),
            ("Docker daemon", self._is_docker_ok),
            ("Milvus 服务", self._is_milvus_ok),
            ("Embedding 模型", self._is_embedding_ok),
        ]

        # 如果前置检查已通过，直接跳到 Embedding 检查
        if docker_pre_verified:
            goal_index = 3  # 从 Embedding 开始
            current_goal_name = goals[goal_index][0]
            # 预填充 Docker 和 Milvus 已就绪
            self.result.docker_desktop_applicable = True
            self.result.milvus_ready = True
            _out()
            _out("=" * 56)
            _out("  Docker & Milvus 已通过前置检查")
            _out("=" * 56)
            _out()
        else:
            goal_index = 0
            current_goal_name = goals[goal_index][0]
        total_iterations = 0
        max_total_iterations = self.max_iterations * len(goals)  # 每个目标最多 N 轮

        while goal_index < len(goals):
            # 安全检查：防止无限循环
            total_iterations += 1
            if total_iterations > max_total_iterations:
                if self.verbose:
                    _out(f"\n已达到最大迭代限制（{max_total_iterations}轮），强制结束当前目标")
                goal_index += 1
                stuck.reset()
                continue
            current_goal_name = goals[goal_index][0]
            is_goal_ok = goals[goal_index][1]

            # ---- LLM call ----
            response = self.llm.invoke([
                SystemMessage(content=system_msg),
                HumanMessage(content=_build_user_message(self.history, current_goal_name)),
            ])
            llm_output = response.content if hasattr(response, "content") else str(response)

            # ---- Parse ----
            thought, action_str = self._extract_thought_action(llm_output)

            if not action_str:
                self.history.append({
                    "thought": thought,
                    "action": "",
                    "observation": "【格式错误】输出缺少 Action 行。",
                })
                if self.verbose:
                    _out(thought)
                    _out()
                stuck.record(False)
                continue

            try:
                tool_name, args_str = self._parse_action(action_str)
            except ValueError:
                self.history.append({
                    "thought": thought,
                    "action": action_str,
                    "observation": f"【格式错误】无法解析 Action '{action_str}'。",
                })
                if self.verbose:
                    _out(thought)
                    _out()
                stuck.record(False)
                continue

            # ---- Execute tool ----
            # install_embedding_deps 需要更长的超时时间（pip install 可能需要 5 分钟）
            tool_timeout = 300 if tool_name == "install_embedding_deps" else 30
            tool_result = self._execute_tool_with_timeout(tool_name, args_str, timeout=tool_timeout)
            observation = self._tool_result_to_observation(tool_result, tool_name)
            self._update_result_state(tool_name, tool_result)

            self.history.append({
                "thought": thought,
                "action": action_str,
                "observation": observation,
            })

            # 记录结果并检查是否 stuck
            is_stuck = stuck.record(tool_result.success)

            if self.verbose:
                _out(thought)
                _out()

            # ---- 检查当前目标是否达成 ----
            if is_goal_ok():
                _out(f"【{current_goal_name} 已就绪】")
                _out()
                goal_index += 1
                stuck.reset()  # 切换目标时重置计数器
                if goal_index >= len(goals):
                    break
                current_goal_name = goals[goal_index][0]
                _out(f"【进入下一目标】确保 {current_goal_name} 正常运行")
                continue

            # ---- Stuck 检测：连续失败超过阈值则跳过当前目标 ----
            if is_stuck:
                _out(f"【警告】{current_goal_name} 连续 {stuck.attempts} 次检查失败，跳过此步骤")
                _out()
                goal_index += 1
                stuck.reset()
                if goal_index >= len(goals):
                    break
                current_goal_name = goals[goal_index][0]
                _out(f"【进入下一目标】确保 {current_goal_name} 正常运行")

        # ---- 所有目标完成后 ----
        if self.verbose:
            _out(f"所有组件已就绪，环境诊断完成。")
        self._print_summary()
        return self.result

    def _is_platform_checked(self) -> bool:
        """检查平台是否已检测"""
        return hasattr(self.result, 'platform') and bool(self.result.platform)

    def _is_docker_ok(self) -> bool:
        """检查 Docker 是否就绪"""
        # 如果环境变量 DIALECTIC_DOCKER_VERIFIED=1（由前置检查设置），表示 Docker 已验证
        if os.environ.get("DIALECTIC_DOCKER_VERIFIED") == "1":
            return True
        return not any("Docker" in w for w in self.result.warnings)

    def _is_milvus_ok(self) -> bool:
        """检查 Milvus 是否就绪"""
        return self.result.milvus_ready

    def _is_embedding_ok(self) -> bool:
        """检查 Embedding 是否就绪"""
        return self.result.embedding_configured

    def _extract_thought_action(self, text: str) -> tuple[str, str]:
        """
        Extract the LAST Thought and LAST Action from LLM output.
        """
        thought = ""
        action = ""

        for line in text.splitlines():
            line_s = line.strip()
            if not line_s:
                continue
            for prefix in ("Thought:", "thought:", "Thought "):
                if line_s.startswith(prefix):
                    thought = line_s[len(prefix):].strip()
                    break
            for prefix in ("Action:", "action:", "Action ", "action "):
                if line_s.startswith(prefix):
                    action = line_s[len(prefix):].strip()
                    break

        return thought, action

    def _update_result_state(self, tool_name: str, result: ToolResult) -> None:
        """Update the BootstrapResult from tool execution results."""
        if result.success:
            if tool_name == "check_device_platform":
                self.result.platform = result.data.get("platform", "") if result.data else ""
                self.result.docker_desktop_applicable = result.data.get("docker_desktop_applicable", False) if result.data else False
            elif tool_name == "check_docker_daemon":
                self.result.warnings = [w for w in self.result.warnings if "Docker" not in w]
            elif tool_name == "check_milvus":
                self.result.milvus_ready = True
            elif tool_name == "bootstrap_milvus":
                self.result.milvus_ready = True
                self.result.milvus_started_by_us = True
            elif tool_name == "check_embedding":
                self.result.embedding_configured = True
                if result.data:
                    self.result.embedding_model = result.data.get("model", result.data.get("backend", "?"))
        else:
            if tool_name == "check_docker_daemon":
                self.result.warnings.append("Docker not available")

    def _final_observation(self) -> str:
        docker_status = "OK" if not any("Docker" in w for w in self.result.warnings) else "FAIL"
        milvus_status = "OK" if self.result.milvus_ready else "FAIL"
        embed_status = "OK" if self.result.embedding_configured else "FAIL"
        return f"Docker: {docker_status} | Milvus: {milvus_status} | Embedding: {embed_status}"

    def _print_summary(self) -> None:
        _out("=" * 56)
        _out("  诊断完成 · 环境状态")
        _out("=" * 56)
        docker_ok = not any("Docker" in w for w in self.result.warnings)
        _out(f"  Docker   · {'OK' if docker_ok else 'FAIL'}  {'(Milvus 将不可用)' if not docker_ok else ''}")
        _out(f"  Milvus   · {'OK' if self.result.milvus_ready else '未运行'}  {'(长期记忆不可用)' if not self.result.milvus_ready else ''}")
        _out(f"  Embedding · {'OK' if self.result.embedding_configured else '不可用'}  {'(语义搜索不可用)' if not self.result.embedding_configured else ''}")
        if self.result.warnings:
            _out()
            for w in self.result.warnings:
                _out(f"  警告: {w}")
        _out()
        _out("  DialecticEngine 已就绪，开始使用吧。")

    # --------------------------------------------------------------
    # Silent mode (used at startup)
    # --------------------------------------------------------------

    def ensure_prerequisites(self, skip_steps: Optional[list[str]] = None) -> BootstrapResult:
        """
        Silent bootstrap: run the ReAct agent without printing output.
        Returns BootstrapResult. Used at startup.
        """
        original_verbose = self.verbose
        self.verbose = False
        self.run()
        self.verbose = original_verbose
        return self.result or BootstrapResult(warnings=["Bootstrap agent did not produce a result"])


# ============================================================
# Public API
# ============================================================

def ensure_prerequisites(skip_steps: Optional[list[str]] = None) -> BootstrapResult:
    """
    Run the ReAct bootstrap agent silently.
    Returns BootstrapResult with final environment status.
    """
    agent = ReActBootstrapAgent(verbose=False, max_iterations=20)
    return agent.ensure_prerequisites(skip_steps)


def run_interactive() -> BootstrapResult:
    """
    Run the ReAct bootstrap agent with Chinese ReAct output.
    This is the interactive entry point shown to the user.
    """
    agent = ReActBootstrapAgent(verbose=True, max_iterations=20)
    return agent.run()


def print_summary(result: BootstrapResult) -> None:
    """Print a final summary of the bootstrap result."""
    _out()
    _out("=" * 56)
    _out("  诊断完成 · 环境状态")
    _out("=" * 56)
    docker_ok = not any("Docker" in w for w in result.warnings)
    _out(f"  Docker   · {'OK' if docker_ok else 'FAIL'}  {'(Milvus 将不可用)' if not docker_ok else ''}")
    _out(f"  Milvus   · {'OK' if result.milvus_ready else '未运行'}  {'(长期记忆不可用)' if not result.milvus_ready else ''}")
    _out(f"  Embedding · {'OK' if result.embedding_configured else '不可用'}  {'(语义搜索不可用)' if not result.embedding_configured else ''}")
    if result.warnings:
        _out()
        for w in result.warnings:
            _out(f"  警告: {w}")
    _out()
