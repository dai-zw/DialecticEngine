"""
DialecticEngine 检索操作

提供记忆记录的各种检索方法
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from pymilvus.exceptions import MilvusException

from ..config import config as default_config, Config
from ..client import MilvusClient
from .insert import MemoryRecord

logger = logging.getLogger(__name__)


# ============================================================
# 检索结果模型
# ============================================================

@dataclass
class SearchResult:
    """
    检索结果
    
    包含相似记忆和原始查询信息
    """
    
    query: str
    query_embedding: list
    
    # 相似记忆列表
    results: list["MemoryRecord"] = field(default_factory=list)
    scores: list[float] = field(default_factory=list)
    
    # 统计信息
    total_found: int = 0
    query_time_ms: float = 0.0
    
    def get_top(self, n: int = 3) -> list[tuple[MemoryRecord, float]]:
        """
        获取 Top-N 相似结果
        
        Args:
            n: 返回数量
        
        Returns:
            (记录, 相似度分数) 元组列表
        """
        return list(zip(self.results[:n], self.scores[:n]))
    
    def filter_by_score(self, threshold: float) -> list[tuple[MemoryRecord, float]]:
        """
        按相似度分数过滤
        
        Args:
            threshold: 分数阈值
        
        Returns:
            符合条件的 (记录, 分数) 元组列表
        """
        return [
            (r, s) for r, s in zip(self.results, self.scores)
            if s >= threshold
        ]


# ============================================================
# 检索操作类
# ============================================================

class SearchOperations:
    """
    检索操作类
    
    提供记忆记录的各种检索方法
    """
    
    def __init__(self, client: MilvusClient, cfg: Optional[Config] = None):
        """
        初始化
        
        Args:
            client: MilvusClient 实例
            cfg: 配置对象（默认使用全局配置）
        """
        self.client = client
        self.cfg = cfg or default_config
    
    def search(
        self,
        query: str,
        query_embedding: list,
        top_k: Optional[int] = None,
        similarity_threshold: Optional[float] = None,
        user_id: Optional[str] = None,
    ) -> SearchResult:
        """
        语义相似度检索
        
        Args:
            query: 原始查询文本
            query_embedding: 查询向量
            top_k: 返回数量（默认使用配置值）
            similarity_threshold: 相似度阈值（默认使用配置值）
            user_id: 按用户 ID 过滤（可选）
        
        Returns:
            SearchResult
        """
        import time
        start_time = time.time()
        
        top_k = top_k or self.cfg.search.top_k
        similarity_threshold = similarity_threshold or self.cfg.search.similarity_threshold
        
        try:
            # 构建搜索参数
            search_params = {
                "metric_type": "COSINE",
                "params": {},
            }
            
            # 构建表达式（用于过滤）
            expressions = []
            if user_id:
                expressions.append(f'user_id == "{user_id}"')
            
            expr = " and ".join(expressions) if expressions else None
            
            # 向量检索
            results = self.client.memories.search(
                data=[query_embedding],
                anns_field="query_embedding",
                param=search_params,
                limit=top_k * 2,  # 多检索一些，后面过滤
                expr=expr,
                output_fields=["record_id"],
            )
            
            if not results or not results[0]:
                return SearchResult(
                    query=query,
                    query_embedding=query_embedding,
                    total_found=0,
                    query_time_ms=(time.time() - start_time) * 1000,
                )
            
            # 获取 record_id 列表
            record_ids = [r.entity.get("record_id") for r in results[0]]
            
            # 查询元数据
            meta_results = self._get_meta_batch(record_ids)
            
            # 组装结果
            memory_records = []
            scores = []
            
            for hit in results[0]:
                record_id = hit.entity.get("record_id")
                
                if record_id in meta_results:
                    record = MemoryRecord.from_meta_data(meta_results[record_id])
                    score = float(hit.distance)
                    
                    # 按阈值过滤
                    if score >= similarity_threshold:
                        memory_records.append(record)
                        scores.append(score)
                        
                        # 达到 top_k 停止
                        if len(memory_records) >= top_k:
                            break
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            logger.info(f"检索完成: 找到 {len(memory_records)} 条相似记忆 ({elapsed_ms:.1f}ms)")
            
            return SearchResult(
                query=query,
                query_embedding=query_embedding,
                results=memory_records,
                scores=scores,
                total_found=len(memory_records),
                query_time_ms=elapsed_ms,
            )
            
        except MilvusException as e:
            logger.error(f"检索失败: {e}")
            return SearchResult(
                query=query,
                query_embedding=query_embedding,
                total_found=0,
                query_time_ms=(time.time() - start_time) * 1000,
            )
    
    def _get_meta_batch(self, record_ids: list[str]) -> dict:
        """
        批量获取元数据
        
        Args:
            record_ids: record_id 列表
        
        Returns:
            record_id -> 元数据字典
        """
        if not record_ids:
            return {}
        
        try:
            # 构建 IN 表达式
            id_list = "', '".join(record_ids)
            expr = f"record_id in ['{id_list}']"
            
            results = self.client.meta.query(
                expr=expr,
                output_fields=["*"],
            )
            
            return {r["record_id"]: r for r in results}
            
        except MilvusException as e:
            logger.error(f"批量查询元数据失败: {e}")
            return {}
    
    def search_by_record_id(self, record_id: str) -> Optional[MemoryRecord]:
        """
        根据 record_id 获取完整记忆
        
        Args:
            record_id: 记录 ID
        
        Returns:
            MemoryRecord 或 None
        """
        try:
            # 查询元数据
            expr = f"record_id == '{record_id}'"
            
            results = self.client.meta.query(
                expr=expr,
                output_fields=["*"],
            )
            
            if not results:
                return None
            
            return MemoryRecord.from_meta_data(results[0])
            
        except MilvusException as e:
            logger.error(f"查询失败: {e}")
            return None
    
    def get_recent(
        self,
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """
        获取最近的记忆
        
        Args:
            user_id: 用户 ID（可选）
            limit: 返回数量
        
        Returns:
            MemoryRecord 列表
        """
        try:
            # 构建查询参数
            expr = None
            if user_id:
                expr = f'user_id == "{user_id}"'
            
            # 按时间倒序查询
            results = self.client.meta.query(
                expr=expr,
                output_fields=["*"],
                limit=limit,
                sort=["created_at", "desc"],
            )
            
            return [MemoryRecord.from_meta_data(r) for r in results]
            
        except MilvusException as e:
            logger.error(f"查询最近记忆失败: {e}")
            return []
    
    def get_by_skills(
        self,
        skills: list[str],
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """
        按技能/视角筛选记忆
        
        Args:
            skills: 技能/视角列表
            user_id: 用户 ID（可选）
            limit: 返回数量
        
        Returns:
            MemoryRecord 列表
        """
        try:
            # 构建 JSON 包含查询
            skill_conditions = [f'selected_skills like "%{s}%"' for s in skills]
            skill_expr = " or ".join(skill_conditions)
            
            if user_id:
                expr = f'user_id == "{user_id}" and ({skill_expr})'
            else:
                expr = f"({skill_expr})"
            
            results = self.client.meta.query(
                expr=expr,
                output_fields=["*"],
                limit=limit,
            )
            
            return [MemoryRecord.from_meta_data(r) for r in results]
            
        except MilvusException as e:
            logger.error(f"按技能筛选失败: {e}")
            return []
    
    def get_high_confidence(
        self,
        min_confidence: float = 0.8,
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """
        获取高置信度记忆
        
        Args:
            min_confidence: 最低置信度
            user_id: 用户 ID（可选）
            limit: 返回数量
        
        Returns:
            MemoryRecord 列表
        """
        try:
            # 构建查询表达式
            expr = f"confidence >= {min_confidence}"
            if user_id:
                expr = f'user_id == "{user_id}" and {expr}'
            
            results = self.client.meta.query(
                expr=expr,
                output_fields=["*"],
                limit=limit,
                sort=["confidence", "desc"],
            )
            
            return [MemoryRecord.from_meta_data(r) for r in results]
            
        except MilvusException as e:
            logger.error(f"查询高置信度记忆失败: {e}")
            return []
    
    def get_helpful(
        self,
        min_helpful_count: int = 1,
        user_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[MemoryRecord]:
        """
        获取被多次采纳的记忆
        
        Args:
            min_helpful_count: 最少采纳次数
            user_id: 用户 ID（可选）
            limit: 返回数量
        
        Returns:
            MemoryRecord 列表
        """
        try:
            # 构建查询表达式
            expr = f"helpful_count >= {min_helpful_count}"
            if user_id:
                expr = f'user_id == "{user_id}" and {expr}'
            
            results = self.client.meta.query(
                expr=expr,
                output_fields=["*"],
                limit=limit,
                sort=["helpful_count", "desc"],
            )
            
            return [MemoryRecord.from_meta_data(r) for r in results]
            
        except MilvusException as e:
            logger.error(f"查询被采纳记忆失败: {e}")
            return []
