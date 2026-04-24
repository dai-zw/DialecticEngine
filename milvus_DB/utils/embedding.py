"""
DialecticEngine 向量生成工具

支持两种模式：
- 本地模型：sentence-transformers（默认，无需 API Key）
- OpenAI API：text-embedding-ada-002（需要 OPENAI_API_KEY）
"""

import logging
import os
from pathlib import Path
from typing import Optional

from ..config import config as default_config, env_config, Config

logger = logging.getLogger(__name__)

# 全局模型实例（延迟初始化，跨调用复用）
_local_model: Optional["LocalEmbeddingModel"] = None


# ============================================================
# 本地模型（sentence-transformers）
# ============================================================

class LocalEmbeddingModel:
    """
    本地 Embedding 模型封装。
    
    基于 sentence-transformers，支持 CPU/GPU 自动调度，
    模型首次使用自动下载到 ~/.cache/huggingface/。
    """
    
    # 推荐模型速查
    MODEL_DIMENSIONS = {
        "all-MiniLM-L6-v2": 384,      # 轻量快速，中英双语尚可
        "all-mpnet-base-v2": 768,     # 质量更高，速度较慢
        "paraphrase-multilingual-MiniLM-L12-v2": 384,  # 多语言优秀
        "bge-small-zh-v1.5": 512,     # 中文优化
        "bge-base-zh-v1.5": 768,      # 中文高质量
    }
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: Optional[str] = None):
        """
        Args:
            model_name: HuggingFace 模型名称
            device: 强制设备，"cpu" / "cuda" / None（自动检测）
        """
        from sentence_transformers import SentenceTransformer
        
        self.model_name = model_name
        
        if device is None:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info(f"加载本地 Embedding 模型: {model_name} (device={device})")
        self._model = SentenceTransformer(model_name, device=device)
        
        # 自动推断维度
        self._dim = self._model.get_embedding_dimension()
        logger.info(f"模型向量维度: {self._dim}")
    
    @property
    def dimension(self) -> int:
        return self._dim
    
    def encode(self, texts: list[str]) -> list[list[float]]:
        """生成向量"""
        embeddings = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return embeddings.tolist()


def _get_local_model(model_name: str = "all-MiniLM-L6-v2") -> LocalEmbeddingModel:
    """获取全局本地模型实例（单例）"""
    global _local_model
    if _local_model is None or _local_model.model_name != model_name:
        _local_model = LocalEmbeddingModel(model_name)
    return _local_model


# ============================================================
# OpenAI API 模型
# ============================================================

class RemoteEmbeddingModel:
    """OpenAI Embedding API 封装"""
    
    def __init__(self, api_key: str, model: str, api_base: Optional[str] = None):
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=api_base)
        self._model = model
    
    @property
    def dimension(self) -> int:
        return 1536  # OpenAI ada-002 固定维度
    
    def encode(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [item.embedding for item in response.data]


# ============================================================
# 统一接口
# ============================================================

class EmbeddingGenerator:
    """
    向量生成器（统一接口）
    
    自动选择本地模型或远程 API。
    """
    
    def __init__(self, cfg: Optional[Config] = None):
        self.cfg = cfg or env_config  # Use env_config to pick up .env settings
        self._impl: Optional[object] = None
        self._init_impl()
    
    def _init_impl(self) -> None:
        # Check env var directly - cfg defaults to False so we need the env var
        use_local = os.environ.get("EMBEDDING_USE_LOCAL", "").lower() in ("1", "true", "yes")
        local_model_name = os.environ.get("EMBEDDING_LOCAL_MODEL", "all-MiniLM-L6-v2")

        if use_local:
            try:
                self._impl = _get_local_model(local_model_name)
                logger.info(f"Embedding using local model: {local_model_name}")
                return
            except ImportError:
                logger.warning("sentence-transformers not installed, falling back to OpenAI API")
            except Exception as e:
                logger.warning(f"Local model failed: {e}, falling back to OpenAI API")

        # OpenAI API fallback
        api_key = self.cfg.embedding.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set, Embedding unavailable")
            self._impl = None
            return

        try:
            self._impl = RemoteEmbeddingModel(
                api_key,
                self.cfg.embedding.model,
                self.cfg.embedding.api_base,
            )
            logger.info(f"Embedding using OpenAI API: {self.cfg.embedding.model}")
        except Exception as e:
            logger.error(f"OpenAI Embedding init failed: {e}")
            self._impl = None
    
    @property
    def model(self) -> str:
        cfg = self.cfg.embedding
        if cfg.use_local:
            return f"local:{cfg.local_model_name}"
        return cfg.model
    
    @property
    def dimension(self) -> int:
        if self._impl is None:
            return self.cfg.embedding.dim
        return self._impl.dimension
    
    def generate(self, text: str) -> list[float]:
        """生成单条文本的向量"""
        if self._impl is None:
            raise RuntimeError("Embedding 模型未初始化，请检查 API Key 或模型安装")
        return self._impl.encode([text])[0]
    
    def generate_batch(self, texts: list[str]) -> list[list[float]]:
        """批量生成文本向量"""
        if not texts:
            return []
        if self._impl is None:
            raise RuntimeError("Embedding 模型未初始化")
        return self._impl.encode(texts)
    
    def validate(self, embedding: list[float]) -> bool:
        if not embedding:
            return False
        if len(embedding) != self.dimension:
            logger.warning(f"向量维度不匹配: 期望 {self.dimension}, 实际 {len(embedding)}")
            return False
        return True


# ============================================================
# 全局实例
# ============================================================

_generator: Optional[EmbeddingGenerator] = None


def get_generator(cfg: Optional[Config] = None) -> EmbeddingGenerator:
    """获取全局向量生成器实例"""
    global _generator
    if _generator is None:
        _generator = EmbeddingGenerator(cfg or env_config)
    return _generator


def reset_generator() -> None:
    """重置全局实例（用于配置变更后重新初始化）"""
    global _generator, _local_model
    _generator = None
    _local_model = None
