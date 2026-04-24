"""
DialecticEngine Tool System

Exports the ToolRegistry and all tool classes for use by the bootstrap agent.

Usage:
    from tools import get_registry, get_all_schemas

    registry = get_registry()
    schemas = registry.get_schemas()  # for LLM function calling

    tool = registry.get("check_docker_daemon")
    result = tool.execute()
"""

from __future__ import annotations

from tools.base import (
    BaseTool,
    ToolCategory,
    ToolDefinition,
    ToolRegistry,
    ToolResult,
)

# Import all tool modules to trigger registration
from tools import docker_tools
from tools import embedding_tools
from tools import milvus_tools
from tools import bootstrap_tools
from tools import rescue_tools

__all__ = [
    "ToolRegistry",
    "ToolResult",
    "ToolDefinition",
    "ToolCategory",
    "BaseTool",
    "get_registry",
    "get_all_schemas",
    "get_tool",
    "list_tools",
]


_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """
    Get the singleton ToolRegistry with all tools registered.
    Safe to call multiple times.
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        docker_tools.register_tools(_registry)
        embedding_tools.register_tools(_registry)
        milvus_tools.register_tools(_registry)
        bootstrap_tools.register_tools(_registry)
        rescue_tools.register_tools(_registry)
    return _registry


def get_all_schemas() -> list[dict]:
    """Return OpenAI function-calling schemas for all registered tools."""
    return get_registry().get_schemas()


def get_tool(name: str) -> BaseTool | None:
    """Get a tool by name from the registry."""
    return get_registry().get(name)


def list_tools() -> list[str]:
    """Return names of all registered tools."""
    return get_registry().get_names()
