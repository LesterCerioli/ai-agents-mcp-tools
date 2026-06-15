import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.architecture.schemas.design_patterns import (
    CONFLICT_RULES,
    PatternCategory,
    PatternConflict,
    PatternRecommendation,
    PatternRecommendationReport,
)
from app.architecture.schemas.solid import (
    ComplianceLevel,
    NormalizedDesignInput,
    SOLIDComplianceReport,
)
from app.skills.base import SkillCategory
from .base import AgentContext, AgentResult, BaseAgent

if TYPE_CHECKING:
    from app.architecture.context.pipeline_context import PipelineContext
    from app.architecture.schemas.requirements import ArchitectureRequirements
    from app.architecture.schemas.solution import SolutionArchitectureDecision
    from app.architecture.schemas.system_design import SystemDesignOutput
    from app.llm.base import BaseLLMProvider

logger = logging.getLogger(__name__)

_MIN_RECOMMENDATIONS = 3
_MAX_RECOMMENDATIONS = 10

_SKILL_NAMES = [
    "design_patterns.creational_analyze",
    "design_patterns.structural_analyze",
    "design_patterns.behavioral_analyze",
    "design_patterns.enterprise_analyze",
]


@dataclass
class _PatternCandidate:
    pattern_name: str
    category: PatternCategory
    target_components: list[str]
    problem_solved: str
    implementation_sketch: str
    solid_principles_reinforced: list[str]
    rationale: str
    score: float

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "_PatternCandidate":
        return cls(
            pattern_name=data.get("pattern_name", ""),
            category=PatternCategory(data.get("category", "creational")),
            target_components=data.get("target_components", []),
            problem_solved=data.get("problem_solved", ""),
            implementation_sketch=data.get("implementation_sketch", ""),
            solid_principles_reinforced=data.get("solid_principles_reinforced", []),
            rationale=data.get("rationale", ""),
            score=float(data.get("score", 0.0)),
        )


def _extract_violations(report: SOLIDComplianceReport | None) -> list[str]:
    if report is None:
        return []
    return [
        r.principle.value
        for r in report.principle_results
        if r.compliance_level == ComplianceLevel.VIOLATION
    ]


def _detect_conflicts(
    recommendations: list[_PatternCandidate],
    architecture_style: str,
) -> list[PatternConflict]:
    conflicts: list[PatternConflict] = []
    names = {c.pattern_name for c in recommendations}

    for rule in CONFLICT_RULES:
        pa, pb = rule["pattern_a"], rule["pattern_b"]
        arch = rule["arch_style"]
        reason = rule["reason"]

        if pa not in names or pb not in names:
            continue
        if arch != "*" and architecture_style.lower() != arch.lower():
            continue

        
        comp_a = next(
            (c.target_components for c in recommendations if c.pattern_name == pa), []
        )
        comp_b = next(
            (c.target_components for c in recommendations if c.pattern_name == pb), []
        )
        shared = list(set(comp_a) & set(comp_b)) or comp_a[:1] or comp_b[:1] or ["Architecture"]
        target = shared[0]

        conflicts.append(PatternConflict(
            pattern_a=pa,
            pattern_b=pb,
            target_component=target,
            reason=reason,
        ))

    return conflicts


def _merge_and_rank(
    raw_candidates: list[list[_PatternCandidate]],
    solid_violations: list[str],
) -> list[_PatternCandidate]:
    seen: dict[str, _PatternCandidate] = {}
    for batch in raw_candidates:
        for c in batch:
            if c.pattern_name not in seen or c.score > seen[c.pattern_name].score:
                seen[c.pattern_name] = c

    
    violation_set = set(solid_violations)
    for candidate in seen.values():
        reinforced_lower = {p.lower() for p in candidate.solid_principles_reinforced}
        overlap = reinforced_lower & violation_set
        candidate.score += len(overlap) * 0.5

    
    return sorted(seen.values(), key=lambda c: c.score, reverse=True)


def _normalize_from_decision(decision: "SolutionArchitectureDecision") -> NormalizedDesignInput:
    from app.agents.solid_agent import _normalize_from_decision as _nd
    return _nd(decision)


def _normalize_from_system_design(design: "SystemDesignOutput", pattern: str = "") -> NormalizedDesignInput:
    from app.agents.solid_agent import _normalize_from_system_design as _nsd
    return _nsd(design, pattern=pattern)


def _merge_inputs(a: NormalizedDesignInput, b: NormalizedDesignInput) -> NormalizedDesignInput:
    from app.agents.solid_agent import _merge_inputs as _mi
    return _mi(a, b)


class DesignPatternRecommenderAgent(BaseAgent):
    

    name = "design_patterns"
    description = (
        "Design Pattern Recommender — analyses any architecture design artifact and SOLID "
        "compliance report to recommend the most appropriate GoF (Gang of Four) and enterprise "
        "design patterns. Produces 3–10 ranked, non-conflicting recommendations with "
        "implementation sketches and SOLID principle mappings."
    )
    category = SkillCategory.DESIGN_PATTERNS
    system_prompt = (
        "You are a senior software architect specialising in design patterns, Domain-Driven Design, "
        "and SOLID principles. You evaluate architecture designs and produce actionable, "
        "context-aware pattern recommendations that address identified violations and align "
        "with the chosen architecture style."
    )

    async def recommend(
        self,
        design: "SolutionArchitectureDecision | SystemDesignOutput | PipelineContext | NormalizedDesignInput",
        solid_report: "SOLIDComplianceReport | None" = None,
        requirements: "ArchitectureRequirements | None" = None,
    ) -> PatternRecommendationReport:
        
        inp = self._normalize(design)
        architecture_style = inp.pattern or ""
        solid_violations = _extract_violations(solid_report)
        input_dict = inp.to_dict()

        
        raw_results: list[Any] = await asyncio.gather(
            *[
                self.execute_skill(
                    sk,
                    design_input=input_dict,
                    solid_violations=solid_violations,
                    architecture_style=architecture_style,
                )
                for sk in _SKILL_NAMES
            ],
            return_exceptions=True,
        )

        raw_candidate_batches: list[list[_PatternCandidate]] = []
        for skill_name, result in zip(_SKILL_NAMES, raw_results):
            if isinstance(result, Exception):
                logger.warning("Design pattern skill %s raised: %s", skill_name, result)
                continue
            if result.success and result.artifacts:
                try:
                    data = json.loads(result.artifacts[0].content)
                    batch = [_PatternCandidate.from_dict(item) for item in data]
                    raw_candidate_batches.append(batch)
                except Exception as exc:
                    logger.warning("Failed to parse %s result: %s", skill_name, exc)

        total_evaluated = sum(len(b) for b in raw_candidate_batches)
        
        merged = _merge_and_rank(raw_candidate_batches, solid_violations)

        
        conflicts = _detect_conflicts(merged, architecture_style)

        
        conflict_losers: set[str] = set()
        for conflict in conflicts:
            cand_a = next((c for c in merged if c.pattern_name == conflict.pattern_a), None)
            cand_b = next((c for c in merged if c.pattern_name == conflict.pattern_b), None)
            if cand_a is not None and cand_b is not None:
                loser = conflict.pattern_b if (cand_a.score >= cand_b.score) else conflict.pattern_a
                conflict_losers.add(loser)

        filtered = [c for c in merged if c.pattern_name not in conflict_losers]

        
        final_candidates = filtered[:_MAX_RECOMMENDATIONS]

        
        if len(final_candidates) < _MIN_RECOMMENDATIONS:
            seen_names = {c.pattern_name for c in final_candidates}
            for c in filtered:
                if c.pattern_name not in seen_names:
                    final_candidates.append(c)
                    seen_names.add(c.pattern_name)
                if len(final_candidates) >= _MIN_RECOMMENDATIONS:
                    break
            
            if len(final_candidates) < _MIN_RECOMMENDATIONS:
                for c in merged:
                    if c.pattern_name not in {fc.pattern_name for fc in final_candidates}:
                        final_candidates.append(c)
                    if len(final_candidates) >= _MIN_RECOMMENDATIONS:
                        break

        
        recommendations = [
            PatternRecommendation(
                rank=i + 1,
                pattern_name=c.pattern_name,
                category=c.category,
                target_components=c.target_components,
                problem_solved=c.problem_solved,
                implementation_sketch=c.implementation_sketch,
                solid_principles_reinforced=c.solid_principles_reinforced,
                rationale=c.rationale,
                score=round(c.score, 2),
            )
            for i, c in enumerate(final_candidates)
        ]

        solid_violations_addressed = sum(
            1 for r in recommendations
            if any(v.upper() in [p.upper() for p in r.solid_principles_reinforced]
                   for v in solid_violations)
        )

        overall_compliance = (
            solid_report.overall_compliance.value if solid_report else "unknown"
        )
        violation_note = (
            f" Addresses {len(solid_violations)} SOLID violation(s): {', '.join(v.upper() for v in solid_violations)}."
            if solid_violations else " No SOLID violations reported."
        )
        conflict_note = (
            f" {len(conflicts)} pattern conflict(s) detected and resolved."
            if conflicts else ""
        )

        summary = (
            f"Design pattern analysis complete for '{architecture_style or 'unknown'}' architecture. "
            f"{total_evaluated} patterns evaluated, {len(recommendations)} recommended "
            f"(ranked 1–{len(recommendations)}).{violation_note}{conflict_note}"
        )

        return PatternRecommendationReport(
            recommendations=recommendations,
            conflicts=conflicts,
            total_patterns_evaluated=total_evaluated,
            architecture_style=architecture_style,
            solid_violations_addressed=solid_violations_addressed,
            analysis_summary=summary,
        )

    def _normalize(
        self,
        artifact: "SolutionArchitectureDecision | SystemDesignOutput | PipelineContext | NormalizedDesignInput",
    ) -> NormalizedDesignInput:
        from app.architecture.schemas.system_design import SystemDesignOutput
        from app.architecture.schemas.solution import SolutionArchitectureDecision
        from app.architecture.context.pipeline_context import PipelineContext

        if isinstance(artifact, NormalizedDesignInput):
            return artifact

        if isinstance(artifact, PipelineContext):
            ctx: PipelineContext = artifact
            decision_inp = (
                _normalize_from_decision(ctx.decision) if ctx.decision else NormalizedDesignInput()
            )
            design_inp = (
                _normalize_from_system_design(ctx.system_design, pattern=decision_inp.pattern)
                if ctx.system_design
                else NormalizedDesignInput()
            )
            merged = _merge_inputs(decision_inp, design_inp)
            if not merged.domain and ctx.requirements and ctx.requirements.domain_boundaries:
                merged.domain = ctx.requirements.domain_boundaries.primary_domain or ""
            return merged

        if isinstance(artifact, SolutionArchitectureDecision):
            return _normalize_from_decision(artifact)

        if isinstance(artifact, SystemDesignOutput):
            return _normalize_from_system_design(artifact)

        return NormalizedDesignInput()

    async def run(self, context: AgentContext) -> AgentResult:
        
        inp: NormalizedDesignInput = context.metadata.get(
            "design_input", NormalizedDesignInput()
        )
        solid_report: SOLIDComplianceReport | None = context.metadata.get(
            "solid_compliance_report"
        )

        try:
            report = await self.recommend(inp, solid_report=solid_report)
            return AgentResult(
                success=True,
                summary=report.analysis_summary,
                agent_name=self.name,
            )
        except Exception as exc:
            logger.exception("Design pattern recommendation failed")
            return AgentResult(
                success=False,
                summary="Design pattern recommendation failed.",
                agent_name=self.name,
                error=str(exc),
            )
