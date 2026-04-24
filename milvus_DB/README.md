# DialecticEngine 向量数据库架构

基于 Milvus 的长期记忆存储系统

---

## 目录

- [概述](#概述)
- [架构设计](#架构设计)
- [Collection 设计](#collection-设计)
- [索引设计](#索引设计)
- [工作流程](#工作流程)
- [代码结构](#代码结构)
- [使用说明](#使用说明)

---

## 概述

DialecticEngine 使用 Milvus 作为向量数据库，存储历史决策记忆，支持语义相似度检索。

### 核心需求

- 存储用户问题与 AI 决策结果
- 通过语义相似度找到历史类似问题
- 支持按置信度、时间等条件过滤

### 设计原则

| 原则 | 说明 |
|-----|------|
| 双 Collection | 向量检索与元数据分离，平衡性能与灵活性 |
| JSON 字段 | 结构化存储 selected_skills、skill_scores 等 |
| 智能索引选择 | 自动检测 GPU，优先使用 GPU_CAGRA |
| COSINE 度量 | 更适合语义相似度检索 |

### 索引选择策略

```
┌─────────────────────────────────────────────────────────────────┐
│                    索引自动选择逻辑                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  检测 GPU 可用性                                                 │
│        │                                                        │
│        ▼                                                        │
│  ┌─────────────┐     是      ┌─────────────────┐               │
│  │ GPU 可用？   │───────────►│ GPU_CAGRA       │               │
│  └─────────────┘            │ • 极低延迟      │               │
│        │ 否                  │ • 高召回        │               │
│        ▼                    │ • 适合实时查询  │               │
│  ┌─────────────┐            └─────────────────┘               │
│  │ HNSW       │                                               │
│  │ • 中等延迟  │                                               │
│  │ • 高召回    │                                               │
│  │ • CPU 环境  │                                               │
│  └─────────────┘                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 架构设计

### 双 Collection 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  dialectic_memories                                     │   │
│   │  ───────────────────                                   │   │
│   │  向量检索主表                                           │   │
│   │  存储: record_id + 向量                                 │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  dialectic_meta                                         │   │
│   │  ─────────────────                                       │   │
│   │  元数据表                                               │   │
│   │  存储: record_id + 完整元数据                           │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 分离理由

| 优势 | 说明 |
|-----|------|
| 检索性能 | 向量表字段少，索引更高效（GPU_CAGRA 或 HNSW） |
| 灵活性 | 元数据可独立扩展字段 |
| 内存效率 | 频繁检索只加载向量表 |

---

## Collection 设计

### Collection 1: `dialectic_memories`

**用途**: 向量检索主表

| 字段名 | 数据类型 | 主键 | 说明 |
|-------|---------|-----|------|
| `record_id` | VARCHAR(64) | ✅ | 记忆唯一 ID（UUID） |
| `user_id` | VARCHAR(64) | ❌ | 用户 ID（预留，初期可为空） |
| `query_embedding` | FLOAT_VECTOR(1536) | ❌ | 问题语义向量 |

### Collection 2: `dialectic_meta`

**用途**: 元数据表

| 字段名 | 数据类型 | 主键 | 说明 |
|-------|---------|-----|------|
| `record_id` | VARCHAR(64) | ✅ | 关联 dialectic_memories |
| `user_id` | VARCHAR(64) | ❌ | 用户 ID（预留） |
| `query` | VARCHAR(2048) | ❌ | 原始问题文本 |
| `query_keywords` | JSON | ❌ | 问题关键词列表 |
| `selected_skills` | JSON | ❌ | 选中的技能/视角列表 |
| `skill_scores` | JSON | ❌ | 各技能得分 |
| `confidence` | Float | ❌ | 决策置信度 |
| `reasoning` | VARCHAR(1024) | ❌ | 决策理由 |
| `feedback_score` | Float | ❌ | 用户反馈评分 |
| `helpful_count` | Int64 | ❌ | 被采纳次数 |
| `created_at` | Int64 | ❌ | 创建时间戳 |

---

## 索引设计

### 索引选择策略

系统自动检测 GPU 可用性，选择最优索引：

| 环境 | 推荐索引 | 度量方式 | 说明 |
|-----|---------|---------|------|
| **GPU 可用** | GPU_CAGRA | COSINE | 极低延迟（<10ms），高召回率，适合实时查询 |
| **CPU 环境** | HNSW | COSINE | 中等延迟，高召回率，适合通用场景 |

### CPU 环境索引

| Collection | 字段 | 索引类型 | 度量方式 | 参数 |
|-----------|-----|---------|---------|------|
| dialectic_memories | query_embedding | **HNSW** | COSINE | M=16, efConstruction=200 |
| dialectic_memories | user_id | INVERTED | - | - |
| dialectic_meta | user_id | INVERTED | - | - |
| dialectic_meta | confidence | INVERTED | - | - |
| dialectic_meta | created_at | STL_SORT | - | - |

### GPU 环境索引

| Collection | 字段 | 推荐索引 | 度量方式 | 说明 |
|-----------|-----|---------|---------|------|
| dialectic_memories | query_embedding | **GPU_CAGRA** | COSINE | 高召回低延迟，实时查询首选 |

### 索引对比参考

| 索引类型 | 召回率 | 延迟 | 内存占用 | 建索引速度 | 适用场景 |
|---------|-------|------|---------|-----------|---------|
| FLAT | 100% | 高 | 大 | 无需建索引 | 小数据集验证 |
| IVF_FLAT | 高 | 中 | 中 | 快 | 批量导入 |
| HNSW | 极高 | 低 | 中~高 | 慢 | CPU 环境首选 |
| IVF_PQ | 中~高 | 低 | 小 | 快 | 内存受限场景 |
| DiskANN | 高 | 低 | 小(磁盘) | 慢 | 超大规模数据 |
| **GPU_CAGRA** | **极高** | **极低** | 中 | 快 | **GPU 环境首选** |

---

## 工作流程

### 写入流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        写入流程                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 创建 MemoryRecord (包含所有元数据)                          │
│  2. 使用 OpenAI text-embedding-ada-002 生成 1536维向量         │
│  3. 写入 dialectic_memories:                                   │
│     └── {record_id, user_id, query_embedding}                 │
│  4. 写入 dialectic_meta:                                       │
│     └── {record_id, user_id, query, selected_skills, ...}     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 查询流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        查询流程                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. 接收用户问题                                                │
│  2. 使用 OpenAI text-embedding-ada-002 生成向量                │
│  3. 在 dialectic_memories 中向量检索:                          │
│     ├── metric_type: COSINE                                    │
│     ├── limit: Top-K                                          │
│     └── 获取 record_id 列表                                    │
│  4. 在 dialectic_meta 中批量查询元数据                         │
│  5. 返回完整结果                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 架构图示

```
                              用户输入问题
                                    │
                                    ▼
                          ┌─────────────────┐
                          │  OpenAI API     │
                          │  生成 1536维向量 │
                          └─────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │  dialectic_memories       │
                    │  ─────────────────────── │
                    │  • record_id (PK)        │
                    │  • user_id               │
                    │  • query_embedding       │
                    │    (GPU_CAGRA / HNSW)    │◄── COSINE 检索
                    └───────────────────────────┘
                                    │
                          Top-K 相似记忆
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │  dialectic_meta           │
                    │  ─────────────────────── │
                    │  • record_id (PK)        │
                    │  • query                 │
                    │  • selected_skills (JSON)│
                    │  • skill_scores (JSON)   │
                    │  • confidence            │
                    │  • reasoning            │
                    │  • feedback_score       │
                    │  • helpful_count        │
                    │  • created_at           │
                    └───────────────────────────┘
                                    │
                                    ▼
                          返回检索结果 + 元数据
```

---

## 代码结构

```
milvus_DB/
├── README.md                 # 本文档
├── create_collections.py    # Collection 创建脚本
├── config.py                # 配置（连接、维度等）
├── client.py                # Milvus 客户端封装
├── long_term_memory.py      # 长期记忆封装（与 DialecticEngine 集成）
├── operations/
│   ├── __init__.py
│   ├── insert.py            # 写入操作
│   └── search.py            # 查询操作
└── utils/
    ├── __init__.py
    └── embedding.py          # 向量生成工具
```

---

## 与 DialecticEngine 集成

### 集成架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    DialecticEngine 完整流程                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  用户输入问题                                                     │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ PolicyRouter.route()                                    │    │
│  │  ├── 特征提取                                           │    │
│  │  ├── 上下文加载                                         │    │
│  │  ├── 长期记忆检索 ←─────────────────────────────────┐  │    │
│  │  │        (检索相似历史决策)                          │  │    │
│  │  └── Skill 评分与融合                                  │  │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ SkillExecutor.execute()                                  │    │
│  │  ├── 加载 Skill 上下文                                  │    │
│  │  ├── 长期记忆上下文 ←───────────────────────────────┐  │    │
│  │  │      (历史回答参考)                                │  │    │
│  │  └── DeepSeek LLM 生成回答                            │  │    │
│  └─────────────────────────────────────────────────────────┘    │
│       │                                                         │
│       ▼                                                         │
│  存储到长期记忆 ←───────────────────────────────────────────    │
│  (query, selected_skills, response, confidence)                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 启用长期记忆

**方式 1: 环境变量**

```bash
export LONG_TERM_MEMORY_ENABLED=true
export MILVUS_HOST=localhost
export MILVUS_PORT=19530
export OPENAI_API_KEY=your-api-key
```

**方式 2: 代码中启用**

```python
from main_entry import DialecticEngine

# 启用长期记忆
engine = DialecticEngine(
    long_term_memory_enabled=True,
)

# 正常使用
result = engine.chat("我和老板意见不合，该直言吗？")
```

### API 接口

| 方法 | 说明 |
|-----|------|
| `engine.chat(query)` | 对话，自动存储记忆 |
| `engine.get_similar_memories(query, top_k)` | 获取相似记忆 |
| `engine.update_memory_feedback(decision_id, score)` | 更新反馈 |

---

## 使用说明

### 前提条件

1. 安装 Milvus（参考 [官方文档](https://milvus.io/docs/zh/quickstart.md)）

   ```bash
   # 下载 docker-compose 配置
   wget https://github.com/milvus-io/milvus/releases/download/v2.6.7/milvus-standalone-docker-compose.yml -O docker-compose.yml

   # 启动
   docker compose up -d
   ```

2. 安装 Python 依赖

   ```bash
   pip install pymilvus openai
   ```

### 初始化 Collection

```bash
python create_collections.py
```

### 连接配置

编辑 `config.py`:

```python
MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
MILVUS_TOKEN = "root:Milvus"  # 默认凭证，生产环境请修改

EMBEDDING_MODEL = "text-embedding-ada-002"
EMBEDDING_DIM = 1536
```

---

## 附录

### Milvus 字段类型参考

| 类型 | 说明 |
|-----|------|
| Int64 | 64位整数 |
| Float | 32位浮点 |
| Double | 64位浮点 |
| Bool | 布尔值 |
| VARCHAR(n) | 可变长度字符串，需指定 max_length |
| JSON | JSON 对象/数组（Milvus 2.3+） |
| FLOAT_VECTOR(n) | n维浮点向量 |
| FLOAT16_VECTOR(n) | n维半精度向量 |
| BINARY_VECTOR(n) | n维二进制向量 |

### 参考链接

- [Milvus 官方文档](https://milvus.io/docs/zh/home)
- [Schema 详解](https://milvus.io/docs/zh/schema.md)
- [索引说明](https://milvus.io/docs/zh/index-explained.md)
- [GPU 索引](https://milvus.io/docs/zh/gpu-index-overview.md)

---

*Last updated: 2026-04-19*