
from typing import TYPE_CHECKING

from app.architecture.agents.business_objective_parser import BusinessObjectiveParserAgent
from app.architecture.agents.decision_engine import SolutionArchitectureDecisionEngine
from app.architecture.agents.solution_flow_diagram import SolutionFlowDiagramAgent
from app.architecture.agents.validation_agent import SolutionArchitectureValidationAgent
from app.architecture.agents.system.design_partner_orchestrator import DesignPartnerOrchestrator
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.schemas.system_design import (
    MicroservicesSystemDesign,
    MonolithSystemDesign,
    HexagonalSystemDesign,
    SystemDesignOutput,
)
from app.architecture.schemas.workflow import IntegrationContract, WorkflowOutput, WorkflowScope
from app.architecture.schemas.solution import (
    ArchitecturalDriver,
    ArchitecturePattern,
    ComponentType,
    ArchitectureLayer,
    DecisionComponent,
    RiskFactor,
    SolutionArchitectureDecision,
    SolutionPattern,
    TradeOffMatrix,
    TradeOffRating,
)
from app.skills.base import CodeArtifact

if TYPE_CHECKING:
    from app.agents.orchestrator import AgentOrchestrator
    from app.llm.base import BaseLLMProvider


class WorkflowCoordinator:
    
    def __init__(
        self,
        orchestrator: "AgentOrchestrator",
        llm: "BaseLLMProvider | None" = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._llm = llm
        self._parser = BusinessObjectiveParserAgent(llm)
        self._decision_engine = SolutionArchitectureDecisionEngine(llm)
        self._diagram_agent = SolutionFlowDiagramAgent(llm)
        self._validation_agent = SolutionArchitectureValidationAgent(llm)
        self._design_partner = DesignPartnerOrchestrator(llm)

    async def run(
        self,
        objective: str,
        scope: WorkflowScope,
        session_id: str | None = None,
        existing_context: PipelineContext | None = None,
        backend_language: str = "python",
        backend_framework: str = "fiber",
        forced_pattern: str | None = None,
    ) -> WorkflowOutput:
        """
        Execute the complete workflow from a business objective to generated code artifacts.

        Args:
            objective: Natural-language description of what to build.
            scope: backend | frontend | fullstack — which artifacts to generate.
            session_id: Optional session ID for an already-started architecture session.
            existing_context: If provided, skips the parse step and uses this context directly.
            forced_pattern: When set (e.g. "microservices"), bypasses the decision engine
                            and forces this architecture pattern directly.
        """
        ctx = existing_context or PipelineContext(
            session_id=session_id or PipelineContext().session_id
        )
        ctx.execution_scope = scope

        
        if ctx.requirements is None:
            ctx.add_turn("user", objective)
            await self._parser.run(ctx)

        
        if forced_pattern and ctx.decision is None and ctx.requirements is not None:
            ctx = self._apply_forced_pattern(ctx, forced_pattern)

        if ctx.decision is None and ctx.requirements is not None:
            ctx = await self._decision_engine.run(ctx)

        
        if ctx.diagram is None and ctx.decision is not None:
            ctx = await self._diagram_agent.run(ctx)

        
        if ctx.decision is not None and ctx.requirements is not None:
            ctx = await self._validation_agent.run(ctx)

        
        if ctx.system_design is None and ctx.decision is not None:
            ctx = await self._design_partner.run(ctx)

        system_design = ctx.system_design
        pattern_name = (
            ctx.decision.primary_pattern.pattern.value.upper()
            if ctx.decision and ctx.decision.primary_pattern
            else "UNKNOWN"
        )

        
        backend_artifacts: list[CodeArtifact] = []
        if scope in (WorkflowScope.BACKEND, WorkflowScope.FULLSTACK) and system_design is not None:
            backend_artifacts = await self._generate_backend(system_design, backend_language, backend_framework)

        
        frontend_artifacts: list[CodeArtifact] = []
        if scope in (WorkflowScope.FRONTEND, WorkflowScope.FULLSTACK) and ctx.requirements is not None:
            frontend_artifacts = await self._generate_frontend(ctx)

        
        contracts: IntegrationContract | None = None
        if scope == WorkflowScope.FULLSTACK and system_design is not None and ctx.requirements is not None:
            contracts = self._generate_contracts(system_design, ctx)

        all_deps: set[str] = set()
        all_dev_deps: set[str] = set()

        design_summary = (
            system_design.microservices_design.rationale
            if system_design and system_design.microservices_design
            else system_design.hexagonal_design.rationale
            if system_design and system_design.hexagonal_design
            else system_design.monolith_design.rationale
            if system_design and system_design.monolith_design
            else "Architecture pipeline completed."
        )

        output = WorkflowOutput(
            session_id=ctx.session_id,
            scope=scope,
            system_design_summary=design_summary,
            architecture_pattern=pattern_name,
            backend_artifacts=backend_artifacts,
            frontend_artifacts=frontend_artifacts,
            integration_contracts=contracts,
            all_dependencies=sorted(all_deps),
            all_dev_dependencies=sorted(all_dev_deps),
            summary=(
                f"Workflow complete. Pattern: {pattern_name}. "
                f"Backend artifacts: {len(backend_artifacts)}. "
                f"Frontend artifacts: {len(frontend_artifacts)}."
            ),
            confidence=ctx.decision.decision_confidence if ctx.decision else 0.5,
        )

        ctx.workflow_output = output
        return output

    
    def _apply_forced_pattern(self, ctx: PipelineContext, pattern_name: str) -> PipelineContext:
        
        try:
            pattern = ArchitecturePattern(pattern_name.lower())
        except ValueError:
            pattern = ArchitecturePattern.MICROSERVICES

        domain = (
            ctx.requirements.domain_boundaries.primary_domain
            if ctx.requirements and ctx.requirements.domain_boundaries
            else "application"
        ) or "application"

        _tm: dict[ArchitecturePattern, TradeOffMatrix] = {
            ArchitecturePattern.MICROSERVICES: TradeOffMatrix(
                scalability=TradeOffRating.HIGH,
                consistency=TradeOffRating.LOW,
                operational_complexity=TradeOffRating.HIGH,
                time_to_market=TradeOffRating.LOW,
                cost=TradeOffRating.HIGH,
            ),
            ArchitecturePattern.HEXAGONAL: TradeOffMatrix(
                scalability=TradeOffRating.MEDIUM,
                consistency=TradeOffRating.HIGH,
                operational_complexity=TradeOffRating.MEDIUM,
                time_to_market=TradeOffRating.MEDIUM,
                cost=TradeOffRating.MEDIUM,
            ),
            ArchitecturePattern.MONOLITH: TradeOffMatrix(
                scalability=TradeOffRating.MEDIUM,
                consistency=TradeOffRating.HIGH,
                operational_complexity=TradeOffRating.LOW,
                time_to_market=TradeOffRating.HIGH,
                cost=TradeOffRating.LOW,
            ),
        }
        trade_off_matrix = _tm.get(
            pattern,
            TradeOffMatrix(
                scalability=TradeOffRating.MEDIUM,
                consistency=TradeOffRating.MEDIUM,
                operational_complexity=TradeOffRating.MEDIUM,
                time_to_market=TradeOffRating.MEDIUM,
                cost=TradeOffRating.MEDIUM,
            ),
        )

        primary = SolutionPattern(
            pattern=pattern,
            rationale=f"Pattern '{pattern.value}' was explicitly requested by the caller.",
            confidence=1.0,
            trade_offs=[],
            trade_off_matrix=trade_off_matrix,
            is_primary=True,
        )

        ctx.decision = SolutionArchitectureDecision(
            domain=domain,
            patterns=[primary],
            components=[
                DecisionComponent(
                    name="API Gateway",
                    type=ComponentType.GATEWAY,
                    layer=ArchitectureLayer.APPLICATION,
                    responsibility="Entry point for all client requests.",
                    technology_hints=["Kong", "Nginx"],
                    protocols=["HTTP/REST"],
                ),
                DecisionComponent(
                    name=f"{domain.title()} Service",
                    type=ComponentType.SERVICE,
                    layer=ArchitectureLayer.DOMAIN,
                    responsibility=f"Core business logic for {domain}.",
                    technology_hints=["Go", "Fiber"],
                    protocols=["HTTP/REST"],
                ),
                DecisionComponent(
                    name="Primary Database",
                    type=ComponentType.DATABASE,
                    layer=ArchitectureLayer.INFRASTRUCTURE,
                    responsibility="Persistent storage.",
                    technology_hints=["PostgreSQL"],
                    protocols=["TCP"],
                ),
            ],
            external_integrations=[],
            rationale=f"Forced pattern: {pattern.value}.",
            architectural_drivers=[
                ArchitecturalDriver(
                    driver="Explicit caller override",
                    weight=1.0,
                    source_dimension="forced_pattern",
                )
            ],
            risk_factors=[
                RiskFactor(
                    risk="Pattern forced without full requirements analysis",
                    severity="low",
                    mitigation="Validate that the chosen pattern fits the actual workload",
                )
            ],
            decision_confidence=1.0,
            is_rule_based=True,
        )
        return ctx

    
    async def _generate_backend(
        self,
        system_design: SystemDesignOutput,
        language: str = "python",
        framework: str = "fiber",
    ) -> list[CodeArtifact]:
        if language == "go":
            backend_agent = self._orchestrator.agents.get("go")
        else:
            backend_agent = self._orchestrator.agents.get("backend")
        if backend_agent is None:
            return []

        artifacts: list[CodeArtifact] = []

        if language == "go":
            resources: list[str] = []
            if system_design.microservices_design:
                resources = [bc.subdomain for bc in system_design.microservices_design.bounded_contexts]
            elif system_design.monolith_design:
                resources = [m.name for m in system_design.monolith_design.modules]
            elif system_design.hexagonal_design:
                resources = [s.name for s in system_design.hexagonal_design.domain_services]
            artifacts.extend(await self._backend_from_go(backend_agent, resources, framework))
        elif system_design.microservices_design:
            artifacts.extend(await self._backend_from_microservices(backend_agent, system_design.microservices_design))
        elif system_design.monolith_design:
            artifacts.extend(await self._backend_from_monolith(backend_agent, system_design.monolith_design))
        elif system_design.hexagonal_design:
            artifacts.extend(await self._backend_from_hexagonal(backend_agent, system_design.hexagonal_design))

        return artifacts

    async def _backend_from_go(self, agent, resources: list[str], framework: str = "fiber") -> list[CodeArtifact]:
        
        artifacts: list[CodeArtifact] = []
        framework = framework or "fiber"
        for resource in resources:
            r = resource.lower().replace(" ", "_").replace("-", "_")
            for skill_name, params in [
                ("go.go_struct", {"resource": r}),
                ("go.repository", {"resource": r}),
                ("go.service", {"resource": r}),
                (f"go.{framework}_handler", {"resource": r}),
                (f"go.{framework}_routes", {"resource": r}),
            ]:
                try:
                    result = await agent.execute_skill(skill_name, **params)
                    if result.success:
                        artifacts.extend(result.artifacts)
                except Exception:
                    pass
        try:
            result = await agent.execute_skill("go.docker_setup", app_name="app", services="postgres")
            if result.success:
                artifacts.extend(result.artifacts)
        except Exception:
            pass
        return artifacts

    async def _backend_from_microservices(
        self, agent, design: MicroservicesSystemDesign
    ) -> list[CodeArtifact]:
        artifacts: list[CodeArtifact] = []
        for bc in design.bounded_contexts:
            resource = bc.subdomain.lower().replace(" ", "_").replace("-", "_")
            for skill_name, params in [
                ("backend.fastapi_endpoint", {"resource": resource}),
                ("backend.sqlalchemy_model", {"resource": resource}),
                ("backend.repository_pattern", {"resource": resource}),
            ]:
                try:
                    result = await agent.execute_skill(skill_name, **params)
                    if result.success:
                        artifacts.extend(result.artifacts)
                except Exception:
                    pass
        return artifacts

    async def _backend_from_monolith(
        self, agent, design: MonolithSystemDesign
    ) -> list[CodeArtifact]:
        artifacts: list[CodeArtifact] = []
        for module in design.modules:
            resource = module.name.lower().replace(" ", "_").replace("-", "_")
            for skill_name, params in [
                ("backend.fastapi_endpoint", {"resource": resource}),
                ("backend.sqlalchemy_model", {"resource": resource}),
            ]:
                try:
                    result = await agent.execute_skill(skill_name, **params)
                    if result.success:
                        artifacts.extend(result.artifacts)
                except Exception:
                    pass
        try:
            docker_result = await agent.execute_skill("backend.docker_setup", app_name="app", services="postgres")
            if docker_result.success:
                artifacts.extend(docker_result.artifacts)
        except Exception:
            pass
        return artifacts

    async def _backend_from_hexagonal(
        self, agent, design: HexagonalSystemDesign
    ) -> list[CodeArtifact]:
        artifacts: list[CodeArtifact] = []
        for svc in design.domain_services:
            resource = svc.name.lower().replace(" ", "_").replace("-", "_")
            for skill_name, params in [
                ("backend.fastapi_endpoint", {"resource": resource}),
                ("backend.repository_pattern", {"resource": resource}),
            ]:
                try:
                    result = await agent.execute_skill(skill_name, **params)
                    if result.success:
                        artifacts.extend(result.artifacts)
                except Exception:
                    pass
        return artifacts

    

    async def _generate_frontend(self, ctx: PipelineContext) -> list[CodeArtifact]:
        nextjs_agent = self._orchestrator.agents.get("nextjs")
        design_agent = self._orchestrator.agents.get("design")
        if nextjs_agent is None:
            return []

        artifacts: list[CodeArtifact] = []
        req = ctx.requirements

        
        domain = (
            req.domain_boundaries.primary_domain if req and req.domain_boundaries else ""
        ) or "app"

        
        try:
            result = await nextjs_agent.execute_skill(
                "nextjs.generate_page",
                route=f"/{domain}/dashboard",
                description=f"Main dashboard for the {domain} system",
            )
            if result.success:
                artifacts.extend(result.artifacts)
        except Exception:
            pass

        
        try:
            result = await nextjs_agent.execute_skill(
                "nextjs.generate_layout",
                name=f"{domain.capitalize()}Layout",
                description=f"Root layout for {domain}",
            )
            if result.success:
                artifacts.extend(result.artifacts)
        except Exception:
            pass

        
        if design_agent:
            try:
                result = await design_agent.execute_skill(
                    "design.generate_tailwind_config",
                    project_type=domain,
                )
                if result.success:
                    artifacts.extend(result.artifacts)
            except Exception:
                pass

        return artifacts

    

    def _generate_contracts(
        self,
        system_design: SystemDesignOutput,
        ctx: PipelineContext,
    ) -> IntegrationContract:
        resources: list[str] = []

        if system_design.microservices_design:
            resources = [bc.subdomain for bc in system_design.microservices_design.bounded_contexts]
        elif system_design.monolith_design:
            resources = [m.name for m in system_design.monolith_design.modules]
        elif system_design.hexagonal_design:
            resources = [s.name for s in system_design.hexagonal_design.domain_services]

        openapi_paths = "\n".join(
            f"  /{r.lower()}s:\n"
            f"    get:\n"
            f"      summary: List {r}s\n"
            f"      responses:\n"
            f"        '200':\n"
            f"          description: Success\n"
            f"    post:\n"
            f"      summary: Create {r}\n"
            f"      responses:\n"
            f"        '201':\n"
            f"          description: Created\n"
            for r in resources
        )

        openapi_stub = (
            "openapi: 3.1.0\n"
            "info:\n"
            f"  title: {ctx.requirements.domain_boundaries.primary_domain if ctx.requirements and ctx.requirements.domain_boundaries else 'API'} API\n"
            "  version: 1.0.0\n"
            "paths:\n"
            f"{openapi_paths}"
        )

        ts_interfaces = "\n\n".join(
            f"export interface {r.capitalize()} {{\n"
            f"  id: number;\n"
            f"  name: string;\n"
            f"  description?: string;\n"
            f"  createdAt: string;\n"
            f"  updatedAt: string;\n"
            f"}}\n\n"
            f"export interface Create{r.capitalize()}Request {{\n"
            f"  name: string;\n"
            f"  description?: string;\n"
            f"}}"
            for r in resources
        )

        pydantic_schemas = (
            "from pydantic import BaseModel\n\n\n"
            + "\n\n".join(
                f"class {r.capitalize()}Base(BaseModel):\n"
                f"    name: str\n"
                f"    description: str | None = None\n\n"
                f"class {r.capitalize()}Response({r.capitalize()}Base):\n"
                f"    id: int\n"
                f"    created_at: str\n"
                f"    updated_at: str"
                for r in resources
            )
            + "\n"
        )

        return IntegrationContract(
            openapi_stub=openapi_stub,
            typescript_types=ts_interfaces,
            pydantic_schemas=pydantic_schemas,
        )
