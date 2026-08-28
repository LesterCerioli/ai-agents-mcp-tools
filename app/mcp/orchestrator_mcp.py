
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from typing import Any, TYPE_CHECKING

from mcp.server import FastMCP

if TYPE_CHECKING:
    from app.agents.orchestrator import AgentOrchestrator
    from app.architecture.workflow_coordinator import WorkflowCoordinator
    from app.architecture.context.pipeline_context import PipelineContext
    from app.llm.grok import GrokProvider
    from app.llm.grok_planner import GrokPlanner, ExecutionPlan, PlanStep

logger = logging.getLogger(__name__)

_plan_store: dict[str, "ExecutionPlan"] = {}
_execution_status: dict[str, dict[str, Any]] = {}


def create_orchestrator_mcp(
    orchestrator: "AgentOrchestrator",
    workflow_coordinator: "WorkflowCoordinator | None" = None,
    sessions: "dict[str, PipelineContext] | None" = None,
    grok_provider: "GrokProvider | None" = None,
) -> FastMCP:
    mcp = FastMCP("orchestrator-mcp")
    sessions = sessions or {}
        
    grok_planner = None
    if grok_provider:
        from app.llm.grok_planner import GrokPlanner
        grok_planner = GrokPlanner(grok_provider)

    @mcp.resource("orchestrator://plans")
    async def list_plans() -> str:
        return json.dumps({
            pid: {
                "plan_id": p.plan_id,
                "analysis": p.analysis,
                "step_count": len(p.steps),
                "status": _execution_status.get(pid, {}).get("status", "pending"),
            }
            for pid, p in _plan_store.items()
        }, indent=2)

    @mcp.resource("orchestrator://skills")
    async def available_skills() -> str:
        from app.skills.registry import SkillRegistry
        return json.dumps(SkillRegistry.list_for_planner(), indent=2)

    @mcp.tool()
    async def analyze_context(
        instruction: str,
        project_path: str = ".",
        project_type: str = "auto",
    ) -> str:
        """
        Analyze project context and instruction to understand what needs to be done.
        
        Args:
            instruction: Natural language instruction (PT/EN)
            project_path: Path to project directory
            project_type: go | nextjs | python | node | auto
            
        Returns analysis with suggested skill domains.
        """
        from app.cli.project_scanner import scan_project
        from app.skills.registry import SkillRegistry, SkillDomain
        
        
        project_context = scan_project(project_path)
        detected_type = project_context["project_type"]
        if project_type != "auto":
            detected_type = project_type
        
        
        instruction_lower = instruction.lower()
        suggested_domains = []
        if any(kw in instruction_lower for kw in ["kanban", "backlog", "requisito", "user story", "planejamento", "estimativa", "planejar"]):
            suggested_domains.append("planning")
        if any(kw in instruction_lower for kw in ["código", "code", "bug", "erro", "refactor", "feature", "implementar"]):
            suggested_domains.extend(["code", "diagnostic"])
        if any(kw in instruction_lower for kw in ["api", "endpoint", "database", "schema"]):
            suggested_domains.append("architecture")
        if any(kw in instruction_lower for kw in ["doc", "readme", "spec", "documentação"]):
            suggested_domains.append("docs")
        
        
        domain_counts = {}
        for skill in SkillRegistry.list_for_planner():
            domain = skill.get("metadata", {}).get("domain", "unknown")
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        return json.dumps({
            "project_path": project_path,
            "project_type": detected_type,
            "file_count": project_context["file_count"],
            "instruction": instruction,
            "suggested_domains": suggested_domains or ["planning", "code"],
            "available_skills_by_domain": domain_counts,
            "files_sample": [f["path"] for f in project_context["files"][:20]],
        }, indent=2, ensure_ascii=False)

    @mcp.tool()
    async def create_execution_plan(
        instruction: str,
        project_path: str = ".",
        project_type: str = "auto",
        max_steps: int = 8,
    ) -> str:
        """
        Create an execution plan using Grok reasoning.
        
        Args:
            instruction: What to do (natural language, PT/EN)
            project_path: Path to project
            project_type: go | nextjs | python | node | auto
            max_steps: Maximum number of steps in plan
            
        Returns execution plan with ordered steps, dependencies, and parameters.
        """
        if not grok_planner:
            return json.dumps({"error": "Grok provider not available. Set GROCK_API_TOKEN."})
        
        from app.cli.project_scanner import scan_project
        
        project_context = scan_project(project_path)
        detected_type = project_context["project_type"]
        if project_type != "auto":
            detected_type = project_type
        
        
        project_files = project_context["files"]
        
        try:
            plan = await grok_planner.create_plan(
                instruction=instruction,
                project_files=project_files,
                project_type=detected_type,
                project_context={"path": project_path, "type": detected_type},
            )
        except Exception as e:
            logger.exception("Plan creation failed")
            return json.dumps({"error": f"Plan creation failed: {e}"})
        
        
        _plan_store[plan.plan_id] = plan
        _execution_status[plan.plan_id] = {
            "status": "pending_approval",
            "current_step": 0,
            "results": [],
        }
        
        
        steps_display = []
        for step in plan.steps:
            steps_display.append({
                "step": step.step,
                "skill": step.skill,
                "params": step.params,
                "reason": step.reason,
                "depends_on": step.depends_on,
                "confidence": step.confidence,
            })
        
        return json.dumps({
            "plan_id": plan.plan_id,
            "analysis": plan.analysis,
            "total_steps": len(plan.steps),
            "estimated_duration_seconds": plan.total_estimated_duration,
            "steps": steps_display,
            "status": "pending_approval",
            "message": "Review the plan below. Call approve_plan to execute.",
        }, indent=2, ensure_ascii=False)

    @mcp.tool()
    async def present_plan(plan_id: str) -> str:
        """Get formatted plan for user review."""
        if plan_id not in _plan_store:
            return json.dumps({"error": f"Plan {plan_id} not found"})
        
        plan = _plan_store[plan_id]
        status = _execution_status.get(plan_id, {})
        
        lines = [
            f"# Execution Plan: {plan_id}",
            f"**Analysis**: {plan.analysis}",
            f"**Steps**: {len(plan.steps)} | **Est. Duration**: {plan.total_estimated_duration}s",
            f"**Status**: {status.get('status', 'pending_approval')}",
            "",
            "## Steps",
        ]
        
        for step in plan.steps:
            deps = f" (depends on: {', '.join(map(str, step.depends_on))})" if step.depends_on else ""
            lines.append(f"### Step {step.step}: {step.skill}{deps}")
            lines.append(f"**Reason**: {step.reason}")
            lines.append(f"**Confidence**: {step.confidence:.0%}")
            if step.params:
                lines.append(f"**Params**: {json.dumps(step.params, ensure_ascii=False)}")
            lines.append("")
        
        lines.append("---")
        lines.append("**Next**: Call `approve_plan` with `approved: true` to execute.")
        
        return "\n".join(lines)

    @mcp.tool()
    async def approve_plan(
        plan_id: str,
        approved: bool = True,
        modifications: list[dict] | None = None,
    ) -> str:
        """
        Approve or reject a plan. If approved, execution begins.
        
        Args:
            plan_id: Plan ID from create_execution_plan
            approved: true to execute, false to reject
            modifications: Optional list of step modifications
        """
        if plan_id not in _plan_store:
            return json.dumps({"error": f"Plan {plan_id} not found"})
        
        if not approved:
            _execution_status[plan_id]["status"] = "rejected"
            return json.dumps({"status": "rejected", "plan_id": plan_id})
        
        
        plan = _plan_store[plan_id]
        if modifications:
            
            for mod in modifications:
                step_idx = mod.get("step", 0) - 1
                if 0 <= step_idx < len(plan.steps):
                    if "params" in mod:
                        plan.steps[step_idx].params.update(mod["params"])
        
        
        _execution_status[plan_id]["status"] = "running"
        _execution_status[plan_id]["current_step"] = 0
        
        return json.dumps({
            "status": "approved",
            "plan_id": plan_id,
            "message": "Plan approved. Call execute_plan to run steps.",
        })

    @mcp.tool()
    async def execute_plan(plan_id: str) -> str:
        """
        Execute the approved plan step by step.
        Returns streaming results for each step.
        """
        if plan_id not in _plan_store:
            return json.dumps({"error": f"Plan {plan_id} not found"})
        
        if _execution_status[plan_id]["status"] != "running":
            return json.dumps({"error": f"Plan not in running state. Status: {_execution_status[plan_id]['status']}"})
        
        plan = _plan_store[plan_id]
        status = _execution_status[plan_id]
        current = status["current_step"]
        
        results = []
                
        for i in range(current, len(plan.steps)):
            step = plan.steps[i]
            status["current_step"] = i + 1
                        
            deps_ok = all(
                _execution_status[plan_id]["results"][d - 1].get("success", False)
                for d in step.depends_on
            )
            
            if not deps_ok:
                result = {
                    "step": step.step,
                    "skill": step.skill,
                    "success": False,
                    "error": f"Dependencies not met: {step.depends_on}",
                }
            else:
                try:
                    agent_name = step.skill.split(".")[0]
                    agent = orchestrator.agents.get(agent_name)
                    if not agent:
                        raise ValueError(f"Agent {agent_name} not found")
                    
                    skill_result = await agent.execute_skill(step.skill, **step.params)
                    result = {
                        "step": step.step,
                        "skill": step.skill,
                        "success": skill_result.success,
                        "summary": skill_result.summary,
                        "artifacts_count": len(skill_result.artifacts),
                        "error": skill_result.error,
                    }
                except Exception as e:
                    logger.exception(f"Step {step.step} failed")
                    result = {
                        "step": step.step,
                        "skill": step.skill,
                        "success": False,
                        "error": str(e),
                    }
            
            status["results"].append(result)
            results.append(result)
            
            if not result["success"]:
                status["status"] = "failed"
                break
        
        if all(r["success"] for r in status["results"]):
            status["status"] = "completed"
        
        return json.dumps({
            "plan_id": plan_id,
            "status": status["status"],
            "completed_steps": len([r for r in status["results"] if r["success"]]),
            "total_steps": len(plan.steps),
            "results": results,
        }, indent=2, ensure_ascii=False)

    @mcp.tool()
    async def get_plan_status(plan_id: str) -> str:
        """Get current execution status of a plan."""
        if plan_id not in _plan_store:
            return json.dumps({"error": f"Plan {plan_id} not found"})
        
        status = _execution_status.get(plan_id, {})
        plan = _plan_store[plan_id]
        
        return json.dumps({
            "plan_id": plan_id,
            "status": status.get("status", "unknown"),
            "current_step": status.get("current_step", 0),
            "total_steps": len(plan.steps),
            "completed": len([r for r in status.get("results", []) if r.get("success")]),
            "results": status.get("results", []),
        }, indent=2)

    return mcp


class OrchestratorMCPServer:
    def __init__(
        self,
        orchestrator: "AgentOrchestrator",
        workflow_coordinator: "WorkflowCoordinator | None" = None,
        sessions: "dict[str, PipelineContext] | None" = None,
        grok_provider: "GrokProvider | None" = None,
    ):
        self._mcp = create_orchestrator_mcp(
            orchestrator, workflow_coordinator, sessions, grok_provider
        )

    def sse_app(self):
        return self._mcp.sse_app()