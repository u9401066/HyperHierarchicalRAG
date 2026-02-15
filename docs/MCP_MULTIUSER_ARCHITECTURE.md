# MCP 多人連線與持久化架構設計

> 最後更新: 2026-01-06

## 📊 問題分析

### 1. LightRAG 向量庫對應

**✅ LightRAG 完全具備 HGMem 需要的三個向量庫：**

| HGMem 名稱 | LightRAG 對應 | 用途 |
|-----------|--------------|------|
| `entities_vdb` | `rag.entities_vdb` | 實體嵌入向量搜尋 |
| `relationships_vdb` | `rag.relationships_vdb` | 關係嵌入向量搜尋 |
| `text_chunks_vdb` | `rag.chunks_vdb` | 文本塊向量搜尋 |

**位置:** `external/LightRAG/lightrag/lightrag.py` L625-637

```python
self.entities_vdb: BaseVectorStorage = self.vector_db_storage_cls(
    namespace=NameSpace.VECTOR_STORE_ENTITIES,
    meta_fields={"entity_name", "source_id", "content", "file_path"},
)
self.relationships_vdb: BaseVectorStorage = self.vector_db_storage_cls(
    namespace=NameSpace.VECTOR_STORE_RELATIONSHIPS,
    meta_fields={"src_id", "tgt_id", "source_id", "content", "file_path"},
)
self.chunks_vdb: BaseVectorStorage = self.vector_db_storage_cls(
    namespace=NameSpace.VECTOR_STORE_CHUNKS,
    meta_fields={"full_doc_id", "content", "file_path"},
)
```

---

## 🔄 MCP 模式下的 collect_absent_entities_relationships

### 問題

當作為 MCP Server 時：
- **LLM 不在 RAG 內部** - LLM 是外部 Client (Claude/GPT)
- **無狀態** - 每次 Tool 調用都是獨立的
- **需要保持這個核心功能** - 自動補全缺失實體是 HGMem 的創新

### 解決方案：雙軌制

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                    MCP 雙軌 LLM 架構                                       ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  ┌─────────────────────┐         ┌─────────────────────────────────────┐  ║
║  │   軌道 1: 外部 LLM   │         │       軌道 2: 內部 LLM (可選)       │  ║
║  │  (Claude via MCP)   │         │      (Ollama/OpenAI 自動化)         │  ║
║  └──────────┬──────────┘         └───────────────┬─────────────────────┘  ║
║             │                                     │                        ║
║             ▼                                     ▼                        ║
║  ┌──────────────────────┐         ┌─────────────────────────────────────┐  ║
║  │ 高層對話/推理/回答    │         │ 自動化任務 (可用 小/快 模型):       │  ║
║  │ - 使用者問答          │         │ - collect_absent_entities          │  ║
║  │ - 複雜推理           │         │ - 實體抽取                          │  ║
║  │ - 多輪對話           │         │ - 關係抽取                          │  ║
║  └──────────────────────┘         │ - 記憶演化                          │  ║
║                                    └─────────────────────────────────────┘  ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

### 實作方式

#### 方式 A: 內部 LLM 自動化 (推薦)

```python
# config.py 新增設定
class MCPConfig:
    # 外部 LLM 處理高層對話 (MCP Client)
    # 內部 LLM 處理自動化任務
    internal_llm_provider: str = "ollama"  # ollama, openai, none
    internal_llm_model: str = "qwen2:7b"   # 小模型即可
    internal_llm_host: str = "http://localhost:11434"

    # 是否啟用自動實體補全
    auto_collect_absent_entities: bool = True
```

```python
# MCP Tool 觸發自動補全
@mcp.tool()
async def query_with_memory(query: str) -> str:
    """查詢並自動演化記憶"""

    # 1. 執行查詢
    result = await engine.query(query)

    # 2. 檢測缺失實體 (在查詢過程中已收集)
    if result.absent_entities and engine.config.mcp.auto_collect_absent_entities:
        # 使用內部 LLM 自動補全
        await engine.sync_service.collect_absent_entities_relationships(
            absent_entities_hyperedges_kv=result.absent_entities,
            context_info=result.retrieved_context,
            # 使用內部 LLM，不需要外部 Client
        )

    return result.answer
```

#### 方式 B: 暴露為 MCP Tool (讓外部 LLM 決定)

```python
@mcp.tool()
async def collect_missing_entities(
    entities: List[str],
    context: str,
    descriptions: Dict[str, str]  # 外部 LLM 提供描述
) -> Dict[str, Any]:
    """
    補全 Knowledge Graph 中缺失的實體。

    當你在對話中發現提到了 KG 中不存在的重要實體時，
    使用此工具將其添加到知識庫。

    Args:
        entities: 缺失的實體名稱列表
        context: 提及這些實體的上下文
        descriptions: 每個實體的描述 {"實體名": "描述..."}
    """
    # 外部 LLM 已經完成抽取，直接寫入
    for entity, description in descriptions.items():
        await engine.kg_adapter.upsert_node(
            entity,
            {"description": description, "source": "mcp_user"}
        )
    return {"added": list(descriptions.keys())}
```

#### 方式 C: 混合模式 (最靈活)

```python
class HybridEntityCollector:
    """混合模式：優先內部 LLM，失敗時請求外部"""

    async def collect(self, absent_entities, context) -> CollectResult:
        if self.internal_llm:
            try:
                # 優先使用內部小模型
                return await self._collect_with_internal_llm(
                    absent_entities, context
                )
            except Exception as e:
                logger.warning(f"Internal LLM failed: {e}")

        # Fallback: 返回需要外部處理的標記
        return CollectResult(
            status="needs_external_llm",
            pending_entities=absent_entities,
            prompt_for_client=self._generate_extraction_prompt(
                absent_entities, context
            )
        )
```

---

## 🔒 多人連線持久化問題

### 當前狀態

| 存儲類型 | 預設 | 多人並發問題 |
|---------|------|-------------|
| KV Storage | JsonKVStorage | ❌ **檔案鎖競爭** |
| Vector Storage | NanoVectorDBStorage | ❌ **記憶體模式，無持久化** |
| Graph Storage | NetworkXStorage | ❌ **記憶體模式** |
| Doc Status | JsonDocStatusStorage | ❌ **檔案鎖競爭** |

### LightRAG 提供的多人解決方案

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                    LightRAG 存儲後端選項                                   ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                            ║
║  ┌─────────────────────────────────────────────────────────────────────┐  ║
║  │  🏠 單人/開發模式 (預設)                                              │  ║
║  │  KV: JsonKVStorage | Vector: NanoVectorDB | Graph: NetworkXStorage  │  ║
║  └─────────────────────────────────────────────────────────────────────┘  ║
║                                                                            ║
║  ┌─────────────────────────────────────────────────────────────────────┐  ║
║  │  👥 多人模式 - PostgreSQL 全家桶 (推薦)                              │  ║
║  │  KV: PGKVStorage | Vector: PGVectorStorage | Graph: PGGraphStorage  │  ║
║  │  ✅ ACID 事務 | ✅ 行級鎖 | ✅ 連線池 | ✅ 原生支援                   │  ║
║  └─────────────────────────────────────────────────────────────────────┘  ║
║                                                                            ║
║  ┌─────────────────────────────────────────────────────────────────────┐  ║
║  │  👥 多人模式 - MongoDB 全家桶                                        │  ║
║  │  KV: MongoKVStorage | Vector: MongoVectorStorage | Graph: MongoGraph │  ║
║  │  ✅ 文檔鎖 | ✅ 分片支援 | ⚠️ 需要 Atlas Search 或 $vectorSearch     │  ║
║  └─────────────────────────────────────────────────────────────────────┘  ║
║                                                                            ║
║  ┌─────────────────────────────────────────────────────────────────────┐  ║
║  │  👥 多人模式 - 混合架構 (高效能)                                     │  ║
║  │  KV: Redis | Vector: Milvus/Qdrant | Graph: Neo4j                   │  ║
║  │  ✅ 最佳效能 | ⚠️ 維運複雜                                           │  ║
║  └─────────────────────────────────────────────────────────────────────┘  ║
║                                                                            ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

### 推薦配置

#### 開發/單人模式

```python
# .env (預設，無需更改)
LIGHTRAG_KV_STORAGE=JsonKVStorage
LIGHTRAG_VECTOR_STORAGE=NanoVectorDBStorage
LIGHTRAG_GRAPH_STORAGE=NetworkXStorage
```

#### 多人模式 - PostgreSQL (推薦)

```python
# .env
LIGHTRAG_KV_STORAGE=PGKVStorage
LIGHTRAG_VECTOR_STORAGE=PGVectorStorage
LIGHTRAG_GRAPH_STORAGE=PGGraphStorage

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=lightrag

# 連線池設定 (多人優化)
POSTGRES_MAX_CONNECTIONS=20
POSTGRES_MIN_CONNECTIONS=5
```

#### 高效能模式 - 混合架構

```python
# .env
LIGHTRAG_KV_STORAGE=RedisKVStorage
LIGHTRAG_VECTOR_STORAGE=MilvusVectorDBStorage
LIGHTRAG_GRAPH_STORAGE=Neo4JStorage

REDIS_URI=redis://localhost:6379
MILVUS_URI=http://localhost:19530
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

---

## 🔧 我們需要做的整合

### 1. 自動存儲後端偵測

```python
# config.py 新增
class StorageConfig:
    """根據環境自動選擇存儲後端"""

    @classmethod
    def auto_detect(cls) -> "StorageConfig":
        # 優先檢查 PostgreSQL
        if all(os.getenv(k) for k in ["POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DATABASE"]):
            return cls(
                kv_storage="PGKVStorage",
                vector_storage="PGVectorStorage",
                graph_storage="PGGraphStorage",
                mode="postgres"
            )

        # 檢查 MongoDB
        if os.getenv("MONGO_URI"):
            return cls(
                kv_storage="MongoKVStorage",
                vector_storage="MongoVectorDBStorage",
                graph_storage="MongoGraphStorage",
                mode="mongodb"
            )

        # 檢查 Redis + 其他組合
        if os.getenv("REDIS_URI"):
            return cls(
                kv_storage="RedisKVStorage",
                vector_storage=os.getenv("LIGHTRAG_VECTOR_STORAGE", "NanoVectorDBStorage"),
                graph_storage=os.getenv("LIGHTRAG_GRAPH_STORAGE", "NetworkXStorage"),
                mode="hybrid"
            )

        # 預設: 本地模式
        return cls(
            kv_storage="JsonKVStorage",
            vector_storage="NanoVectorDBStorage",
            graph_storage="NetworkXStorage",
            mode="local"
        )
```

### 2. MCP 配置擴展

```python
# config.py
@dataclass
class MCPServerConfig:
    """MCP Server 專用配置"""

    # 內部 LLM 配置 (用於自動化任務)
    internal_llm: LLMConfig = field(default_factory=lambda: LLMConfig(
        provider="ollama",
        model="qwen2:7b",
        ollama_host="http://localhost:11434"
    ))

    # 是否啟用自動實體補全
    auto_collect_entities: bool = True

    # 多人模式自動偵測
    storage: StorageConfig = field(default_factory=StorageConfig.auto_detect)

    # 連線池配置
    max_connections: int = 20
    connection_timeout: float = 30.0

    # Session 管理
    enable_sessions: bool = True
    session_timeout: int = 3600  # 1 hour
```

### 3. SQLite 增強 (輕量多人)

我們的 `SQLiteHypergraphRepository` 可以作為輕量級多人方案：

```python
# Infrastructure/persistence/sqlite_repository.py 增強
class SQLiteHypergraphRepository:
    def __init__(
        self,
        db_path: str = "./hypergraph.db",
        # 多人優化
        wal_mode: bool = True,          # Write-Ahead Logging
        busy_timeout: int = 30000,       # 30s 等待鎖
        max_connections: int = 10,       # 連線池大小
    ):
        self._pool: Optional[aiosqlite.Pool] = None
        self._wal_mode = wal_mode
        self._busy_timeout = busy_timeout
        self._max_connections = max_connections

    async def initialize(self):
        if self._wal_mode:
            async with self._get_connection() as conn:
                await conn.execute("PRAGMA journal_mode=WAL")
                await conn.execute(f"PRAGMA busy_timeout={self._busy_timeout}")
                # 允許多讀單寫
                await conn.execute("PRAGMA synchronous=NORMAL")
```

---

## 📋 實作優先順序

| 優先級 | 任務 | 複雜度 | 影響 |
|-------|------|--------|------|
| 🔴 P0 | 內部 LLM 配置 (collect_entities 自動化) | 中 | 核心功能 |
| 🔴 P0 | 存儲後端自動偵測 | 低 | 用戶體驗 |
| 🟡 P1 | SQLite WAL 模式 | 低 | 輕量多人 |
| 🟡 P1 | MCP Tool 暴露實體補全 | 中 | 靈活性 |
| 🟢 P2 | PostgreSQL 整合測試 | 中 | 生產就緒 |
| 🟢 P2 | Session 管理 | 高 | 企業功能 |

---

## 總結

1. **LightRAG 完全具備** HGMem 需要的三個向量庫 ✅
2. **MCP 模式保持 collect_absent_entities** 透過內部小 LLM 或暴露 Tool
3. **多人持久化** LightRAG 原生支援 PostgreSQL/MongoDB/Redis+Milvus+Neo4j
4. **我們需要做的** 主要是配置整合，而非重新實現存儲後端
