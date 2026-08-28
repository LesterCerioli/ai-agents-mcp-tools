
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.llm.grok import GrokProvider
from app.skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    step: int
    skill: str
    params: dict[str, Any]
    reason: str
    depends_on: list[int] = field(default_factory=list)
    confidence: float = 0.8


@dataclass
class ExecutionPlan:
    plan_id: str
    analysis: str
    steps: list[PlanStep]
    total_estimated_duration: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class GrokPlanner:
        
    def __init__(self, grok_provider: GrokProvider | None = None):
        self.grok = grok_provider
        self._skill_catalog = self._build_skill_catalog()
    
    def _build_skill_catalog(self) -> list[dict[str, Any]]:
        
        skills = SkillRegistry.list_for_planner()
        catalog = []
        for skill in skills:
            catalog.append({
                "name": skill["name"],
                "description": skill["description"],
                "category": skill["category"],
                "metadata": skill.get("metadata", {}),
            })
        return catalog
    
    async def create_plan(
        self,
        instruction: str,
        project_files: list[dict[str, Any]],
        project_type: str,
        project_context: dict[str, Any] | None = None,
    ) -> ExecutionPlan:
                
        if not self.grok:
            return self._fallback_plan(instruction, project_files, project_type)
        
        
        context = self._build_context(instruction, project_files, project_type, project_context)
        
        
        try:
            plan_json = await self._call_grok_planner(context)
            return self._parse_plan(plan_json, instruction)
        except Exception as e:
            logger.warning(f"Grok planner failed: {e}, using fallback")
            return self._fallback_plan(instruction, project_files, project_type)
    
    def _build_context(
        self,
        instruction: str,
        project_files: list[dict[str, Any]],
        project_type: str,
        project_context: dict[str, Any] | None,
    ) -> str:
        
        file_summary = []
        total_files = len(project_files)
        for f in project_files[:30]:  # Limit to 30 files
            path = f.get("path", "")
            content = f.get("content") or ""
            truncated = content[:1000] + ("..." if len(content) > 1000 else "")
            file_summary.append(f"- {path} ({len(content)} chars): {truncated}")
        
        files_text = "\n".join(file_summary) if file_summary else "(no files)"
        
        
        skill_summary = []
        for skill in self._skill_catalog:
            meta = skill.get("metadata", {})
            domain = meta.get("domain", "unknown")
            complexity = meta.get("complexity", "medium")
            inputs = meta.get("inputs", [])
            outputs = meta.get("outputs", [])
            prereqs = meta.get("prerequisites", [])
            tags = meta.get("tags", [])
            skill_summary.append(
                f"- {skill['name']} ({domain}/{complexity}): {skill['description'][:80]}"
                f" | inputs: {inputs} | outputs: {outputs} | prereqs: {prereqs} | tags: {tags}"
            )
        
        catalog_text = "\n".join(skill_summary[:50])  # Limit skills
        
        project_ctx_text = ""
        if project_context:
            project_ctx_text = f"\nProject Context: {json.dumps(project_context, ensure_ascii=False)[:500]}"
        
        return f"""You are an expert Technical Program Manager + Architect. Create an execution plan.

INSTRUCTION: {instruction}

PROJECT TYPE: {project_type}
TOTAL FILES: {total_files}{project_ctx_text}

PROJECT FILES (sample):
{files_text}

AVAILABLE SKILLS (124 total, showing key ones):
{catalog_text}

YOUR TASK:
1. Analyze the instruction and project context
2. Select the MINIMAL set of skills needed (max 8 steps)
3. Order them by dependencies (prerequisites first)
4. For each step, infer reasonable parameters from context
5. Return a JSON plan with steps ordered by dependency

OUTPUT FORMAT (JSON only, no markdown):
{{
  "analysis": "Brief analysis of what needs to be done",
  "steps": [
    {{
      "step": 1,
      "skill": "planning.analyze_requirements",
      "params": {{"source_files": ["kanban.txt"], "project_context": "..."}},
      "reason": "Extract requirements from kanban",
      "depends_on": [],
      "confidence": 0.9
    }},
    ...
  ]
}}

RULES:
- Use EXACT skill names from the catalog
- Max 8 steps
- Include prerequisites in depends_on
- Infer params from context (file paths, project type, etc.)
- If non-technical (kanban, planning, docs), prefer planning.* skills
- If technical (code, bugs, features), prefer code skills
- Confidence 0.0-1.0
"""

    async def _call_grok_planner(self, context: str) -> str:
        from app.llm.base import LLMMessage
        
        system = """You are an expert Technical Program Manager. Create minimal, dependency-ordered execution plans using the provided skill catalog. Return ONLY valid JSON."""
        
        response = await self.grok.complete([
            LLMMessage(role="system", content=system),
            LLMMessage(role="user", content=context),
        ], max_tokens=3000, temperature=0.1)
        
        return response.content.strip()
    
    def _parse_plan(self, plan_json: str, instruction: str) -> ExecutionPlan:
        import uuid
        
        # Clean JSON
        cleaned = plan_json.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        cleaned = cleaned.strip()
        
        data = json.loads(cleaned)
        
        steps = []
        for i, step_data in enumerate(data.get("steps", []), 1):
            step = PlanStep(
                step=i,
                skill=step_data.get("skill", ""),
                params=step_data.get("params", {}),
                reason=step_data.get("reason", ""),
                depends_on=step_data.get("depends_on", []),
                confidence=step_data.get("confidence", 0.8),
            )
            steps.append(step)
        
        total_duration = sum(
            self._estimate_step_duration(step.skill) for step in steps
        )
        
        return ExecutionPlan(
            plan_id=f"plan-{uuid.uuid4().hex[:8]}",
            analysis=data.get("analysis", f"Plan for: {instruction}"),
            steps=steps,
            total_estimated_duration=total_duration,
            metadata={"instruction": instruction},
        )
    
    def _estimate_step_duration(self, skill_name: str) -> int:
        """Estimate duration in seconds for a skill."""
        # Quick lookup from skill catalog
        for skill in self._skill_catalog:
            if skill["name"] == skill_name:
                return skill.get("metadata", {}).get("estimated_duration_seconds", 30)
        return 30
    
    def _fallback_plan(self, instruction: str, project_files: list[dict], project_type: str) -> ExecutionPlan:
        """Smart fallback: prefer planning skills for planning-related instructions."""
        from app.llm.bm25_index import SkillBM25Index
        from app.skills.registry import SkillDomain, SkillRegistry
        
        # Detect if this is a planning task
        instruction_lower = instruction.lower()
        is_planning = any(kw in instruction_lower for kw in [
            "kanban", "backlog", "requisito", "user story", "planejamento", 
            "estimativa", "planejar", "melhorar descri", "refinar", "organizar",
            "priorizar", "breakdown", "break down", "spec", "especifica"
        ])
        
        
        if is_planning:
            planning_skills = SkillRegistry.list_by_domain(SkillDomain.PLANNING)
            if planning_skills:
                bm25 = SkillBM25Index()
                bm25.build({"planning": planning_skills})
                matches = bm25.search(instruction, top_k=5)
            else:
                # Fall back to all skills
                bm25 = SkillBM25Index()
                skills_by_agent = {s["category"]: s for s in SkillRegistry.list_all()}
                bm25.build({cat: [s] for cat, s in skills_by_agent.items()})
                matches = bm25.search(instruction, top_k=5)
        else:
            # Non-planning: use all skills
            bm25 = SkillBM25Index()
            skills_by_agent = {s["category"]: s for s in SkillRegistry.list_all()}
            bm25.build({cat: [s] for cat, s in skills_by_agent.items()})
            matches = bm25.search(instruction, top_k=5)
        
        steps = []
        for i, match in enumerate(matches[:5], 1):
            steps.append(PlanStep(
                step=i,
                skill=match.skill_name,
                params={},
                reason=f"BM25 matched: {match.description[:80]}",
                depends_on=[i-1] if i > 1 else [],
                confidence=0.6,
            ))
        
        return ExecutionPlan(
            plan_id=f"plan-fallback-{hash(instruction) % 10000}",
            analysis=f"Fallback BM25 plan for: {instruction} (planning={is_planning})",
            steps=steps,
            total_estimated_duration=sum(self._estimate_step_duration(s.skill) for s in steps),
            metadata={"instruction": instruction, "fallback": True, "is_planning": is_planning},
        )