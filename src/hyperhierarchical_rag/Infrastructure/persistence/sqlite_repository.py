"""
SQLite Unified Repository

一站式 SQLite 持久化儲存實現。
整合了：
1. Knowledge Graph (Nodes, Edges)
2. HGMem Hypergraph (Memory Points)
3. Text Chunks & Metadata (取代 LightRAG 的 JSON 儲存)

Features:
- 完整 ACID 事務支援
- 開啟 WAL (Write-Ahead Logging) 模式，支援併發讀寫
- 統一路徑管理，實現「一站式本地 RAG」
"""

import json
import logging
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from hyperhierarchical_rag.Domain.entities import HyperEdge, HyperNode, NodeLevel
from hyperhierarchical_rag.Domain.repositories import IHypergraphRepository

logger = logging.getLogger(__name__)


class SQLiteUnifiedRepository(IHypergraphRepository):
    """
    Unified SQLite-based implementation for RAG storage.

    適合場景：
    - 單機極速部署
    - 中小規模數據 (1M chunks 以內)
    - 本地快速開發與測試
    """

    def __init__(self, db_path: str = "data/hyperhierarchical.db") -> None:
        """
        Initialize SQLite repository.

        Args:
            db_path: 統一數據庫文件路徑
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # 初始化數據庫與開啟 WAL 模式
        self._init_db()

        logger.info(f"SQLiteUnifiedRepository initialized at {db_path} (WAL mode enabled)")

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """獲取數據庫連接，自動處理事務與開啟 WAL"""
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row

        # 開啟 WAL 模式，支援多人讀寫
        conn.execute("PRAGMA journal_mode=WAL")
        # 同步模式改為 NORMAL (推薦與 WAL 配合使用)
        conn.execute("PRAGMA synchronous=NORMAL")

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """初始化數據庫表結構"""
        with self._get_conn() as conn:
            cursor = conn.cursor()

            # 1. Chunks 表 (取代 LightRAG 的 JSON 存儲)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata TEXT,      -- JSON object
                    source_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. Nodes 表 (KG 節點)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    description TEXT,
                    source_id TEXT,
                    keywords TEXT,      -- JSON array
                    metadata TEXT,      -- JSON object
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 3. Edges 表 (KG 關係 / 超邊)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    node_ids TEXT NOT NULL,  -- JSON array
                    weight REAL DEFAULT 1.0,
                    edge_type TEXT,
                    description TEXT,
                    metadata TEXT,           -- JSON object
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 4. 關鍵字索引表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS keyword_index (
                    keyword TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    PRIMARY KEY (keyword, node_id),
                    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
                )
            """)

            # 5. Node-Edge 關聯表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_edges (
                    node_id TEXT NOT NULL,
                    edge_id TEXT NOT NULL,
                    PRIMARY KEY (node_id, edge_id),
                    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (edge_id) REFERENCES edges(id) ON DELETE CASCADE
                )
            """)

            # 6. Memory Points 表 (HGMem 持久化)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    involved_objects TEXT NOT NULL,  -- JSON array
                    description TEXT NOT NULL,
                    source_query TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 7. Subquery History 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subquery_history (
                    session_id TEXT PRIMARY KEY,
                    subqueries TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 創建必備索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_level ON nodes(level)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_keyword_index_keyword ON keyword_index(keyword)"
            )

    # ==================== Chunk Operations ====================

    async def upsert_chunk(
        self,
        chunk_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        source_id: str | None = None,
    ) -> None:
        """保存文本切片與元數據"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO chunks (id, content, metadata, source_id)
                VALUES (?, ?, ?, ?)
            """,
                (chunk_id, content, json.dumps(metadata or {}), source_id),
            )

    async def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        """獲取指定切片"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row["id"],
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"] or "{}"),
                    "source_id": row["source_id"],
                }
            return None

    # ==================== Node Operations ====================

    async def get_node(self, node_id: str) -> HyperNode | None:
        """獲取節點"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_node(row)
            return None

    async def delete_node(self, node_id: str) -> bool:
        """刪除節點"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM keyword_index WHERE node_id = ?", (node_id,))
            cursor.execute("DELETE FROM node_edges WHERE node_id = ?", (node_id,))
            cursor.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            return bool(cursor.rowcount > 0)

    async def has_node(self, node_id: str) -> bool:
        """檢查節點是否存在"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM nodes WHERE id = ?", (node_id,))
            return cursor.fetchone() is not None

    async def get_nodes(self, node_ids: list[str]) -> list[HyperNode]:
        """批量獲取節點"""
        if not node_ids:
            return []
        with self._get_conn() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(node_ids))
            cursor.execute(f"SELECT * FROM nodes WHERE id IN ({placeholders})", node_ids)  # nosec B608
            return [self._row_to_node(row) for row in cursor.fetchall()]

    async def upsert_node(self, node: HyperNode) -> HyperNode:
        """更新或插入節點"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM keyword_index WHERE node_id = ?", (node.id,))

            keywords = list(node.keywords) if node.keywords else []
            cursor.execute(
                """
                INSERT OR REPLACE INTO nodes
                (id, name, level, description, source_id, keywords, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (
                    node.id,
                    node.name,
                    node.level.value if isinstance(node.level, NodeLevel) else node.level,
                    node.description,
                    node.source_id,
                    json.dumps(keywords),
                    "{}",
                ),
            )

            for kw in keywords:
                cursor.execute(
                    "INSERT OR IGNORE INTO keyword_index (keyword, node_id) VALUES (?, ?)",
                    (kw.lower(), node.id),
                )
        return node

    async def find_by_keywords(
        self, keywords: list[str], level: NodeLevel | None = None
    ) -> list[HyperNode]:
        if not keywords:
            return []
        with self._get_conn() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(keywords))
            params = [kw.lower() for kw in keywords]
            if level:
                cursor.execute(
                    f"SELECT DISTINCT n.* FROM nodes n JOIN keyword_index ki ON n.id = ki.node_id WHERE ki.keyword IN ({placeholders}) AND n.level = ?",  # nosec B608
                    params + [level.value],
                )
            else:
                cursor.execute(
                    f"SELECT DISTINCT n.* FROM nodes n JOIN keyword_index ki ON n.id = ki.node_id WHERE ki.keyword IN ({placeholders})",  # nosec B608
                    params,
                )
            return [self._row_to_node(row) for row in cursor.fetchall()]

    # ==================== Edge Operations ====================

    async def get_edge(self, edge_id: str) -> HyperEdge | None:
        """獲取邊"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM edges WHERE id = ?", (edge_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_edge(row)
            return None

    async def delete_edge(self, edge_id: str) -> bool:
        """刪除邊"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM node_edges WHERE edge_id = ?", (edge_id,))
            cursor.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
            return bool(cursor.rowcount > 0)

    async def get_hyperedge(self, node_ids: list[str]) -> HyperEdge | None:
        """按節點組合獲取超邊"""
        if not node_ids:
            return None
        # 這裡需要匹配所有節點都被包含的邊，且節點列表一致（不考慮順序）
        # 為簡單起見，在內存中過濾
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 我們需要檢查 node_ids 包含所有指定的 node_id
            # 這裡的實現較為簡單：尋找包含第一個節點的所有邊，然後在內存中驗證
            cursor.execute(
                """
                SELECT e.* FROM edges e
                JOIN node_edges ne ON e.id = ne.edge_id
                WHERE ne.node_id = ?
            """,
                (node_ids[0],),
            )

            target_set = set(node_ids)
            for row in cursor.fetchall():
                edge = self._row_to_edge(row)
                if edge.node_ids == target_set:
                    return edge
        return None

    async def upsert_edge(self, edge: HyperEdge) -> HyperEdge:
        """更新或插入關係（超邊）"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM node_edges WHERE edge_id = ?", (edge.id,))

            node_ids = list(edge.node_ids) if edge.node_ids else []
            cursor.execute(
                """
                INSERT OR REPLACE INTO edges
                (id, node_ids, weight, edge_type, description, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (edge.id, json.dumps(node_ids), edge.weight, edge.relation, edge.context, "{}"),
            )

            for node_id in node_ids:
                cursor.execute(
                    "INSERT OR IGNORE INTO node_edges (node_id, edge_id) VALUES (?, ?)",
                    (node_id, edge.id),
                )
        return edge

    async def get_edges_for_node(self, node_id: str) -> list[HyperEdge]:
        """獲取與節點相關的所有邊"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT e.* FROM edges e
                JOIN node_edges ne ON e.id = ne.edge_id
                WHERE ne.node_id = ?
            """,
                (node_id,),
            )
            return [self._row_to_edge(row) for row in cursor.fetchall()]

    # ==================== HGMem Multi-hop Expansion ====================

    async def find_connected_nodes(self, node_id: str, max_hops: int = 2) -> list[HyperNode]:
        """BFS 走訪發現超圖連接節點"""
        visited: set[str] = {node_id}
        frontier: set[str] = {node_id}

        for _ in range(max_hops):
            if not frontier:
                break
            next_frontier: set[str] = set()
            with self._get_conn() as conn:
                cursor = conn.cursor()
                for current_id in frontier:
                    cursor.execute(
                        """
                        SELECT DISTINCT ne2.node_id FROM node_edges ne1
                        JOIN node_edges ne2 ON ne1.edge_id = ne2.edge_id
                        WHERE ne1.node_id = ? AND ne2.node_id != ?
                    """,
                        (current_id, current_id),
                    )
                    for row in cursor.fetchall():
                        cid = row[0]
                        if cid not in visited:
                            visited.add(cid)
                            next_frontier.add(cid)
            frontier = next_frontier

        visited.discard(node_id)
        return await self.get_nodes(list(visited))

    # ==================== Helper Methods ====================

    def _row_to_node(self, row: sqlite3.Row) -> HyperNode:
        return HyperNode(
            id=row["id"],
            name=row["name"],
            level=NodeLevel(row["level"])
            if row["level"] in [e.value for e in NodeLevel]
            else NodeLevel.LOCAL,
            description=row["description"] or "",
            source_id=row["source_id"] or "",
            keywords=json.loads(row["keywords"] or "[]"),
        )

    def _row_to_edge(self, row: sqlite3.Row) -> HyperEdge:
        return HyperEdge(
            id=row["id"],
            node_ids=set(json.loads(row["node_ids"])),
            weight=row["weight"] or 1.0,
            relation=row["edge_type"] or "",
            context=row["description"] or "",
        )

    # ==================== HGMem Memory Point Methods ====================

    async def save_memory_point(
        self, involved_objects: list[str], description: str, source_query: str | None = None
    ) -> int:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memory_points (involved_objects, description, source_query) VALUES (?, ?, ?)",
                (json.dumps(involved_objects), description, source_query),
            )
            return cursor.lastrowid or 0

    async def delete_memory_point(self, memory_id: int) -> bool:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_points WHERE id = ?", (memory_id,))
            return bool(cursor.rowcount > 0)

    async def load_all_memory_points(self) -> list[dict[str, Any]]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memory_points ORDER BY created_at ASC")
            return [
                {
                    "id": r["id"],
                    "involved_objects": json.loads(r["involved_objects"]),
                    "description": r["description"],
                    "source_query": r["source_query"],
                    "created_at": r["created_at"],
                }
                for r in cursor.fetchall()
            ]

    async def clear_memory_points(self) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM memory_points")

    # ==================== Subquery History Methods ====================

    async def save_subquery_history(self, session_id: str, subqueries: list[str]) -> None:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO subquery_history (session_id, subqueries)
                VALUES (?, ?)
            """,
                (session_id, json.dumps(subqueries)),
            )

    async def load_subquery_history(self, session_id: str) -> list[str]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT subqueries FROM subquery_history WHERE session_id = ?", (session_id,)
            )
            row = cursor.fetchone()
            if row:
                result = json.loads(row["subqueries"])
                if isinstance(result, list):
                    return [str(q) for q in result]
            return []

    # ==================== System Methods ====================

    async def clear_all(self) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM keyword_index")
            conn.execute("DELETE FROM node_edges")
            conn.execute("DELETE FROM edges")
            conn.execute("DELETE FROM nodes")
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM memory_points")
            conn.execute("DELETE FROM subquery_history")

    async def get_stats(self) -> dict[str, Any]:
        with self._get_conn() as conn:
            cursor = conn.cursor()
            res = {}
            res["nodes"] = cursor.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
            res["edges"] = cursor.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
            res["chunks"] = cursor.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            res["memory_points"] = cursor.execute("SELECT COUNT(*) FROM memory_points").fetchone()[
                0
            ]
            return res
