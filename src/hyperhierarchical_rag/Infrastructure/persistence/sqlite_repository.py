"""
SQLite Hypergraph Repository

基於 SQLite 的持久化超圖存儲實現。
適合中小規模數據，無需額外數據庫服務。

Features:
- 完整 ACID 事務支援
- SQL 查詢優化
- JSON 欄位存儲複雜數據
- 自動建立索引
"""

import json
import logging
import sqlite3
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from contextlib import contextmanager

from hyperhierarchical_rag.Domain.entities import HyperNode, HyperEdge, NodeLevel
from hyperhierarchical_rag.Domain.repositories import IHypergraphRepository

logger = logging.getLogger(__name__)


class SQLiteHypergraphRepository(IHypergraphRepository):
    """
    SQLite-based implementation of IHypergraphRepository.
    
    適合場景：
    - 單機部署
    - 數據量 < 100K nodes
    - 需要持久化但不需要分布式
    """
    
    def __init__(self, db_path: str = "hypergraph.db") -> None:
        """
        Initialize SQLite repository.
        
        Args:
            db_path: SQLite 數據庫文件路徑
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 創建表
        self._init_db()
        
        logger.info(f"SQLiteHypergraphRepository initialized at {db_path}")
    
    @contextmanager
    def _get_conn(self):
        """獲取數據庫連接"""
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
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
            
            # Nodes 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL,
                    description TEXT,
                    source_id TEXT,
                    keywords TEXT,  -- JSON array
                    metadata TEXT,  -- JSON object
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Edges 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS edges (
                    id TEXT PRIMARY KEY,
                    node_ids TEXT NOT NULL,  -- JSON array
                    weight REAL DEFAULT 1.0,
                    edge_type TEXT,
                    description TEXT,
                    metadata TEXT,  -- JSON object
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 關鍵字索引表 (用於快速查找)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS keyword_index (
                    keyword TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    PRIMARY KEY (keyword, node_id),
                    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
                )
            """)
            
            # Node-Edge 關聯表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS node_edges (
                    node_id TEXT NOT NULL,
                    edge_id TEXT NOT NULL,
                    PRIMARY KEY (node_id, edge_id),
                    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (edge_id) REFERENCES edges(id) ON DELETE CASCADE
                )
            """)
            
            # 創建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_level ON nodes(level)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_keyword_index_keyword ON keyword_index(keyword)")
            
            # Memory Points 表 (HGMem 持久化)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    involved_objects TEXT NOT NULL,  -- JSON array of object names
                    description TEXT NOT NULL,
                    source_query TEXT,  -- The query that created this memory point
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Subquery History 表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subquery_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,  -- Optional session grouping
                    subqueries TEXT NOT NULL,  -- JSON array
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    
    # ==================== Node Operations ====================
    
    async def get_node(self, node_id: str) -> Optional[HyperNode]:
        """Get a node by ID."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_node(row)
            return None
    
    async def get_nodes(self, node_ids: List[str]) -> List[HyperNode]:
        """Get multiple nodes by IDs."""
        if not node_ids:
            return []
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            placeholders = ",".join("?" * len(node_ids))
            cursor.execute(f"SELECT * FROM nodes WHERE id IN ({placeholders})", node_ids)
            
            return [self._row_to_node(row) for row in cursor.fetchall()]
    
    async def upsert_node(self, node: HyperNode) -> HyperNode:
        """Insert or update a node."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 刪除舊的關鍵字索引
            cursor.execute("DELETE FROM keyword_index WHERE node_id = ?", (node.id,))
            
            # Upsert node - 適應 HyperNode 的實際結構
            keywords = list(node.keywords) if node.keywords else []
            
            cursor.execute("""
                INSERT OR REPLACE INTO nodes 
                (id, name, level, description, source_id, keywords, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                node.id,
                node.name,
                node.level.value if isinstance(node.level, NodeLevel) else node.level,
                node.description,
                node.source_id,
                json.dumps(keywords),
                "{}"  # HyperNode 沒有 metadata 欄位
            ))
            
            # 插入關鍵字索引
            for kw in keywords:
                cursor.execute(
                    "INSERT OR IGNORE INTO keyword_index (keyword, node_id) VALUES (?, ?)",
                    (kw.lower(), node.id)
                )
        
        return node
    
    async def delete_node(self, node_id: str) -> bool:
        """Delete a node and its associated edges."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 獲取關聯的邊
            cursor.execute("SELECT edge_id FROM node_edges WHERE node_id = ?", (node_id,))
            edge_ids = [row[0] for row in cursor.fetchall()]
            
            # 刪除邊
            for edge_id in edge_ids:
                cursor.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
                cursor.execute("DELETE FROM node_edges WHERE edge_id = ?", (edge_id,))
            
            # 刪除節點
            cursor.execute("DELETE FROM keyword_index WHERE node_id = ?", (node_id,))
            cursor.execute("DELETE FROM node_edges WHERE node_id = ?", (node_id,))
            cursor.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            
            return cursor.rowcount > 0
    
    async def has_node(self, node_id: str) -> bool:
        """Check if a node exists."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM nodes WHERE id = ?", (node_id,))
            return cursor.fetchone() is not None
    
    # ==================== Edge Operations ====================
    
    async def get_edge(self, edge_id: str) -> Optional[HyperEdge]:
        """Get an edge by ID."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM edges WHERE id = ?", (edge_id,))
            row = cursor.fetchone()
            
            if row:
                return self._row_to_edge(row)
            return None
    
    async def get_edges_for_node(self, node_id: str) -> List[HyperEdge]:
        """Get all edges connected to a node."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT e.* FROM edges e
                JOIN node_edges ne ON e.id = ne.edge_id
                WHERE ne.node_id = ?
            """, (node_id,))
            
            return [self._row_to_edge(row) for row in cursor.fetchall()]
    
    async def upsert_edge(self, edge: HyperEdge) -> HyperEdge:
        """Insert or update an edge."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 刪除舊的 node-edge 關聯
            cursor.execute("DELETE FROM node_edges WHERE edge_id = ?", (edge.id,))
            
            # Upsert edge - 適應 HyperEdge 的實際結構
            node_ids = list(edge.node_ids) if edge.node_ids else []
            
            cursor.execute("""
                INSERT OR REPLACE INTO edges 
                (id, node_ids, weight, edge_type, description, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                edge.id,
                json.dumps(node_ids),
                edge.weight,
                edge.relation,  # HyperEdge 使用 relation 而非 edge_type
                edge.context,   # HyperEdge 使用 context 而非 description
                "{}"  # HyperEdge 沒有 metadata 欄位
            ))
            
            # 插入 node-edge 關聯
            for node_id in node_ids:
                cursor.execute(
                    "INSERT OR IGNORE INTO node_edges (node_id, edge_id) VALUES (?, ?)",
                    (node_id, edge.id)
                )
        
        return edge
    
    async def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM node_edges WHERE edge_id = ?", (edge_id,))
            cursor.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
            return cursor.rowcount > 0
    
    # ==================== Query Operations ====================
    
    async def find_by_keywords(
        self,
        keywords: List[str],
        level: Optional[NodeLevel] = None,
    ) -> List[HyperNode]:
        """Find nodes by keywords."""
        if not keywords:
            return []
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 構建查詢
            placeholders = ",".join("?" * len(keywords))
            params = [kw.lower() for kw in keywords]
            
            if level:
                cursor.execute(f"""
                    SELECT DISTINCT n.* FROM nodes n
                    JOIN keyword_index ki ON n.id = ki.node_id
                    WHERE ki.keyword IN ({placeholders}) AND n.level = ?
                """, params + [level.value if isinstance(level, NodeLevel) else level])
            else:
                cursor.execute(f"""
                    SELECT DISTINCT n.* FROM nodes n
                    JOIN keyword_index ki ON n.id = ki.node_id
                    WHERE ki.keyword IN ({placeholders})
                """, params)
            
            return [self._row_to_node(row) for row in cursor.fetchall()]
    
    async def find_connected_nodes(
        self,
        node_id: str,
        max_hops: int = 2,
    ) -> List[HyperNode]:
        """Find nodes connected via hyperedges (BFS traversal)."""
        visited: Set[str] = {node_id}
        frontier: Set[str] = {node_id}
        
        for _ in range(max_hops):
            if not frontier:
                break
            
            next_frontier: Set[str] = set()
            
            with self._get_conn() as conn:
                cursor = conn.cursor()
                
                for current_id in frontier:
                    # 獲取該節點所有邊的其他節點
                    cursor.execute("""
                        SELECT DISTINCT ne2.node_id FROM node_edges ne1
                        JOIN node_edges ne2 ON ne1.edge_id = ne2.edge_id
                        WHERE ne1.node_id = ? AND ne2.node_id != ?
                    """, (current_id, current_id))
                    
                    for row in cursor.fetchall():
                        connected_id = row[0]
                        if connected_id not in visited:
                            visited.add(connected_id)
                            next_frontier.add(connected_id)
            
            frontier = next_frontier
        
        visited.discard(node_id)
        return await self.get_nodes(list(visited))
    
    async def get_hyperedge(self, node_ids: List[str]) -> Optional[HyperEdge]:
        """Get a hyperedge by its member nodes."""
        node_ids_set = set(node_ids)
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM edges")
            
            for row in cursor.fetchall():
                edge_node_ids = set(json.loads(row["node_ids"]))
                if edge_node_ids == node_ids_set:
                    return self._row_to_edge(row)
        
        return None
    
    # ==================== Statistics ====================
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM nodes")
            total_nodes = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM nodes WHERE level = 'local'")
            local_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM nodes WHERE level = 'global'")
            global_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM edges")
            total_edges = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT keyword) FROM keyword_index")
            keywords_count = cursor.fetchone()[0]
            
            return {
                "nodes": {
                    "total": total_nodes,
                    "local": local_count,
                    "global": global_count,
                },
                "edges": {
                    "total": total_edges,
                },
                "keywords_indexed": keywords_count,
            }
    
    # ==================== Helper Methods ====================
    
    def _row_to_node(self, row: sqlite3.Row) -> HyperNode:
        """Convert database row to HyperNode."""
        return HyperNode(
            id=row["id"],
            name=row["name"],
            level=NodeLevel(row["level"]) if row["level"] in [e.value for e in NodeLevel] else NodeLevel.LOCAL,
            description=row["description"] or "",
            source_id=row["source_id"] or "",
            keywords=json.loads(row["keywords"] or "[]"),  # List, not Set
        )
    
    def _row_to_edge(self, row: sqlite3.Row) -> HyperEdge:
        """Convert database row to HyperEdge."""
        return HyperEdge(
            id=row["id"],
            node_ids=set(json.loads(row["node_ids"])),  # Convert to set
            weight=row["weight"] or 1.0,
            relation=row["edge_type"] or "",  # edge_type -> relation
            context=row["description"] or "",  # description -> context
        )
    
    # ==================== Cleanup ====================
    
    async def vacuum(self) -> None:
        """Optimize database storage."""
        with self._get_conn() as conn:
            conn.execute("VACUUM")
        logger.info("Database vacuumed")
    
    async def clear_all(self) -> None:
        """Clear all data (for testing)."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM keyword_index")
            cursor.execute("DELETE FROM node_edges")
            cursor.execute("DELETE FROM edges")
            cursor.execute("DELETE FROM nodes")
            cursor.execute("DELETE FROM memory_points")
            cursor.execute("DELETE FROM subquery_history")
        logger.info("All data cleared")

    # ==================== Memory Points Operations ====================
    
    async def save_memory_point(
        self, 
        involved_objects: List[str], 
        description: str,
        source_query: Optional[str] = None
    ) -> int:
        """
        Save a memory point to persistent storage.
        
        Returns:
            The ID of the saved memory point
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO memory_points (involved_objects, description, source_query)
                VALUES (?, ?, ?)
            """, (json.dumps(involved_objects), description, source_query))
            return cursor.lastrowid or 0
    
    async def load_all_memory_points(self) -> List[Dict[str, Any]]:
        """
        Load all memory points from storage.
        
        Returns:
            List of memory point dictionaries with keys:
            - id, involved_objects, description, source_query, created_at
        """
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, involved_objects, description, source_query, created_at 
                FROM memory_points 
                ORDER BY created_at ASC
            """)
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "involved_objects": json.loads(row["involved_objects"]),
                    "description": row["description"],
                    "source_query": row["source_query"],
                    "created_at": row["created_at"],
                })
            return results
    
    async def delete_memory_point(self, point_id: int) -> bool:
        """Delete a memory point by ID."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_points WHERE id = ?", (point_id,))
            return bool(cursor.rowcount > 0)
    
    async def clear_memory_points(self) -> int:
        """Clear all memory points. Returns count deleted."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_points")
            return int(cursor.rowcount)
    
    async def get_memory_points_count(self) -> int:
        """Get total count of memory points."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memory_points")
            return int(cursor.fetchone()[0])
    
    # ==================== Subquery History Operations ====================
    
    async def save_subquery_history(
        self, 
        subqueries: List[str],
        session_id: Optional[str] = None
    ) -> int:
        """Save subquery history."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO subquery_history (session_id, subqueries)
                VALUES (?, ?)
            """, (session_id, json.dumps(subqueries)))
            return cursor.lastrowid or 0
    
    async def load_subquery_history(
        self, 
        session_id: Optional[str] = None,
        limit: int = 100
    ) -> List[List[str]]:
        """Load subquery history."""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            if session_id:
                cursor.execute("""
                    SELECT subqueries FROM subquery_history 
                    WHERE session_id = ?
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (session_id, limit))
            else:
                cursor.execute("""
                    SELECT subqueries FROM subquery_history 
                    ORDER BY created_at ASC
                    LIMIT ?
                """, (limit,))
            
            return [json.loads(row["subqueries"]) for row in cursor.fetchall()]
