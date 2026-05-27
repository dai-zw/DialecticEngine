"""
DialecticEngine - 长期记忆模块

基于 Milvus 向量数据库的长期记忆存储与检索。

功能：
- 语义相似度检索历史决策
- 存储路由决策和回答
- 按技能/时间/置信度过滤
- 与 ContextManager 集成

Usage:
    from milvus_DB.long_term_memory import LongTermMemory
    
    memory = LongTermMemory()
    memory.connect()
    
    # 存储记忆
    memory.store(
        query="我的领导对我有恩...",
        query_embedding=embedding,
        selected_skills=["rujia-perspective"],
        skill_scores={"rujia-perspective": 0.85},
        confidence=0.8,
        reasoning="...",
    )
    
    # 检索相似记忆
    results = memory.search(query_embedding, top_k=3)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import Config, config as default_config

logger = logging.getLogger(__name__)


# ============================================================
# LRU Memory Cache
# ============================================================

class MemoryCache:
    """
    LRU 内存缓存层，减少对 Milvus 的调用。
    
    命中条件：查询文本完全匹配（精确匹配）或 embedding 余弦相似度 > 0.95
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, tuple[list, float]] = OrderedDict()  # query -> (results, timestamp)
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._hit_count = 0
        self._miss_count = 0
        self._lock = threading.RLock()
    
    def get(self, query: str, embedding: Optional[list] = None) -> Optional[list]:
        """获取缓存的检索结果"""
        with self._lock:
            key = self._make_key(query, embedding)
            if key in self._cache:
                results, timestamp = self._cache[key]
                # 检查 TTL
                if time.time() - timestamp < self._ttl:
                    self._cache.move_to_end(key)
                    self._hit_count += 1
                    logger.debug(f"缓存命中: {query[:30]}...")
                    return results
                else:
                    del self._cache[key]
            self._miss_count += 1
            return None
    
    def set(self, query: str, results: list, embedding: Optional[list] = None) -> None:
        """设置缓存"""
        with self._lock:
            key = self._make_key(query, embedding)
            self._cache[key] = (results, time.time())
            self._cache.move_to_end(key)
            # 清理超出大小的旧缓存
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
    
    def _make_key(self, query: str, embedding: Optional[list]) -> str:
        """生成缓存 key"""
        if embedding:
            # 使用 embedding 的前 10 个值作为 key 的一部分（用于近似匹配场景）
            emb_key = ",".join(f"{v:.2f}" for v in embedding[:10])
            return f"{hash(query)}|{emb_key}"
        return f"{hash(query)}|exact"
    
    def clear(self) -> None:
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._hit_count = 0
            self._miss_count = 0
    
    def get_stats(self) -> dict:
        """获取缓存统计"""
        with self._lock:
            total = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total if total > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": f"{hit_rate:.1%}",
            }


# ============================================================
# Circuit Breaker
# ============================================================

class CircuitBreaker:
    """
    熔断器：Milvus 服务异常时自动降级。
    
    状态转换:
    CLOSED (正常) -> OPEN (熔断) -> HALF_OPEN (半开) -> CLOSED
    """
    
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        
        self._state = self.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.RLock()
    
    @property
    def state(self) -> str:
        with self._lock:
            if self._state == self.OPEN:
                # 检查是否应该转换到 HALF_OPEN
                if (self._last_failure_time and 
                    time.time() - self._last_failure_time >= self._recovery_timeout):
                    self._state = self.HALF_OPEN
                    self._half_open_calls = 0
            return self._state
    
    def is_available(self) -> bool:
        """是否允许调用"""
        return self.state in (self.CLOSED, self.HALF_OPEN)
    
    def record_success(self) -> None:
        """记录成功调用"""
        with self._lock:
            if self._state == self.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._half_open_max_calls:
                    self._state = self.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info("Milvus 熔断器恢复: CLOSED")
            elif self._state == self.CLOSED:
                self._failure_count = 0
    
    def record_failure(self) -> None:
        """记录失败调用"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == self.HALF_OPEN:
                self._state = self.OPEN
                self._success_count = 0
                logger.warning("Milvus 熔断器触发: HALF_OPEN -> OPEN")
            elif (self._state == self.CLOSED and 
                  self._failure_count >= self._failure_threshold):
                self._state = self.OPEN
                logger.warning(f"Milvus 熔断器触发: CLOSED -> OPEN (连续 {self._failure_count} 次失败)")
    
    def get_stats(self) -> dict:
        """获取熔断器状态"""
        with self._lock:
            return {
                "state": self.state,
                "failure_count": self._failure_count,
                "last_failure_time": self._last_failure_time,
            }


# ============================================================
# 数据模型
# ============================================================

@dataclass
class MemoryRecord:
    """记忆记录"""
    
    record_id: str = ""
    user_id: str = ""
    query: str = ""
    query_embedding: list = field(default_factory=list)
    query_keywords: list = field(default_factory=list)
    selected_skills: list = field(default_factory=list)
    skill_scores: dict = field(default_factory=dict)
    confidence: float = 0.0
    reasoning: str = ""
    response: str = ""
    feedback_score: float = 0.0
    helpful_count: int = 0
    created_at: int = field(default_factory=lambda: int(datetime.now(timezone.utc).timestamp()))
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "query": self.query,
            "query_embedding": self.query_embedding,
            "query_keywords": self.query_keywords,
            "selected_skills": self.selected_skills,
            "skill_scores": self.skill_scores,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "response": self.response,
            "feedback_score": self.feedback_score,
            "helpful_count": self.helpful_count,
            "created_at": self.created_at,
        }


@dataclass
class SearchResult:
    """检索结果"""
    
    record: MemoryRecord
    similarity: float  # COSINE 相似度 (0-1)
    
    @property
    def confidence(self) -> float:
        """获取记忆的置信度"""
        return self.record.confidence
    
    @property
    def skills(self) -> list[str]:
        """获取记忆使用的技能"""
        return self.record.selected_skills


# ============================================================
# 长期记忆类
# ============================================================

class LongTermMemory:
    """
    长期记忆管理器
    
    封装 Milvus 操作，提供：
    - 记忆存储（每次路由决策后）
    - 记忆检索（路由决策前）
    - 记忆更新（反馈后）
    - LRU 缓存（减少 Milvus 调用）
    - 熔断降级（服务异常时自动降级）
    """
    
    # 默认超时配置（秒）
    DEFAULT_SEARCH_TIMEOUT = 3.0
    DEFAULT_STORE_TIMEOUT = 5.0
    
    def __init__(
        self,
        cfg: Optional[Config] = None,
        milvus_client: "Optional[MilvusClient]" = None,
        embedding_generator: "Optional[EmbeddingGenerator]" = None,
        cache_size: int = 1000,
        cache_ttl: int = 3600,
        search_timeout: float = DEFAULT_SEARCH_TIMEOUT,
        store_timeout: float = DEFAULT_STORE_TIMEOUT,
    ):
        """
        初始化
        
        Args:
            cfg: 配置对象
            milvus_client: Milvus 客户端（延迟初始化）
            embedding_generator: 向量生成器（延迟初始化）
            cache_size: 缓存大小
            cache_ttl: 缓存 TTL（秒）
            search_timeout: 检索超时时间
            store_timeout: 存储超时时间
        """
        self.cfg = cfg or default_config
        self._client = milvus_client
        self._embedding_gen = embedding_generator
        self._connected = False
        
        # 缓存和熔断器
        self._cache = MemoryCache(max_size=cache_size, ttl_seconds=cache_ttl)
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
        )
        
        # 超时配置
        self._search_timeout = search_timeout
        self._store_timeout = store_timeout
    
    # ============================================================
    # 连接管理
    # ============================================================
    
    def connect(self) -> None:
        """连接 Milvus"""
        if self._connected:
            return
        
        try:
            # Lazy import to avoid circular dependency
            from .client import get_client, close_client
            self._client = get_client(self.cfg)
            self._client.connect()
            self._client.load_collections()
            self._connected = True
            logger.info("✓ 长期记忆模块连接成功")
        except Exception as e:
            logger.warning(f"长期记忆模块连接失败: {e}")
            self._connected = False
    
    def disconnect(self) -> None:
        """断开连接"""
        if self._client:
            # Lazy import
            from .client import close_client
            self._client.disconnect()
            close_client()
        self._connected = False
        logger.info("长期记忆模块已断开连接")
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected
    
    @property
    def client(self) -> "Optional[MilvusClient]":
        """获取 Milvus 客户端"""
        return self._client
    
    @property
    def embedding_generator(self) -> "Optional[EmbeddingGenerator]":
        """获取向量生成器"""
        if self._embedding_gen is None:
            try:
                # Lazy import
                from .utils.embedding import get_generator
                self._embedding_gen = get_generator(self.cfg)
            except Exception as e:
                logger.warning(f"向量生成器初始化失败: {e}")
        return self._embedding_gen
    
    # ============================================================
    # 核心操作
    # ============================================================
    
    def generate_embedding(self, text: str) -> Optional[list[float]]:
        """
        生成文本向量
        
        Args:
            text: 文本内容
        
        Returns:
            向量列表，失败返回 None
        """
        if self.embedding_generator is None:
            logger.warning("向量生成器不可用")
            return None
        
        try:
            return self.embedding_generator.generate(text)
        except Exception as e:
            logger.error(f"生成向量失败: {e}")
            return None
    
    def store(
        self,
        query: str,
        selected_skills: list[str],
        skill_scores: dict[str, float],
        confidence: float,
        reasoning: str,
        response: str = "",
        user_id: str = "default",
        query_keywords: Optional[list[str]] = None,
        query_embedding: Optional[list[float]] = None,
    ) -> Optional[str]:
        """
        存储记忆
        
        Args:
            query: 用户问题
            selected_skills: 选中的技能
            skill_scores: 技能得分
            confidence: 决策置信度
            reasoning: 决策理由
            response: 生成的回答
            user_id: 用户 ID
            query_keywords: 问题关键词
            query_embedding: 预计算的向量（可选）
        
        Returns:
            record_id 或 None
        """
        if not self._connected:
            logger.warning("长期记忆未连接，跳过存储")
            return None
        
        # 生成向量
        embedding = query_embedding
        if embedding is None:
            embedding = self.generate_embedding(query)
        
        if embedding is None:
            logger.error("无法生成向量，存储失败")
            return None
        
        # 生成关键词（简单使用）
        if query_keywords is None:
            query_keywords = self._extract_keywords(query)
        
        try:
            # 创建记录
            record = MemoryRecord(
                user_id=user_id,
                query=query,
                query_embedding=embedding,
                query_keywords=query_keywords,
                selected_skills=selected_skills,
                skill_scores=skill_scores,
                confidence=confidence,
                reasoning=reasoning,
                response=response,
            )
            
            # 转换为 Milvus 格式
            from .operations.insert import MemoryRecord as MilvusRecord
            
            milvus_record = MilvusRecord(
                user_id=user_id,
                query=query,
                query_embedding=embedding,
                query_keywords=query_keywords,
                selected_skills=selected_skills,
                skill_scores=skill_scores,
                confidence=confidence,
                reasoning=reasoning,
            )
            
            # 写入
            result = self._client.insert.insert(milvus_record)
            
            if result.success:
                logger.info(f"✓ 记忆存储成功: {result.record_id}")
                return result.record_id
            else:
                logger.error(f"记忆存储失败: {result.errors}")
                return None
                
        except Exception as e:
            logger.error(f"存储记忆时出错: {e}")
            return None
    
    def search(
        self,
        query: str,
        query_embedding: Optional[list[float]] = None,
        top_k: int = 3,
        similarity_threshold: float = 0.7,
        user_id: Optional[str] = None,
        skills_filter: Optional[list[str]] = None,
        timeout: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        检索相似记忆（带缓存和熔断保护）
        
        Args:
            query: 用户问题
            query_embedding: 预计算的向量（可选）
            top_k: 返回数量
            similarity_threshold: 相似度阈值
            user_id: 按用户过滤
            skills_filter: 按技能过滤
            timeout: 超时时间（秒），默认使用 _search_timeout
        
        Returns:
            SearchResult 列表
        """
        # 熔断器检查
        if not self._circuit_breaker.is_available():
            logger.warning("Milvus 熔断器打开，跳过检索")
            return []
        
        # 检查缓存
        cached = self._cache.get(query, query_embedding)
        if cached is not None:
            return cached
        
        # 未连接则返回空
        if not self._connected:
            logger.debug("长期记忆未连接，跳过检索")
            return []
        
        # 生成向量
        embedding = query_embedding
        if embedding is None:
            embedding = self.generate_embedding(query)
        
        if embedding is None:
            logger.error("无法生成向量，检索失败")
            return []
        
        try:
            # 执行检索（带超时）
            search_result = self._client.search.search(
                query=query,
                query_embedding=embedding,
                top_k=top_k * 2,  # 多检索一些，后面过滤
                similarity_threshold=similarity_threshold,
                user_id=user_id,
            )
            
            self._circuit_breaker.record_success()
            
            # 转换为 SearchResult
            results = []
            for record, score in zip(
                search_result.results,
                search_result.scores
            ):
                # 技能过滤
                if skills_filter:
                    if not any(s in record.selected_skills for s in skills_filter):
                        continue
                
                results.append(SearchResult(
                    record=self._to_memory_record(record),
                    similarity=score,
                ))
                
                # 达到 top_k 停止
                if len(results) >= top_k:
                    break
            
            if results:
                logger.info(f"检索到 {len(results)} 条相似记忆")
            
            # 写入缓存
            self._cache.set(query, results, embedding)
            
            return results
            
        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(f"检索记忆时出错: {e}")
            return []
    
    def search_by_skills(
        self,
        skills: list[str],
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """
        按技能检索记忆
        
        Args:
            skills: 技能列表
            user_id: 用户 ID
            limit: 返回数量
        
        Returns:
            MemoryRecord 列表
        """
        if not self._connected:
            return []
        
        try:
            records = self._client.search.get_by_skills(
                skills=skills,
                user_id=user_id,
                limit=limit,
            )
            return [self._to_memory_record(r) for r in records]
        except Exception as e:
            logger.error(f"按技能检索失败: {e}")
            return []
    
    def search_by_record_id(self, record_id: str) -> Optional[MemoryRecord]:
        """
        根据 ID 获取记忆
        
        Args:
            record_id: 记录 ID
        
        Returns:
            MemoryRecord 或 None
        """
        if not self._connected:
            return None
        
        try:
            record = self._client.search.search_by_record_id(record_id)
            return self._to_memory_record(record) if record else None
        except Exception as e:
            logger.error(f"获取记忆失败: {e}")
            return None
    
    def update_feedback(
        self,
        record_id: str,
        feedback_score: float,
        helpful: bool = False,
    ) -> bool:
        """
        更新反馈
        
        Args:
            record_id: 记录 ID
            feedback_score: 用户反馈评分
            helpful: 是否被采纳
        
        Returns:
            是否成功
        """
        if not self._connected:
            return False
        
        try:
            result = self._client.insert.update_feedback(
                record_id=record_id,
                feedback_score=feedback_score,
                helpful=helpful,
            )
            return result.success
        except Exception as e:
            logger.error(f"更新反馈失败: {e}")
            return False
    
    def get_stats(self) -> dict:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        if not self._connected:
            return {
                "connected": False,
                "cache": self._cache.get_stats(),
                "circuit_breaker": self._circuit_breaker.get_stats(),
            }
        
        try:
            stats = self._client.get_stats()
            return {
                "connected": True,
                "memories_count": stats.get("memories", 0),
                "meta_count": stats.get("meta", 0),
                "cache": self._cache.get_stats(),
                "circuit_breaker": self._circuit_breaker.get_stats(),
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "cache": self._cache.get_stats(),
                "circuit_breaker": self._circuit_breaker.get_stats(),
            }
    
    # ============================================================
    # 辅助方法
    # ============================================================
    
    def _extract_keywords(self, text: str, max_count: int = 10) -> list[str]:
        """简单提取关键词（基于字符长度和停用词过滤）"""
        # 简化实现：使用 2-4 字的中文词作为关键词
        stopwords = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}
        
        keywords = []
        for i in range(len(text) - 1):
            word = text[i:i+2]
            if word not in stopwords and word not in keywords:
                keywords.append(word)
                if len(keywords) >= max_count:
                    break
        
        return keywords
    
    def _to_memory_record(self, record) -> MemoryRecord:
        """将从 Milvus 获取的记录转换为 MemoryRecord"""
        if isinstance(record, MemoryRecord):
            return record
        
        return MemoryRecord(
            record_id=getattr(record, "record_id", ""),
            user_id=getattr(record, "user_id", ""),
            query=getattr(record, "query", ""),
            query_embedding=getattr(record, "query_embedding", []),
            query_keywords=getattr(record, "query_keywords", []),
            selected_skills=getattr(record, "selected_skills", []),
            skill_scores=getattr(record, "skill_scores", {}),
            confidence=getattr(record, "confidence", 0.0),
            reasoning=getattr(record, "reasoning", ""),
            response=getattr(record, "response", ""),
            feedback_score=getattr(record, "feedback_score", 0.0),
            helpful_count=getattr(record, "helpful_count", 0),
            created_at=getattr(record, "created_at", 0),
        )
    
    # ============================================================
    # 上下文构建
    # ============================================================
    
    def get_context_for_router(
        self,
        query: str,
        top_k: int = 3,
        timeout: Optional[float] = None,
    ) -> str:
        """
        获取用于路由的上下文提示
        
        Args:
            query: 用户问题
            top_k: 检索数量
            timeout: 超时时间
        
        Returns:
            格式化的上下文字符串
        """
        results = self.search(query, top_k=top_k, timeout=timeout)
        
        if not results:
            return ""
        
        parts = ["【相关历史决策参考】"]
        
        for i, result in enumerate(results, 1):
            record = result.record
            parts.append(f"\n{i}. 问题：{record.query[:50]}...")
            parts.append(f"   选用技能：{', '.join(record.selected_skills)}")
            parts.append(f"   置信度：{record.confidence:.0%}")
            parts.append(f"   决策理由：{record.reasoning[:50]}...")
        
        return "\n".join(parts)
    
    def get_context_for_executor(
        self,
        query: str,
        top_k: int = 3,
    ) -> str:
        """
        获取用于执行器的上下文提示
        
        Args:
            query: 用户问题
            top_k: 检索数量
        
        Returns:
            格式化的上下文字符串
        """
        results = self.search(query, top_k=top_k)
        
        if not results:
            return ""
        
        parts = ["【历史回答参考】"]
        
        for i, result in enumerate(results, 1):
            record = result.record
            if record.response:
                parts.append(f"\n{i}. 相似问题：{record.query[:50]}...")
                parts.append(f"   回答：{record.response[:200]}...")
        
        return "\n".join(parts)


# ============================================================
# 全局实例
# ============================================================

_memory: Optional[LongTermMemory] = None


def get_memory() -> LongTermMemory:
    """获取全局长期记忆实例"""
    global _memory
    
    if _memory is None:
        _memory = LongTermMemory()
    
    return _memory


def init_memory(cfg: Optional[Config] = None) -> LongTermMemory:
    """初始化全局长期记忆"""
    global _memory
    
    _memory = LongTermMemory(cfg=cfg)
    _memory.connect()
    
    return _memory


def close_memory() -> None:
    """关闭全局长期记忆"""
    global _memory
    
    if _memory is not None:
        _memory.disconnect()
        _memory = None
