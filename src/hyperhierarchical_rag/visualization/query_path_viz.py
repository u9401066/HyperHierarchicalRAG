"""
Query Path Visualization

Visualizes the traversal path of a query through the hypergraph:
1. Starting nodes (from keyword matching)
2. Hyperedges traversed
3. Discovered nodes (via hypergraph expansion)
4. Memory evolution points

This answers the question: "Which paths did the RAG system take?"
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from hyperhierarchical_rag.Domain.entities import HyperNode, HyperEdge, NodeLevel

logger = logging.getLogger(__name__)


@dataclass
class QueryStep:
    """A single step in the query traversal."""
    
    step_number: int
    step_type: str  # "keyword_match", "kg_retrieval", "hyperedge_traverse", "memory_evolve"
    description: str
    
    # Nodes involved
    input_node_ids: List[str] = field(default_factory=list)
    output_node_ids: List[str] = field(default_factory=list)
    
    # Edges traversed
    edge_ids: List[str] = field(default_factory=list)
    
    # Additional info
    keywords: List[str] = field(default_factory=list)
    level: Optional[str] = None  # "local", "global", "hybrid"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step_number,
            "type": self.step_type,
            "description": self.description,
            "input_nodes": self.input_node_ids,
            "output_nodes": self.output_node_ids,
            "edges": self.edge_ids,
            "keywords": self.keywords,
            "level": self.level,
        }


@dataclass
class QueryTrace:
    """Complete trace of a query's execution."""
    
    query: str
    mode: str  # "local", "global", "hybrid"
    steps: List[QueryStep] = field(default_factory=list)
    
    # Summary
    total_nodes_visited: int = 0
    total_edges_traversed: int = 0
    local_keywords: List[str] = field(default_factory=list)
    global_keywords: List[str] = field(default_factory=list)
    
    # Timing (optional)
    duration_ms: Optional[float] = None
    
    def add_step(self, step: QueryStep) -> None:
        """Add a step to the trace."""
        self.steps.append(step)
    
    def get_all_traversed_node_ids(self) -> Set[str]:
        """Get all node IDs that were visited."""
        nodes = set()
        for step in self.steps:
            nodes.update(step.input_node_ids)
            nodes.update(step.output_node_ids)
        return nodes
    
    def get_all_traversed_edge_ids(self) -> Set[str]:
        """Get all edge IDs that were traversed."""
        edges = set()
        for step in self.steps:
            edges.update(step.edge_ids)
        return edges
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "mode": self.mode,
            "steps": [s.to_dict() for s in self.steps],
            "summary": {
                "total_steps": len(self.steps),
                "nodes_visited": self.total_nodes_visited,
                "edges_traversed": self.total_edges_traversed,
                "local_keywords": self.local_keywords,
                "global_keywords": self.global_keywords,
                "duration_ms": self.duration_ms,
            }
        }


class QueryPathVisualizer:
    """
    Visualize query execution paths.
    
    Generates:
    1. Step-by-step trace visualization
    2. Highlighted path on full graph
    3. Text summary of traversal
    """
    
    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or Path("./data/visualizations")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def trace_to_mermaid(self, trace: QueryTrace) -> str:
        """
        Convert query trace to Mermaid flowchart.
        
        Example output:
        ```mermaid
        flowchart TD
            Q[Query: propofol sedation]
            K1[Keywords: propofol, sedation]
            N1((Propofol))
            N2((Sedation))
            H1{HyperEdge: drugs}
            N3((Remimazolam))
            
            Q --> K1
            K1 --> N1
            K1 --> N2
            N1 --> H1
            N2 --> H1
            H1 --> N3
        ```
        """
        lines = [
            "```mermaid",
            "flowchart TD",
            f'    Q["{self._escape(trace.query[:50])}..."]',
        ]
        
        node_ids_seen = set()
        
        for step in trace.steps:
            step_id = f"S{step.step_number}"
            
            # Add step description
            lines.append(f'    {step_id}["{step.description}"]')
            
            # Connect from previous
            if step.step_number == 1:
                lines.append(f"    Q --> {step_id}")
            else:
                prev_id = f"S{step.step_number - 1}"
                lines.append(f"    {prev_id} --> {step_id}")
            
            # Add output nodes
            for node_id in step.output_node_ids[:5]:  # Limit for readability
                if node_id not in node_ids_seen:
                    safe_id = self._safe_id(node_id)
                    lines.append(f'    {safe_id}(("{node_id[:15]}"))')
                    lines.append(f"    {step_id} --> {safe_id}")
                    node_ids_seen.add(node_id)
        
        lines.append("```")
        
        return "\n".join(lines)
    
    def trace_to_ascii(self, trace: QueryTrace) -> str:
        """
        Generate ASCII art representation of query path.
        
        ╔═══════════════════════════════════════════════════════════════╗
        ║ Query: "propofol sedation"                                     ║
        ╠═══════════════════════════════════════════════════════════════╣
        ║                                                                ║
        ║ Step 1: Keyword Extraction                                     ║
        ║ ├── LOCAL: propofol                                            ║
        ║ └── GLOBAL: sedation                                           ║
        ║     │                                                          ║
        ║     ▼                                                          ║
        ║ Step 2: Node Retrieval                                         ║
        ║ ├── [LOCAL] Propofol                                           ║
        ║ └── [GLOBAL] Sedation                                          ║
        ║     │                                                          ║
        ║     ▼                                                          ║
        ║ Step 3: Hyperedge Traversal                                    ║
        ║ ├── HE: {Propofol, Remimazolam, Sedation}                      ║
        ║ └── Discovered: Remimazolam                                    ║
        ║                                                                ║
        ╚═══════════════════════════════════════════════════════════════╝
        """
        width = 70
        lines = []
        
        # Header
        lines.append("╔" + "═" * (width - 2) + "╗")
        query_line = f' Query: "{trace.query[:50]}"'
        lines.append("║" + query_line.ljust(width - 2) + "║")
        lines.append("╠" + "═" * (width - 2) + "╣")
        lines.append("║" + " " * (width - 2) + "║")
        
        # Steps
        for i, step in enumerate(trace.steps):
            step_header = f" Step {step.step_number}: {step.step_type}"
            lines.append("║" + step_header.ljust(width - 2) + "║")
            
            # Keywords
            if step.keywords:
                for j, kw in enumerate(step.keywords[:3]):
                    prefix = " ├──" if j < len(step.keywords) - 1 else " └──"
                    level = step.level or "?"
                    kw_line = f"{prefix} [{level.upper()}] {kw}"
                    lines.append("║" + kw_line.ljust(width - 2) + "║")
            
            # Output nodes
            if step.output_node_ids:
                for j, node_id in enumerate(step.output_node_ids[:3]):
                    prefix = " ├──" if j < len(step.output_node_ids) - 1 else " └──"
                    node_line = f"{prefix} {node_id[:30]}"
                    lines.append("║" + node_line.ljust(width - 2) + "║")
            
            # Arrow to next step
            if i < len(trace.steps) - 1:
                lines.append("║" + "     │".ljust(width - 2) + "║")
                lines.append("║" + "     ▼".ljust(width - 2) + "║")
        
        # Footer
        lines.append("║" + " " * (width - 2) + "║")
        lines.append("╚" + "═" * (width - 2) + "╝")
        
        return "\n".join(lines)
    
    def trace_to_html(
        self,
        trace: QueryTrace,
        nodes: List[HyperNode],
        edges: List[HyperEdge],
        filename: str = "query_path.html",
    ) -> Path:
        """
        Generate HTML visualization with highlighted query path.
        """
        from hyperhierarchical_rag.visualization.hypergraph_viz import HypergraphVisualizer
        
        visualizer = HypergraphVisualizer(output_dir=self.output_dir)
        
        # Get traversed IDs
        traversed_nodes = trace.get_all_traversed_node_ids()
        traversed_edges = trace.get_all_traversed_edge_ids()
        
        # Generate HTML with highlighting
        return visualizer.to_html(
            nodes=nodes,
            edges=edges,
            title=f"Query Path: {trace.query[:30]}...",
            traversed_edge_ids=traversed_edges,
            traversed_node_ids=traversed_nodes,
            filename=filename,
        )
    
    def save_trace(self, trace: QueryTrace, filename: str = "query_trace.json") -> Path:
        """Save trace to JSON file."""
        output_path = self.output_dir / filename
        output_path.write_text(
            json.dumps(trace.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return output_path
    
    def _escape(self, text: str) -> str:
        """Escape special characters for Mermaid."""
        return text.replace('"', "'").replace("\n", " ")
    
    def _safe_id(self, node_id: str) -> str:
        """Convert node ID to valid Mermaid ID."""
        return "N" + node_id.replace("-", "").replace("_", "")[:10]
