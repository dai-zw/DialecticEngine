#!/usr/bin/env python3
"""Write docker_tools.py with correct UTF-8 encoding."""
import sys

content = """\"\"\"
Docker-related tools: check daemon status, launch Docker Desktop, manage containers.
\"\"\"

from __future__ import annotations

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


def _is_windows() -> bool:
    return sys.platform == \"win32\"


def _run(args, timeout=30, check=False):
    return subprocess.run(
        args,
        capture_output=True,
        encoding=\"utf-8\",
        errors=\"replace\",
        timeout=timeout,
        check=check,
    )


def _diag_docker_status():
    import shutil
    cli_found = bool(shutil.which(\"docker\"))
    if not cli_found:
        return False, False, \"Docker CLI \u672a\u5b89\u88c5\"
    try:
        r = _run([\"docker\", \"info\"], timeout=8)
        if r.returncode == 0:
            return True, True, \"Docker daemon \u5c31\u7eea\"
        stderr_lower = r.stderr.lower()
        if any(kw in stderr_lower for kw in [\"not logged\", \"authenticate\", \"401\", \"unauthorized\"]):
            return True, False, \"Docker \u672a\u767b\u5f55\uff08\u8ba4\u8bc1\u5931\u8d25\uff09\"
        if any(kw in stderr_lower for kw in [\"connection refused\", \"is the docker daemon running\", \"cannot connect\"]):
            return True, False, \"Docker daemon \u672a\u8fd0\u884c\"
        if any(kw in stderr_lower for kw in [\"wsl\", \"WSL\"]):
            return True, False, \"WSL2 \u95ee\u9898\uff0cDocker Desktop \u53ef\u80fd\u5f02\u5e38\"
        return True, False, \"docker info \u5931\u8d25: \" + r.stderr[:100]
    except Exception as e:
        return True, False, \"\u68c0\u67e5\u5f02\u5e38: \" + str(e)


def check_docker_prereqs(max_soft_prompts=3):
    import shutil

    def _print_block(lines):
        for line in lines:
            print(line)

    def _banner(title, char=\"=\"):
        width = max(shutil.get_terminal_size().columns, 60)
        _print_block([\"\", char * width, f\"  {title}\", char * width, \"\"])

    soft_prompts = 0
    while True:
        installed, ready, detail = _diag_docker_status()
        if ready:
            _banner(\"\u4e0a\u6d77\u4e2d Docker \u5c31\u7eea\", \"=\")
            print(f\"  {detail}  (docker info \u6210\u529f)\")
            return \"ok\"

        soft_prompts += 1
        _banner(\"\u4e0b\u6d77\u4e2d Docker \u672a\u5c31\u7eea\", \"=\")

        if not installed:
            _print_block([
                \"  [\u6b65\u9aa4 1] \u5b89\u88c5 Docker Desktop\",
                \"  --------------------\",
                \"  1. \u4e0b\u8f7d: https://www.docker.com/products/docker-desktop/\",
                \"  2. \u8fd0\u884c\u5b89\u88c5\u7a0b\u5e8f\uff08Windows \u7248\uff09\",
                \"  3. \u5b89\u88c5\u8fc7\u7a0b\u4e2d\u52fe\u9009 Use WSL 2 instead of Hyper-V (\u63a8\u8350)\",
                \"  4. \u5b89\u88c5\u5b8c\u6210\u540e\u4ece\u5f00\u59cb\u83dc\u5355\u542f\u52a8 Docker Desktop\",
                \"  5. \u7b49\u5f85\u6258\u76d8\u56fe\u6807\u53d8\u4e3a\u7eff\u8272\",
                \"\",
            ])
        else:
            _print_block([
                f\"  \u8bca\u65ad\u8be6\u60c5: {detail}\",
                \"\",
                \"  [\u6b65\u9aa4 1] \u542f\u52a8 Docker Desktop\",
                \"  --------------------\",
                \"  - \u4ece\u5f00\u59cb\u83dc\u5355\u542f\u52a8 Docker Desktop\",
                \"  - \u7b49\u5f85\u6258\u76d8\u56fe\u6807\u53d8\u4e3a\u7eff\u8272\uff08\u7ea6 20-40 \u79d2\uff09\",
                \"\",
                \"  [\u6b65\u9aa4 2] \u767b\u5f55 Docker Hub\uff08\u5982\u679c\u9700\u8981\uff09\",
                \"  --------------------\",
                \"  - \u6253\u5f00 Docker Desktop\",
                \"  - \u53f3\u4e0a\u89d2 Sign In \u767b\u5f55 Docker Hub \u8d26\u53f7\",
                \"  - \u516c\u5f00\u955c\u50cf\uff08milvusdb/milvus\uff09\u65e0\u9700\u767b\u5f55\",
                \"\",
            ])

        _print_block([
            \"  \u8bf7\u5b8c\u6210\u4e0a\u8ff0\u64cd\u4f5c\u540e\u8f93\u5165\u9009\u9879:\",
            \"    r/R  - \u5df2\u5b8c\u6210\uff0c\u91cd\u65b0\u68c0\u6d4b\",
            \"    s/S  - \u8df3\u8fc7\u68c0\u67e5\uff0c\u76f4\u63a5\u542f\u52a8\uff08milvus \u529f\u80fd\u53ef\u80fd\u4e0d\u53ef\u7528\uff09\",
            \"    q/Q  - \u9000\u51fa\u7a0b\u5e8f\",
            \"\",
        ])

        if soft_prompts > max_soft_prompts:
            _print_block([
                \"  [\u786c\u505c\u6b62] \u5df2\u91cd\u8bd5\u591a\u6b21\u4ecd\u5931\u8d25\",
                \"  --------------------\",
                \"  \u8bf7\u624b\u52a8\u89e3\u51b3 Docker \u95ee\u9898\u540e\u518d\u6b21\u8fd0\u884c\u7a0b\u5e8f\u3002\",
                \"  \u8f93\u5165 q \u9000\u51fa\uff0c\u6216\u8f93\u5165 r \u518d\u8bd5\u4e00\u6b21: \",
            ])

        try:
            choice = input(\">>> \").strip().lower()
        except (KeyboardInterrupt, EOFError):
            _print_block([\"\", \"  \u5df2\u9000\u51fa\u3002\", \"\"])
            return \"failed\"

        if choice == \"q\":
            _print_block([\"\", \"  \u5df2\u9000\u51fa\u3002\", \"\"])
            return \"failed\"
        elif choice == \"s\":
            _print_block([\"\", \"  \u5df2\u8df3\u8fc7 Docker \u68c0\u67e5\uff0cmilvus \u529f\u80fd\u5c06\u4e0d\u53ef\u7528\u3002\", \"\"])
            return \"skipped\"
        elif choice == \"r\":
            continue
        else:
            _print_block([\"\", \"  \u65e0\u6548\u8f93\u5165\uff0c\u8bf7\u8f93\u5165 r / s / q\", \"\"])


class CheckDevicePlatformTool(BaseTool):
    definition = ToolDefinition(
        name=\"check_device_platform\",
        description=\"Detect the current device operating system.\",
        category=ToolCategory.SYSTEM,
        parameters={\"type\": \"object\", \"properties\": {}, \"required\": []},
        returns=\"success, platform, docker_desktop_applicable, observation\",
        examples=[\"check_device_platform()\"],
    )

    def _execute(self, **kwargs):
        import platform as pmod
        p = sys.platform
        if p == \"win32\":
            os_name = \"Windows\"; dda = True; note = \"Docker Desktop for Windows\"
        elif p == \"darwin\":
            os_name = \"macOS\"; dda = False; note = \"macOS \u9700\u8981 Docker Desktop for Mac\"
        elif p.startswith(\"linux\"):
            os_name = \"Linux\"; dda = False; note = \"Linux \u9700\u8981 dockerd \u670d\u52a1\"
        else:
            os_name = f\"Unknown ({p})\"; dda = False; note = f\"\u672a\u77e5\u5e73\u53f0: {p}\"
        return ToolResult(
            success=True,
            message=f\"Platform: {os_name}\",
            data={\"platform\": os_name, \"raw_platform\": p, \"is_windows\": p == \"win32\",
                  \"is_macos\": p == \"darwin\", \"is_linux\": p.startswith(\"linux\"),
                  \"docker_desktop_applicable\": dda, \"system\": pmod.system(),
                  \"release\": pmod.release()},
            observation=f\"\u5e73\u53f0: {os_name} | {note}\" if note else f\"\u5e73\u53f0: {os_name}\",
        )


class CheckDockerDaemonTool(BaseTool):
    definition = ToolDefinition(
        name=\"check_docker_daemon\",
        description=\"Check if Docker daemon is running and accessible.\",
        category=ToolCategory.DOCKER,
        parameters={\"type\": \"object\", \"properties\": {}, \"required\": []},
        returns=\"success, version, observation\",
        examples=[\"check_docker_daemon()\"],
    )

    def _execute(self, **kwargs):
        try:
            r = _run([\"docker\", \"info\"], timeout=8)
            if r.returncode != 0:
                return ToolResult(success=False, message=\"Docker daemon not accessible\",
                                 error=r.stderr[:200] if r.stderr else None,
                                 observation=\"docker info returned non-zero.\")
            version = None
            for line in r.stdout.splitlines():
                if line.startswith(\"Server Version:\"):
                    version = line.split(\":\", 1)[1].strip()
                    break
            return ToolResult(success=True, message=\"Docker daemon is running\",
                              data={\"version\": version},
                              observation=f\"Docker daemon is accessible (Server Version: {version})\")
        except Exception as exc:
            return ToolResult(success=False, message=\"Docker daemon check failed\",
                              error=str(exc), observation=f\"Could not connect: {exc}\")


class CheckDockerLoginTool(BaseTool):
    definition = ToolDefinition(
        name=\"check_docker_login\",
        description=\"Check if Docker CLI is authenticated to Docker Hub.\",
        category=ToolCategory.DOCKER,
        parameters={\"type\": \"object\", \"properties\": {}, \"required\": []},
        returns=\"success, logged_in, auth_details, observation\",
        examples=[\"check_docker_login()\"],
    )

    def _execute(self, **kwargs):
        import json, os
        auth_details = {}; logged_in = False
        try:
            r = subprocess.run([\"docker\", \"info\"], capture_output=True, timeout=10,
                               encoding=\"utf-8\", errors=\"replace\")
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    if \"Username:\" in line:
                        auth_details[\"username\"] = line.split(\":\", 1)[1].strip(); logged_in = True
        except Exception as e:
            auth_details[\"docker_info_exception\"] = str(e)

        cfg_paths = []
        if sys.platform == \"win32\":
            cfg_paths = [os.path.expandvars(r\"%USERPROFILE%\\.docker\\config.json\"),
                         os.path.expandvars(r\"%APPDATA%\\Docker\\config.json\")]
        else:
            cfg_paths = [os.path.expandenv(\"HOME\", \"/root\") + \"/.docker/config.json\"]
        for cpath in cfg_paths:
            if os.path.exists(cpath):
                try:
                    with open(cpath, encoding=\"utf-8\", errors=\"replace\") as f:
                        cfg = json.load(f)
                    auths = cfg.get(\"auths\", {})
                    if auths:
                        auth_details[\"config_file\"] = cpath
                        auth_details[\"registries\"] = list(auths.keys())
                        for reg, creds in auths.items():
                            if creds.get(\"auth\"):
                                logged_in = True
                                auth_details[\"authenticated_registries\"] = list(auths.keys())
                                break
                except Exception:
                    pass

        pull_works = None
        try:
            r = subprocess.run([\"docker\", \"pull\", \"--quiet\", \"hello-world\"],
                               capture_output=True, timeout=30, encoding=\"utf-8\", errors=\"replace\")
            pull_works = r.returncode == 0
            auth_details[\"pull_test\"] = \"success\" if r.returncode == 0 else r.stderr[:100]
        except Exception as e:
            pull_works = False
            auth_details[\"pull_test\"] = f\"error: {e}\"

        if logged_in:
            obs = \"Docker \u5df2\u767b\u5f55\u3002\u5df2\u8ba4\u8bc1: \" + \", \".join(auth_details.get(\"authenticated_registries\", [\"Docker Hub\"]))
        else:
            if pull_works is False:
                obs = \"Docker \u672a\u767b\u5f55\u6216\u8ba4\u8bc1\u5df2\u8fc7\u671f\uff08docker pull \u6d4b\u8bd5\u5931\u8d25\uff09\u3002\u8bf7\u8fd0\u884c: docker login\"
            else:
                obs = \"Docker CLI \u672a\u767b\u5f55\uff0c\u4f46 pull \u53ef\u80fd\u4ecd\u53ef\u7528\uff08\u516c\u5f00\u955c\u50cf\uff09\u3002\"
                auth_details[\"note\"] = \"\u672a\u767b\u5f55\uff0c\u533f\u540d\u8bbf\u95ee\u516c\u5f00\u955c\u50cf\"

        return ToolResult(success=True, message=\"Docker login check complete\",
                          data={\"logged_in\": logged_in, \"pull_works\": pull_works, \"auth_details\": auth_details},
                          observation=obs)


class CheckDockerInstalledTool(BaseTool):
    definition = ToolDefinition(
        name=\"check_docker_installed\",
        description=\"Check if Docker is installed (CLI and Desktop).\",
        category=ToolCategory.DOCKER,
        parameters={\"type\": \"object\", \"properties\": {}, \"required\": []},
        returns=\"success, docker_installed, docker_desktop_installed, wsl2_installed, observation\",
        examples=[\"check_docker_installed()\"],
    )

    def _execute(self, **kwargs):
        import os, shutil
        cli_found = bool(shutil.which(\"docker\"))
        cli_version = None
        if cli_found:
            try:
                r = _run([\"docker\", \"--version\"], timeout=5)
                if r.returncode == 0: cli_version = r.stdout.strip()
            except Exception: pass
        desktop_found = False; desktop_path = None
        if sys.platform == \"win32\":
            for path in [os.path.expandvars(r\"%ProgramFiles%\\Docker\\Docker\\Docker Desktop.exe\"),
                         os.path.expandvars(r\"%LocalAppData%\\Docker\\Docker Desktop.exe\"),
                         r\"C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe\"]:
                if os.path.exists(path): desktop_found = True; desktop_path = path; break
        wsl_found = False
        if sys.platform == \"win32\":
            try:
                r = subprocess.run([\"wsl\", \"--list\", \"--verbose\"], capture_output=True, timeout=10,
                                   encoding=\"utf-8\", errors=\"replace\")
                wsl_found = r.returncode == 0
            except Exception: pass
        installed = cli_found; desktop_installed = desktop_found
        parts = []
        if cli_version: parts.append(\"Docker CLI: \u5df2\u5b89\u88c5\")
        elif cli_found: parts.append(\"Docker CLI: \u5df2\u5b89\u88c5\")
        else: parts.append(\"Docker CLI: \u672a\u5b89\u88c5\")
        if sys.platform == \"win32\":
            parts.append(\"Docker Desktop: \" + (\"\u5df2\u5b89\u88c5\" if desktop_found else \"\u672a\u5b89\u88c5\"))
            parts.append(\"WSL2: \" + (\"\u5df2\u5b89\u88c5\" if wsl_found else \"\u672a\u5b89\u88c5\"))
            if not desktop_found and not cli_found:
                parts.append(\"\u5efa\u8bae: \u5b89\u88c5 Docker Desktop for Windows\")
        elif not installed:
            parts.append(\"\u5efa\u8bae: \u5b89\u88c5 Docker Engine\")
        return ToolResult(success=True, message=\"Docker installation check complete\",
                          data={\"docker_installed\": installed, \"docker_desktop_installed\": desktop_installed,
                                \"docker_desktop_path\": desktop_path, \"wsl2_installed\": wsl_found,
                                \"cli_version\": cli_version},
                          observation=\" | \".join(parts))


class LaunchDockerDesktopTool(BaseTool):
    definition = ToolDefinition(
        name=\"launch_docker_desktop\",
        description=\"Launch Docker Desktop on Windows.\",
        category=ToolCategory.DOCKER,
        parameters={\"type\": \"object\", \"properties\": {}, \"required\": []},
        returns=\"success, daemon_ready, observation\",
        examples=[\"launch_docker_desktop()\"],
    )

    def _execute(self, **kwargs):
        import os
        if not _is_windows():
            return ToolResult(success=True, message=\"Not on Windows, skipping\",
                              data={\"launched\": False}, observation=\"Only on Windows.\")
        try:
            r = _run([\"tasklist\", \"/FI\", \"IMAGENAME eq Docker Desktop.exe\", \"/NH\"], timeout=10)
            already_running = \"Docker Desktop.exe\" in r.stdout
        except Exception: already_running = False
        if already_running:
            return ToolResult(success=True, message=\"Docker Desktop already running\",
                              data={\"launched\": False, \"already_running\": True},
                              observation=\"Docker Desktop.exe is already running.\")
        desktop_exe = None
        for path in [os.path.expandvars(r\"%ProgramFiles%\\Docker\\Docker\\Docker Desktop.exe\"),
                      os.path.expandvars(r\"%LocalAppData%\\Docker\\Docker Desktop.exe\"),
                      r\"C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe\"]:
            if os.path.exists(path): desktop_exe = path; break
        if not desktop_exe:
            return ToolResult(success=False, message=\"Docker Desktop executable not found\",
                              data={\"launched\": False},
                              observation=\"\u672a\u627e\u5230 Docker Desktop\uff0c\u8bf7\u4ece https://docs.docker.com/desktop/install/windows-install/ \u4e0b\u8f7d\u3002\")
        try:
            subprocess.Popen([desktop_exe, \"--version-switch\"], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, cwd=os.path.dirname(desktop_exe))
            return ToolResult(success=True, message=\"Docker Desktop launch initiated\",
                              data={\"launched\": True, \"already_running\": False, \"executable\": desktop_exe},
                              observation=f\"Docker Desktop \u5df2\u542f\u52a8\u3002\u7b49\u5f85 20-40 \u79d2\u540e\u8c03\u7528 check_docker_daemon() \u786e\u8ba4\u3002\")
        except Exception as exc:
            return ToolResult(success=False, message=\"Failed to launch Docker Desktop\",
                              error=str(exc), observation=\"\u65e0\u6cd5\u542f\u52a8 Docker Desktop\u3002\u8bf7\u624b\u52a8\u4ece\u5f00\u59cb\u83dc\u5355\u542f\u52a8\u3002\")


class WaitDockerReadyTool(BaseTool):
    definition = ToolDefinition(
        name=\"wait_docker_ready\",
        description=\"Poll docker info until daemon responds or timeout.\",
        category=ToolCategory.DOCKER,
        parameters={\"type\": \"object\", \"properties\": {\"timeout\": {\"type\": \"integer\", \"default\": 60}},
                    \"required\": []},
        returns=\"success, waited_seconds, observation\",
        examples=[\"wait_docker_ready(timeout=45)\"],
    )

    def _execute(self, timeout=60, **kwargs):
        start = time.time()
        for i in range(timeout):
            if CheckDockerDaemonTool().execute().success:
                elapsed = int(time.time() - start)
                return ToolResult(success=True, message=f\"Docker daemon ready after {elapsed}s\",
                                  data={\"waited_seconds\": elapsed},
                                  observation=f\"Docker daemon responded after {elapsed} seconds.\")
            time.sleep(1)
        elapsed = int(time.time() - start)
        return ToolResult(success=False, message=f\"Docker daemon not ready after {elapsed}s\",
                          data={\"waited_seconds\": elapsed},
                          observation=f\"Timed out after {elapsed}s.\")


class CheckPortTool(BaseTool):
    definition = ToolDefinition(
        name=\"check_port\",
        description=\"Check if a TCP port is open on localhost.\",
        category=ToolCategory.DOCKER,
        parameters={\"type\": \"object\", \"properties\": {\"port\": {\"type\": \"integer\"}, \"timeout\": {\"type\": \"number\", \"default\": 2.0}},
                    \"required\": [\"port\"]},
        returns=\"success, observation\",
        examples=[\"check_port(port=19530)\"],
    )

    def _execute(self, port, timeout=2.0, **kwargs):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect((\"localhost\", port))
            return ToolResult(success=True, message=f\"Port {port} is open\",
                              data={\"port\": port, \"open\": True},
                              observation=f\"TCP port {port} is accepting connections.\")
        except (socket.timeout, ConnectionRefusedError, OSError) as exc:
            return ToolResult(success=False, message=f\"Port {port} is not open\",
                              data={\"port\": port, \"open\": False},
                              observation=f\"Port {port} not accepting connections ({type(exc).__name__}).\")
        finally:
            sock.close()


class DockerContainerStatusTool(BaseTool):
    definition = ToolDefinition(
        name=\"docker_container_status\",
        description=\"Get status of a Docker container by name.\",
        category=ToolCategory.DOCKER,
        parameters={\"type\": \"object\", \"properties\": {\"name\": {\"type\": \"string\"}}, \"required\": [\"name\"]},
        returns=\"success, status, observation\",
        examples=[\"docker_container_status(name='dialectic_milvus')\"],
    )

    def _execute(self, name, **kwargs):
        try:
            r = _run([\"docker\", \"inspect\", \"--format={{.State.Status}}\", name], timeout=10, check=False)
            if r.returncode == 0:
                status = r.stdout.strip()
                return ToolResult(success=True, message=f\"Container '{name}' status: {status}\",
                                  data={\"name\": name, \"status\": status},
                                  observation=f\"Container '{name}' is {status}.\")
            return ToolResult(success=False, message=f\"Container '{name}' not found\",
                              data={\"name\": name, \"status\": \"missing\"},
                              observation=f\"No container named '{name}' exists.\")
        except Exception as exc:
            return ToolResult(success=False, message=f\"Failed to query container '{name}'\", error=str(exc))


class StartDockerContainerTool(BaseTool):
    definition = ToolDefinition(
        name=\"start_docker_container\",
        description=\"Start a stopped container, or create it if missing.\",
        category=ToolCategory.DOCKER,
        parameters={\"type\": \"object\",
                    \"properties\": {\"name\": {\"type\": \"string\"}, \"image\": {\"type\": \"string\"},
                                   \"args\": {\"type\": \"array\", \"items\": {\"type\": \"string\"}},
                                   \"pull\": {\"type\": \"boolean\", \"default\": True}},
                    \"required\": [\"name\", \"image\", \"args\"]},
        returns=\"success, created, observation\",
        examples=[\"start_docker_container(name='dialectic_milvus', image='milvusdb/milvus:v2.4.0', args=['-d','--name','dialectic_milvus','-p','19530:19530','milvusdb/milvus:v2.4.0'])\"],
    )

    def _execute(self, name, image, args, pull=True, **kwargs):
        sr = DockerContainerStatusTool().execute(name=name)
        status = sr.data.get(\"status\") if sr.success else \"missing\"
        if status == \"running\":
            return ToolResult(success=True, message=f\"Container '{name}' already running\",
                              data={\"name\": name, \"created\": False, \"started\": False},
                              observation=f\"Container '{name}' is already running.\")
        if status == \"stopped\":
            try:
                r = _run([\"docker\", \"start\", name], timeout=15)
                if r.returncode == 0:
                    return ToolResult(success=True, message=f\"Container '{name}' started\",
                                      data={\"name\": name, \"created\": False, \"started\": True},
                                      observation=f\"Container '{name}' was stopped, now started.\")
                return ToolResult(success=False, message=f\"Failed to start '{name}'\", error=r.stderr[:200])
            except Exception as exc:
                return ToolResult(success=False, message=f\"Failed to start '{name}'\", error=str(exc))
        if pull:
            try:
                r = _run([\"docker\", \"pull\", image], timeout=300)
                if r.returncode != 0:
                    return ToolResult(success=False, message=f\"Failed to pull '{image}'\", error=r.stderr[:200],
                                      observation=f\"Could not pull '{image}'.\")
            except subprocess.TimeoutExpired:
                return ToolResult(success=False, message=f\"Image pull timed out for '{image}'\",
                                  observation=\"Image pull took > 5 minutes.\")
        try:
            r = _run([\"docker\", \"run\"] + args, timeout=30, check=False)
            if r.returncode != 0:
                return ToolResult(success=False, message=f\"Failed to create '{name}'\", error=r.stderr[:200],
                                  observation=f\"docker run failed: {r.stderr[:200]}\")
            return ToolResult(success=True, message=f\"Container '{name}' created and started\",
                              data={\"name\": name, \"created\": True, \"started\": True},
                              observation=f\"Container '{name}' created from '{image}' and starting.\")
        except Exception as exc:
            return ToolResult(success=False, message=f\"Failed to create '{name}'\", error=str(exc))


def register_tools(registry):
    registry.register(CheckDevicePlatformTool())
    registry.register(CheckDockerLoginTool())
    registry.register(CheckDockerInstalledTool())
    registry.register(CheckDockerDaemonTool())
    registry.register(LaunchDockerDesktopTool())
    registry.register(WaitDockerReadyTool())
    registry.register(CheckPortTool())
    registry.register(DockerContainerStatusTool())
    registry.register(StartDockerContainerTool())
"""

with open(\"d:/DialecticEngine/tools/docker_tools.py\", \"w\", encoding=\"utf-8\") as f:
    f.write(content)
print(f\"Written {len(content)} chars to docker_tools.py\")
