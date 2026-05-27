"""
DialecticEngine Milvus Collection 创建脚本

自动检测 GPU 可用性，选择最优索引：
- GPU 可用 → GPU_CAGRA
- CPU 环境 → HNSW
"""

import logging
import os
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    Index,
    utility,
)
from pymilvus.exceptions import MilvusException

# ============================================================
# 配置
# ============================================================

MILVUS_HOST = os.environ.get("MILVUS_HOST", "localhost")
MILVUS_PORT = os.environ.get("MILVUS_PORT", "19530")
MILVUS_TOKEN = os.environ.get("MILVUS_TOKEN", "root:Milvus")

COLLECTION_MEMORIES = "dialectic_memories"
COLLECTION_META = "dialectic_meta"


def _get_embedding_dim() -> int:
    """动态获取当前 embedding 模型的向量维度"""
    try:
        from .utils.embedding import get_generator
        gen = get_generator()
        return gen.dimension
    except Exception:
        return 1536  # 回退默认值


EMBEDDING_DIM = _get_embedding_dim()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
# GPU 检测
# ============================================================

def detect_gpu() -> bool:
    """检测 Milvus 是否支持 GPU"""
    try:
        from pymilvus import connections
        connections.connect(host=MILVUS_HOST, port=MILVUS_PORT, token=MILVUS_TOKEN)
        
        # 尝试获取 GPU 信息
        try:
            from pymilvus.client.types import ConsistenBundle
            # Milvus 2.4+ 方式
            gpu_info = utility.get_gpu_status()
            if gpu_info and gpu_info.get("available_count", 0) > 0:
                return True
        except (ImportError, AttributeError):
            pass
        
        # 降级检测：尝试列出可用索引类型
        available_indexes = utility.list_indexes(COLLECTION_MEMORIES) if utility.has_collection(COLLECTION_MEMORIES) else []
        
        logger.info("GPU 检测完成，未发现可用 GPU 或 Milvus 版本不支持 GPU 索引")
        return False
        
    except MilvusException as e:
        logger.warning(f"连接 Milvus 失败: {e}")
        return False
    except Exception as e:
        logger.warning(f"GPU 检测异常: {e}")
        return False


def check_gpu_available() -> bool:
    """检查 GPU 是否可用（简化版）"""
    try:
        # 尝试导入 GPU 相关模块
        from pymilvus.client.config import Config
        return True
    except ImportError:
        pass
    
    # 检查环境变量
    import os
    if os.environ.get("MILVUS_GPU_ENABLED", "").lower() in ("1", "true", "yes"):
        return True
    
    return False


# ============================================================
# Schema 定义
# ============================================================

def create_memories_schema(dim: int = 768) -> CollectionSchema:
    """dialectic_memories 表 Schema"""
    
    fields = [
        FieldSchema(
            name="record_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            is_primary=True,
            description="记忆唯一 ID（UUID）",
        ),
        FieldSchema(
            name="user_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="用户 ID（预留）",
        ),
        FieldSchema(
            name="query_embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=dim,
            description="问题语义向量（text-embedding-ada-002）",
        ),
    ]
    
    return CollectionSchema(
        fields=fields,
        description="DialecticEngine 向量检索主表",
        enable_dynamic_field=False,
    )


def create_meta_schema(dim: int = 768) -> CollectionSchema:
    """dialectic_meta 表 Schema"""
    
    fields = [
        FieldSchema(
            name="record_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            is_primary=True,
            description="关联 dialectic_memories",
        ),
        FieldSchema(
            name="user_id",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="用户 ID（预留）",
        ),
        FieldSchema(
            name="query",
            dtype=DataType.VARCHAR,
            max_length=2048,
            description="原始问题文本",
        ),
        FieldSchema(
            name="query_embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=dim,
            description="问题语义向量（用于相似度搜索）",
        ),
        FieldSchema(
            name="query_keywords",
            dtype=DataType.JSON,
            description="问题关键词列表",
        ),
        FieldSchema(
            name="selected_skills",
            dtype=DataType.JSON,
            description="选中的技能/视角列表",
        ),
        FieldSchema(
            name="skill_scores",
            dtype=DataType.JSON,
            description="各技能得分",
        ),
        FieldSchema(
            name="confidence",
            dtype=DataType.FLOAT,
            description="决策置信度",
        ),
        FieldSchema(
            name="reasoning",
            dtype=DataType.VARCHAR,
            max_length=1024,
            description="决策理由",
        ),
        FieldSchema(
            name="feedback_score",
            dtype=DataType.FLOAT,
            description="用户反馈评分",
        ),
        FieldSchema(
            name="helpful_count",
            dtype=DataType.INT64,
            description="被采纳次数",
        ),
        FieldSchema(
            name="created_at",
            dtype=DataType.INT64,
            description="创建时间戳",
        ),
    ]
    
    return CollectionSchema(
        fields=fields,
        description="DialecticEngine 元数据表",
        enable_dynamic_field=False,
    )


# ============================================================
# 索引定义
# ============================================================

def create_memories_index_params(is_gpu: bool) -> list:
    """
    dialectic_memories 索引参数定义
    
    Args:
        is_gpu: 是否使用 GPU
    
    Returns:
        索引参数字典列表，用于 collection.create_index()
    """
    index_params_list = []
    
    # 向量索引
    if is_gpu:
        # GPU_CAGRA - GPU 环境首选
        index_params_list.append({
            "field_name": "query_embedding",
            "index_type": "GPU_CAGRA",
            "metric_type": "COSINE",
            "params": {},
        })
    else:
        # HNSW - CPU 环境首选
        index_params_list.append({
            "field_name": "query_embedding",
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 200},
        })
    
    # user_id 索引（用于按用户过滤）
    index_params_list.append({
        "field_name": "user_id",
        "index_type": "INVERTED",
        "params": {},
    })
    
    return index_params_list


def create_meta_index_params(is_gpu: bool = False) -> list:
    """dialectic_meta 索引参数定义"""
    # 向量索引
    if is_gpu:
        vector_index = {
            "field_name": "query_embedding",
            "index_type": "GPU_CAGRA",
            "metric_type": "COSINE",
            "params": {},
        }
    else:
        vector_index = {
            "field_name": "query_embedding",
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 200},
        }
    
    return [
        vector_index,
        # user_id 索引
        {
            "field_name": "user_id",
            "index_type": "INVERTED",
            "params": {},
        },
        # confidence 索引（用于按置信度排序/过滤）
        {
            "field_name": "confidence",
            "index_type": "INVERTED",
            "params": {},
        },
        # created_at 索引（用于按时间排序）
        {
            "field_name": "created_at",
            "index_type": "STL_SORT",
            "params": {},
        },
    ]


# ============================================================
# Collection 操作
# ============================================================

def create_or_recreate_collection(
    name: str,
    schema: CollectionSchema,
    index_params_list: list,
    recreate: bool = False,
) -> Collection:
    """
    创建或重建 Collection
    
    Args:
        name: Collection 名称
        schema: Schema 定义
        index_params_list: 索引参数列表
        recreate: 是否强制重建（删除后重建）
    
    Returns:
        Collection 对象
    """
    try:
        if utility.has_collection(name):
            if recreate:
                logger.info(f"删除已存在的 Collection: {name}")
                utility.drop_collection(name)
            else:
                logger.info(f"Collection 已存在: {name}，跳过创建")
                collection = Collection(name)
                collection.load()
                return collection
        
        # 创建 Collection
        logger.info(f"创建 Collection: {name}")
        collection = Collection(name=name, schema=schema)
        
        # 创建索引
        logger.info(f"创建索引，共 {len(index_params_list)} 个...")
        for idx_params in index_params_list:
            field_name = idx_params["field_name"]
            idx_type = idx_params.get("index_type", "UNKNOWN")
            logger.info(f"  - {field_name}: {idx_type}")
            collection.create_index(field_name, idx_params)
        
        # 加载 Collection
        logger.info(f"加载 Collection: {name}")
        collection.load()
        
        logger.info(f"✓ Collection {name} 创建成功")
        return collection
        
    except MilvusException as e:
        logger.error(f"创建 Collection {name} 失败: {e}")
        raise


def ensure_collections_exist(recreate: bool = False) -> None:
    """
    确保所有必需的 Milvus collections 存在。

    Args:
        recreate: 如果为 True，删除已存在的 collections 并重建
    """
    # 连接 Milvus
    logger.info(f"连接 Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
    connections.connect(
        host=MILVUS_HOST,
        port=MILVUS_PORT,
        token=MILVUS_TOKEN,
    )
    logger.info("✓ 连接成功")

    # 检查 GPU
    is_gpu = check_gpu_available()
    if is_gpu:
        logger.info("检测到 GPU 可用，将使用 GPU 索引")
    else:
        logger.info("使用 CPU 索引 (HNSW)")

    # 获取 embedding 维度
    dim = _get_embedding_dim()
    logger.info(f"Embedding 维度: {dim}")

    # 创建 dialectic_memories
    memories_schema = create_memories_schema(dim)
    memories_index_params = create_memories_index_params(is_gpu)
    create_or_recreate_collection(
        COLLECTION_MEMORIES,
        memories_schema,
        memories_index_params,
        recreate=recreate,
    )

    # 创建 dialectic_meta
    meta_schema = create_meta_schema(dim)
    meta_index_params = create_meta_index_params(is_gpu)
    create_or_recreate_collection(
        COLLECTION_META,
        meta_schema,
        meta_index_params,
        recreate=recreate,
    )

    logger.info("✓ 所有 Collections 创建完成")


# ============================================================
# 主函数
# ============================================================

def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("DialecticEngine Milvus Collection 初始化")
    logger.info("=" * 60)
    
    # 连接 Milvus
    try:
        logger.info(f"连接 Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
        connections.connect(
            host=MILVUS_HOST,
            port=MILVUS_PORT,
            token=MILVUS_TOKEN,
        )
        logger.info("✓ 连接成功")
    except MilvusException as e:
        logger.error(f"连接 Milvus 失败: {e}")
        return
    
    # GPU 检测
    is_gpu = check_gpu_available()
    if is_gpu:
        logger.info("✓ 检测到 GPU，将使用 GPU_CAGRA 索引")
        index_type = "GPU_CAGRA"
    else:
        logger.info("⚠ 未检测到 GPU，将使用 HNSW 索引（CPU）")
        index_type = "HNSW"
    
    # 记录配置
    logger.info("-" * 60)
    logger.info(f"配置:")
    logger.info(f"  - Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
    logger.info(f"  - 向量维度: {EMBEDDING_DIM}")
    logger.info(f"  - 度量方式: COSINE")
    logger.info(f"  - 向量索引: {index_type}")
    logger.info(f"  - Collection: {COLLECTION_MEMORIES}, {COLLECTION_META}")
    logger.info("-" * 60)
    
    # 获取 embedding 维度
    dim = _get_embedding_dim()
    
    # 创建 dialectic_memories
    logger.info("")
    memories_schema = create_memories_schema(dim)
    memories_index_params = create_memories_index_params(is_gpu)
    create_or_recreate_collection(
        name=COLLECTION_MEMORIES,
        schema=memories_schema,
        index_params_list=memories_index_params,
        recreate=False,
    )
    
    # 创建 dialectic_meta
    logger.info("")
    meta_schema = create_meta_schema(dim)
    meta_index_params = create_meta_index_params(is_gpu)
    create_or_recreate_collection(
        name=COLLECTION_META,
        schema=meta_schema,
        index_params_list=meta_index_params,
        recreate=False,
    )
    
    # 总结
    logger.info("")
    logger.info("=" * 60)
    logger.info("✓ 所有 Collection 初始化完成")
    logger.info("=" * 60)
    
    # 列出所有 Collection
    logger.info("")
    logger.info("当前 Collection 列表:")
    for name in utility.list_collections():
        coll = Collection(name)
        stats = coll.num_entities
        logger.info(f"  - {name}: {stats} 条记录")
    
    connections.disconnect("default")
    logger.info("已断开连接")


if __name__ == "__main__":
    main()
