"""
Embedding model tools: check availability, install deps, and generate vectors.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Optional

from .base import BaseTool, ToolCategory, ToolDefinition, ToolResult


# ============================================================
# Helpers
# ============================================================

def _get_cache_dir() -> str:
    return os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))


def _model_exists_locally(model: str) -> bool:
    """
    Check if model exists in HuggingFace cache.
    Handles both formats: 'BAAI/bge-base-zh-v1.5' and 'bge-base-zh-v1.5'
    """
    cache_dir = _get_cache_dir()
    model_path = os.path.join(cache_dir, "hub")
    if not os.path.exists(model_path):
        return False
    
    # Normalize model name: 'BAAI/bge-base-zh-v1.5' -> 'models--BAAI--bge-base-zh-v1.5'
    normalized = model.replace("/", "--")
    if not normalized.startswith("models--"):
        normalized = f"models--{normalized}"
    
    # Also check without org prefix (sentence-transformers uses just model name)
    model_short = model.split("/")[-1] if "/" in model else model
    normalized_short = f"models--{model_short}"
    
    for p in os.listdir(model_path):
        if normalized in p or normalized_short in p:
            return True
    return False


# ============================================================
# Tool: check_embedding
# ============================================================

class CheckEmbeddingTool(BaseTool):
    """Check which embedding backend is available (local or OpenAI API)."""

    definition = ToolDefinition(
        name="check_embedding",
        description=(
            "Check whether an embedding model is available. "
            "Priority: local sentence-transformers > OpenAI API. "
            "Returns which backend is active and the embedding dimension."
        ),
        category=ToolCategory.EMBEDDING,
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
        },
        returns="success: bool, backend: str, dimension: str, observation: str",
        examples=[
            "check_embedding()",
            "Tool: check_embedding - no parameters needed",
        ],
    )

    def _execute(self, **kwargs) -> ToolResult:
        use_local = os.environ.get("EMBEDDING_USE_LOCAL", "").lower() in ("1", "true", "yes")
        local_model = os.environ.get("EMBEDDING_LOCAL_MODEL", "all-MiniLM-L6-v2")
        api_key = os.environ.get("OPENAI_API_KEY")

        # Try local first
        if use_local:
            try:
                from sentence_transformers import SentenceTransformer

                if _model_exists_locally(local_model):
                    model = SentenceTransformer(local_model, local_files_only=True)
                    dim = model.get_embedding_dimension()
                    return ToolResult(
                        success=True,
                        message="Local embedding ready",
                        data={"backend": "local", "model": local_model, "dimension": dim},
                        observation=f"Local model '{local_model}' loaded (dim={dim}).",
                    )
                else:
                    return ToolResult(
                        success=False,
                        message="Local model not downloaded",
                        data={"backend": "local", "model": local_model},
                        observation=f"Model '{local_model}' not found locally. Run install_embedding_deps.",
                    )
            except ImportError:
                return ToolResult(
                    success=False,
                    message="sentence-transformers not installed",
                    data={"backend": "local", "model": local_model, "dimension": "?"},
                    observation="sentence-transformers package not installed. "
                                "Run install_embedding_deps to install.",
                )
            except Exception as exc:
                return ToolResult(
                    success=False,
                    message=f"Local embedding check failed: {exc}",
                    data={"backend": "local", "model": local_model, "dimension": "?"},
                    observation=f"Failed to load local model: {exc}",
                )

        # Try OpenAI API
        if api_key:
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                client.models.list()
                return ToolResult(
                    success=True,
                    message="OpenAI embedding ready",
                    data={"backend": "openai", "model": "text-embedding-ada-002", "dimension": "1536"},
                    observation="OpenAI API key configured and accessible. "
                                "Using text-embedding-ada-002 (dim=1536).",
                )
            except Exception as exc:
                return ToolResult(
                    success=False,
                    message=f"OpenAI API check failed: {exc}",
                    data={"backend": "openai", "dimension": "1536"},
                    observation=f"OpenAI API key is set but connection failed: {exc}. "
                                "Check your API key and network.",
                )

        return ToolResult(
            success=False,
            message="No embedding backend configured",
            data={"backend": "none"},
            observation="No embedding model is configured. "
                        "Set EMBEDDING_USE_LOCAL=true for local model, "
                        "or OPENAI_API_KEY for OpenAI API.",
        )


# ============================================================
# Tool: install_embedding_deps
# ============================================================

class InstallEmbeddingDepsTool(BaseTool):
    """Install sentence-transformers locally so a local embedding model can be used."""

    definition = ToolDefinition(
        name="install_embedding_deps",
        description=(
            "Install the sentence-transformers package (and its torch dependency) "
            "to enable local embedding generation without an API key. "
            "This is a one-time setup that downloads the model (~90MB) on first use."
        ),
        category=ToolCategory.EMBEDDING,
        parameters={
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Model name to download. Default: all-MiniLM-L6-v2.",
                    "default": "all-MiniLM-L6-v2",
                },
                "use_mirror": {
                    "type": "boolean",
                    "description": "Use HuggingFace mirror for faster download in China. Default: true.",
                    "default": True,
                },
            },
            "required": [],
        },
        returns="success: bool, observation: str",
        examples=[
            "install_embedding_deps()",
            "install_embedding_deps(model='all-MiniLM-L6-v2')",
        ],
    )

    def _execute(self, model: str = "all-MiniLM-L6-v2", use_mirror: bool = True, **kwargs) -> ToolResult:
        self._logger.info(f"Installing sentence-transformers (model: {model})...")

        try:
            # Step 1: Install sentence-transformers via pip
            r = subprocess.run(
                [sys.executable, "-m", "pip", "install", "sentence-transformers"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
            if r.returncode != 0:
                return ToolResult(
                    success=False,
                    message=f"pip install failed: {r.stderr[:200]}",
                    error=r.stderr[:200],
                    observation="sentence-transformers installation failed. "
                                "Run manually: pip install sentence-transformers",
                )

            # Step 2: Set mirror for faster download (helpful for users in China)
            if use_mirror:
                os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

            # Step 3: Download the model (this triggers actual download)
            from sentence_transformers import SentenceTransformer
            SentenceTransformer(model)

            return ToolResult(
                success=True,
                message="sentence-transformers installed and model downloaded",
                data={"model": model, "cache_dir": _get_cache_dir()},
                observation=f"sentence-transformers installed and model '{model}' downloaded to {_get_cache_dir()}.",
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                message="Installation timed out (>5 min)",
                observation="pip install took longer than 5 minutes. Check network and try manually.",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Installation failed: {exc}",
                error=str(exc),
            )


# ============================================================
# Tool: generate_embedding
# ============================================================

class GenerateEmbeddingTool(BaseTool):
    """Generate an embedding vector for a text string."""

    definition = ToolDefinition(
        name="generate_embedding",
        description=(
            "Generate an embedding vector for a single text string using the "
            "configured embedding backend (local or OpenAI). "
            "The embedding is a normalized float array used for semantic similarity search."
        ),
        category=ToolCategory.EMBEDDING,
        parameters={
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to embed (e.g. a user query or memory content).",
                },
            },
            "required": ["text"],
        },
        returns="success: bool, vector: list[float], dimension: int, observation: str",
        examples=[
            'generate_embedding(text="What is the best career path for a new grad?")',
            'generate_embedding(text="用户问关于职业规划的问题")',
        ],
    )

    def _execute(self, text: str, **kwargs) -> ToolResult:
        try:
            from milvus_DB.utils.embedding import get_generator
            gen = get_generator()
            vector = gen.generate(text)
            dim = gen.dimension
            return ToolResult(
                success=True,
                message=f"Embedding generated (dim={dim})",
                data={"dimension": dim, "vector_length": len(vector)},
                observation=f"Generated embedding of length {dim} for text: {text[:50]!r}...",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                message=f"Embedding generation failed: {exc}",
                error=str(exc),
                observation="Could not generate embedding. Check that an embedding backend is configured.",
            )


# ============================================================
# Register
# ============================================================

def register_tools(registry) -> None:
    registry.register(CheckEmbeddingTool())
    registry.register(InstallEmbeddingDepsTool())
    registry.register(GenerateEmbeddingTool())
