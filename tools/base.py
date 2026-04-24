"""
Tool base classes and registry for the DialecticEngine agent toolset.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)
# Tools should be silent by default; logs go to file if explicitly configured.
logger.addHandler(logging.NullHandler())


class ToolCategory(Enum):
    SYSTEM = "system"
    DOCKER = "docker"
    MILVUS = "milvus"
    EMBEDDING = "embedding"
    MEMORY = "memory"
    BOOTSTRAP = "bootstrap"
    RESCUE = "rescue"


@dataclass
class ToolResult:
    """Result returned by every tool invocation."""

    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None
    observation: str = ""  # Human-readable description of what happened

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "observation": self.observation,
        }

    def __str__(self) -> str:
        status = "OK" if self.success else "FAIL"
        parts = [f"[{status}] {self.message}"]
        if self.observation:
            parts.append(f"  → {self.observation}")
        if self.error:
            parts.append(f"  error: {self.error}")
        return "\n".join(parts)


@dataclass
class ToolDefinition:
    """Static metadata describing a tool's interface."""

    name: str
    description: str
    category: ToolCategory
    parameters: dict[str, Any] = field(default_factory=dict)
    returns: str = ""
    examples: list[str] = field(default_factory=list)

    def to_openai_format(self) -> dict:
        """Return the OpenAI function-calling schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class BaseTool(ABC):
    """
    Abstract base for all tools.

    Subclass must:
    1. Define `definition` (ToolDefinition instance)
    2. Implement `_execute(**kwargs) -> ToolResult`
    3. Optionally override `_validate(**kwargs)` for param pre-check
    """

    definition: ToolDefinition

    def __init__(self):
        self._logger = logger

    def execute(self, **kwargs) -> ToolResult:
        """
        Public entry point. Validates, logs, executes, and formats result.
        """
        self._logger.debug(f"[Tool:{self.definition.name}] Executing with kwargs={kwargs}")
        try:
            # Validate parameters (subclasses override _validate; None means no validation needed)
            validation = self._validate(**kwargs)
            if validation is not None and not validation.success:
                return validation

            # Execute
            result = self._execute(**kwargs)

            # Enrich with observation if not set
            if not result.observation:
                result.observation = result.message

            self._logger.info(f"[Tool:{self.definition.name}] {result}")
            return result

        except Exception as exc:
            self._logger.exception(f"[Tool:{self.definition.name}] Unexpected error")
            return ToolResult(
                success=False,
                message=f"Tool '{self.definition.name}' raised an exception",
                error=str(exc),
            )

    def _validate(self, **kwargs) -> Optional[ToolResult]:
        """Override to add parameter validation. Return ToolResult on failure, None to proceed."""
        return None

    @abstractmethod
    def _execute(self, **kwargs) -> ToolResult:
        """Subclass implements the actual tool logic here."""
        ...


# ============================================================
# Tool Registry
# ============================================================

class ToolRegistry:
    """
    Global registry of all available tools.
    Also generates the OpenAI function-calling schema for LLM use.
    """

    _instance: Optional[ToolRegistry] = None

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._logger = logging.getLogger(f"{__name__}.ToolRegistry")

    @classmethod
    def get_instance(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        name = tool.definition.name
        if name in self._tools:
            self._logger.warning(f"Tool '{name}' is already registered, replacing")
        self._tools[name] = tool
        self._logger.debug(f"Registered tool: {name}")

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_by_category(self, category: ToolCategory) -> list[BaseTool]:
        return [t for t in self._tools.values() if t.definition.category == category]

    def get_names(self) -> list[str]:
        return list(self._tools.keys())

    def get_schemas(self) -> list[dict]:
        """Return OpenAI function-calling schemas for all registered tools."""
        return [t.definition.to_openai_format() for t in self._tools.values()]

    def tool_summaries(self) -> str:
        """Human-readable list of all tools."""
        lines = []
        for tool in self._tools.values():
            d = tool.definition
            lines.append(f"  - {d.name} ({d.category.value}): {d.description}")
        return "\n".join(lines) if lines else "  (no tools registered)"
