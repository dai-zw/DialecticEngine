"""
DialecticEngine Milvus 客户端封装

提供连接管理和 Collection 操作的统一接口
"""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

from pymilvus import connections, Collection
from pymilvus.exceptions import MilvusException

from .config import config as default_config, Config

logger = logging.getLogger(__name__)


class MilvusClient:
    """
    Milvus 客户端封装
    
    提供连接管理、Collection 操作、插入和检索的统一接口
    """
    
    def __init__(self, cfg: Optional[Config] = None):
        """
        初始化客户端
        
        Args:
            cfg: 配置对象（默认使用全局配置）
        """
        self.cfg = cfg or default_config
        self._connected = False
        self._collections = {}
        
        # 延迟初始化操作类
        self._insert_ops: "Optional[InsertOperations]" = None
        self._search_ops: "Optional[SearchOperations]" = None
    
    # ============================================================
    # 连接管理
    # ============================================================
    
    def connect(self) -> None:
        """建立 Milvus 连接"""
        if self._connected:
            logger.warning("milvus已连接，未检索到相似问题")
            return
        
        try:
            logger.info(f"连接 Milvus: {self.cfg.milvus.host}:{self.cfg.milvus.port}")
            connections.connect(
                alias="default",
                host=self.cfg.milvus.host,
                port=self.cfg.milvus.port,
                token=self.cfg.milvus.token,
                timeout=self.cfg.milvus.timeout,
            )
            self._connected = True
            logger.info("✓ Milvus 连接成功")
        except MilvusException as e:
            logger.error(f"连接 Milvus 失败: {e}")
            raise
    
    def disconnect(self) -> None:
        """断开 Milvus 连接"""
        if not self._connected:
            return
        
        connections.disconnect("default")
        self._connected = False
        self._collections.clear()
        logger.info("已断开 Milvus 连接")
    
    @contextmanager
    def session(self) -> Generator["MilvusClient", None, None]:
        """
        上下文管理器，自动管理连接
        
        Usage:
            with client.session() as c:
                c.insert(...)
                results = c.search(...)
        """
        try:
            self.connect()
            yield self
        finally:
            self.disconnect()
    
    # ============================================================
    # Collection 操作
    # ============================================================
    
    def get_collection(self, name: str) -> Collection:
        """
        获取 Collection 对象
        
        Args:
            name: Collection 名称（memories 或 meta）
        
        Returns:
            Collection 对象
        """
        if name not in self._collections:
            collection_name = (
                self.cfg.collection.memories if name == "memories"
                else self.cfg.collection.meta if name == "meta"
                else name
            )
            self._collections[name] = Collection(collection_name)
        
        return self._collections[name]
    
    @property
    def memories(self) -> Collection:
        """dialectic_memories Collection"""
        return self.get_collection("memories")
    
    @property
    def meta(self) -> Collection:
        """dialectic_meta Collection"""
        return self.get_collection("meta")
    
    def load_collections(self) -> None:
        """加载所有 Collection 到内存"""
        logger.info("加载 Collection...")
        self.memories.load()
        self.meta.load()
        logger.info("✓ Collection 加载完成")
    
    # ============================================================
    # 操作类代理
    # ============================================================
    
    @property
    def insert(self) -> "InsertOperations":
        """插入操作"""
        if self._insert_ops is None:
            from .operations import InsertOperations
            self._insert_ops = InsertOperations(self)
        return self._insert_ops
    
    @property
    def search(self) -> "SearchOperations":
        """检索操作"""
        if self._search_ops is None:
            from .operations import SearchOperations
            self._search_ops = SearchOperations(self)
        return self._search_ops
    
    # ============================================================
    # 便捷方法
    # ============================================================
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            包含各 Collection 记录数的字典
        """
        return {
            "memories": self.memories.num_entities,
            "meta": self.meta.num_entities,
        }
    
    def health_check(self) -> dict:
        """
        健康检查
        
        Returns:
            健康状态字典
        """
        status = {
            "connected": self._connected,
            "collections": {},
            "healthy": False,
        }
        
        if self._connected:
            try:
                status["collections"] = self.get_stats()
                status["healthy"] = True
            except Exception as e:
                status["error"] = str(e)
        
        return status


# ============================================================
# 全局客户端实例（延迟连接）
# ============================================================

_client: Optional[MilvusClient] = None


def get_client(cfg: Optional[Config] = None) -> MilvusClient:
    """
    获取全局客户端实例（单例模式）
    
    Args:
        cfg: 配置对象（仅首次调用生效）
    
    Returns:
        MilvusClient 实例
    """
    global _client
    
    if _client is None:
        _client = MilvusClient(cfg)
    
    return _client


def close_client() -> None:
    """关闭全局客户端"""
    global _client
    
    if _client is not None:
        _client.disconnect()
        _client = None
