"""
MemoryEvolver - LLM-driven hypergraph memory evolution service.

Core HGMem logic: Uses LLM to analyze retrieved context and evolve the hypergraph.

This is the KEY INTEGRATION POINT between LightRAG (retrieval) and HGMem (memory).

ENHANCED VERSION: Now includes:
- evolve(): 原始記憶演化 (from HGMem)
- reorganize_memory(): 記憶重組/合併 (from HGMem)  
- get_extended_info(): 通過鄰居節點擴展上下文 (from HGMem)

References:
- HGMem: external/HGMem/myrag/memory.py (Memory class)
- HGMem: external/HGMem/myrag/prompt.py (PROMPTS)
"""

import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from hyperhierarchical_rag.Domain.entities import HyperNode, HyperEdge, NodeLevel

logger = logging.getLogger(__name__)


# ==================== Prompts (Adapted from HGMem) ====================

EVOLVE_MEMORY_SYSTEM_PROMPT = """You are a memory evolution system. Your task is to analyze retrieved information and extract key memory points.

A memory point captures important relationships between multiple entities (objects). Each memory point should:
1. Identify 2-4 involved objects (entities) that are meaningfully related
2. Provide a concise description of their relationship

Output Format:
[Inserted Memory Points]:
(point{tuple_delimiter}<OBJECT1>{object_delimiter}<OBJECT2>{object_delimiter}...{tuple_delimiter}<DESCRIPTION>){record_delimiter}
...

[Updated Memory Points]:
(point_index, point{tuple_delimiter}<OBJECT1>{object_delimiter}<OBJECT2>{tuple_delimiter}<UPDATED_DESCRIPTION>){record_delimiter}
...

{completion_delimiter}
"""

EVOLVE_MEMORY_USER_PROMPT = """Given the following information, extract or update memory points.

**Main Query**: {main_query}

**Current Subqueries**:
{cur_subqueries}

**Existing Memory Points**:
{memory}

**Retrieved Information**:
{retrieved_info}

Analyze the retrieved information and:
1. Create NEW memory points for important relationships not yet captured
2. UPDATE existing memory points if new evidence strengthens or modifies them

Remember: Each memory point should connect 2-4 objects with a meaningful description.
"""


@dataclass
class MemoryPoint:
    """A memory point connecting multiple entities."""
    involved_objects: List[str]
    description: str
    

@dataclass
class EvolveResult:
    """Result of memory evolution."""
    inserted_points: List[MemoryPoint]
    updated_points: List[Tuple[int, MemoryPoint]]  # (index, updated_point)


class MemoryEvolver:
    """
    LLM-driven memory evolution service.
    
    This service:
    1. Takes retrieved context (from LightRAG)
    2. Uses LLM to analyze and extract memory points
    3. Converts memory points to HyperEdges
    4. Updates the hypergraph
    
    Integration with LightRAG:
    - Uses the same LLM service (OpenAI, etc.)
    - Takes LightRAG's retrieval results as input
    - Outputs expanded context via hypergraph traversal
    """
    
    def __init__(
        self,
        llm_func: Optional[Callable] = None,
        object_delimiter: str = ", ",
        tuple_delimiter: str = " | ",
        record_delimiter: str = "\n",
        completion_delimiter: str = "##END##",
    ) -> None:
        """
        Initialize MemoryEvolver.
        
        Args:
            llm_func: Async function to call LLM (signature: async (prompt, system_prompt) -> str)
            object_delimiter: Delimiter between objects in a memory point
            tuple_delimiter: Delimiter between fields in a record
            record_delimiter: Delimiter between records
            completion_delimiter: Marker for end of output
        """
        self.llm_func = llm_func
        self.format_dict = {
            "object_delimiter": object_delimiter,
            "tuple_delimiter": tuple_delimiter,
            "record_delimiter": record_delimiter,
            "completion_delimiter": completion_delimiter,
        }
        logger.info("MemoryEvolver initialized")
    
    def set_llm_func(self, llm_func: Callable) -> None:
        """Set the LLM function (allows lazy initialization)."""
        self.llm_func = llm_func
    
    async def evolve(
        self,
        retrieved_info: str,
        main_query: str,
        subqueries: List[str],
        existing_memory_points: List[MemoryPoint],
    ) -> EvolveResult:
        """
        Evolve memory based on retrieved information.
        
        This is the core HGMem algorithm adapted for our architecture.
        
        Args:
            retrieved_info: Context retrieved from LightRAG
            main_query: User's main query
            subqueries: Related subqueries
            existing_memory_points: Current memory points
        
        Returns:
            EvolveResult with inserted and updated memory points
        """
        if self.llm_func is None:
            logger.warning("LLM function not set, using mock evolve")
            return self._mock_evolve(retrieved_info, main_query)
        
        # Build prompts
        system_prompt = EVOLVE_MEMORY_SYSTEM_PROMPT.format(**self.format_dict)
        
        memory_context = self._format_memory_points(existing_memory_points)
        subqueries_str = "\n".join([f"- {sq}" for sq in subqueries if sq != main_query])
        
        user_prompt = EVOLVE_MEMORY_USER_PROMPT.format(
            main_query=main_query,
            cur_subqueries=subqueries_str or "None",
            memory=memory_context or "No existing memory points",
            retrieved_info=retrieved_info[:4000],  # Truncate to avoid token limits
        )
        
        # Call LLM
        try:
            response = await self.llm_func(user_prompt, system_prompt=system_prompt)
            return self._parse_evolve_response(response)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return EvolveResult(inserted_points=[], updated_points=[])
    
    def _format_memory_points(self, points: List[MemoryPoint]) -> str:
        """Format existing memory points for prompt."""
        if not points:
            return ""
        
        lines = []
        for idx, point in enumerate(points):
            objects_str = self.format_dict["object_delimiter"].join(point.involved_objects)
            lines.append(f"- Point ({idx})\n  Objects: {objects_str}\n  Description: {point.description}")
        return "\n".join(lines)
    
    def _parse_evolve_response(self, response: str) -> EvolveResult:
        """
        Parse LLM response to extract memory points.
        
        Adapted from HGMem's postprocess_evolve_memory().
        """
        inserted_points: List[MemoryPoint] = []
        updated_points: List[Tuple[int, MemoryPoint]] = []
        
        object_delimiter = self.format_dict["object_delimiter"]
        tuple_delimiter = self.format_dict["tuple_delimiter"]
        record_delimiter = self.format_dict["record_delimiter"]
        completion_delimiter = self.format_dict["completion_delimiter"]
        
        response = response.strip()
        
        # Find section markers
        loc_updated = response.find("[Updated Memory Points]:")
        if loc_updated == -1:
            loc_updated = len(response)
        
        # Parse inserted points
        inserted_str = response[:loc_updated].replace("[Inserted Memory Points]:", "").strip()
        inserted_points = self._parse_memory_points_section(
            inserted_str, object_delimiter, tuple_delimiter, record_delimiter
        )
        
        # Parse updated points
        updated_str = response[loc_updated:].replace("[Updated Memory Points]:", "").strip()
        updated_points = self._parse_updated_points_section(
            updated_str, object_delimiter, tuple_delimiter, record_delimiter
        )
        
        logger.info(f"Evolved: {len(inserted_points)} inserted, {len(updated_points)} updated")
        return EvolveResult(inserted_points=inserted_points, updated_points=updated_points)
    
    def _parse_memory_points_section(
        self,
        section: str,
        object_delimiter: str,
        tuple_delimiter: str,
        record_delimiter: str,
    ) -> List[MemoryPoint]:
        """Parse a section containing memory points."""
        points = []
        
        # Find all (point...) patterns
        pattern = r'\(point\s*\|([^)]+)\)'
        matches = re.findall(pattern, section, re.IGNORECASE)
        
        for match in matches:
            parts = match.split(tuple_delimiter)
            if len(parts) >= 2:
                # First part contains objects, last part is description
                objects_str = parts[0].strip()
                description = parts[-1].strip()
                
                objects = [obj.strip().upper() for obj in objects_str.split(object_delimiter) if obj.strip()]
                
                if objects and description:
                    points.append(MemoryPoint(involved_objects=objects, description=description))
        
        return points
    
    def _parse_updated_points_section(
        self,
        section: str,
        object_delimiter: str,
        tuple_delimiter: str,
        record_delimiter: str,
    ) -> List[Tuple[int, MemoryPoint]]:
        """Parse a section containing updated memory points."""
        updated = []
        
        # Find patterns like (0, point | ...)
        pattern = r'\((\d+)\s*,\s*point\s*\|([^)]+)\)'
        matches = re.findall(pattern, section, re.IGNORECASE)
        
        for idx_str, content in matches:
            try:
                idx = int(idx_str)
                parts = content.split(tuple_delimiter)
                if len(parts) >= 2:
                    objects_str = parts[0].strip()
                    description = parts[-1].strip()
                    
                    objects = [obj.strip().upper() for obj in objects_str.split(object_delimiter) if obj.strip()]
                    
                    if objects and description:
                        updated.append((idx, MemoryPoint(involved_objects=objects, description=description)))
            except ValueError:
                continue
        
        return updated
    
    def _mock_evolve(self, retrieved_info: str, main_query: str) -> EvolveResult:
        """
        Mock evolution when LLM is not available.
        Extracts simple patterns from the retrieved info.
        """
        # Simple heuristic: extract capitalized words as entities
        words = re.findall(r'\b[A-Z][a-z]+\b', retrieved_info)
        unique_words = list(set(words))[:4]  # Max 4 entities
        
        if len(unique_words) >= 2:
            point = MemoryPoint(
                involved_objects=unique_words,
                description=f"Entities related to query: {main_query[:50]}",
            )
            return EvolveResult(inserted_points=[point], updated_points=[])
        
        return EvolveResult(inserted_points=[], updated_points=[])
    
    # ==================== Convert to HyperEdge ====================
    
    def memory_point_to_hyperedge(
        self,
        point: MemoryPoint,
        node_id_map: Dict[str, str],
        source_id: Optional[str] = None,
    ) -> HyperEdge:
        """
        Convert a MemoryPoint to a HyperEdge.
        
        Args:
            point: The memory point
            node_id_map: Mapping from entity name to node ID
            source_id: Optional source document ID
        
        Returns:
            HyperEdge connecting the involved entities
        """
        node_ids = set()
        for obj in point.involved_objects:
            if obj in node_id_map:
                node_ids.add(node_id_map[obj])
            else:
                # Create a new node ID if not exists
                node_ids.add(HyperNode._generate_id(obj))
        
        return HyperEdge(
            node_ids=node_ids,
            relation="memory_point",
            context=point.description,
            weight=1.0,
            source_id=source_id,
        )


# ==================== NEW: Prompts from HGMem ====================

REORGANIZE_MEMORY_PROMPT = """For resolving the [Main Query], you have consolidated some memory points in your [Memory] recording the relevant information you have known.
Based on current [Memory], your task is to conduct memory reorganization that merges multiple memory points into new ones when they are more suitable to constitute a semantically/logically cohesive unit as a whole. 

Specifically, you need to specify the indices of original memory points to merge.
Then, for each newly merged point, provide updated descriptions that could build essentially higher-order associations while preserving their original information necessary for dealing with the [Main Query].

Format each reorganized memory point as <indices>{tuple_delimiter}<new_description>
Output in [Points_to_Merge] using the **Example of Anticipated Output Format**.

######################-Example of Anticipated Output Format-######################
[Points_to_Merge]:
(1,2{tuple_delimiter}<new_description>){record_delimiter}
(2,4,5{tuple_delimiter}<new_description>){record_delimiter}
{completion_delimiter}

######################-Real Data-######################
[Main Query]: {main_query}
[Memory]:
{memory}

######################
Note that, after reorganization,
(1) Each new memory point should encapsulate a semantically/logically cohesive unit.
(2) Each memory point aims to cover distinct aspects, minimizing overlap.
(3) Memory redundancy is reduced by eliminating duplicate content.
(4) If an original point itself is more suitable to be kept separate, leave it unchanged.
(5) Avoid forcibly merging. If there is no suitable points to merge, output <None>.

Output:
"""

SELECT_ENTITIES_PROMPT = """You will be provided with a [Query], [Entity Candidates] and your current [Memory].

Your task is to select entities relevant and potentially useful to deal with the [Query].

Output comma-separated indices of your selected entities in ascending order in [Selected]. 
If no candidate is useful, just output <None>

######################-Example Output-######################
[Selected]: 1,2,5

######################-Real Data-######################
[Query]: {query}

[Memory]:
{memory}

[Entity Candidates]:
{entities_str}
######################
Note: Only output the indices of selected entities without explanation.
Output:
"""


@dataclass
class ReorganizeResult:
    """Result of memory reorganization."""
    merged_groups: List[Tuple[List[int], str]]  # [(indices_to_merge, new_description), ...]


@dataclass 
class ExtendedInfoResult:
    """Result of extended info retrieval."""
    extended_entities: List[Dict[str, Any]]
    extension_context: str


class EnhancedMemoryEvolver(MemoryEvolver):
    """
    Enhanced MemoryEvolver with full HGMem capabilities.
    
    Additional methods from HGMem:
    - reorganize_memory(): Merge similar memory points
    - get_extended_info(): Expand context via neighbor nodes
    - select_entities(): LLM-driven entity selection
    
    This class maintains DDD architecture while providing HGMem's full functionality.
    """
    
    def __init__(
        self,
        llm_func: Optional[Callable] = None,
        knowledge_graph_adapter: Optional[Any] = None,  # LightRAG adapter
        persistence_repo: Optional[Any] = None,  # SQLiteHypergraphRepository
        **kwargs
    ) -> None:
        """
        Initialize EnhancedMemoryEvolver.
        
        Args:
            llm_func: Async LLM function
            knowledge_graph_adapter: Optional adapter to LightRAG's KG
            persistence_repo: Optional repository for memory persistence
        """
        super().__init__(llm_func=llm_func, **kwargs)
        self.kg_adapter = knowledge_graph_adapter
        self._persistence_repo = persistence_repo
        self._history_subqueries: List[List[str]] = []
        self._memory_points: List[MemoryPoint] = []
        logger.info("EnhancedMemoryEvolver initialized with full HGMem capabilities")
    
    def set_persistence_repo(self, repo: Any) -> None:
        """Set the persistence repository."""
        self._persistence_repo = repo
    
    async def load_from_persistence(self) -> int:
        """
        Load memory points from persistent storage.
        
        Returns:
            Number of memory points loaded
        """
        if not self._persistence_repo:
            return 0
        
        try:
            points_data = await self._persistence_repo.load_all_memory_points()
            self._memory_points = []
            
            for data in points_data:
                point = MemoryPoint(
                    involved_objects=list(data["involved_objects"]),
                    description=data["description"],
                )
                self._memory_points.append(point)
            
            # Also load subquery history
            history = await self._persistence_repo.load_subquery_history()
            self._history_subqueries = history
            
            logger.info(f"Loaded {len(self._memory_points)} memory points from persistence")
            return len(self._memory_points)
        except Exception as e:
            logger.warning(f"Failed to load memory from persistence: {e}")
            return 0
    
    async def save_to_persistence(self, point: MemoryPoint, source_query: Optional[str] = None) -> bool:
        """Save a single memory point to persistent storage."""
        if not self._persistence_repo:
            return False
        
        try:
            await self._persistence_repo.save_memory_point(
                involved_objects=list(point.involved_objects),
                description=point.description,
                source_query=source_query,
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to save memory point: {e}")
            return False
    
    def set_kg_adapter(self, adapter: Any) -> None:
        """Set the knowledge graph adapter for extended operations."""
        self.kg_adapter = adapter
    
    @property
    def memory_points(self) -> List[MemoryPoint]:
        """Get current memory points."""
        return self._memory_points
    
    def add_memory_point(self, point: MemoryPoint) -> None:
        """Add a memory point."""
        self._memory_points.append(point)
    
    def clear_memory(self) -> None:
        """Clear all memory points and history (from HGMem)."""
        self._memory_points = []
        self._history_subqueries = []
        logger.info("Memory cleared")
    
    async def evolve_and_track(
        self,
        retrieved_info: str,
        main_query: str,
        subqueries: List[str],
        persist: bool = True,  # Auto-persist by default
    ) -> EvolveResult:
        """
        Evolve memory and track history (enhanced version).
        
        Unlike base evolve(), this:
        1. Tracks subquery history
        2. Updates internal memory points list
        3. Optionally persists to storage
        4. Optionally syncs with external KG
        """
        # Track history
        self._history_subqueries.append(subqueries)
        
        # Call base evolve
        result = await self.evolve(
            retrieved_info=retrieved_info,
            main_query=main_query,
            subqueries=subqueries,
            existing_memory_points=self._memory_points,
        )
        
        # Update internal state and persist
        for point in result.inserted_points:
            self._memory_points.append(point)
            # Persist each new memory point
            if persist and self._persistence_repo:
                await self.save_to_persistence(point, source_query=main_query)
        
        for idx, updated_point in result.updated_points:
            if 0 <= idx < len(self._memory_points):
                self._memory_points[idx] = updated_point
        
        # Save subquery history
        if persist and self._persistence_repo:
            await self._persistence_repo.save_subquery_history(subqueries)
        
        # Optionally sync with external KG
        if self.kg_adapter is not None:
            await self._sync_with_kg(result)
        
        return result
    
    async def _sync_with_kg(self, result: EvolveResult) -> None:
        """Sync memory points with external Knowledge Graph."""
        # This is where we'd integrate with LightRAG's KG
        # For now, just log
        logger.debug(f"Would sync {len(result.inserted_points)} new points to KG")
    
    async def reorganize_memory(self, main_query: str) -> ReorganizeResult:
        """
        Reorganize memory by merging similar points (from HGMem).
        
        Uses LLM to identify memory points that should be merged
        to form higher-order associations.
        
        Args:
            main_query: The main query context
            
        Returns:
            ReorganizeResult with merged groups
        """
        if self.llm_func is None:
            logger.warning("LLM function not set, skipping reorganization")
            return ReorganizeResult(merged_groups=[])
        
        if len(self._memory_points) < 2:
            return ReorganizeResult(merged_groups=[])
        
        # Build prompt
        memory_context = self._format_memory_points(self._memory_points)
        
        prompt = REORGANIZE_MEMORY_PROMPT.format(
            main_query=main_query,
            memory=memory_context,
            **self.format_dict,
        )
        
        try:
            response = await self.llm_func(prompt)
            return self._parse_reorganize_response(response)
        except Exception as e:
            logger.error(f"Reorganize memory failed: {e}")
            return ReorganizeResult(merged_groups=[])
    
    def _parse_reorganize_response(self, response: str) -> ReorganizeResult:
        """Parse reorganization response."""
        merged_groups = []
        
        if "<None>" in response:
            return ReorganizeResult(merged_groups=[])
        
        # Find patterns like (1,2 | description)
        pattern = r'\(([0-9,\s]+)\s*\|\s*([^)]+)\)'
        matches = re.findall(pattern, response)
        
        for indices_str, description in matches:
            try:
                indices = [int(i.strip()) for i in indices_str.split(",")]
                if len(indices) > 1:
                    merged_groups.append((indices, description.strip()))
            except ValueError:
                continue
        
        logger.info(f"Reorganized: {len(merged_groups)} merge groups identified")
        return ReorganizeResult(merged_groups=merged_groups)
    
    def apply_reorganization(self, reorg_result: ReorganizeResult) -> None:
        """
        Apply reorganization result to memory points.
        
        Merges the identified groups and updates internal state.
        """
        if not reorg_result.merged_groups:
            return
        
        indices_to_remove: Set[int] = set()
        new_points: List[MemoryPoint] = []
        
        for indices, new_description in reorg_result.merged_groups:
            # Collect all objects from merged points
            merged_objects: Set[str] = set()
            for idx in indices:
                if 0 <= idx < len(self._memory_points):
                    merged_objects.update(self._memory_points[idx].involved_objects)
                    indices_to_remove.add(idx)
            
            if merged_objects:
                new_points.append(MemoryPoint(
                    involved_objects=list(merged_objects),
                    description=new_description,
                ))
        
        # Remove merged points and add new ones
        self._memory_points = [
            p for i, p in enumerate(self._memory_points) 
            if i not in indices_to_remove
        ]
        self._memory_points.extend(new_points)
        
        logger.info(f"Applied reorganization: removed {len(indices_to_remove)}, added {len(new_points)}")
    
    async def get_extended_info(
        self,
        query: str,
        top_k: int = 5,
    ) -> ExtendedInfoResult:
        """
        Get extended information via neighbor nodes (from HGMem).
        
        This expands the context by:
        1. Collecting entities from current memory points
        2. Finding their neighbors in the KG
        3. Optionally using LLM to select most relevant
        
        Args:
            query: The query to find relevant neighbors for
            top_k: Maximum number of extended entities
            
        Returns:
            ExtendedInfoResult with entities and context
        """
        if not self._memory_points:
            return ExtendedInfoResult(extended_entities=[], extension_context="")
        
        # Collect all entities from memory points
        memory_entities: Set[str] = set()
        for point in self._memory_points:
            memory_entities.update(point.involved_objects)
        
        # If we have a KG adapter, use it to find neighbors
        candidate_entities: List[Dict[str, Any]] = []
        
        if self.kg_adapter is not None:
            try:
                for entity_name in memory_entities:
                    neighbors = await self._get_neighbors_from_kg(entity_name)
                    for neighbor in neighbors:
                        if neighbor["name"] not in memory_entities:
                            candidate_entities.append(neighbor)
            except Exception as e:
                logger.warning(f"Failed to get neighbors from KG: {e}")
        
        # If no KG or no results, return empty
        if not candidate_entities:
            return ExtendedInfoResult(
                extended_entities=[],
                extension_context=f"Memory contains entities: {', '.join(list(memory_entities)[:10])}"
            )
        
        # Optionally use LLM to select most relevant
        if self.llm_func is not None and len(candidate_entities) > top_k:
            selected = await self._select_entities(query, candidate_entities, top_k)
            candidate_entities = selected
        else:
            candidate_entities = candidate_entities[:top_k]
        
        # Build extension context
        extension_lines = []
        for ent in candidate_entities:
            desc = ent.get("description", "")[:200]
            extension_lines.append(f"- {ent['name']}: {desc}")
        
        return ExtendedInfoResult(
            extended_entities=candidate_entities,
            extension_context="\n".join(extension_lines),
        )
    
    async def _get_neighbors_from_kg(self, entity_name: str) -> List[Dict[str, Any]]:
        """Get neighbor entities from knowledge graph."""
        # This would call LightRAG's KG if available
        if self.kg_adapter is None:
            return []
        
        try:
            # Assuming kg_adapter has a get_neighbors method
            if hasattr(self.kg_adapter, 'get_neighbors'):
                return await self.kg_adapter.get_neighbors(entity_name)
            return []
        except Exception:
            return []
    
    async def _select_entities(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """Use LLM to select most relevant entities."""
        if self.llm_func is None:
            return candidates[:top_k]
        
        # Format candidates
        entities_str = "\n".join([
            f"- ({i}): {c['name']}\nDescription: {c.get('description', 'N/A')[:100]}"
            for i, c in enumerate(candidates)
        ])
        
        memory_context = self._format_memory_points(self._memory_points)
        
        prompt = SELECT_ENTITIES_PROMPT.format(
            query=query,
            memory=memory_context,
            entities_str=entities_str,
        )
        
        try:
            response = await self.llm_func(prompt)
            
            # Parse selected indices
            if "<None>" in response:
                return []
            
            selected_match = re.search(r'\[Selected\]:\s*([\d,\s]+)', response)
            if selected_match:
                indices = [int(i.strip()) for i in selected_match.group(1).split(",")]
                return [candidates[i] for i in indices if 0 <= i < len(candidates)][:top_k]
        except Exception as e:
            logger.warning(f"Entity selection failed: {e}")
        
        return candidates[:top_k]
    
    def get_history_subqueries_context(self, include_first: bool = False) -> str:
        """Get formatted history of subqueries (from HGMem)."""
        history = self._history_subqueries
        if not include_first and history:
            history = history[1:]
        
        all_subqueries = []
        for subquery_list in history:
            all_subqueries.extend(subquery_list)
        
        return "\n".join([f"- {sq}" for sq in all_subqueries])
    
    def get_history_retrieved_chunks_ids(self) -> List[Set[str]]:
        """Get list of retrieved chunk IDs per turn (from HGMem)."""
        # 這會在後續整合時使用
        # 目前返回空列表
        return []
    
    async def get_memory_point_info(self, mp_identifier: Tuple[str, ...] | List[str]) -> str:
        """
        Get description of a single memory point (from HGMem).
        
        Args:
            mp_identifier: Memory point identifier (tuple of entity names)
            
        Returns:
            Description string of the memory point
        """
        # 將 list 轉換為 tuple 用於匹配
        mp_key = tuple(mp_identifier) if isinstance(mp_identifier, list) else mp_identifier
        
        # 在內部記憶點列表中查找
        for point in self._memory_points:
            if tuple(point.involved_objects) == mp_key or set(point.involved_objects) == set(mp_key):
                return point.description
        
        # 如果有 KG adapter，嘗試從超圖獲取
        if self.kg_adapter and hasattr(self.kg_adapter, 'get_hyperedge'):
            try:
                edge_data = await self.kg_adapter.get_hyperedge(mp_key)
                if edge_data and 'description' in edge_data:
                    return str(edge_data['description'])
            except Exception:
                pass
        
        # 返回默認描述
        return f"Memory point involving: {', '.join(mp_key)}"
    
    async def get_memory_context(self, include_first_query: bool = False) -> str:
        """Get full memory context including history (from HGMem)."""
        subqueries_context = self.get_history_subqueries_context(include_first=include_first_query)
        memory_context = self._format_memory_points(self._memory_points)
        
        return f"""**Previous Subqueries**
{subqueries_context or "None"}

**Memory Points**
{memory_context or "No memory points yet"}"""
    
    async def get_memory_points_context(self, object_delimiter: str = ", ") -> str:
        """
        Get formatted context of all memory points (from HGMem).
        
        Args:
            object_delimiter: Delimiter for objects in each point
            
        Returns:
            Formatted string with all memory points
        """
        if not self._memory_points:
            return ""
        
        memory_point_details = []
        for idx, point in enumerate(self._memory_points):
            objects_str = object_delimiter.join(point.involved_objects)
            point_str = f"- Point ({idx})\nInvolved Objects: {objects_str}\nDescription: {point.description}"
            memory_point_details.append(point_str)
        
        return "\n".join(memory_point_details)
