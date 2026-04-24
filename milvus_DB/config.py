"""
DialecticEngine 配置管理

集中管理所有配置项，支持环境变量覆盖
"""

import os
from dotenv import load_dotenv

load_dotenv()

from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# Milvus 连接配置
# ============================================================

@dataclass
class MilvusConfig:
    """Milvus 连接配置"""
    
    host: str = "localhost"
    port: str = "19530"
    token: str = "root:Milvus"
    
    # 连接池配置
    pool_size: int = 10
    timeout: int = 30
    
    @classmethod
    def from_env(cls) -> "MilvusConfig":
        """从环境变量加载配置"""
        return cls(
            host=os.environ.get("MILVUS_HOST", "localhost"),
            port=os.environ.get("MILVUS_PORT", "19530"),
            token=os.environ.get("MILVUS_TOKEN", "root:Milvus"),
        )


# ============================================================
# Collection 名称配置
# ============================================================

@dataclass
class CollectionConfig:
    """Collection 名称配置"""
    
    memories: str = "dialectic_memories"
    meta: str = "dialectic_meta"
    
    @classmethod
    def from_env(cls) -> "CollectionConfig":
        """从环境变量加载配置"""
        return cls(
            memories=os.environ.get("MILVUS_COLLECTION_MEMORIES", "dialectic_memories"),
            meta=os.environ.get("MILVUS_COLLECTION_META", "dialectic_meta"),
        )


# ============================================================
# Embedding 配置
# ============================================================

@dataclass
class EmbeddingConfig:
    """Embedding 配置"""
    
    model: str = "text-embedding-ada-002"
    dim: int = 1536
    batch_size: int = 100
    
    # 本地模型配置
    use_local: bool = False
    local_model_name: str = "all-MiniLM-L6-v2"
    
    # OpenAI API 配置
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """从环境变量加载配置"""
        use_local = os.environ.get("EMBEDDING_USE_LOCAL", "").lower() in ("1", "true", "yes")

        local_model = os.environ.get("EMBEDDING_LOCAL_MODEL", "all-MiniLM-L6-v2")
        
        # 根据模型名称推断维度
        dim = 1536
        if use_local:
            if local_model in ("all-MiniLM-L6-v2", "paraphrase-multilingual-MiniLM-L12-v2"):
                dim = 384
            elif local_model in ("all-mpnet-base-v2", "BAAI/bge-base-zh-v1.5"):
                dim = 768
            elif local_model in ("BAAI/bge-small-zh-v1.5",):
                dim = 512

        explicit_dim = os.environ.get("OPENAI_EMBEDDING_DIM") or os.environ.get("EMBEDDING_DIM")
        if explicit_dim:
            dim = int(explicit_dim)

        return cls(
            model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-ada-002"),
            dim=dim,
            batch_size=int(os.environ.get("OPENAI_EMBEDDING_BATCH_SIZE", "100")),
            use_local=use_local,
            local_model_name=local_model,
            api_key=os.environ.get("OPENAI_API_KEY"),
            api_base=os.environ.get("OPENAI_API_BASE"),
        )


# ============================================================
# 检索配置
# ============================================================

@dataclass
class SearchConfig:
    """检索配置"""
    
    top_k: int = 5
    similarity_threshold: float = 0.7
    
    # GPU 配置
    gpu_enabled: bool = False
    
    @classmethod
    def from_env(cls) -> "SearchConfig":
        """从环境变量加载配置"""
        return cls(
            top_k=int(os.environ.get("MILVUS_SEARCH_TOP_K", "5")),
            similarity_threshold=float(os.environ.get("MILVUS_SIMILARITY_THRESHOLD", "0.7")),
            gpu_enabled=os.environ.get("MILVUS_GPU_ENABLED", "").lower() in ("1", "true", "yes"),
        )


# ============================================================
# 全局配置
# ============================================================

@dataclass
class Config:
    """全局配置"""
    
    milvus: MilvusConfig = field(default_factory=MilvusConfig)
    collection: CollectionConfig = field(default_factory=CollectionConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    
    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量加载所有配置"""
        return cls(
            milvus=MilvusConfig.from_env(),
            collection=CollectionConfig.from_env(),
            embedding=EmbeddingConfig.from_env(),
            search=SearchConfig.from_env(),
        )


# ============================================================
# 全局配置实例
# ============================================================

# 默认配置（可直接使用）
config = Config()

# 从环境变量加载的配置
env_config = Config.from_env()


# ============================================================
# 配置验证
# ============================================================

def validate_config(cfg: Config) -> list:
    """
    验证配置是否有效
    
    Args:
        cfg: 配置对象
    
    Returns:
        警告列表（空表示配置有效）
    """
    warnings = []
    
    # 检查 Milvus 连接
    if not cfg.milvus.host:
        warnings.append("MILVUS_HOST 未设置")
    
    if not cfg.milvus.port:
        warnings.append("MILVUS_PORT 未设置")
    
    # 检查 Embedding API Key
    if not cfg.embedding.api_key:
        warnings.append("OPENAI_API_KEY 未设置，Embedding 功能将不可用")
    
    # 检查向量维度
    if cfg.embedding.dim <= 0:
        warnings.append(f"OPENAI_EMBEDDING_DIM 无效: {cfg.embedding.dim}")
    
    # 检查检索参数
    if cfg.search.top_k <= 0:
        warnings.append(f"MILVUS_SEARCH_TOP_K 无效: {cfg.search.top_k}")
    
    if not 0 <= cfg.search.similarity_threshold <= 1:
        warnings.append(f"MILVUS_SIMILARITY_THRESHOLD 超出范围: {cfg.search.similarity_threshold}")
    
    return warnings
