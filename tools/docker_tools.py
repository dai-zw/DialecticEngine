"""
Docker-related tools: platform detection, Docker daemon check, port check, container management.
Simplified for resume project - focuses on Agent tool-calling showcase, not DevOps details.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from typing import Any

from .base import (
    BaseTool,
    ToolCategory,
    ToolDefinition,
    ToolResult,
)


# ============================================================
# Platform helpers
# ============================================================

def _run(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a subprocess command with timeout."""
    return subprocess.run(
        args,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _is_port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is open."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


# ============================================================
# Pre-flight check (used by main_entry.py)
# ============================================================

def check_docker_prereqs() -> bool:
    """
    Simple Docker/Milvus readiness check.
    Returns True if Docker daemon is running, False otherwise.
    Milvus check is delegated to the Bootstrap Agent.
    """
    print("\n[1/2] Checking Docker daemon...")
    
    try:
        r = _run(["docker", "info"], timeout=8)
        if r.returncode != 0:
            print("[WARN] Docker daemon not running")
            print("  ? Please start Docker Desktop and restart this program")
            return False
        print("[OK] Docker daemon is running")
    except FileNotFoundError:
        print("[ERROR] Docker CLI not found")
        print("  ? Please install Docker Desktop: https://docker.com/products/docker-desktop")
        return False
    except subprocess.TimeoutExpired:
        print("[WARN] Docker check timeout")
        return False
    
    print("[2/2] Milvus check delegated to Bootstrap Agent")
    return True


# ============================================================
# Tool: check_device_platform
# ============================================================

class CheckDevicePlatformTool(BaseTool):
    """Detect the current device's operating system platform."""

    definition = ToolDefinition(
        name="check_device_platform",
        description="Detect the current device's operating system (Windows/Linux/macOS).",
        category=ToolCategory.SYSTEM,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        returns="platform: str, docker_desktop_applicable: bool, observation: str",
        examples=["check_device_platform()"],
    )

    def _execute(self, **kwargs) -> ToolResult:
        p = sys.platform
        if p == "win32":
            os_name = "Windows"
            docker_applicable = True
        elif p == "darwin":
            os_name = "macOS"
            docker_applicable = True
        elif p.startswith("linux"):
            os_name = "Linux"
            docker_applicable = True
        else:
            os_name = f"Unknown ({p})"
            docker_applicable = False

        return ToolResult(
            success=True,
            message=f"Platform: {os_name}",
            data={
                "platform": os_name,
                "raw_platform": p,
                "docker_desktop_applicable": docker_applicable,
            },
            observation=f"Detected platform: {os_name}",
        )


# ============================================================
# Tool: check_docker_daemon
# ============================================================

class CheckDockerDaemonTool(BaseTool):
    """Check if Docker daemon is running and accessible."""

    definition = ToolDefinition(
        name="check_docker_daemon",
        description="Check if Docker daemon is running. Returns version if accessible.",
        category=ToolCategory.DOCKER,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        returns="success: bool, version: str, observation: str",
        examples=["check_docker_daemon()"],
    )

    def _execute(self, **kwargs) -> ToolResult:
        try:
            r = _run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=10)
            if r.returncode == 0:
                version = r.stdout.strip()
                return ToolResult(
                    success=True,
                    message="Docker daemon is running",
                    data={"version": version},
                    observation=f"Docker Server Version: {version}",
                )
            return ToolResult(
                success=False,
                message="Docker daemon check failed",
                data={"stderr": r.stderr[:100]},
                observation="Docker daemon is not accessible",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message="Docker daemon check failed",
                error=str(exc),
                observation=f"Could not connect to Docker daemon: {exc}",
            )


# ============================================================
# Tool: check_port
# ============================================================

class CheckPortTool(BaseTool):
    """Check if a TCP port is open (used to check if services like Milvus are running)."""

    definition = ToolDefinition(
        name="check_port",
        description="Check if a TCP port is open and accepting connections.",
        category=ToolCategory.SYSTEM,
        parameters={
            "type": "object",
            "properties": {
                "host": {"type": "string", "default": "localhost", "description": "Host to check"},
                "port": {"type": "integer", "description": "Port number to check"},
            },
            "required": ["port"],
        },
        returns="success: bool, port_open: bool, observation: str",
        examples=['check_port(port=19530)', 'check_port(host="localhost", port=19530)'],
    )

    def _execute(self, host: str = "localhost", port: int = 19530, **kwargs) -> ToolResult:
        is_open = _is_port_open(host, port)
        
        service_name = "Milvus" if port == 19530 else f"Port {port}"
        status = "running" if is_open else "not running"
        
        return ToolResult(
            success=True,
            message=f"{service_name} on {host}:{port}",
            data={"port_open": is_open, "host": host, "port": port},
            observation=f"{service_name} is {status}",
        )


# ============================================================
# Tool: start_docker_container
# ============================================================

class StartDockerContainerTool(BaseTool):
    """Start a Docker container. Pulls image if needed."""

    definition = ToolDefinition(
        name="start_docker_container",
        description=(
            "Start a Docker container. "
            "If the image doesn't exist locally, it will be pulled automatically. "
            "Common use: start Milvus container on port 19530."
        ),
        category=ToolCategory.DOCKER,
        parameters={
            "type": "object",
            "properties": {
                "image": {"type": "string", "description": "Docker image name"},
                "name": {"type": "string", "description": "Container name"},
                "ports": {
                    "type": "object",
                    "description": "Port mappings, e.g. {\"19530/tcp\": 19530}",
                },
                "detach": {"type": "boolean", "default": True, "description": "Run in background"},
            },
            "required": ["image", "name"],
        },
        returns="success: bool, container_id: str, observation: str",
        examples=[
            'start_docker_container(image="milvusdb/milvus:v2.4.0", name="milvus", ports={"19530/tcp": 19530})',
        ],
    )

    def _execute(
        self,
        image: str,
        name: str,
        ports: dict[str, int] | None = None,
        detach: bool = True,
        **kwargs,
    ) -> ToolResult:
        # Check if container already exists
        r = _run(["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"])
        existing = r.stdout.strip()
        
        if existing:
            # Container exists, try to start it
            r = _run(["docker", "start", name])
            if r.returncode == 0:
                time.sleep(2)
                return ToolResult(
                    success=True,
                    message=f"Started existing container: {name}",
                    data={"container_name": name, "action": "started"},
                    observation=f"Container '{name}' started successfully",
                )
            else:
                return ToolResult(
                    success=False,
                    message=f"Failed to start container: {name}",
                    error=r.stderr[:200],
                    observation=f"Failed to start container: {r.stderr[:100]}",
                )

        # Build docker run command
        cmd = ["docker", "run", "-d", "--name", name]
        
        if ports:
            for container_port, host_port in ports.items():
                cmd.extend(["-p", f"{host_port}:{container_port}"])
        
        cmd.append(image)

        # Try to pull image first
        print(f"  Pulling image: {image}")
        pull_r = _run(["docker", "pull", image], timeout=300)
        if pull_r.returncode != 0:
            return ToolResult(
                success=False,
                message=f"Failed to pull image: {image}",
                error=pull_r.stderr[:200],
                observation=f"Image pull failed: {pull_r.stderr[:100]}",
            )

        # Start container
        r = _run(cmd)
        if r.returncode == 0:
            container_id = r.stdout.strip()[:12]
            time.sleep(2)
            return ToolResult(
                success=True,
                message=f"Container started: {name}",
                data={"container_id": container_id, "container_name": name},
                observation=f"Container '{name}' started (ID: {container_id})",
            )
        else:
            return ToolResult(
                success=False,
                message=f"Failed to start container: {name}",
                error=r.stderr[:200],
                observation=f"Failed to start container: {r.stderr[:100]}",
            )


# ============================================================
# Tool registry
# ============================================================

def register_tools(registry) -> None:
    """Register all Docker-related tools to the registry."""
    registry.register(CheckDevicePlatformTool())
    registry.register(CheckDockerDaemonTool())
    registry.register(CheckPortTool())
    registry.register(StartDockerContainerTool())
