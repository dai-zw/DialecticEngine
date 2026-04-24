"""
Rescue tools: self-healing and diagnostic tools for the ReAct bootstrap agent.
These tools help the agent break out of stuck loops, search for solutions,
and provide user-activatable fallbacks when automatic recovery fails.
"""

from __future__ import annotations

import json
import platform
import socket
import subprocess
import sys
import time
from typing import Any, Optional

from .base import (
    BaseTool,
    ToolCategory,
    ToolDefinition,
    ToolResult,
    ToolRegistry,
)


# ============================================================
# Tool: web_search — search the internet for solutions
# ============================================================

class WebSearchTool(BaseTool):
    """
    Search the web for solutions to error messages or problems.
    Uses DuckDuckGo HTML (no API key needed) as the primary backend.

    Use when:
    - A tool fails with an unfamiliar error message
    - The agent has been stuck for 2+ rounds on the same problem
    - Manual steps are needed but you don't know what to suggest
    """

    definition = ToolDefinition(
        name="web_search",
        description=(
            "Search the web for solutions to a problem. "
            "Use this when you encounter an unfamiliar error or need step-by-step instructions. "
            "Returns top search results with titles and snippets.\n\n"
            "Supports: error messages, Docker/Milvus setup issues, Windows WSL2 problems, "
            "environment configuration, installation guides."
        ),
        category=ToolCategory.RESCUE,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query. Be specific: include error messages, "
                                  "OS name, software version. Example: "
                                  "'Docker Desktop WSL2 not starting Windows 11 error 0x......'",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return. Default: 5.",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        returns="success: bool, results: list[dict], observation: str",
        examples=[
            "web_search(query='Docker Desktop WSL2 not starting Windows 11')",
            "web_search(query='milvus connection refused 19530 fix')",
        ],
    )

    def _execute(self, query: str, max_results: int = 5, **kwargs) -> ToolResult:
        try:
            import urllib.request
            import urllib.parse

            encoded = urllib.parse.quote_plus(query)
            url = f"https://duckduckgo.com/html/?q={encoded}"

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            results = self._parse_duckduckgo(html, max_results)
            if results:
                lines = []
                for r in results:
                    lines.append(f"- [{r['title']}]({r['url']})")
                    lines.append(f"  {r['snippet']}")
                observation = (
                    f"找到 {len(results)} 条相关结果：\n" + "\n".join(lines)
                )
            else:
                observation = "搜索完成但未找到相关结果，请尝试更通用的关键词。"

            return ToolResult(
                success=True,
                message=f"Web search completed for: {query}",
                data={"query": query, "results": results},
                observation=observation,
            )

        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Web search failed: {exc}",
                error=str(exc),
                observation=f"无法执行网络搜索（{type(exc).__name__}）。可能是网络连接问题。",
            )

    def _parse_duckduckgo(self, html: str, max_results: int) -> list[dict]:
        """Parse DuckDuckGo HTML results page."""
        results = []
        import re
        # Each result is in a <a> tag with class "result__a"
        # and the snippet in <a> class "result__snippet"
        for a_match in re.finditer(
            r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>', html
        ):
            url = a_match.group(1)
            title = a_match.group(2).strip()
            # Find snippet after this <a>
            start = a_match.end()
            snippet_match = re.search(
                r'<a class="result__snippet"[^>]*>([^<]+(?:<[^>]+>[^<]+)*)</a>',
                html[start:start + 500],
            )
            snippet = snippet_match.group(1) if snippet_match else ""
            # Strip tags from snippet
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            if url.startswith("http") and title:
                results.append({"title": title, "url": url, "snippet": snippet})
                if len(results) >= max_results:
                    break
        return results


# ============================================================
# Tool: deep_system_diagnostics — gather all system info
# ============================================================

class DeepSystemDiagnosticsTool(BaseTool):
    """
    Gather comprehensive system diagnostics to help the agent understand
    the full environment context. Use this as the FIRST rescue tool when
    stuck, to give the agent the complete picture.

    Checks:
    - OS, kernel, architecture
    - CPU cores, RAM
    - Disk space
    - Network connectivity
    - Docker installation and daemon
    - WSL2 status (on Windows)
    - Hyper-V status (on Windows)
    - Port availability
    - PATH environment
    """

    definition = ToolDefinition(
        name="deep_system_diagnostics",
        description=(
            "Run a comprehensive system diagnostic to gather all relevant "
            "environment information. Use this FIRST when stuck, before "
            "searching or giving up. Returns: OS info, Docker status, "
            "WSL2/Hyper-V status, network, disk, CPU/RAM, PATH entries."
        ),
        category=ToolCategory.RESCUE,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        returns="success: bool, diagnostics: dict, observation: str",
        examples=[
            "deep_system_diagnostics()",
            "deep_system_diagnostics() then web_search() with findings",
        ],
    )

    def _execute(self, **kwargs) -> ToolResult:
        diag: dict[str, Any] = {}
        warnings: list[str] = []

        # --- OS Info ---
        diag["os"] = {
            "platform": sys.platform,
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
        }

        # --- CPU / RAM ---
        try:
            import os
            if sys.platform == "win32":
                out = subprocess.check_output(
                    ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/format:list"],
                    timeout=5, encoding="utf-8", errors="replace",
                )
                free_kb = int(next((l.split("=", 1)[1] for l in out.splitlines() if "FreePhysicalMemory" in l), "0"))
                total_kb = int(next((l.split("=", 1)[1] for l in out.splitlines() if "TotalVisibleMemorySize" in l), "1"))
                diag["memory"] = {
                    "total_mb": total_kb // 1024,
                    "free_mb": free_kb // 1024,
                    "used_mb": (total_kb - free_kb) // 1024,
                }
                out2 = subprocess.check_output(
                    ["wmic", "cpu", "get", "NumberOfCores,NumberOfLogicalProcessors", "/format:list"],
                    timeout=5, encoding="utf-8", errors="replace",
                )
                cores = next((l.split("=", 1)[1] for l in out2.splitlines() if "NumberOfCores" in l), "N/A")
                logical = next((l.split("=", 1)[1] for l in out2.splitlines() if "NumberOfLogicalProcessors" in l), "N/A")
                diag["cpu"] = {"cores": cores, "logical_processors": logical}
            else:
                diag["memory"] = {"note": "Not implemented for this OS"}
                diag["cpu"] = {"note": "Not implemented for this OS"}
        except Exception as e:
            diag["hardware"] = f"Error gathering hardware info: {e}"

        # --- Disk ---
        try:
            if sys.platform == "win32":
                out = subprocess.check_output(
                    ["wmic", "logicaldisk", "get", "DeviceID,FreeSpace,Size,DriveType", "/format:list"],
                    timeout=5, encoding="utf-8", errors="replace",
                )
                disks = []
                for line in out.splitlines():
                    if "DeviceID" in line:
                        parts = {"DeviceID": line.split("=", 1)[1].strip()}
                        disks.append(parts)
                    elif "FreeSpace" in line:
                        try:
                            parts["FreeSpace_MB"] = int(line.split("=", 1)[1]) // (1024 * 1024)
                        except Exception:
                            parts["FreeSpace_MB"] = 0
                    elif "Size" in line:
                        try:
                            parts["Size_MB"] = int(line.split("=", 1)[1]) // (1024 * 1024)
                        except Exception:
                            parts["Size_MB"] = 0
                    elif "DriveType" in line:
                        parts["DriveType"] = line.split("=", 1)[1].strip()
                diag["disks"] = disks
            else:
                diag["disks"] = {"note": "Not implemented for this OS"}
        except Exception as e:
            diag["disks"] = f"Error: {e}"

        # --- Docker ---
        try:
            r = subprocess.run(
                ["docker", "info"], capture_output=True, timeout=8, encoding="utf-8", errors="replace",
            )
            if r.returncode == 0:
                diag["docker"] = {"status": "running"}
                for line in r.stdout.splitlines():
                    if "Server Version" in line:
                        diag["docker"]["version"] = line.split(":", 1)[1].strip()
                    elif "Kernel Version" in line:
                        diag["docker"]["kernel"] = line.split(":", 1)[1].strip()
            else:
                diag["docker"] = {"status": "not_running", "error": r.stderr[:200]}
        except FileNotFoundError:
            diag["docker"] = {"status": "not_installed"}
        except subprocess.TimeoutExpired:
            diag["docker"] = {"status": "timeout"}
        except Exception as e:
            diag["docker"] = {"status": "error", "detail": str(e)}

        # --- Docker Desktop process ---
        if sys.platform == "win32":
            try:
                r2 = subprocess.check_output(
                    ["tasklist", "/FI", "IMAGENAME eq Docker Desktop.exe", "/NH"],
                    timeout=5, encoding="utf-8", errors="replace",
                )
                diag["docker_desktop_process"] = (
                    "running" if "Docker Desktop.exe" in r2 else "not_running"
                )
            except Exception:
                diag["docker_desktop_process"] = "unknown"

        # --- WSL2 (Windows only) ---
        if sys.platform == "win32":
            try:
                r = subprocess.run(
                    ["wsl", "--list", "--verbose"], capture_output=True, timeout=10, encoding="utf-8", errors="replace",
                )
                diag["wsl2"] = {
                    "installed": r.returncode == 0,
                    "output": r.stdout.strip()[:500],
                }
            except FileNotFoundError:
                diag["wsl2"] = {"installed": False, "reason": "wsl command not found"}
            except subprocess.TimeoutExpired:
                diag["wsl2"] = {"installed": "unknown", "reason": "timeout"}
            except Exception as e:
                diag["wsl2"] = {"installed": False, "reason": str(e)}

            # --- Hyper-V ---
            try:
                r = subprocess.run(
                    ["systeminfo"], capture_output=True, timeout=10, encoding="utf-8", errors="replace",
                )
                hyper_v = "Hyper-V" in r.stdout
                diag["hyperv"] = {"present": hyper_v}
            except Exception:
                diag["hyperv"] = {"present": "unknown"}

        # --- Network ---
        net_check = {}
        for host, port, name in [
            ("8.8.8.8", 53, "dns_google"),
            ("1.1.1.1", 443, "cloudflare"),
            ("localhost", 2375, "docker_api"),
            ("localhost", 19530, "milvus"),
        ]:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            try:
                s.connect((host, port))
                net_check[name] = "open"
            except Exception:
                net_check[name] = "closed"
            finally:
                s.close()
        diag["network"] = net_check

        # --- PATH entries for Docker ---
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["where", "docker"], capture_output=True, timeout=5, encoding="utf-8", errors="replace",
                )
                diag["docker_path"] = r.stdout.strip().splitlines() if r.returncode == 0 else []
            else:
                r = subprocess.run(
                    ["which", "docker"], capture_output=True, timeout=5, encoding="utf-8", errors="replace",
                )
                diag["docker_path"] = r.stdout.strip().splitlines() if r.returncode == 0 else []
        except Exception as e:
            diag["docker_path"] = f"error: {e}"

        # --- Build observation ---
        obs_parts = []
        obs_parts.append(f"平台: {diag['os']['system']} {diag['os']['release']}")
        if "memory" in diag and isinstance(diag["memory"], dict):
            m = diag["memory"]
            obs_parts.append(f"内存: {m.get('total_mb', '?')} MB 总计, {m.get('free_mb', '?')} MB 可用")
        obs_parts.append(f"Docker: {diag['docker'].get('status', 'unknown')}")
        if "docker_desktop_process" in diag:
            obs_parts.append(f"Docker Desktop 进程: {diag['docker_desktop_process']}")
        if sys.platform == "win32" and "wsl2" in diag:
            obs_parts.append(f"WSL2: {'已安装' if diag['wsl2'].get('installed') else '未安装'}")
        obs_parts.append(f"网络: DNS {net_check['dns_google']}, Milvus端口 {net_check['milvus']}")

        return ToolResult(
            success=True,
            message="Deep system diagnostics complete",
            data=diag,
            observation=" | ".join(obs_parts),
        )


# ============================================================
# Tool: skip_bootstrap_step — skip the current failing step
# ============================================================

class SkipBootstrapStepTool(BaseTool):
    """
    Skip the currently failing bootstrap step and move to the next one.
    Use when:
    - A step cannot be resolved automatically (e.g., Docker Desktop won't start)
    - The user has acknowledged the warning and wants to continue
    - The agent is stuck with no path forward

    This is a controlled escape hatch — it doesn't hide the problem,
    it just allows the agent to continue past it.
    """

    definition = ToolDefinition(
        name="skip_bootstrap_step",
        description=(
            "Skip the current failing bootstrap step and move to the next goal. "
            "Use when a step cannot be resolved automatically and the user "
            "acknowledges the limitation. The skipped step's warning is preserved "
            "in the final summary.\n\n"
            "Returns the current step name and what will be attempted next."
        ),
        category=ToolCategory.RESCUE,
        parameters={
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why this step is being skipped. "
                                  "Be specific: what failed and why manual intervention is needed.",
                    "default": "Automatic resolution failed",
                },
            },
            "required": [],
        },
        returns="success: bool, skipped_step: str, next_step: str, observation: str",
        examples=[
            "skip_bootstrap_step(reason='Docker Desktop cannot start automatically on this system')",
            "skip_bootstrap_step()",
        ],
    )

    def _execute(self, reason: str = "Automatic resolution failed", **kwargs) -> ToolResult:
        # The agent needs to know what step it's on — this is passed via context
        # For now, we return a generic skip instruction
        return ToolResult(
            success=True,
            message=f"Step skipped: {reason}",
            data={
                "skipped": True,
                "reason": reason,
                "suggestion": "The agent should now call bootstrap_complete with warnings intact.",
            },
            observation=(
                f"已跳过当前失败步骤。原因: {reason}。"
                "系统将在最终总结中记录此警告，用户可稍后手动解决。"
            ),
        )


# ============================================================
# Tool: check_docs — lookup internal documentation
# ============================================================

class CheckDocsTool(BaseTool):
    """
    Search internal project documentation for solutions.
    Looks in: README.md, setup.sh, .env.example, docs/ folder.
    """

    definition = ToolDefinition(
        name="check_docs",
        description=(
            "Search internal project documentation for setup instructions or troubleshooting. "
            "Searches: README.md, setup.sh, .env.example, milvus_DB/README.md, docs/ folder.\n\n"
            "Use when: Docker/Milvus setup fails, environment config is unclear, "
            "or you need to know the expected setup steps."
        ),
        category=ToolCategory.RESCUE,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in the documentation. "
                                  "Example: 'docker setup', 'milvus port', '.env embedding'",
                },
            },
            "required": ["query"],
        },
        returns="success: bool, matches: list[dict], observation: str",
        examples=[
            "check_docs(query='docker setup windows')",
            "check_docs(query='milvus configuration')",
        ],
    )

    def _execute(self, query: str, **kwargs) -> ToolResult:
        import os
        import re

        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        search_paths = [
            os.path.join(base, "README.md"),
            os.path.join(base, "setup.sh"),
            os.path.join(base, ".env.example"),
            os.path.join(base, ".env"),
            os.path.join(base, "milvus_DB", "README.md"),
        ]

        # Also find docs/ folder
        docs_dir = os.path.join(base, "docs")
        if os.path.isdir(docs_dir):
            for f in os.listdir(docs_dir):
                if f.endswith(".md") or f.endswith(".txt"):
                    search_paths.append(os.path.join(docs_dir, f))

        query_lower = query.lower()
        matches: list[dict] = []

        for path in search_paths:
            if not os.path.exists(path):
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                for i, line in enumerate(lines):
                    if query_lower in line.lower():
                        context_before = "".join(lines[max(0, i - 1):i])
                        context_after = "".join(lines[i + 1:min(len(lines), i + 3)])
                        snippet = context_before + line + context_after
                        snippet = re.sub(r'\s+', ' ', snippet).strip()
                        matches.append({
                            "file": os.path.relpath(path, base),
                            "line": i + 1,
                            "snippet": snippet[:200],
                        })
            except Exception:
                pass

        if matches:
            lines_out = [f"在 {len(matches)} 个文档中找到匹配:"]
            for m in matches[:5]:
                lines_out.append(f"  [{m['file']}:{m['line']}] {m['snippet'][:120]}")
            observation = "\n".join(lines_out)
        else:
            observation = f"在项目文档中未找到 '{query}' 相关内容。"

        return ToolResult(
            success=True,
            message=f"Documentation search for: {query}",
            data={"query": query, "matches": matches},
            observation=observation,
        )


# ============================================================
# Tool: ask_user_for_help — call for human assistance
# ============================================================

class AskUserForHelpTool(BaseTool):
    """
    Output a structured help request for the user to act on.
    This is the last resort when all automatic recovery paths are exhausted.
    It outputs a clear, actionable message that the agent should present.

    The agent should call this when:
    - Docker Desktop won't start after multiple attempts
    - A critical system dependency is missing
    - The user needs to perform a manual action
    """

    definition = ToolDefinition(
        name="ask_user_for_help",
        description=(
            "Request human assistance for a step that cannot be resolved automatically. "
            "Use as a LAST RESORT when all automatic recovery options are exhausted. "
            "Outputs a structured, actionable help request that the user can act on.\n\n"
            "The agent should provide: what failed, what was tried, and what the user needs to do."
        ),
        category=ToolCategory.RESCUE,
        parameters={
            "type": "object",
            "properties": {
                "step": {
                    "type": "string",
                    "description": "Which bootstrap step failed (e.g. 'Docker daemon', 'Milvus', 'Embedding').",
                },
                "tried": {
                    "type": "string",
                    "description": "What the agent already tried.",
                    "default": "",
                },
                "user_action": {
                    "type": "string",
                    "description": "What the user needs to do to resolve it.",
                    "default": "",
                },
            },
            "required": ["step"],
        },
        returns="success: bool, help_request: dict, observation: str",
        examples=[
            "ask_user_for_help(step='Docker daemon', tried='launch_docker_desktop x3', user_action='Start Docker Desktop manually from Start menu')",
        ],
    )

    def _execute(
        self,
        step: str,
        tried: str = "",
        user_action: str = "",
        **kwargs,
    ) -> ToolResult:
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Build step-specific default actions
        defaults = {
            "Docker daemon": (
                "1. 按 Win 键，搜索 'Docker Desktop'，点击启动\n"
                "2. 等待约30秒直到 Docker 图标显示 'Running'\n"
                "3. 重新运行本程序"
            ),
            "Milvus": (
                "1. 确保 Docker Desktop 已启动\n"
                "2. 在终端运行: docker pull milvusdb/milvus:v2.4.0\n"
                "3. 重新运行本程序"
            ),
            "Embedding": (
                "1. 检查 .env 文件中的 EMBEDDING_BACKEND 配置\n"
                "2. 如果使用 OpenAI，确保 OPENAI_API_KEY 已设置\n"
                "3. 如果使用本地模型，确保 MODEL_PATH 正确"
            ),
        }

        action = user_action or defaults.get(step, "请查看上方错误信息并手动解决。")

        help_request = {
            "step": step,
            "tried": tried,
            "user_action": action,
            "continue_command": "python main_entry.py",
        }

        msg = [
            f"\n{'='*56}",
            f"  【需要人工干预】{step}",
            f"{'='*56}",
            f"  自动解决方案已用尽。请执行以下步骤:",
            f"",
            f"  {action}",
            f"",
            f"  完成后重新运行: python main_entry.py",
            f"{'='*56}\n",
        ]

        return ToolResult(
            success=True,
            message=f"User assistance requested for: {step}",
            data=help_request,
            observation="\n".join(msg),
        )


# ============================================================
# Tool: check_docker_desktop_health — diagnose Docker Desktop crashes
# ============================================================

class CheckDockerDesktopHealthTool(BaseTool):
    """
    Diagnose WHY Docker Desktop fails to start or crashes on Windows.
    Reads Windows Event Log, checks WSL2 backend health, WSL distributions,
    Docker Desktop logs, and Hyper-V status.

    Use when:
    - launch_docker_desktop succeeds but daemon never becomes ready
    - Docker Desktop appears to start but immediately exits
    - The agent is stuck on "Docker daemon not running" despite launching
    """

    definition = ToolDefinition(
        name="check_docker_desktop_health",
        description=(
            "Diagnose WHY Docker Desktop fails to start or crashes on Windows. "
            "Checks: Windows Event Log for Docker errors, WSL2 backend health, "
            "WSL distributions (docker-desktop, docker-desktop-data), Docker Desktop logs, "
            "Hyper-V status, and common failure patterns.\n\n"
            "Use this BEFORE calling launch_docker_desktop again, or when Docker Desktop "
            "appears to start but immediately exits."
        ),
        category=ToolCategory.RESCUE,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        returns="success: bool, diagnosis: dict, likely_cause: str, "
                "fix_steps: list[str], observation: str",
        examples=[
            "check_docker_desktop_health()",
            "check_docker_desktop_health() then web_search() with findings",
        ],
    )

    def _execute(self, **kwargs) -> ToolResult:
        import os
        findings: dict[str, Any] = {}
        fix_steps: list[str] = []
        likely_cause = "unknown"

        # --- WSL2 core check ---
        try:
            r = subprocess.run(
                ["wsl", "--status"], capture_output=True, timeout=10, encoding="utf-8", errors="replace",
            )
            findings["wsl_status"] = r.stdout.strip()
        except Exception as e:
            findings["wsl_status"] = f"error: {e}"
            fix_steps.append("WSL2 未安装或损坏：运行 'wsl --install' 安装 WSL2")

        # --- WSL distributions ---
        try:
            r = subprocess.run(
                ["wsl", "--list", "--verbose"], capture_output=True, timeout=10, encoding="utf-8", errors="replace",
            )
            findings["wsl_distributions"] = r.stdout.strip()
            # Check for Docker-related distros
            docker_desktop_distros = []
            for line in r.stdout.splitlines():
                if "docker" in line.lower() or "docker-desktop" in line.lower():
                    docker_desktop_distros.append(line.strip())
            findings["docker_desktop_distros"] = docker_desktop_distros
            if not docker_desktop_distros:
                fix_steps.append(
                    "WSL 中缺少 docker-desktop 分发版："
                    "重启 Docker Desktop（任务管理器结束进程后重新启动）"
                )
        except Exception as e:
            findings["wsl_distributions"] = f"error: {e}"

        # --- WSL2 backend health (docker-desktop-data check) ---
        try:
            r = subprocess.run(
                ["wsl", "-d", "docker-desktop-data", "--", "ps"],
                capture_output=True, timeout=10, encoding="utf-8", errors="replace",
            )
            findings["docker_desktop_data_health"] = (
                "running" if r.returncode == 0 else f"error: {r.stderr[:100]}"
            )
        except Exception as e:
            findings["docker_desktop_data_health"] = f"unreachable: {e}"
            fix_steps.append(
                "docker-desktop-data WSL 分发版无法访问："
                "运行 'wsl --shutdown' 后重启 WSL"
            )

        # --- Windows Event Log (Docker errors) ---
        docker_events = []
        try:
            r = subprocess.run(
                [
                    "powershell", "-Command",
                    "Get-WinEvent -FilterHashtable @{LogName='Application'; "
                    "ProviderName='Application Error'; StartTime=(Get-Date).AddHours(-1)} "
                    "-MaxEvents 20 -ErrorAction SilentlyContinue | "
                    "Where-Object { $_.Message -like '*Docker*' -or $_.Message -like '*docker*' } | "
                    "Select-Object -First 5 TimeCreated, Message | "
                    "ConvertTo-Json -Compress"
                ],
                capture_output=True, timeout=15, encoding="utf-8", errors="replace",
            )
            if r.stdout.strip():
                import json
                try:
                    docker_events = json.loads(r.stdout)
                    if isinstance(docker_events, dict):
                        docker_events = [docker_events]
                except Exception:
                    docker_events = [{"raw": r.stdout[:500]}]
        except Exception:
            pass
        findings["recent_docker_events"] = docker_events

        # --- Docker Desktop log files ---
        log_files = []
        log_paths = [
            os.path.expandvars(r"%LOCALAPPDATA%\Docker\log"),
            os.path.expandvars(r"%APPDATA%\Docker\log"),
            os.path.expandvars(r"%LOCALAPPDATA%\Docker Desktop"),
        ]
        for lp in log_paths:
            if os.path.isdir(lp):
                try:
                    files = sorted(
                        os.listdir(lp),
                        key=lambda x: os.path.getmtime(os.path.join(lp, x)),
                        reverse=True,
                    )
                    for f in files[:5]:
                        fp = os.path.join(lp, f)
                        if os.path.isfile(fp):
                            size = os.path.getsize(fp)
                            log_files.append({"name": f, "path": fp, "size_bytes": size})
                except Exception:
                    pass
        findings["log_files"] = log_files

        # --- Read latest Docker Desktop log for errors ---
        latest_errors = []
        if log_files:
            latest = log_files[0]
            try:
                with open(latest["path"], encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                for line in lines[-200:]:  # last 200 lines
                    lower = line.lower()
                    if any(kw in lower for kw in [
                        "error", "exception", "failed", "panic", "crash", "wsl"
                    ]):
                        latest_errors.append(line.strip())
                latest_errors = latest_errors[-20:]  # last 20 error lines
            except Exception:
                pass
        findings["latest_log_errors"] = latest_errors

        # --- Hyper-V check ---
        try:
            r = subprocess.run(
                ["powershell", "-Command",
                 "(Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All).State"],
                capture_output=True, timeout=10, encoding="utf-8", errors="replace",
            )
            findings["hyperv"] = r.stdout.strip()
        except Exception as e:
            findings["hyperv"] = f"error: {e}"

        # --- Diagnose ---
        if findings.get("wsl_distributions") and "docker-desktop" not in findings["wsl_distributions"].lower():
            likely_cause = "missing_docker_desktop_wsl"
            if not fix_steps:
                fix_steps.append("WSL 分发版 docker-desktop 丢失：打开 PowerShell 运行 'wsl --shutdown' 后重新启动 Docker Desktop")
        elif latest_errors:
            for err in latest_errors[:5]:
                if "wsl" in err.lower() and "update" in err.lower():
                    likely_cause = "wsl2_update_required"
                    fix_steps.insert(0, "WSL2 内核需要更新：运行 'wsl --update' 更新 WSL 内核")
                    break
                elif "hyper-v" in err.lower() or "hyperv" in err.lower():
                    likely_cause = "hyperv_issue"
                    if not any("hyper" in s.lower() for s in fix_steps):
                        fix_steps.insert(0, "Hyper-V 配置问题：确保 'Windows 功能' 中 Hyper-V 已启用")
                    break
            if likely_cause == "unknown":
                likely_cause = "log_errors_found"
        elif findings.get("wsl_distributions"):
            lines = findings["wsl_distributions"].splitlines()
            for line in lines[1:]:
                if "docker-desktop" in line.lower():
                    parts = line.split()
                    if len(parts) >= 4 and parts[3] in ("Stopped", "Stopping"):
                        likely_cause = "docker_desktop_wsl_stopped"
                        fix_steps.append(
                            "docker-desktop WSL 分发版处于停止状态："
                            "运行 'wsl -t docker-desktop' 和 'wsl -t docker-desktop-data' 后重启 Docker Desktop"
                        )
        if not likely_cause or likely_cause == "unknown":
            likely_cause = "undetermined"
            fix_steps.append("请查看 Docker Desktop 日志文件获取详细信息")

        # --- Build observation ---
        obs_parts = [f"诊断原因: {likely_cause}"]
        if latest_errors:
            obs_parts.append(f"日志错误数: {len(latest_errors)}")
        if fix_steps:
            obs_parts.append("修复步骤:")
            for step in fix_steps[:5]:
                obs_parts.append(f"  - {step}")

        return ToolResult(
            success=True,
            message="Docker Desktop health check complete",
            data={
                "likely_cause": likely_cause,
                "findings": findings,
                "fix_steps": fix_steps,
            },
            observation=" | ".join(obs_parts[:3]) + "\n" + "\n".join(f"  → {s}" for s in fix_steps[:5]),
        )


# ============================================================
# Tool: fix_docker_desktop — attempt known fixes for Windows
# ============================================================

class FixDockerDesktopTool(BaseTool):
    """
    Attempt common fixes for Docker Desktop on Windows.
    Uses the diagnosis from check_docker_desktop_health to apply the right fix:
    - WSL shutdown and restart
    - Reset Docker Desktop
    - Clear WSL docker-desktop distributions
    - Update WSL kernel
    """

    definition = ToolDefinition(
        name="fix_docker_desktop",
        description=(
            "Attempt to fix Docker Desktop issues on Windows using known remediation steps. "
            "Options: 'wsl_shutdown' (restart WSL), 'reset' (reset Docker Desktop data), "
            "'update_wsl' (update WSL kernel), 'restart_service' (restart Docker Engine service).\n\n"
            "Use after check_docker_desktop_health() identifies the root cause."
        ),
        category=ToolCategory.RESCUE,
        parameters={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Fix action: 'wsl_shutdown', 'reset', 'update_wsl', 'restart_service'.",
                },
            },
            "required": ["action"],
        },
        returns="success: bool, action_taken: str, observation: str",
        examples=[
            "fix_docker_desktop(action='wsl_shutdown')",
            "fix_docker_desktop(action='update_wsl')",
        ],
    )

    def _execute(self, action: str, **kwargs) -> ToolResult:
        if sys.platform != "win32":
            return ToolResult(
                success=False,
                message="fix_docker_desktop is only available on Windows",
                observation="此工具仅适用于 Windows 系统。",
            )

        results: dict[str, Any] = {}

        if action == "wsl_shutdown":
            try:
                r = subprocess.run(
                    ["wsl", "--shutdown"], capture_output=True, timeout=10, encoding="utf-8", errors="replace",
                )
                results["wsl_shutdown"] = "success" if r.returncode == 0 else r.stderr[:200]
                return ToolResult(
                    success=True,
                    message="WSL shutdown complete",
                    data={"action": "wsl_shutdown", "result": results},
                    observation=(
                        "WSL 已关闭。请手动重新启动 Docker Desktop，"
                        "或在任务管理器中重启 Docker Desktop 进程。"
                    ),
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    message=f"WSL shutdown failed: {e}",
                    observation=f"WSL 关闭失败: {e}",
                )

        elif action == "update_wsl":
            try:
                r = subprocess.run(
                    ["wsl", "--update"], capture_output=True, timeout=30, encoding="utf-8", errors="replace",
                )
                results["wsl_update"] = r.stdout.strip() or r.stderr.strip()
                return ToolResult(
                    success=True,
                    message="WSL kernel update triggered",
                    data={"action": "update_wsl", "result": results},
                    observation=f"WSL 内核更新完成: {results['wsl_update']}",
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    message=f"WSL update failed: {e}",
                    observation=f"WSL 更新失败: {e}",
                )

        elif action == "reset":
            try:
                # Run Docker Desktop reset
                reset_script = (
                    "Remove-Item -Path '$env:APPDATA\\Docker\\settings.json' -Force -ErrorAction SilentlyContinue; "
                    "Remove-Item -Path '$env:LOCALAPPDATA\\Docker\\settings.json' -Force -ErrorAction SilentlyContinue; "
                    "'Docker Desktop settings reset'"
                )
                r = subprocess.run(
                    ["powershell", "-Command", reset_script],
                    capture_output=True, timeout=10, encoding="utf-8", errors="replace",
                )
                results["reset"] = r.stdout.strip() or "settings files cleared"
                return ToolResult(
                    success=True,
                    message="Docker Desktop reset complete",
                    data={"action": "reset", "result": results},
                    observation=(
                        "Docker Desktop 设置已重置。请手动重启 Docker Desktop。"
                    ),
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    message=f"Docker Desktop reset failed: {e}",
                    observation=f"重置失败: {e}",
                )

        elif action == "restart_service":
            try:
                r = subprocess.run(
                    ["powershell", "-Command",
                     "Restart-Service com.docker.service -ErrorAction SilentlyContinue; "
                     "'service restart attempted'"],
                    capture_output=True, timeout=10, encoding="utf-8", errors="replace",
                )
                results["restart_service"] = r.stdout.strip()
                return ToolResult(
                    success=True,
                    message="Docker service restart attempted",
                    data={"action": "restart_service", "result": results},
                    observation=results["restart_service"],
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    message=f"Docker service restart failed: {e}",
                    observation=f"服务重启失败: {e}",
                )

        else:
            return ToolResult(
                success=False,
                message=f"Unknown action: {action}",
                observation=f"未知操作: {action}。可用: wsl_shutdown, reset, update_wsl, restart_service",
            )


# ============================================================
# Register all rescue tools
# ============================================================

def register_tools(registry: ToolRegistry) -> None:
    registry.register(WebSearchTool())
    registry.register(DeepSystemDiagnosticsTool())
    registry.register(CheckDockerDesktopHealthTool())
    registry.register(FixDockerDesktopTool())
    registry.register(SkipBootstrapStepTool())
    registry.register(CheckDocsTool())
    registry.register(AskUserForHelpTool())
