"""
Bootstrap orchestration tools: high-level tools that compose sub-tools.
These tools implement the ReAct-style bootstrap loop logic.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from .base import BaseTool, ToolCategory, ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


# ============================================================
# Tool: bootstrap_milvus
# ============================================================

class BootstrapMilvusTool(BaseTool):
    """
    High-level tool that ensures Milvus is running.

    Strategy:
    1. Check if Milvus port 19530 is already open
    2. If not, start the dialectic_milvus container via Docker
    3. Wait for service to be ready (up to 90s)
    4. Return status
    """

    definition = ToolDefinition(
        name="bootstrap_milvus",
        description=(
            "Ensure Milvus is running. This is a high-level tool that:\n"
            "1. Checks if Milvus port 19530 is already open\n"
            "2. If not, creates/starts the dialectic_milvus container\n"
            "3. Waits up to 90s for the service to become ready\n"
            "4. Returns final status\n\n"
            "Uses Docker to manage the Milvus container with embedded etcd."
        ),
        category=ToolCategory.BOOTSTRAP,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        returns="success: bool, started: bool, endpoint: str, observation: str",
        examples=[
            "bootstrap_milvus()",
            "Tool: bootstrap_milvus - starts Milvus if not running",
        ],
    )

    def _execute(self, **kwargs) -> ToolResult:
        from .docker_tools import (
            CheckDockerDaemonTool,
            CheckPortTool,
            StartDockerContainerTool,
        )

        # 1. Docker must be available
        docker = CheckDockerDaemonTool().execute()
        if not docker.success:
            return ToolResult(
                success=False,
                message="Docker not available",
                error="check_docker_daemon failed",
                observation="Docker daemon must be running before Milvus can be started.",
            )

        # 2. Check if Milvus is already up
        port_check = CheckPortTool().execute(port=19530, timeout=2.0)
        if port_check.success:
            return ToolResult(
                success=True,
                message="Milvus is already running",
                data={"started": False, "endpoint": "localhost:19530"},
                observation="Milvus service is already running on port 19530.",
            )

        # 3. Start container
        self._logger.info("Milvus not running, starting container...")
        start_result = StartDockerContainerTool().execute(
            name="dialectic_milvus",
            image="milvusdb/milvus:v2.4.0",
            args=[
                "-d",
                "--name", "dialectic_milvus",
                "-p", "19530:19530",
                "-p", "9091:9091",
                "-e", "ETCD_USE_EMBED=true",
                "-e", "COMMON_STORAGETYPE=local",
                "milvusdb/milvus:v2.4.0",
                "milvus", "run", "standalone",
            ],
            pull=True,
        )
        if not start_result.success:
            return start_result

        # 4. Wait for service ready
        self._logger.info("Waiting for Milvus service to be ready...")
        for i in range(90):
            time.sleep(2)
            if CheckPortTool().execute(port=19530, timeout=1.0).success:
                waited = (i + 1) * 2
                return ToolResult(
                    success=True,
                    message=f"Milvus is ready (started, waited {waited}s)",
                    data={"started": True, "endpoint": "localhost:19530", "waited_seconds": waited},
                    observation=f"Milvus container started and service is ready after ~{waited} seconds.",
                )

        return ToolResult(
            success=False,
            message="Milvus container started but service timed out",
            data={"started": True, "endpoint": "localhost:19530"},
            observation="Milvus container started but the service did not become ready in 90s. "
                        "It may still be initializing. The container is running.",
        )


# ============================================================
# Tool: bootstrap_environment
# ============================================================

class BootstrapEnvironmentTool(BaseTool):
    """
    Full environment bootstrap: Docker → Milvus → Embedding.

    This is the top-level orchestration tool. It sequentially:
    1. Ensures Docker is running (launches Docker Desktop on Windows if needed)
    2. Ensures Milvus is running (starts container if needed)
    3. Checks embedding model availability
    4. Returns a comprehensive status report

    Designed to be called by an LLM agent that decides what to do
    at each step based on the observation returned.
    """

    definition = ToolDefinition(
        name="bootstrap_environment",
        description=(
            "Full environment bootstrap. Sequentially ensures:\n"
            "1. Docker daemon is running (launches Docker Desktop on Windows)\n"
            "2. Milvus is running (starts container if needed)\n"
            "3. Embedding model is available (local or OpenAI)\n\n"
            "Returns a detailed status report for each component. "
            "Use this as the first tool call when starting DialecticEngine."
        ),
        category=ToolCategory.BOOTSTRAP,
        parameters={
            "type": "object",
            "properties": {
                "skip_milvus": {
                    "type": "boolean",
                    "description": "Skip Milvus bootstrap (e.g. in development/test mode).",
                    "default": False,
                },
                "skip_embedding": {
                    "type": "boolean",
                    "description": "Skip embedding check.",
                    "default": False,
                },
            },
            "required": [],
        },
        returns="success: bool, docker_ok: bool, milvus_ok: bool, embedding_ok: bool, "
                "endpoint: str, observation: str",
        examples=[
            "bootstrap_environment()",
            "bootstrap_environment(skip_milvus=True)",
        ],
    )

    def _execute(
        self,
        skip_milvus: bool = False,
        skip_embedding: bool = False,
        **kwargs,
    ) -> ToolResult:
        from .docker_tools import (
            CheckDockerDaemonTool,
            LaunchDockerDesktopTool,
            WaitDockerReadyTool,
        )
        from .milvus_tools import CheckMilvusTool
        from .embedding_tools import CheckEmbeddingTool

        report = {
            "docker_ok": False,
            "milvus_ok": False,
            "embedding_ok": False,
            "endpoint": "localhost:19530",
            "warnings": [],
        }

        # Step 1: Docker
        docker_ok = CheckDockerDaemonTool().execute()
        if docker_ok.success:
            report["docker_ok"] = True
        else:
            # Try to launch Docker Desktop on Windows
            import sys as _sys
            if _sys.platform == "win32":
                launch_result = LaunchDockerDesktopTool().execute()
                if launch_result.success:
                    report["docker_ok"] = True
                    report["warnings"].append("Docker Desktop was auto-launched")
                else:
                    report["warnings"].append("Docker Desktop could not be auto-launched")
            else:
                report["warnings"].append("Docker not running (non-Windows)")

        # Step 2: Milvus
        if not skip_milvus:
            if not report["docker_ok"]:
                report["warnings"].append("Milvus skipped: Docker not available")
            else:
                milvus_ok = CheckMilvusTool().execute()
                if milvus_ok.success:
                    report["milvus_ok"] = True
                else:
                    report["warnings"].append(
                        "Milvus not running. Call bootstrap_milvus() to start it."
                    )

        # Step 3: Embedding
        if not skip_embedding:
            embed_ok = CheckEmbeddingTool().execute()
            if embed_ok.success:
                report["embedding_ok"] = True
            else:
                report["warnings"].append(
                    f"Embedding not available: {embed_ok.message}. "
                    "Memory search will be disabled."
                )

        # Determine overall success
        overall_ok = report["docker_ok"] and (
            report["milvus_ok"] if not skip_milvus else True
        )

        observation = (
            f"Docker: {'OK' if report['docker_ok'] else 'FAIL'}, "
            f"Milvus: {'OK' if report['milvus_ok'] else 'FAIL'}, "
            f"Embedding: {'OK' if report['embedding_ok'] else 'FAIL'}"
        )
        if report["warnings"]:
            observation += f". Warnings: {'; '.join(report['warnings'])}"

        return ToolResult(
            success=overall_ok,
            message="Environment bootstrap complete",
            data=report,
            observation=observation,
        )


def register_tools(registry) -> None:
    registry.register(BootstrapMilvusTool())
    registry.register(BootstrapEnvironmentTool())
