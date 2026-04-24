"""
DialecticEngine 写入操作

提供记忆记录的各种写入方法
"""

import json
import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from pymilvus.exceptions import MilvusException

from ..config import config as default_config, Config
from ..client import MilvusClient

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class MemoryRecord:
    """
    记忆记录数据模型
    
    包含完整的记忆信息
    """
    
    # 基础字段
    user_id: str = ""
    query: str = ""
    query_embedding: list = field(default_factory=list)
    
    # 关键词和技能
    query_keywords: list = field(default_factory=list)
    selected_skills: list = field(default_factory=list)
    skill_scores: dict = field(default_factory=dict)
    
    # 决策信息
    confidence: float = 0.0
    reasoning: str = ""
    
    # 反馈信息
    feedback_score: float = 0.0
    helpful_count: int = 0
    
    # 元数据
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp()))
    
    def to_memories_data(self) -> dict:
        """转换为 dialectic_memories 表数据"""
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "query_embedding": self.query_embedding,
        }
    
    def to_meta_data(self) -> dict:
        """转换为 dialectic_meta 表数据"""
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "query": self.query,
            "query_keywords": json.dumps(self.query_keywords, ensure_ascii=False),
            "selected_skills": json.dumps(self.selected_skills, ensure_ascii=False),
            "skill_scores": json.dumps(self.skill_scores, ensure_ascii=False),
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "feedback_score": self.feedback_score,
            "helpful_count": self.helpful_count,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_meta_data(cls, data: dict) -> "MemoryRecord":
        """从 dialectic_meta 表数据创建记录"""
        record = cls()
        record.record_id = data.get("record_id", "")
        record.user_id = data.get("user_id", "")
        record.query = data.get("query", "")
        
        # 解析 JSON 字段
        for json_field in ["query_keywords", "selected_skills", "skill_scores"]:
            value = data.get(json_field)
            if isinstance(value, str):
                try:
                    setattr(record, json_field, json.loads(value))
                except json.JSONDecodeError:
                    setattr(record, json_field, [])
            else:
                setattr(record, json_field, value or [])
        
        record.confidence = data.get("confidence", 0.0)
        record.reasoning = data.get("reasoning", "")
        record.feedback_score = data.get("feedback_score", 0.0)
        record.helpful_count = data.get("helpful_count", 0)
        record.created_at = data.get("created_at", 0)
        
        return record


@dataclass
class InsertResult:
    """插入结果"""
    
    success: bool
    record_id: Optional[str] = None
    message: str = ""
    errors: list = field(default_factory=list)


# ============================================================
# 写入操作类
# ============================================================

class InsertOperations:
    """
    写入操作类
    
    提供记忆记录的各种写入方法
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
    
    def insert(self, record: MemoryRecord) -> InsertResult:
        """
        插入单条记忆记录
        
        Args:
            record: 记忆记录
        
        Returns:
            InsertResult
        """
        # 生成 record_id
        if not record.record_id:
            record.record_id = str(uuid.uuid4())
        
        try:
            # 写入 dialectic_memories
            self.client.memories.insert(record.to_memories_data())
            
            # 写入 dialectic_meta
            self.client.meta.insert(record.to_meta_data())
            
            logger.info(f"✓ 插入记忆: {record.record_id}")
            
            return InsertResult(
                success=True,
                record_id=record.record_id,
                message="插入成功",
            )
            
        except MilvusException as e:
            logger.error(f"插入失败: {e}")
            return InsertResult(
                success=False,
                record_id=record.record_id,
                message="插入失败",
                errors=[str(e)],
            )
    
    def insert_batch(self, records: list[MemoryRecord]) -> InsertResult:
        """
        批量插入记忆记录
        
        Args:
            records: 记忆记录列表
        
        Returns:
            InsertResult
        """
        if not records:
            return InsertResult(success=True, message="无数据")
        
        # 生成 record_id
        for record in records:
            if not record.record_id:
                record.record_id = str(uuid.uuid4())
        
        try:
            # 准备数据
            memories_data = [r.to_memories_data() for r in records]
            meta_data = [r.to_meta_data() for r in records]
            
            # 批量写入
            self.client.memories.insert(memories_data)
            self.client.meta.insert(meta_data)
            
            record_ids = [r.record_id for r in records]
            logger.info(f"✓ 批量插入 {len(records)} 条记忆")
            
            return InsertResult(
                success=True,
                record_id=",".join(record_ids),
                message=f"成功插入 {len(records)} 条记录",
            )
            
        except MilvusException as e:
            logger.error(f"批量插入失败: {e}")
            return InsertResult(
                success=False,
                message="批量插入失败",
                errors=[str(e)],
            )
    
    def update_feedback(
        self,
        record_id: str,
        feedback_score: float,
        helpful: bool = False,
    ) -> InsertResult:
        """
        更新反馈信息
        
        Args:
            record_id: 记录 ID
            feedback_score: 用户反馈评分 (0-1)
            helpful: 是否被采纳
        
        Returns:
            InsertResult
        """
        try:
            # 构建更新表达式
            expressions = [
                f'feedback_score == {feedback_score}',
            ]
            
            if helpful:
                # 增加采纳计数
                expr = f"record_id == '{record_id}'"
                
                # 查询当前 helpful_count
                results = self.client.meta.query(
                    expr=expr,
                    output_fields=["helpful_count"],
                )
                
                if results:
                    current_count = results[0].get("helpful_count", 0)
                    new_count = current_count + 1
                    
                    # 使用 flush 更新
                    from pymilvus import DataType
                    
                    # 直接删除后重新插入（Milvus 不支持直接更新）
                    # 方案：查询完整数据，修改后重新插入
                    full_data = self.client.meta.query(
                        expr=expr,
                        output_fields=["*"],
                    )
                    
                    if full_data:
                        record = MemoryRecord.from_meta_data(full_data[0])
                        record.feedback_score = feedback_score
                        record.helpful_count = new_count
                        
                        # 删除旧记录
                        self.client.meta.delete(expr)
                        self.client.memories.delete(expr=f"record_id == '{record_id}'")
                        
                        # 重新插入（使用新的 Vector ID）
                        new_record_id = str(uuid.uuid4())
                        
                        # 需要重新获取向量数据
                        vector_data = self.client.memories.query(
                            expr=f"record_id == '{record_id}'",
                            output_fields=["query_embedding"],
                        )
                        
                        if vector_data:
                            record.record_id = new_record_id
                            record.query_embedding = vector_data[0].get("query_embedding", [])
                            
                            self.insert(record)
                            
                            logger.info(f"✓ 更新反馈: {record_id} -> helpful_count={new_count}")
                            
                            return InsertResult(
                                success=True,
                                record_id=new_record_id,
                                message="反馈已更新",
                            )
            
            return InsertResult(
                success=True,
                record_id=record_id,
                message="反馈已记录",
            )
            
        except MilvusException as e:
            logger.error(f"更新反馈失败: {e}")
            return InsertResult(
                success=False,
                record_id=record_id,
                message="更新失败",
                errors=[str(e)],
            )
    
    def delete(self, record_id: str) -> InsertResult:
        """
        删除记忆记录
        
        Args:
            record_id: 记录 ID
        
        Returns:
            InsertResult
        """
        try:
            expr = f"record_id == '{record_id}'"
            
            # 删除两个 Collection 中的记录
            self.client.memories.delete(expr)
            self.client.meta.delete(expr)
            
            logger.info(f"✓ 删除记忆: {record_id}")
            
            return InsertResult(
                success=True,
                record_id=record_id,
                message="删除成功",
            )
            
        except MilvusException as e:
            logger.error(f"删除失败: {e}")
            return InsertResult(
                success=False,
                record_id=record_id,
                message="删除失败",
                errors=[str(e)],
            )
