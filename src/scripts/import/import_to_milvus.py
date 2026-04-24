"""
将知识库数据导入Milvus向量数据库
支持BGE/M3E等中文embedding模型
"""

import json
import sys
from pathlib import Path
from typing import List

try:
    import torch
    from sentence_transformers import SentenceTransformer
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
except ImportError as e:
    print(f"❌ 缺少依赖: {e}")
    print("请运行: pip install torch sentence-transformers pymilvus")
    sys.exit(1)

class MilvusImporter:
    def __init__(self,
                 host: str = "localhost",
                 port: int = 19530,
                 collection_name: str = "chinese_classics",
                 embedding_model: str = "BAAI/bge-large-zh-v1.5"):
        """
        Args:
            embedding_model: 推荐使用中文embedding模型
                - BAAI/bge-large-zh-v1.5 (1024维)
                - moka-ai/m3e-large (1024维)
                - sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 (384维)
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.embedding_model = embedding_model

        # 检查是否有GPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[INFO] Using device: {self.device}")

        # 加载embedding模型
        print(f"[INFO] Loading embedding model: {embedding_model}")
        self.model = SentenceTransformer(embedding_model, device=self.device)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        print(f"[INFO] Embedding dimension: {self.embedding_dim}")

        # 连接Milvus
        try:
            connections.connect(
                alias="default",
                host=host,
                port=port
            )
            print(f"[OK] Connected to Milvus at {host}:{port}")
        except Exception as e:
            print(f"❌ 无法连接到Milvus: {e}")
            print("请确保Milvus服务正在运行（docker run -d -p 19530:19530 milvusdb/milvus:v2.4.0）")
            sys.exit(1)

    def create_collection(self, drop_existing: bool = False):
        """创建Collection"""
        if utility.has_collection(self.collection_name):
            if drop_existing:
                utility.drop_collection(self.collection_name)
                print(f"[INFO] Dropped existing collection: {self.collection_name}")
            else:
                print(f"[WARN] Collection '{self.collection_name}' already exists")
                collection = Collection(self.collection_name)
                collection.load()
                return collection

        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=2000),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
            FieldSchema(name="school", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="classic", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chapter", dtype=DataType.VARCHAR, max_length=200),
            FieldSchema(name="chunk_id", dtype=DataType.INT32),
            FieldSchema(name="source_url", dtype=DataType.VARCHAR, max_length=500),
            FieldSchema(name="dynasty", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="author", dtype=DataType.VARCHAR, max_length=100),
        ]

        schema = CollectionSchema(
            fields=fields,
            description="DialecticEngine Knowledge Base - Chinese Philosophical Classics",
            enable_dynamic_field=True
        )

        collection = Collection(
            name=self.collection_name,
            schema=schema,
            using='default'
        )
        print(f"[OK] Created collection: {self.collection_name}")
        return collection

    def load_chunks(self, chunks_file: Path) -> List[dict]:
        """从JSONL文件加载chunks"""
        chunks = []
        with open(chunks_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    chunks.append(json.loads(line))
        return chunks

    def generate_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """批量生成embeddings"""
        print(f"[INFO] Generating embeddings for {len(texts)} texts...")
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True  # L2归一化，适合cosine相似度
        )
        return embeddings.tolist()

    def import_data(self, chunks_file: Path, batch_size: int = 100, drop_existing: bool = False):
        """导入数据到Milvus"""
        # 加载chunks
        if not chunks_file.exists():
            print(f"❌ {chunks_file} not found. Run preprocess script first.")
            return

        chunks = self.load_chunks(chunks_file)
        print(f"[INFO] Loaded {len(chunks)} chunks")

        # 创建collection
        collection = self.create_collection(drop_existing=drop_existing)

        # 批量插入
        total = len(chunks)
        for i in range(0, total, batch_size):
            batch = chunks[i:i+batch_size]

            texts = [chunk['text'] for chunk in batch]
            embeddings = self.generate_embeddings(texts)

            meta = chunk.get('metadata', {})
            school_list = [meta.get('school', 'unknown') for chunk in batch]
            classic_list = [meta.get('classic', 'unknown') for chunk in batch]
            chapter_list = [meta.get('chapter', '') for chunk in batch]
            chunk_id_list = [meta.get('chunk_id', 0) for chunk in batch]
            url_list = [meta.get('source_url', '') or meta.get('url', '') for chunk in batch]
            dynasty_list = [meta.get('dynasty', '先秦') for chunk in batch]
            author_list = [meta.get('author', '') for chunk in batch]

            # 插入数据
            mr = collection.insert([
                texts,
                embeddings,
                school_list,
                classic_list,
                chapter_list,
                chunk_id_list,
                url_list,
                dynasty_list,
                author_list
            ])

            print(f"[{min(i+batch_size, total)}/{total}] Inserted batch of {len(batch)} vectors")

        # 刷新collection
        collection.flush()
        print(f"\n[OK] Total vectors inserted: {collection.num_entities}")

        # 创建索引
        print("[INFO] Creating index...")
        index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 16, "efConstruction": 200}
        }
        collection.create_index(
            field_name="embedding",
            index_params=index_params
        )
        print("[OK] Index created")

        # 加载到内存
        collection.load()
        print("[OK] Collection loaded into memory")

        return collection

def search_similar(query: str, collection: Collection, model, top_k: int = 5, school_filter: str = None):
    """搜索相似文本"""
    # 生成query embedding
    query_embedding = model.encode([query])
    query_vec = query_embedding[0].tolist()

    # 搜索参数
    search_params = {"metric_type": "COSINE", "params": {"ef": 64}}

    # 构建过滤表达式
    expr = None
    if school_filter:
        expr = f'school == "{school_filter}"'

    # 搜索
    if expr:
        results = collection.search(
            data=[query_vec],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["text", "school", "classic", "chapter"],
            expr=expr
        )
    else:
        results = collection.search(
            data=[query_vec],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            output_fields=["text", "school", "classic", "chapter"]
        )

    # 输出结果
    print(f"\n🔍 查询: {query}")
    print(f"📊 找到 {len(results[0])} 个结果")
    print("-" * 60)

    for i, hits in enumerate(results):
        for hit in hits:
            print(f"\n【{i+1}】 相似度: {hit.score:.4f}")
            print(f"    来源: {hit.entity.classic} ({hit.entity.school})")
            print(f"    章节: {hit.entity.chapter}")
            print(f"    内容: {hit.entity.text[:200]}...")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Import Chinese Classics to Milvus')
    parser.add_argument('--host', default='localhost', help='Milvus host')
    parser.add_argument('--port', type=int, default=19530, help='Milvus port')
    parser.add_argument('--collection', default='chinese_classics', help='Collection name')
    parser.add_argument('--model', default='BAAI/bge-large-zh-v1.5', help='Embedding model')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size for insertion')
    parser.add_argument('--drop', action='store_true', help='Drop existing collection')
    parser.add_argument('--search', type=str, help='Search query after import')
    parser.add_argument('--filter', type=str, help='Filter by school (e.g., daojia, rujia)')

    args = parser.parse_args()

    chunks_file = Path('knowledge/chunks.jsonl')
    if not chunks_file.exists():
        print(f"❌ {chunks_file} not found!")
        print("请先运行: python scripts/preprocess_for_milvus.py")
        return

    # 创建导入器
    importer = MilvusImporter(
        host=args.host,
        port=args.port,
        collection_name=args.collection,
        embedding_model=args.model
    )

    # 导入数据
    collection = importer.import_data(
        chunks_file,
        batch_size=args.batch_size,
        drop_existing=args.drop
    )

    print("\n✅ 导入完成！")
    print(f"   Collection: {args.collection}")
    print(f"   Total vectors: {collection.num_entities}")

    # 如果指定了搜索查询，执行搜索
    if args.search:
        search_similar(
            args.search,
            collection,
            importer.model,
            top_k=5,
            school_filter=args.filter
        )

if __name__ == '__main__':
    main()