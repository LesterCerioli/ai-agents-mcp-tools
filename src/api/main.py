"""FastAPI application — REST API for the agent system."""
from contextlib import asynccontextmanager
from typing import Any
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


_orchestrator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _orchestrator
    from src.llm.huggingface import HuggingFaceProvider
    from src.agents.orchestrator import AgentOrchestrator

    token = os.getenv("HUGGINGFACE_TOKEN")
    model = os.getenv("LLM_MODEL")

    llm = HuggingFaceProvider(token=token, model=model) if token else None
    _orchestrator = AgentOrchestrator(llm=llm)

    print(f"✓ Agents ready — LLM: {'enabled (' + (model or 'default') + ')' if token else 'disabled (no token)'}")
    yield


app = FastAPI(
    title="Enterprise AI Agents",
    description="AI Agents with specialized Next.js, Design, and Frontend skills",
    version="0.1.0",
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



@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "Enterprise AI Agents", "version": "0.1.0"}


@app.get("/health", tags=["Health"])
async def health():
    from src.skills.registry import SkillRegistry
    return {
        "status": "healthy",
        "skills_registered": len(SkillRegistry.names()),
        "llm_enabled": _orchestrator.agents["nextjs"].llm is not None if _orchestrator else False,
    }


@app.get("/skills", tags=["Skills"])
async def list_skills(agent: str | None = None, category: str | None = None, tag: str | None = None):
    
    from src.skills.registry import SkillRegistry
    from src.skills.base import SkillCategory

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
    return {
        "analysis": plan.analysis,
        "tasks": plan.tasks,
    }



def cli():
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        reload=os.getenv("API_DEBUG", "true").lower() == "true",
    )


if __name__ == "__main__":
    cli()
