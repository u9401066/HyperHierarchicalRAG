"""
Hypergraph Visualization

Visualizes the hypergraph structure including:
- Nodes with Level coloring (LOCAL=blue, GLOBAL=orange)
- N-ary hyperedges as "hub" nodes connecting multiple entities
- Query traversal paths

Output formats:
- HTML (interactive, uses vis.js or pyvis)
- PNG/SVG (static, uses matplotlib/networkx)
- JSON (for external tools)
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hyperhierarchical_rag.Domain.entities import HyperEdge, HyperNode, NodeLevel

logger = logging.getLogger(__name__)


@dataclass
class VisualizationOptions:
    """Options for graph visualization."""

    # Layout
    layout: str = "force"  # force, hierarchical, circular

    # Colors
    local_node_color: str = "#4A90D9"  # Blue for LOCAL
    global_node_color: str = "#F5A623"  # Orange for GLOBAL
    hyperedge_color: str = "#7ED321"  # Green for hyperedge hubs
    traversed_color: str = "#D0021B"  # Red for traversed paths

    # Sizes
    node_size: int = 20
    hyperedge_size: int = 15
    edge_width: int = 2

    # Labels
    show_labels: bool = True
    show_weights: bool = True
    max_label_length: int = 20


class HypergraphVisualizer:
    """
    Visualize hypergraph structure.

    Converts n-ary hyperedges to a bipartite representation:
    - Entity nodes (HyperNode) → circles
    - Hyperedge "hub" nodes → squares/diamonds
    - Edges connect entities to their hyperedge hubs

    ╔════════════════════════════════════════════════════════════════╗
    ║  Original Hypergraph:                                          ║
    ║                                                                 ║
    ║     Hyperedge H1 = {A, B, C}                                   ║
    ║     Hyperedge H2 = {B, D}                                      ║
    ║                                                                 ║
    ║  Bipartite Visualization:                                      ║
    ║                                                                 ║
    ║      (A)───┐                                                   ║
    ║            │                                                   ║
    ║      (B)───┼───[H1]                                            ║
    ║       │    │                                                   ║
    ║       │    └───(C)                                             ║
    ║       │                                                        ║
    ║       └───[H2]───(D)                                           ║
    ║                                                                 ║
    ║  Legend:                                                       ║
    ║    (X) = Entity node                                           ║
    ║    [H] = Hyperedge hub                                         ║
    ╚════════════════════════════════════════════════════════════════╝
    """

    def __init__(
        self,
        options: VisualizationOptions | None = None,
        output_dir: Path | None = None,
    ) -> None:
        self.options = options or VisualizationOptions()
        self.output_dir = output_dir or Path("./data/visualizations")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def to_vis_network(
        self,
        nodes: list[HyperNode],
        edges: list[HyperEdge],
        traversed_edge_ids: set[str] | None = None,
        traversed_node_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        """
        Convert hypergraph to vis.js network format.

        Returns:
            Dict with 'nodes' and 'edges' arrays for vis.js
        """
        traversed_edge_ids = traversed_edge_ids or set()
        traversed_node_ids = traversed_node_ids or set()

        vis_nodes = []
        vis_edges = []

        # Build node ID → node mapping
        node_map = {n.id: n for n in nodes}

        # Add entity nodes
        for node in nodes:
            color = self._get_node_color(node, node.id in traversed_node_ids)
            vis_nodes.append(
                {
                    "id": node.id,
                    "label": self._truncate(node.name),
                    "title": f"{node.name}\n{node.description[:100] if node.description else ''}",
                    "color": color,
                    "shape": "dot",
                    "size": self.options.node_size,
                    "font": {"size": 12},
                    "group": node.level.value,
                }
            )

        # Add hyperedge "hub" nodes and connecting edges
        for edge in edges:
            is_traversed = edge.id in traversed_edge_ids
            hub_color = (
                self.options.traversed_color if is_traversed else self.options.hyperedge_color
            )

            # Create hub node for hyperedge
            hub_id = f"he_{edge.id}"
            hub_label = self._truncate(edge.relation) if edge.relation else f"HE-{edge.arity}"

            vis_nodes.append(
                {
                    "id": hub_id,
                    "label": hub_label,
                    "title": f"Hyperedge: {edge.relation}\nWeight: {edge.weight:.2f}\nEvolved: {edge.evolve_count}x",
                    "color": hub_color,
                    "shape": "diamond",
                    "size": self.options.hyperedge_size,
                    "font": {"size": 10},
                    "group": "hyperedge",
                }
            )

            # Connect all member nodes to hub
            for node_id in edge.node_ids:
                if node_id in node_map:
                    vis_edges.append(
                        {
                            "from": node_id,
                            "to": hub_id,
                            "color": {"color": hub_color, "opacity": 0.7},
                            "width": self.options.edge_width if is_traversed else 1,
                            "dashes": not is_traversed,
                        }
                    )

        return {
            "nodes": vis_nodes,
            "edges": vis_edges,
        }

    def to_html(
        self,
        nodes: list[HyperNode],
        edges: list[HyperEdge],
        title: str = "HyperHierarchicalRAG Graph",
        traversed_edge_ids: set[str] | None = None,
        traversed_node_ids: set[str] | None = None,
        filename: str = "hypergraph.html",
    ) -> Path:
        """
        Generate interactive HTML visualization.

        Uses vis.js for rendering.
        """
        vis_data = self.to_vis_network(nodes, edges, traversed_edge_ids, traversed_node_ids)

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1 {{
            color: #333;
            margin-bottom: 10px;
        }}
        #graph {{
            width: 100%;
            height: 80vh;
            border: 1px solid #ddd;
            background: white;
            border-radius: 8px;
        }}
        .legend {{
            display: flex;
            gap: 20px;
            margin: 10px 0;
            padding: 10px;
            background: white;
            border-radius: 4px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 5px;
        }}
        .legend-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
        }}
        .legend-diamond {{
            width: 12px;
            height: 12px;
            transform: rotate(45deg);
        }}
        .stats {{
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="legend">
        <div class="legend-item">
            <div class="legend-dot" style="background: {self.options.local_node_color}"></div>
            <span>LOCAL nodes (entities)</span>
        </div>
        <div class="legend-item">
            <div class="legend-dot" style="background: {self.options.global_node_color}"></div>
            <span>GLOBAL nodes (themes)</span>
        </div>
        <div class="legend-item">
            <div class="legend-diamond" style="background: {self.options.hyperedge_color}"></div>
            <span>Hyperedge hubs</span>
        </div>
        <div class="legend-item">
            <div class="legend-diamond" style="background: {self.options.traversed_color}"></div>
            <span>Traversed paths</span>
        </div>
    </div>
    <div class="stats">
        Nodes: {len(nodes)} | Hyperedges: {len(edges)} |
        LOCAL: {sum(1 for n in nodes if n.level == NodeLevel.LOCAL)} |
        GLOBAL: {sum(1 for n in nodes if n.level == NodeLevel.GLOBAL)}
    </div>
    <div id="graph"></div>

    <script>
        var nodes = new vis.DataSet({json.dumps(vis_data["nodes"])});
        var edges = new vis.DataSet({json.dumps(vis_data["edges"])});

        var container = document.getElementById('graph');
        var data = {{ nodes: nodes, edges: edges }};
        var options = {{
            physics: {{
                stabilization: {{ iterations: 100 }},
                barnesHut: {{
                    gravitationalConstant: -2000,
                    springLength: 100,
                }}
            }},
            groups: {{
                local: {{ color: "{self.options.local_node_color}" }},
                global: {{ color: "{self.options.global_node_color}" }},
                hyperedge: {{ color: "{self.options.hyperedge_color}" }}
            }},
            interaction: {{
                hover: true,
                tooltipDelay: 200,
            }}
        }};

        var network = new vis.Network(container, data, options);
    </script>
</body>
</html>
"""

        output_path = self.output_dir / filename
        output_path.write_text(html_content, encoding="utf-8")
        logger.info(f"Visualization saved to: {output_path}")

        return output_path

    def to_json(
        self,
        nodes: list[HyperNode],
        edges: list[HyperEdge],
        filename: str = "hypergraph.json",
    ) -> Path:
        """Export graph data to JSON."""
        data = {
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "local_nodes": sum(1 for n in nodes if n.level == NodeLevel.LOCAL),
                "global_nodes": sum(1 for n in nodes if n.level == NodeLevel.GLOBAL),
                "binary_edges": sum(1 for e in edges if e.is_binary),
                "nary_edges": sum(1 for e in edges if not e.is_binary),
            },
        }

        output_path = self.output_dir / filename
        output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        return output_path

    def _get_node_color(self, node: HyperNode, is_traversed: bool) -> str:
        """Get color for a node based on level and traversal status."""
        if is_traversed:
            return self.options.traversed_color
        if node.level == NodeLevel.GLOBAL:
            return self.options.global_node_color
        return self.options.local_node_color

    def _truncate(self, text: str) -> str:
        """Truncate text for labels."""
        if len(text) <= self.options.max_label_length:
            return text
        return text[: self.options.max_label_length - 3] + "..."
