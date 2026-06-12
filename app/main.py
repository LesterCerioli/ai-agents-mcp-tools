
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_orchestrator = None
_workflow_coordinator = None
_architecture_sessions: dict[str, Any] = {}
_session_locks: dict[str, asyncio.Lock] = {}
_sessions_creation_lock = asyncio.Lock()


async def _get_or_create_session(session_id: str | None, pipeline_context_cls: type) -> tuple[str, asyncio.Lock]:
    
    async with _sessions_creation_lock:
        if session_id and session_id in _architecture_sessions:
            return session_id, _session_locks[session_id]
        ctx = pipeline_context_cls()
        sid = ctx.session_id
        _architecture_sessions[sid] = ctx
        _session_locks[sid] = asyncio.Lock()
        return sid, _session_locks[sid]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator, _workflow_coordinator
    from app.llm.huggingface import HuggingFaceProvider
    from app.agents.orchestrator import AgentOrchestrator
    from app.architecture.workflow_coordinator import WorkflowCoordinator

    token = os.getenv("HUGGINGFACE_TOKEN")
    model = os.getenv("LLM_MODEL_1")

    llm = HuggingFaceProvider(token=token, model=model) if token else None
    _orchestrator = AgentOrchestrator(llm=llm)
    _workflow_coordinator = WorkflowCoordinator(orchestrator=_orchestrator, llm=llm)

    print(f"✓ Agents ready — LLM: {'enabled (' + (model or 'default') + ')' if token else 'disabled (no token)'}")
    print(f"✓ MCP servers mounted at /mcp/architecture, /mcp/backend, /mcp/frontend, /mcp/orchestrate")
    yield


app = FastAPI(
    title="Enterprise AI Agents",
    description=(
        "AI Agents with specialized Next.js, Design, Frontend, Vercel, and Backend skills. "
        "Full workflow orchestration via REST API and MCP servers."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SkillRequest(BaseModel):
    agent: str
    skill: str
    params: dict[str, Any] = {}


class OrchestrateRequest(BaseModel):
    task: str


class SkillResultResponse(BaseModel):
    success: bool
    summary: str
    artifacts: list[dict[str, Any]]
    instructions: list[str]
    dependencies: list[str]
    dev_dependencies: list[str]
    next_steps: list[str]
    error: str | None = None


class ArchitectureParseRequest(BaseModel):
    objective: str
    session_id: str | None = None


class ArchitectureClarifyRequest(BaseModel):
    session_id: str
    answer: str


class ArchitectureRequirementsResponse(BaseModel):
    session_id: str
    requirements: dict[str, Any]
    overall_confidence: float
    is_complete: bool
    clarification_questions: list[str]


class ArchitectureRunRequest(BaseModel):
    session_id: str
    scope: str = "fullstack"


class WorkflowRunRequest(BaseModel):
    objective: str
    scope: str = "fullstack"
    session_id: str | None = None


class ScaffoldRequest(BaseModel):
    objective: str
    project_name: str
    output_dir: str
    scope: str = "fullstack"
    backend_language: str = "python"
    backend_framework: str = "fiber"
    architecture_pattern: str | None = None


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "Enterprise AI Agents", "version": "0.2.0"}


@app.get("/health", tags=["Health"])
async def health():
    from app.skills.registry import SkillRegistry
    return {
        "status": "healthy",
        "skills_registered": len(SkillRegistry.names()),
        "llm_enabled": _orchestrator.agents["nextjs"].llm is not None if _orchestrator else False,
        "mcp_servers": ["/mcp/architecture", "/mcp/backend", "/mcp/frontend", "/mcp/orchestrate"],
    }


@app.get("/skills", tags=["Skills"])
async def list_skills(agent: str | None = None, category: str | None = None, tag: str | None = None):
    from app.skills.registry import SkillRegistry
    from app.skills.base import SkillCategory

    if category:
        try:
            cat = SkillCategory(category)
            return {"skills": SkillRegistry.list_by_category(cat)}
        except ValueError:
            raise HTTPException(400, f"Invalid category. Valid: {[c.value for c in SkillCategory]}")

    if tag:
        return {"skills": SkillRegistry.list_by_tag(tag)}

    if agent and _orchestrator:
        if agent not in _orchestrator.agents:
            raise HTTPException(404, f"Agent '{agent}' not found")
        return {"skills": _orchestrator.agents[agent].available_skills}

    return {"skills": SkillRegistry.list_all()}


@app.get("/agents", tags=["Agents"])
async def list_agents():
    if not _orchestrator:
        raise HTTPException(503, "Service not initialized")
    return {
        "agents": [
            {
                "name": agent.name,
                "description": agent.description,
                "category": agent.category.value,
                "skill_count": len(agent.available_skills),
            }
            for agent in _orchestrator.agents.values()
        ]
    }



@app.post("/skills/execute", response_model=SkillResultResponse, tags=["Skills"])
async def execute_skill(request: SkillRequest):
    if not _orchestrator:
        raise HTTPException(503, "Service not initialized")

    try:
        result = await _orchestrator.run_skill(request.agent, request.skill, **request.params)
        if not result.skill_results:
            raise HTTPException(500, "No result returned")

        skill_result = result.skill_results[0]
        return SkillResultResponse(
            success=skill_result.success,
            summary=skill_result.summary,
            artifacts=[
                {"filename": a.filename, "content": a.content, "language": a.language, "description": a.description}
                for a in skill_result.artifacts
            ],
            instructions=skill_result.instructions,
            dependencies=skill_result.dependencies,
            dev_dependencies=skill_result.dev_dependencies,
            next_steps=skill_result.next_steps,
            error=skill_result.error,
        )
    except KeyError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Skill execution failed: {e}")


@app.post("/orchestrate", tags=["Orchestration"])
async def orchestrate(request: OrchestrateRequest):
    if not _orchestrator:
        raise HTTPException(503, "Service not initialized")

    result = await _orchestrator.run(request.task)
    return {
        "success": result.success,
        "plan": result.plan.analysis,
        "tasks_completed": len(result.agent_results),
        "errors": result.errors,
        "artifacts": [
            {"filename": a.filename, "language": a.language, "description": a.description}
            for a in result.all_artifacts
        ],
        "dependencies": result.all_dependencies,
        "summary": result.summary(),
    }


@app.post("/plan", tags=["Orchestration"])
async def create_plan(request: OrchestrateRequest):
    if not _orchestrator:
        raise HTTPException(503, "Service not initialized")

    plan = await _orchestrator.plan(request.task)
    return {"analysis": plan.analysis, "tasks": plan.tasks}



@app.post("/architecture/parse", response_model=ArchitectureRequirementsResponse, tags=["Solution Architecture"])
async def architecture_parse(request: ArchitectureParseRequest):
    from app.architecture.agents.business_objective_parser import BusinessObjectiveParserAgent
    from app.architecture.context.pipeline_context import PipelineContext

    llm = _orchestrator.agents["nextjs"].llm if _orchestrator else None
    agent = BusinessObjectiveParserAgent(llm=llm)

    session_id, lock = await _get_or_create_session(request.session_id, PipelineContext)

    async with lock:
        context = _architecture_sessions[session_id]
        try:
            requirements = await agent.parse(request.objective, context)
        except Exception as e:
            logger.exception("Architecture parse failed", extra={"session_id": session_id})
            raise HTTPException(500, "Parsing failed") from e

    return ArchitectureRequirementsResponse(
        session_id=context.session_id,
        requirements=requirements.model_dump(),
        overall_confidence=requirements.overall_confidence,
        is_complete=requirements.is_complete,
        clarification_questions=requirements.clarification_questions,
    )


@app.post("/architecture/clarify", response_model=ArchitectureRequirementsResponse, tags=["Solution Architecture"])
async def architecture_clarify(request: ArchitectureClarifyRequest):
    from app.architecture.agents.business_objective_parser import BusinessObjectiveParserAgent

    if request.session_id not in _architecture_sessions:
        raise HTTPException(404, f"Session '{request.session_id}' not found. Call /architecture/parse first.")

    lock = _session_locks[request.session_id]
    llm = _orchestrator.agents["nextjs"].llm if _orchestrator else None
    agent = BusinessObjectiveParserAgent(llm=llm)

    async with lock:
        context = _architecture_sessions[request.session_id]
        try:
            requirements = await agent.clarify(request.answer, context)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:
            logger.exception("Architecture clarification failed", extra={"session_id": request.session_id})
            raise HTTPException(500, "Clarification failed") from e

    return ArchitectureRequirementsResponse(
        session_id=context.session_id,
        requirements=requirements.model_dump(),
        overall_confidence=requirements.overall_confidence,
        is_complete=requirements.is_complete,
        clarification_questions=requirements.clarification_questions,
    )


@app.get("/architecture/sessions/{session_id}", tags=["Solution Architecture"])
async def architecture_session(session_id: str):
    if session_id not in _architecture_sessions:
        raise HTTPException(404, f"Session '{session_id}' not found.")

    context = _architecture_sessions[session_id]
    return {
        "session_id": context.session_id,
        "turn_count": context.turn_count(),
        "is_ready_for_next_stage": context.is_ready_for_next_stage(),
        "has_decision": context.decision is not None,
        "has_system_design": context.system_design is not None,
        "requirements": context.requirements.model_dump() if context.requirements else None,
    }


@app.post("/architecture/run", tags=["Solution Architecture"])
async def architecture_run(request: ArchitectureRunRequest):
    """
    Run the full architecture pipeline (decision → diagram → validation → design partner)
    for an existing session. Returns the SystemDesignOutput without generating code.
    """
    if not _workflow_coordinator:
        raise HTTPException(503, "Service not initialized")

    if request.session_id not in _architecture_sessions:
        raise HTTPException(404, f"Session '{request.session_id}' not found. Call /architecture/parse first.")

    from app.architecture.schemas.workflow import WorkflowScope
    try:
        scope = WorkflowScope(request.scope)
    except ValueError:
        raise HTTPException(400, f"Invalid scope '{request.scope}'. Valid: backend, frontend, fullstack")

    ctx = _architecture_sessions[request.session_id]
    lock = _session_locks[request.session_id]

    async with lock:
        output = await _workflow_coordinator.run(
            objective="",
            scope=scope,
            session_id=request.session_id,
            existing_context=ctx,
        )

    return {
        "session_id": output.session_id,
        "architecture_pattern": output.architecture_pattern,
        "system_design_summary": output.system_design_summary,
        "confidence": output.confidence,
        "backend_artifacts_count": len(output.backend_artifacts),
        "frontend_artifacts_count": len(output.frontend_artifacts),
        "has_integration_contracts": output.integration_contracts is not None,
    }



@app.post("/workflow/run", tags=["Workflow"])
async def workflow_run(request: WorkflowRunRequest):
    """
    End-to-end workflow: objective → architecture → backend/frontend code → contracts.

    This is the primary entry point for full project scaffolding.
    """
    if not _workflow_coordinator:
        raise HTTPException(503, "Service not initialized")

    from app.architecture.schemas.workflow import WorkflowScope
    try:
        scope = WorkflowScope(request.scope)
    except ValueError:
        raise HTTPException(400, f"Invalid scope '{request.scope}'. Valid: backend, frontend, fullstack")

    existing_ctx = _architecture_sessions.get(request.session_id) if request.session_id else None

    try:
        output = await _workflow_coordinator.run(
            objective=request.objective,
            scope=scope,
            session_id=request.session_id,
            existing_context=existing_ctx,
        )
    except Exception as e:
        logger.exception("Workflow run failed")
        raise HTTPException(500, f"Workflow failed: {e}") from e

    _architecture_sessions[output.session_id] = existing_ctx or {}

    return {
        "workflow_id": output.workflow_id,
        "session_id": output.session_id,
        "scope": output.scope.value,
        "architecture_pattern": output.architecture_pattern,
        "system_design_summary": output.system_design_summary,
        "summary": output.summary,
        "confidence": output.confidence,
        "backend_artifacts": [
            {"filename": a.filename, "language": a.language, "description": a.description}
            for a in output.backend_artifacts
        ],
        "frontend_artifacts": [
            {"filename": a.filename, "language": a.language, "description": a.description}
            for a in output.frontend_artifacts
        ],
        "integration_contracts": {
            "openapi_stub": output.integration_contracts.openapi_stub,
            "typescript_types": output.integration_contracts.typescript_types,
            "pydantic_schemas": output.integration_contracts.pydantic_schemas,
        } if output.integration_contracts else None,
        "all_dependencies": output.all_dependencies,
    }


@app.post("/workflow/scaffold", tags=["Workflow"])
async def workflow_scaffold(request: ScaffoldRequest):
    """
    Generate a full project scaffold from a natural-language objective and write
    all files to disk at output_dir/project_name/.

    Steps:
      1. Architecture pipeline (parse → decide → design partner)
      2. Comprehensive skill generation (nextjs, design, frontend, vercel, backend)
      3. Write every artifact to output_dir/project_name/

    Returns the list of files written and their paths.
    """
    import pathlib
    from app.architecture.schemas.workflow import WorkflowScope

    if not _orchestrator or not _workflow_coordinator:
        raise HTTPException(503, "Service not initialized")

    try:
        scope = WorkflowScope(request.scope)
    except ValueError:
        raise HTTPException(400, f"Invalid scope '{request.scope}'. Valid: backend, frontend, fullstack")

    output_path = pathlib.Path(request.output_dir) / request.project_name
    try:
        output_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise HTTPException(400, f"Cannot create output directory '{output_path}': {e}")
    
    try:
        workflow_output = await _workflow_coordinator.run(
            objective=request.objective,
            scope=scope,
            backend_language=request.backend_language,
            backend_framework=request.backend_framework,
            forced_pattern=request.architecture_pattern,
        )
    except Exception as e:
        # If LLM fails (e.g. token permissions), retry with rule-based mode
        if "403" in str(e) or "permission" in str(e).lower() or "Forbidden" in str(e):
            logger.warning("LLM unavailable, falling back to rule-based pipeline")
            from app.architecture.workflow_coordinator import WorkflowCoordinator
            fallback_coordinator = WorkflowCoordinator(orchestrator=_orchestrator, llm=None)
            try:
                workflow_output = await fallback_coordinator.run(
                    objective=request.objective,
                    scope=scope,
                    backend_language=request.backend_language,
                    backend_framework=request.backend_framework,
                    forced_pattern=request.architecture_pattern,
                )
            except Exception as fallback_exc:
                logger.exception("Scaffold fallback also failed")
                raise HTTPException(500, f"Pipeline failed: {fallback_exc}") from fallback_exc
        else:
            logger.exception("Scaffold workflow failed")
            raise HTTPException(500, f"Architecture pipeline failed: {e}") from e

    domain = (
        workflow_output.architecture_pattern.lower().replace("_", "-")
        if workflow_output.architecture_pattern
        else request.project_name
    )

    
    
    from app.agents.orchestrator import AgentOrchestrator as _AO
    _rule_based = _AO(llm=None)
    nx = _rule_based.agents["nextjs"]
    ds = _rule_based.agents["design"]
    fe = _rule_based.agents["frontend"]
    vc = _rule_based.agents["vercel"]

    skill_calls: list[tuple] = []

    if scope in (WorkflowScope.FRONTEND, WorkflowScope.FULLSTACK):
        skill_calls += [
            (nx, "nextjs.generate_layout",          {"name": "RootLayout", "route": "/", "description": f"Root layout for {request.project_name}"}),
            (nx, "nextjs.generate_page",             {"route": "/", "description": "Landing page"}),
            (nx, "nextjs.generate_page",             {"route": "/dashboard", "description": "Main dashboard"}),
            (nx, "nextjs.generate_loading",          {"route": "/dashboard", "layout": "spinner"}),
            (nx, "nextjs.generate_error_page",       {"route": "/dashboard"}),
            (nx, "nextjs.generate_component",        {"name": "Navbar", "description": "Top navigation bar"}),
            (nx, "nextjs.generate_component",        {"name": "Sidebar", "description": "Collapsible sidebar navigation"}),
            (nx, "nextjs.generate_middleware",       {"description": "Auth middleware protecting /dashboard"}),
            (nx, "nextjs.generate_api_route",        {"route": f"/api/{domain}", "description": f"CRUD API for {domain}"}),
            (nx, "nextjs.generate_server_action",    {"name": f"create{domain.title()}", "description": f"Creates a {domain} entry", "inputs": "title,description", "revalidate": "/dashboard", "db": "prisma"}),
            (nx, "nextjs.setup_nextauth",            {"providers": "Google,GitHub"}),
            (nx, "nextjs.generate_sitemap",          {}),
            (nx, "nextjs.generate_metadata",         {"page_name": "Dashboard", "description": f"Main dashboard for {request.project_name}", "site_name": request.project_name}),
            (ds, "design.generate_tailwind_config",  {"brand_colors": "primary:#6366f1,secondary:#8b5cf6", "plugins": "typography", "dark_mode": "class"}),
            (ds, "design.setup_shadcn",              {"project_type": domain}),
            (ds, "design.implement_dark_mode",       {}),
            (ds, "design.generate_design_tokens_css",{"primary_hsl": "239 84% 67%"}),
            (ds, "design.generate_sidebar_layout",   {"app_name": request.project_name}),
            (ds, "design.generate_loading_ui",       {"component": "dashboard"}),
            (ds, "design.setup_next_fonts",          {"font_config": "--font-sans:Inter,--font-mono:JetBrains Mono"}),
            (fe, "frontend.implement_zustand_store", {"name": "app", "state_fields": "user,theme,sidebarOpen", "actions": "setUser,setTheme,toggleSidebar", "persist": "true"}),
            (fe, "frontend.generate_zod_schema",     {"name": domain.title(), "fields": "title:string,description:string,status:string"}),
            (fe, "frontend.implement_tanstack_query",{"entity": domain, "api_base": f"/api/{domain}", "hooks": "list,detail,create,delete"}),
            (fe, "frontend.implement_toast_system",  {}),
            (vc, "vercel.generate_config",           {"project_name": request.project_name, "framework": "nextjs"}),
            (vc, "vercel.generate_env_validation",   {"server_vars": "DATABASE_URL:url,NEXTAUTH_SECRET,NEXTAUTH_URL:url", "public_vars": "NEXT_PUBLIC_APP_URL:url"}),
            (vc, "vercel.deployment_checklist",      {}),
        ]

    if scope in (WorkflowScope.BACKEND, WorkflowScope.FULLSTACK):
        if request.backend_language == "go":
            fw = request.backend_framework or "fiber"
            go_agent = _orchestrator.agents["go"]
            skill_calls += [
                (go_agent, "go.setup_project",        {"module_name": f"github.com/org/{request.project_name}", "app_name": request.project_name, "framework": fw}),
                (go_agent, "go.go_struct",            {"resource": domain}),
                (go_agent, "go.repository",           {"resource": domain, "module_name": f"github.com/org/{request.project_name}"}),
                (go_agent, "go.service",              {"resource": domain, "module_name": f"github.com/org/{request.project_name}"}),
                (go_agent, f"go.{fw}_app",            {"app_name": request.project_name, "module_name": f"github.com/org/{request.project_name}"}),
                (go_agent, f"go.{fw}_handler",        {"resource": domain, "module_name": f"github.com/org/{request.project_name}"}),
                (go_agent, f"go.{fw}_routes",         {"resource": domain, "module_name": f"github.com/org/{request.project_name}"}),
                (go_agent, f"go.{fw}_middleware",     {"module_name": f"github.com/org/{request.project_name}"}),
                (go_agent, "go.test_suite",           {"resource": domain, "module_name": f"github.com/org/{request.project_name}"}),
                (go_agent, "go.generate_migration",   {"resource": domain}),
                (go_agent, "go.docker_setup",         {"app_name": request.project_name, "services": "postgres,redis"}),
                (go_agent, "go.config",               {"app_name": request.project_name, "module_name": f"github.com/org/{request.project_name}"}),
                (go_agent, "go.logger",               {}),
            ]
        else:
            skill_calls += [
                (_orchestrator.agents["backend"], "backend.fastapi_endpoint",  {"resource": domain}),
                (_orchestrator.agents["backend"], "backend.sqlalchemy_model",   {"resource": domain}),
                (_orchestrator.agents["backend"], "backend.repository_pattern", {"resource": domain}),
                (_orchestrator.agents["backend"], "backend.pytest_suite",       {"resource": domain}),
                (_orchestrator.agents["backend"], "backend.docker_setup",       {"app_name": request.project_name, "services": "postgres,redis"}),
            ]

    
    all_artifacts = list(workflow_output.backend_artifacts) + list(workflow_output.frontend_artifacts)

    
    errors: list[str] = []
    for agent, skill, params in skill_calls:
        try:
            result = await agent.execute_skill(skill, **params)
            if result.success:
                all_artifacts.extend(result.artifacts)
            elif result.error:
                errors.append(f"{skill}: {result.error}")
        except Exception as exc:
            errors.append(f"{skill}: {exc}")

    
    written: list[str] = []
    seen: set[str] = set()
    for artifact in all_artifacts:
        if artifact.filename in seen:
            continue
        seen.add(artifact.filename)
        dest = output_path / artifact.filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(artifact.content, encoding="utf-8")
        written.append(artifact.filename)

    return {
        "project_name": request.project_name,
        "output_path": str(output_path),
        "architecture_pattern": workflow_output.architecture_pattern,
        "system_design_summary": workflow_output.system_design_summary,
        "files_written": len(written),
        "files": sorted(written),
        "errors": errors,
        "session_id": workflow_output.session_id,
    }


@app.get("/workflow/{session_id}", tags=["Workflow"])
async def workflow_status(session_id: str):
    """Return the status and artifacts for a completed or in-progress workflow session."""
    ctx = _architecture_sessions.get(session_id)
    if ctx is None:
        raise HTTPException(404, f"Workflow session '{session_id}' not found.")

    if not hasattr(ctx, "workflow_output"):
        return {"session_id": session_id, "status": "in_progress"}

    wo = ctx.workflow_output
    if wo is None:
        return {
            "session_id": session_id,
            "status": "architecture_only",
            "has_decision": ctx.decision is not None,
            "has_system_design": ctx.system_design is not None,
        }

    return {
        "session_id": session_id,
        "status": "completed",
        "workflow_id": wo.workflow_id,
        "architecture_pattern": wo.architecture_pattern,
        "summary": wo.summary,
        "confidence": wo.confidence,
        "backend_artifacts_count": len(wo.backend_artifacts),
        "frontend_artifacts_count": len(wo.frontend_artifacts),
        "has_integration_contracts": wo.integration_contracts is not None,
    }


# ── MCP server mounts ─────────────────────────────────────────────────────────
# Mounted lazily after lifespan initializes agents and coordinator.
# We use app.router.add_event_handler to defer mounting until startup completes.

@app.on_event("startup")
async def mount_mcp_servers():
    """Mount the three MCP SSE servers once agents are ready."""
    if _orchestrator is None or _workflow_coordinator is None:
        return

    from app.mcp.architecture_mcp import ArchitectureMCPServer
    from app.mcp.backend_mcp import BackendMCPServer
    from app.mcp.frontend_mcp import FrontendMCPServer
    from app.mcp.orchestrator_mcp import OrchestratorMCPServer

    llm = _orchestrator.agents["nextjs"].llm if _orchestrator else None

    architecture_server = ArchitectureMCPServer(_architecture_sessions, llm=llm)
    backend_server = BackendMCPServer(_orchestrator.agents["backend"])
    frontend_server = FrontendMCPServer(_orchestrator)
    orchestrator_server = OrchestratorMCPServer(
        _workflow_coordinator, _orchestrator, _architecture_sessions
    )

    app.mount("/mcp/architecture", architecture_server.sse_app())
    app.mount("/mcp/backend", backend_server.sse_app())
    app.mount("/mcp/frontend", frontend_server.sse_app())
    app.mount("/mcp/orchestrate", orchestrator_server.sse_app())


def cli():
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("API_DEBUG", "true").lower() == "true",
    )


if __name__ == "__main__":
    cli()
