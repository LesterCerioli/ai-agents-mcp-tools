
import difflib
import json
import time
import uuid
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from pydantic import BaseModel

from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.schemas.feedback import (
    STAGE_PIPELINE_ORDER,
    ArchitectureFeedback,
    ArchitectureStage,
    ConvergenceWarning,
    FeedbackProcessingResult,
    FeedbackType,
    IterationRecord,
    PipelineExecutionLog,
    SectionDiff,
    StageExecutionEntry,
    StageExecutionStatus,
    TargetSection,
)
from app.architecture.workflow_coordinator import WorkflowCoordinator

_SECTION_STAGES: dict[TargetSection, tuple[ArchitectureStage, ...]] = {
    TargetSection.SOLUTION_STRATEGY: (
        ArchitectureStage.SOLUTION_STRATEGY,
        ArchitectureStage.FLOW_DIAGRAM,
        ArchitectureStage.VALIDATION,
    ),
    TargetSection.DESIGN_PARTNER_SELECTION: (ArchitectureStage.DESIGN_PARTNER,),
    TargetSection.SOLID_FINDINGS: (ArchitectureStage.SOLID_ANALYSIS,),
    TargetSection.PATTERN_RECOMMENDATIONS: (ArchitectureStage.PATTERN_RECOMMENDATION,),
    TargetSection.QUALITY_SCORES: (ArchitectureStage.QUALITY_ASSESSMENT,),
}

_SECTION_DOWNSTREAM: dict[TargetSection, tuple[TargetSection, ...]] = {
    TargetSection.SOLUTION_STRATEGY: (
        TargetSection.DESIGN_PARTNER_SELECTION,
        TargetSection.SOLID_FINDINGS,
        TargetSection.PATTERN_RECOMMENDATIONS,
        TargetSection.QUALITY_SCORES,
    ),
    TargetSection.DESIGN_PARTNER_SELECTION: (
        TargetSection.SOLID_FINDINGS,
        TargetSection.PATTERN_RECOMMENDATIONS,
        TargetSection.QUALITY_SCORES,
    ),
    TargetSection.SOLID_FINDINGS: (
        TargetSection.PATTERN_RECOMMENDATIONS,
        TargetSection.QUALITY_SCORES,
    ),
    TargetSection.PATTERN_RECOMMENDATIONS: (TargetSection.QUALITY_SCORES,),
    TargetSection.QUALITY_SCORES: (),
}

_STAGE_OWNER_SECTION: dict[ArchitectureStage, TargetSection] = {
    stage: section
    for section, stages in _SECTION_STAGES.items()
    for stage in stages
}

_DEFAULT_STAGE_SECONDS: dict[ArchitectureStage, float] = {
    ArchitectureStage.REQUIREMENTS_PARSE: 1.0,
    ArchitectureStage.SOLUTION_STRATEGY: 2.0,
    ArchitectureStage.FLOW_DIAGRAM: 1.5,
    ArchitectureStage.VALIDATION: 0.5,
    ArchitectureStage.DESIGN_PARTNER: 3.0,
    ArchitectureStage.SOLID_ANALYSIS: 2.0,
    ArchitectureStage.PATTERN_RECOMMENDATION: 1.5,
    ArchitectureStage.QUALITY_ASSESSMENT: 2.0,
}


def _default_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()



_VOLATILE_KEYS = frozenset({
    "decision_id",
    "diagram_id",
    "design_id",
    "plan_id",
    "report_id",
    "session_id",
    "workflow_id",
    "iteration_id",
    "generated_at",
    "created_at",
    "updated_at",
    "timestamp",
})


def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _canonicalize(v) for k, v in value.items() if k not in _VOLATILE_KEYS}
    if isinstance(value, list):
        return [_canonicalize(item) for item in value]
    return value


def _serialize_output(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, BaseModel):
        payload = _canonicalize(value.model_dump(mode="json"))
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return json.dumps(str(value), sort_keys=True, ensure_ascii=False, default=str)


def _unified_diff(previous: str, new: str) -> str:
    if previous == new:
        return ""
    diff = difflib.unified_diff(
        previous.splitlines(),
        new.splitlines(),
        fromfile="previous",
        tofile="re-evaluated",
        lineterm="",
    )
    return "\n".join(diff)


@dataclass
class JobState:
    """Iteration history for one architecture job."""

    job_id: str
    snapshots: list[PipelineContext] = field(default_factory=list)
    iterations: list[IterationRecord] = field(default_factory=list)
    section_history: dict[TargetSection, list[str]] = field(default_factory=dict)
    approved_sections: set[TargetSection] = field(default_factory=set)
    stage_duration_avg: dict[ArchitectureStage, float] = field(
        default_factory=lambda: dict(_DEFAULT_STAGE_SECONDS)
    )

    @property
    def latest(self) -> PipelineContext:
        return self.snapshots[-1]

    def record_section_output(self, section: TargetSection, serialized: str) -> None:
        self.section_history.setdefault(section, []).append(serialized)

    def last_section_output(self, section: TargetSection) -> str | None:
        history = self.section_history.get(section)
        return history[-1] if history else None


class FeedbackEngine:
    
    def __init__(
        self,
        coordinator: WorkflowCoordinator,
        similarity_threshold: float = 0.95,
        convergence_window: int = 3,
        similarity_fn: Callable[[str, str], float] = _default_similarity,
    ) -> None:
        self._coordinator = coordinator
        self._similarity_threshold = similarity_threshold
        self._convergence_window = convergence_window
        self._similarity_fn = similarity_fn
        self._jobs: dict[str, JobState] = {}

    
    def register_job(self, job_id: str, context: PipelineContext) -> JobState:
        state = JobState(job_id=job_id)
        snapshot = deepcopy(context)
        state.snapshots.append(snapshot)
        for section in TargetSection:
            serialized = _serialize_output(self._section_output(snapshot, section))
            state.record_section_output(section, serialized)
        self._jobs[job_id] = state
        return state

    def get_job(self, job_id: str) -> JobState | None:
        return self._jobs.get(job_id)

    
    async def submit(self, job_id: str, feedback: ArchitectureFeedback) -> FeedbackProcessingResult:
        state = self._jobs.get(job_id)
        if state is None:
            raise KeyError(f"Job '{job_id}' not found.")

        if feedback.feedback_type == FeedbackType.APPROVAL:
            return self._process_approval(state, feedback)

        
        state.approved_sections.discard(feedback.target_section)

        working = deepcopy(state.latest)
        self._apply_feedback_constraints(working, feedback)

        plan = self._build_plan(state, feedback.target_section)
        preserved_entries = self._build_preserved_entries(state, working, plan)

        estimated = sum(state.stage_duration_avg.get(stage, 1.0) for stage in plan)

        entries: list[StageExecutionEntry] = []
        started = time.perf_counter()
        for stage in plan:
            t0 = time.perf_counter()
            working = await self._coordinator.run_stage(stage, working)
            duration = time.perf_counter() - t0
            previous_avg = state.stage_duration_avg.get(stage, duration)
            state.stage_duration_avg[stage] = previous_avg * 0.7 + duration * 0.3
            entries.append(
                StageExecutionEntry(
                    stage=stage,
                    status=StageExecutionStatus.EXECUTED,
                    duration_seconds=round(duration, 6),
                    detail=(
                        f"Re-evaluated due to {feedback.feedback_type.value} "
                        f"on '{feedback.target_section.value}'."
                    ),
                )
            )
        actual_duration = time.perf_counter() - started

        all_entries = sorted(
            [*entries, *preserved_entries], key=lambda e: STAGE_PIPELINE_ORDER.index(e.stage)
        )

        evaluated_sections = self._sections_for_stages(plan)
        diffs = self._diff_evaluated_sections(state, working, evaluated_sections)
        warnings = self._detect_convergence(state, feedback.target_section)

        iteration_id = str(uuid.uuid4())
        iteration_number = len(state.iterations) + 1
        execution_log = PipelineExecutionLog(
            job_id=job_id, iteration_id=iteration_id, entries=all_entries
        )
        record = IterationRecord(
            iteration_id=iteration_id,
            iteration_number=iteration_number,
            feedback=feedback,
            execution_log=execution_log,
            section_diffs=diffs,
            convergence_warnings=warnings,
            approved_sections=sorted(state.approved_sections, key=lambda s: s.value),
            status="re_evaluated",
        )
        state.iterations.append(record)
        state.snapshots.append(deepcopy(working))

        return FeedbackProcessingResult(
            job_id=job_id,
            iteration_id=iteration_id,
            iteration_number=iteration_number,
            status=record.status,
            target_section=feedback.target_section,
            feedback_type=feedback.feedback_type,
            stages_re_evaluated=[
                e.stage for e in all_entries if e.status == StageExecutionStatus.EXECUTED
            ],
            stages_preserved=[
                e.stage for e in all_entries if e.status == StageExecutionStatus.PRESERVED
            ],
            approved_sections=list(record.approved_sections),
            section_diffs=diffs,
            convergence_warnings=warnings,
            execution_log=execution_log,
            estimated_reevaluation_seconds=round(estimated, 4),
            actual_duration_seconds=round(actual_duration, 4),
        )

    
    def _process_approval(
        self, state: JobState, feedback: ArchitectureFeedback
    ) -> FeedbackProcessingResult:
        
        state.approved_sections.add(feedback.target_section)

        iteration_id = str(uuid.uuid4())
        iteration_number = len(state.iterations) + 1
        execution_log = PipelineExecutionLog(job_id=state.job_id, iteration_id=iteration_id)
        record = IterationRecord(
            iteration_id=iteration_id,
            iteration_number=iteration_number,
            feedback=feedback,
            execution_log=execution_log,
            approved_sections=sorted(state.approved_sections, key=lambda s: s.value),
            status="approved",
        )
        state.iterations.append(record)
        state.snapshots.append(deepcopy(state.latest))

        return FeedbackProcessingResult(
            job_id=state.job_id,
            iteration_id=iteration_id,
            iteration_number=iteration_number,
            status=record.status,
            target_section=feedback.target_section,
            feedback_type=feedback.feedback_type,
            approved_sections=list(record.approved_sections),
            execution_log=execution_log,
            estimated_reevaluation_seconds=0.0,
        )

    
    def _build_plan(self, state: JobState, target: TargetSection) -> list[ArchitectureStage]:
        """Minimum set of stages to re-run: the target's own stages plus every
        unapproved downstream section's stages."""
        stages: set[ArchitectureStage] = set(_SECTION_STAGES[target])
        for downstream in _SECTION_DOWNSTREAM[target]:
            if downstream not in state.approved_sections:
                stages.update(_SECTION_STAGES[downstream])
        return sorted(stages, key=STAGE_PIPELINE_ORDER.index)

    def _sections_for_stages(self, plan: list[ArchitectureStage]) -> set[TargetSection]:
        return {_STAGE_OWNER_SECTION[stage] for stage in plan}

    def _build_preserved_entries(
        self, state: JobState, ctx: PipelineContext, plan: list[ArchitectureStage]
    ) -> list[StageExecutionEntry]:
        """Record every stage with existing output that is intentionally skipped."""
        entries: list[StageExecutionEntry] = []

        def _add(stage: ArchitectureStage, has_output: bool, owner: TargetSection | None) -> None:
            if stage in plan or not has_output:
                return
            if owner is not None and owner in state.approved_sections:
                detail = f"'{owner.value}' is approved; previously generated output preserved."
            else:
                detail = "Not affected by this feedback; previously generated output preserved."
            entries.append(
                StageExecutionEntry(stage=stage, status=StageExecutionStatus.PRESERVED, detail=detail)
            )

        _add(ArchitectureStage.REQUIREMENTS_PARSE, ctx.requirements is not None, None)
        _add(
            ArchitectureStage.SOLUTION_STRATEGY,
            ctx.decision is not None,
            TargetSection.SOLUTION_STRATEGY,
        )
        _add(ArchitectureStage.FLOW_DIAGRAM, ctx.diagram is not None, TargetSection.SOLUTION_STRATEGY)
        _add(
            ArchitectureStage.VALIDATION,
            ctx.metadata.get("validation_report") is not None,
            TargetSection.SOLUTION_STRATEGY,
        )
        _add(
            ArchitectureStage.DESIGN_PARTNER,
            ctx.system_design is not None,
            TargetSection.DESIGN_PARTNER_SELECTION,
        )
        _add(
            ArchitectureStage.SOLID_ANALYSIS,
            ctx.metadata.get("solid_compliance_report") is not None,
            TargetSection.SOLID_FINDINGS,
        )
        _add(
            ArchitectureStage.PATTERN_RECOMMENDATION,
            ctx.metadata.get("pattern_recommendation_report") is not None,
            TargetSection.PATTERN_RECOMMENDATIONS,
        )
        _add(
            ArchitectureStage.QUALITY_ASSESSMENT,
            ctx.metadata.get("quality_assessment_report") is not None,
            TargetSection.QUALITY_SCORES,
        )
        return entries

    
    def _apply_feedback_constraints(self, ctx: PipelineContext, feedback: ArchitectureFeedback) -> None:
        if feedback.constraint_additions:
            constraints = ctx.metadata.setdefault("feedback_constraints", [])
            constraints.extend(feedback.constraint_additions)
        ctx.add_turn(
            "user",
            f"[feedback:{feedback.target_section.value}:{feedback.feedback_type.value}] "
            f"{feedback.feedback_text}",
        )

    def _section_output(self, ctx: PipelineContext, section: TargetSection) -> Any:
        if section == TargetSection.SOLUTION_STRATEGY:
            return ctx.decision
        if section == TargetSection.DESIGN_PARTNER_SELECTION:
            return ctx.system_design
        if section == TargetSection.SOLID_FINDINGS:
            return ctx.metadata.get("solid_compliance_report")
        if section == TargetSection.PATTERN_RECOMMENDATIONS:
            return ctx.metadata.get("pattern_recommendation_report")
        return ctx.metadata.get("quality_assessment_report")

    def _diff_evaluated_sections(
        self, state: JobState, working: PipelineContext, evaluated: set[TargetSection]
    ) -> list[SectionDiff]:
        diffs: list[SectionDiff] = []
        for section in TargetSection:
            if section not in evaluated:
                continue
            new_serialized = _serialize_output(self._section_output(working, section))
            previous = state.last_section_output(section)
            previous_serialized = previous if previous is not None else "null"
            similarity = round(self._similarity_fn(previous_serialized, new_serialized), 6)
            state.record_section_output(section, new_serialized)
            diffs.append(
                SectionDiff(
                    section=section,
                    changed=new_serialized != previous_serialized,
                    similarity=similarity,
                    previous_output=previous_serialized,
                    new_output=new_serialized,
                    unified_diff=_unified_diff(previous_serialized, new_serialized),
                )
            )
        return diffs

    
    def _detect_convergence(self, state: JobState, section: TargetSection) -> list[ConvergenceWarning]:
        
        submitted_outputs = state.section_history.get(section, [])[1:]
        window = self._convergence_window
        if len(submitted_outputs) < window:
            return []
        recent = submitted_outputs[-window:]
        similarities = [
            self._similarity_fn(recent[i], recent[i + 1]) for i in range(len(recent) - 1)
        ]
        if min(similarities) < self._similarity_threshold:
            return []
        return [
            ConvergenceWarning(
                section=section,
                consecutive_similar_outputs=len(recent),
                similarity_threshold=self._similarity_threshold,
                message=(
                    f"{len(recent)} consecutive re-evaluations of '{section.value}' produced "
                    f"outputs within the {self._similarity_threshold:.2f} similarity threshold. "
                    f"The pipeline appears to have converged; consider resolving the remaining "
                    f"concerns manually."
                ),
            )
        ]
