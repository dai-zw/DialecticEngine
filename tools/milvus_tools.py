"""
Milvus and long-term memory tools.
"""

from __future__ import annotations

from typing import Optional

from .base import BaseTool, ToolCategory, ToolDefinition, ToolResult


# ============================================================
# Tool: check_milvus
# ============================================================

class CheckMilvusTool(BaseTool):
    """Check if Milvus service is running and accessible on port 19530."""

    definition = ToolDefinition(
        name="check_milvus",
        description=(
            "Check whether Milvus is running by attempting a TCP connection to "
            "localhost:19530. Returns OK if the port is open, FAIL otherwise."
        ),
        category=ToolCategory.MILVUS,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        returns="success: bool, observation: str",
        examples=[
            "check_milvus()",
            "Tool: check_milvus - no parameters needed",
        ],
    )

    def _execute(self, **kwargs) -> ToolResult:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2.0)
        try:
            sock.connect(("localhost", 19530))
            return ToolResult(
                success=True,
                message="Milvus is running on port 19530",
                data={"host": "localhost", "port": 19530},
                observation="Milvus service is listening on port 19530.",
            )
        except (socket.timeout, ConnectionRefusedError, OSError) as exc:
            return ToolResult(
                success=False,
                message="Milvus is not running on port 19530",
                data={"error": str(exc)},
                observation="Port 19530 is not accepting connections. "
                            "Milvus needs to be started (see start_docker_container tool).",
            )
        finally:
            sock.close()


# ============================================================
# Tool: check_milvus_collections
# ============================================================

class CheckMilvusCollectionsTool(BaseTool):
    """Check which Milvus collections exist and their entity counts."""

    definition = ToolDefinition(
        name="check_milvus_collections",
        description=(
            "Query the Milvus database to list collections and return entity counts. "
            "Use this to verify that the dialectic_memories and dialectic_meta "
            "collections exist and have data."
        ),
        category=ToolCategory.MILVUS,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        returns="success: bool, collections: dict, observation: str",
        examples=[
            "check_milvus_collections()",
            "Tool: check_milvus_collections - no parameters needed",
        ],
    )

    def _execute(self, **kwargs) -> ToolResult:
        try:
            from milvus_DB.client import get_client
            client = get_client()
            stats = client.get_stats()
            return ToolResult(
                success=True,
                message="Milvus collections queried",
                data=stats,
                observation=f"Collections: {list(stats.keys())}. "
                            f"Entity counts: {{k: v.get('total', 0) for k, v in stats.items()}}",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Failed to query Milvus collections: {exc}",
                error=str(exc),
                observation="Could not connect to Milvus or query collections.",
            )


# ============================================================
# Tool: store_memory
# ============================================================

class StoreMemoryTool(BaseTool):
    """Store a conversation memory in Milvus for long-term retrieval."""

    definition = ToolDefinition(
        name="store_memory",
        description=(
            "Store a conversation memory in Milvus for future retrieval. "
            "The memory includes the user query, selected skills/perspectives, "
            "the agent's response, and optional feedback scores. "
            "Embeddings are generated automatically."
        ),
        category=ToolCategory.MEMORY,
        parameters={
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User identifier."},
                "query": {"type": "string", "description": "The original user query."},
                "selected_skills": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of skill names/perspectives used.",
                },
                "skill_scores": {
                    "type": "object",
                    "description": "Mapping of skill name to confidence score (0-1).",
                },
                "confidence": {
                    "type": "number",
                    "description": "Overall routing confidence score (0-1).",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Why these skills were selected.",
                },
                "response": {
                    "type": "string",
                    "description": "The agent's final response content.",
                },
                "feedback_score": {
                    "type": "integer",
                    "description": "User feedback: 1 (negative) to 5 (positive).",
                },
                "helpful_count": {
                    "type": "integer",
                    "description": "How many times users marked this memory as helpful.",
                },
            },
            "required": ["user_id", "query", "selected_skills", "skill_scores", "confidence", "reasoning", "response"],
        },
        returns="success: bool, record_id: str, observation: str",
        examples=[
            'store_memory(user_id="user1", query="职业规划建议", '
            'selected_skills=["munger", "zhangxuefeng"], '
            'skill_scores={"munger": 0.8, "zhangxuefeng": 0.6}, '
            'confidence=0.85, reasoning="从查理芒格和张雪峰视角分析", '
            'response="建议...")',
        ],
    )

    def _execute(
        self,
        user_id: str,
        query: str,
        selected_skills: list[str],
        skill_scores: dict[str, float],
        confidence: float,
        reasoning: str,
        response: str,
        feedback_score: Optional[int] = None,
        helpful_count: Optional[int] = None,
        **kwargs,
    ) -> ToolResult:
        try:
            from milvus_DB.long_term_memory import get_memory, MemoryRecord
            memory = get_memory()
            record = MemoryRecord(
                user_id=user_id,
                query=query,
                selected_skills=selected_skills,
                skill_scores=skill_scores,
                confidence=confidence,
                reasoning=reasoning,
                response=response,
                feedback_score=feedback_score,
                helpful_count=helpful_count or 0,
            )
            record_id = memory.store(record)
            return ToolResult(
                success=True,
                message=f"Memory stored: {record_id[:16]}...",
                data={"record_id": record_id},
                observation=f"Stored memory for user '{user_id}' with {len(selected_skills)} skills, "
                            f"confidence={confidence}.",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Failed to store memory: {exc}",
                error=str(exc),
                observation="Could not store memory in Milvus. "
                            "Check that Milvus and embedding are both available.",
            )


# ============================================================
# Tool: search_memory
# ============================================================

class SearchMemoryTool(BaseTool):
    """Search past conversation memories semantically using embeddings."""

    definition = ToolDefinition(
        name="search_memory",
        description=(
            "Search past conversation memories using semantic similarity. "
            "Given a query, it generates an embedding and finds the most "
            "similar past memories. Useful for the agent to recall relevant "
            "past advice when the user asks about a similar topic."
        ),
        category=ToolCategory.MEMORY,
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
                "user_id": {"type": "string", "description": "User identifier to filter memories."},
                "top_k": {
                    "type": "integer",
                    "description": "Maximum number of results to return. Default: 3.",
                    "default": 3,
                },
                "similarity_threshold": {
                    "type": "number",
                    "description": "Minimum similarity score (0-1). Default: 0.0.",
                    "default": 0.0,
                },
            },
            "required": ["query", "user_id"],
        },
        returns="success: bool, results: list[dict], observation: str",
        examples=[
            'search_memory(query="职业发展建议", user_id="user1", top_k=3)',
            'search_memory(query="AI算法工程师规划", user_id="user1")',
        ],
    )

    def _execute(
        self,
        query: str,
        user_id: str,
        top_k: int = 3,
        similarity_threshold: float = 0.0,
        **kwargs,
    ) -> ToolResult:
        try:
            from milvus_DB.long_term_memory import get_memory
            memory = get_memory()
            results = memory.search(
                query=query,
                user_id=user_id,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
            )
            if not results:
                return ToolResult(
                    success=True,
                    message="No similar memories found",
                    data={"results": [], "count": 0},
                    observation=f"No past memories match query: {query!r}",
                )

            formatted = [
                {
                    "record_id": r.record.record_id[:16],
                    "query": r.record.query,
                    "skills": r.record.selected_skills,
                    "confidence": r.record.confidence,
                    "similarity": r.similarity,
                    "reasoning": r.record.reasoning,
                    "response_preview": r.record.response[:100],
                }
                for r in results
            ]
            return ToolResult(
                success=True,
                message=f"Found {len(results)} similar memories",
                data={"results": formatted, "count": len(results)},
                observation=f"Found {len(results)} memories with similarity > {similarity_threshold}. "
                            f"Top match: {results[0].record.query[:50]!r}...",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Memory search failed: {exc}",
                error=str(exc),
                observation="Could not search memories. Check that Milvus and embedding are available.",
            )


# ============================================================
# Tool: get_memory_context
# ============================================================

class GetMemoryContextTool(BaseTool):
    """Get formatted context from past memories for use in prompts."""

    definition = ToolDefinition(
        name="get_memory_context",
        description=(
            "Get a formatted context string from past memories suitable for "
            "injection into an LLM prompt. Combines the most relevant past "
            "conversations into a readable summary the agent can reason about."
        ),
        category=ToolCategory.MEMORY,
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The current user query."},
                "user_id": {"type": "string", "description": "User identifier."},
                "top_k": {
                    "type": "integer",
                    "description": "Number of memories to include. Default: 3.",
                    "default": 3,
                },
                "purpose": {
                    "type": "string",
                    "enum": ["router", "executor"],
                    "description": "'router' for skill selection context, 'executor' for response context.",
                    "default": "router",
                },
            },
            "required": ["query", "user_id"],
        },
        returns="success: bool, context: str, observation: str",
        examples=[
            'get_memory_context(query="职业发展", user_id="user1", purpose="router")',
            'get_memory_context(query="职业发展", user_id="user1", purpose="executor")',
        ],
    )

    def _execute(
        self,
        query: str,
        user_id: str,
        top_k: int = 3,
        purpose: str = "router",
        **kwargs,
    ) -> ToolResult:
        try:
            from milvus_DB.long_term_memory import get_context_for_router, get_context_for_executor
            if purpose == "router":
                context = get_context_for_router(query, top_k=top_k)
            else:
                context = get_context_for_executor(query, top_k=top_k)

            return ToolResult(
                success=True,
                message=f"Memory context generated ({purpose})",
                data={"context": context, "purpose": purpose, "top_k": top_k},
                observation=f"Generated {len(context)} chars of memory context "
                            f"for {purpose} purpose from {top_k} memories.",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Failed to get memory context: {exc}",
                error=str(exc),
            )


# ============================================================
# Tool: create_milvus_collections
# ============================================================

class CreateMilvusCollectionsTool(BaseTool):
    """Create the required Milvus collections (dialectic_memories and dialectic_meta)."""

    definition = ToolDefinition(
        name="create_milvus_collections",
        description=(
            "Create the dialectic_memories and dialectic_meta Milvus collections if they don't exist. "
            "This is a one-time setup step required before using long-term memory features."
        ),
        category=ToolCategory.MILVUS,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        returns="success: bool, observation: str",
        examples=[
            "create_milvus_collections()",
        ],
    )

    def _execute(self, **kwargs) -> ToolResult:
        try:
            from milvus_DB.create_collections import ensure_collections_exist
            ensure_collections_exist()
            return ToolResult(
                success=True,
                message="Milvus collections created or verified",
                observation="Collections 'dialectic_memories' and 'dialectic_meta' are ready.",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Failed to create collections: {exc}",
                error=str(exc),
                observation=f"Could not create Milvus collections: {exc}",
            )


def register_tools(registry) -> None:
    registry.register(CheckMilvusTool())
    registry.register(CheckMilvusCollectionsTool())
    registry.register(CreateMilvusCollectionsTool())
    registry.register(StoreMemoryTool())
    registry.register(SearchMemoryTool())
    registry.register(GetMemoryContextTool())
