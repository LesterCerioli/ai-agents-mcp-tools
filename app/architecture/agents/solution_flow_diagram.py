import re
from collections import defaultdict

from app.architecture.agents.base import BaseArchitectureAgent
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.schemas.solution import (
    ArchitectureLayer,
    ComponentType,
    DecisionComponent,
    DiagramEdge,
    DiagramNode,
    DiagramView,
    SolutionArchitectureDecision,
    SolutionFlowDiagram,
)

_LAYER_ORDER = [
    ArchitectureLayer.PRESENTATION,
    ArchitectureLayer.APPLICATION,
    ArchitectureLayer.DOMAIN,
    ArchitectureLayer.INFRASTRUCTURE,
]

_LAYER_LABELS = {
    ArchitectureLayer.PRESENTATION: "Presentation Layer",
    ArchitectureLayer.APPLICATION: "Application Layer",
    ArchitectureLayer.DOMAIN: "Domain Layer",
    ArchitectureLayer.INFRASTRUCTURE: "Infrastructure Layer",
}

_MERMAID_SHAPES = {
    ComponentType.SERVICE: ('["{label}"', "]"),
    ComponentType.GATEWAY: ('["{label}"', "]"),
    ComponentType.STORAGE: ('["{label}"', "]"),
    ComponentType.DATABASE: ('[("{label}"', ")]"),
    ComponentType.CACHE: ('[("{label}"', ")]"),
    ComponentType.QUEUE: ('[["    {label}    "', "]]"),
    ComponentType.EXTERNAL: ('(["{label}"', "])"),
    ComponentType.CLIENT: ('(["{label}"', "])"),
}


def _node_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "_", name.lower()).strip("_")


def _mermaid_node(node: DiagramNode) -> str:
    open_shape, close_shape = _MERMAID_SHAPES.get(node.type, ('["{label}"', "]"))
    tech = ", ".join(node.technology_hints) if node.technology_hints else ""
    label = f"{node.label}\\n[{tech}]" if tech else node.label
    inner = open_shape.format(label=label)
    return f"    {node.id}{inner}{close_shape}"


class SolutionFlowDiagramAgent(BaseArchitectureAgent):
    
    name = "solution_flow_diagram"
    description = (
        "Generates context, container, and component architecture flow diagrams "
        "from a SolutionArchitectureDecision, producing Mermaid strings and structured models."
    )
    system_prompt = ""

    def generate(self, decision: SolutionArchitectureDecision) -> SolutionFlowDiagram:
        
        nodes = self._build_nodes(decision)
        edges = self._build_edges(nodes, decision)

        return SolutionFlowDiagram(
            decision_id=decision.decision_id,
            context_view=self._build_context_view(nodes, edges, decision),
            container_view=self._build_container_view(nodes, edges),
            component_view=self._build_component_view(nodes, edges),
            annotations=self._build_annotations(decision),
        )

    async def run(self, context: PipelineContext) -> PipelineContext:
        if context.decision is None:
            return context
        context.diagram = self.generate(context.decision)
        return context

    
    def _build_nodes(self, decision: SolutionArchitectureDecision) -> list[DiagramNode]:
        nodes: list[DiagramNode] = []

        for comp in sorted(decision.components, key=lambda c: (c.layer.value, c.name)):
            nodes.append(
                DiagramNode(
                    id=_node_id(comp.name),
                    label=comp.name,
                    type=comp.type,
                    layer=comp.layer,
                    responsibility=comp.responsibility,
                    technology_hints=list(comp.technology_hints),
                    protocols=list(comp.protocols),
                )
            )

        for ext in sorted(decision.external_integrations):
            nodes.append(
                DiagramNode(
                    id=_node_id(f"ext_{ext}"),
                    label=ext,
                    type=ComponentType.EXTERNAL,
                    layer=ArchitectureLayer.INFRASTRUCTURE,
                    responsibility=f"External integration: {ext}",
                    technology_hints=[],
                    protocols=["HTTP/REST"],
                )
            )

        return nodes

    
    def _build_edges(
        self,
        nodes: list[DiagramNode],
        decision: SolutionArchitectureDecision,
    ) -> list[DiagramEdge]:
        by_layer: dict[ArchitectureLayer, list[DiagramNode]] = defaultdict(list)
        external_nodes: list[DiagramNode] = []

        for node in nodes:
            if node.type == ComponentType.EXTERNAL:
                external_nodes.append(node)
            else:
                by_layer[node.layer].append(node)

        edges: list[DiagramEdge] = []

        for i in range(len(_LAYER_ORDER) - 1):
            sources = by_layer.get(_LAYER_ORDER[i], [])
            targets = by_layer.get(_LAYER_ORDER[i + 1], [])
            for src in sources:
                for tgt in targets:
                    protocol = src.protocols[0] if src.protocols else "HTTP/REST"
                    edges.append(
                        DiagramEdge(
                            source_id=src.id,
                            target_id=tgt.id,
                            label=protocol,
                            protocol=protocol,
                        )
                    )

        app_nodes = by_layer.get(ArchitectureLayer.APPLICATION, [])
        if app_nodes:
            anchor = app_nodes[0]
            for ext in external_nodes:
                protocol = anchor.protocols[0] if anchor.protocols else "HTTP/REST"
                edges.append(
                    DiagramEdge(
                        source_id=anchor.id,
                        target_id=ext.id,
                        label=protocol,
                        protocol=protocol,
                    )
                )

        return sorted(edges, key=lambda e: (e.source_id, e.target_id))

    
    def _build_context_view(
        self,
        nodes: list[DiagramNode],
        edges: list[DiagramEdge],
        decision: SolutionArchitectureDecision,
    ) -> DiagramView:
        presentation = [n for n in nodes if n.layer == ArchitectureLayer.PRESENTATION]
        gateways = [
            n
            for n in nodes
            if n.layer == ArchitectureLayer.APPLICATION and n.type == ComponentType.GATEWAY
        ]
        externals = [n for n in nodes if n.type == ComponentType.EXTERNAL]

        entry_nodes = gateways or [
            n for n in nodes if n.layer == ArchitectureLayer.APPLICATION
        ][:1]

        lines = ["graph TB"]

        for node in sorted(presentation, key=lambda n: n.id):
            lines.append(_mermaid_node(node))

        system_id = _node_id(f"{decision.domain}_system")
        lines.append(f'    subgraph {system_id} ["{decision.domain.title()} System"]')
        for node in sorted(entry_nodes, key=lambda n: n.id):
            lines.append("    " + _mermaid_node(node).strip())
        lines.append("    end")

        for node in sorted(externals, key=lambda n: n.id):
            lines.append(_mermaid_node(node))

        for src in sorted(presentation, key=lambda n: n.id):
            for tgt in sorted(entry_nodes, key=lambda n: n.id):
                lines.append(f"    {src.id} --> {tgt.id}")

        for node in sorted(entry_nodes, key=lambda n: n.id):
            for ext in sorted(externals, key=lambda n: n.id):
                lines.append(f"    {node.id} --> {ext.id}")

        view_nodes = presentation + entry_nodes + externals
        view_edges = [
            e
            for e in edges
            if e.source_id in {n.id for n in view_nodes}
            and e.target_id in {n.id for n in view_nodes}
        ]

        return DiagramView(mermaid="\n".join(lines), nodes=view_nodes, edges=view_edges)

    def _build_container_view(
        self,
        nodes: list[DiagramNode],
        edges: list[DiagramEdge],
    ) -> DiagramView:
        by_layer: dict[ArchitectureLayer, list[DiagramNode]] = defaultdict(list)
        for node in nodes:
            if node.type != ComponentType.EXTERNAL:
                by_layer[node.layer].append(node)

        lines = ["graph TB"]

        for layer in _LAYER_ORDER:
            layer_nodes = sorted(by_layer.get(layer, []), key=lambda n: n.id)
            if not layer_nodes:
                continue
            sub_id = f"layer_{layer.value}"
            lines.append(f'    subgraph {sub_id} ["{_LAYER_LABELS[layer]}"]')
            for node in layer_nodes:
                lines.append("    " + _mermaid_node(node).strip())
            lines.append("    end")

        internal_ids = {n.id for n in nodes if n.type != ComponentType.EXTERNAL}
        for edge in edges:
            if edge.source_id in internal_ids and edge.target_id in internal_ids:
                lines.append(f'    {edge.source_id} -->|"{edge.label}"| {edge.target_id}')

        internal_nodes = [n for n in nodes if n.type != ComponentType.EXTERNAL]
        view_edges = [
            e
            for e in edges
            if e.source_id in internal_ids and e.target_id in internal_ids
        ]

        return DiagramView(mermaid="\n".join(lines), nodes=internal_nodes, edges=view_edges)

    def _build_component_view(
        self,
        nodes: list[DiagramNode],
        edges: list[DiagramEdge],
    ) -> DiagramView:
        lines = ["graph LR"]

        for node in sorted(nodes, key=lambda n: n.id):
            lines.append(_mermaid_node(node))

        for edge in edges:
            lines.append(f'    {edge.source_id} -->|"{edge.label}"| {edge.target_id}')

        return DiagramView(mermaid="\n".join(lines), nodes=list(nodes), edges=list(edges))

    

    def _build_annotations(self, decision: SolutionArchitectureDecision) -> list[str]:
        annotations: list[str] = []

        for sp in sorted(decision.patterns, key=lambda p: -p.confidence):
            annotations.append(
                f"Pattern: {sp.pattern.value} — {sp.rationale} (confidence: {sp.confidence:.0%})"
            )

        domain_comps = [c for c in decision.components if c.layer == ArchitectureLayer.DOMAIN]
        if domain_comps:
            names = ", ".join(sorted(c.name for c in domain_comps))
            annotations.append(f"Core domain components: {names}")

        if decision.external_integrations:
            integrations = ", ".join(sorted(decision.external_integrations))
            annotations.append(f"External integrations: {integrations}")

        return annotations

    
    @staticmethod
    def _components_by_layer(
        components: list[DecisionComponent],
    ) -> dict[ArchitectureLayer, list[DecisionComponent]]:
        result: dict[ArchitectureLayer, list[DecisionComponent]] = defaultdict(list)
        for comp in components:
            result[comp.layer].append(comp)
        return result
