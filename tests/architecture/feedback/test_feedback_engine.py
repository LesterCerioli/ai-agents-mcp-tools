
import pytest
from pydantic import ValidationError

from app.agents.orchestrator import AgentOrchestrator
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.feedback.engine import FeedbackEngine
from app.architecture.schemas.feedback import (
    ArchitectureFeedback,
    ArchitectureStage,
    FeedbackType,
    TargetSection,
)
from app.architecture.schemas.workflow import WorkflowScope
from app.architecture.workflow_coordinator import WorkflowCoordinator

_OBJECTIVE = (
    "Build a fintech SaaS with user accounts and transactions. "
    "Needs compliance, 10k users, team of 20."
)


def _engine(**kwargs) -> tuple[WorkflowCoordinator, FeedbackEngine]:
    orchestrator = AgentOrchestrator(llm=None)
    coordinator = WorkflowCoordinator(orchestrator=orchestrator, llm=None)
    return coordinator, FeedbackEngine(coordinator=coordinator, **kwargs)


async def _seed_job(coordinator: WorkflowCoordinator, engine: FeedbackEngine, job_id: str = "job-1"):
    ctx = PipelineContext()
    await coordinator.run(objective=_OBJECTIVE, scope=WorkflowScope.BACKEND, existing_context=ctx)
    engine.register_job(job_id, ctx)
    return job_id


def _feedback(
    section: TargetSection,
    feedback_type: FeedbackType = FeedbackType.REJECTION,
    **overrides,
) -> ArchitectureFeedback:
    payload = {
        "target_section": section,
        "feedback_type": feedback_type,
        "feedback_text": f"Please revisit {section.value}",
        "constraint_additions": [],
    }
    payload.update(overrides)
    return ArchitectureFeedback(**payload)


def test_architecture_feedback_schema_accepts_valid_payload():
    fb = ArchitectureFeedback(
        target_section=TargetSection.SOLID_FINDINGS,
        feedback_type=FeedbackType.REFINEMENT,
        feedback_text="Too many god classes.",
        constraint_additions=["Extract a LedgerService."],
    )
    assert fb.target_section == TargetSection.SOLID_FINDINGS
    assert fb.constraint_additions == ["Extract a LedgerService."]


@pytest.mark.parametrize("field", ["target_section", "feedback_type"])
def test_architecture_feedback_schema_rejects_invalid_enums(field: str):
    with pytest.raises(ValidationError):
        ArchitectureFeedback(**{field: "not-a-valid-value", "feedback_text": "x"})



@pytest.mark.asyncio
async def test_rejection_on_quality_scores_reruns_only_quality_stage():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)

    result = await engine.submit(job_id, _feedback(TargetSection.QUALITY_SCORES))

    assert result.status == "re_evaluated"
    assert result.stages_re_evaluated == [ArchitectureStage.QUALITY_ASSESSMENT]
    executed = result.execution_log.executed_stages()
    assert executed == [ArchitectureStage.QUALITY_ASSESSMENT]
    preserved = result.execution_log.preserved_stages()
    assert ArchitectureStage.DESIGN_PARTNER in preserved
    assert ArchitectureStage.SOLUTION_STRATEGY in preserved
    assert ArchitectureStage.REQUIREMENTS_PARSE in preserved



@pytest.mark.asyncio
async def test_refinement_on_pattern_recommendations_reruns_pattern_and_quality():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)

    result = await engine.submit(
        job_id,
        _feedback(
            TargetSection.PATTERN_RECOMMENDATIONS,
            FeedbackType.REFINEMENT,
            constraint_additions=["Prefer strategy pattern over conditionals."],
        ),
    )

    assert result.stages_re_evaluated == [
        ArchitectureStage.PATTERN_RECOMMENDATION,
        ArchitectureStage.QUALITY_ASSESSMENT,
    ]
    # SOLID findings are upstream of patterns → must be preserved.
    assert ArchitectureStage.SOLID_ANALYSIS not in result.stages_re_evaluated
    assert ArchitectureStage.SOLID_ANALYSIS in result.stages_preserved



@pytest.mark.asyncio
async def test_rejection_on_solution_strategy_reruns_full_downstream_chain():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)

    result = await engine.submit(job_id, _feedback(TargetSection.SOLUTION_STRATEGY))

    assert result.stages_re_evaluated == [
        ArchitectureStage.SOLUTION_STRATEGY,
        ArchitectureStage.FLOW_DIAGRAM,
        ArchitectureStage.VALIDATION,
        ArchitectureStage.DESIGN_PARTNER,
        ArchitectureStage.SOLID_ANALYSIS,
        ArchitectureStage.PATTERN_RECOMMENDATION,
        ArchitectureStage.QUALITY_ASSESSMENT,
    ]
    assert result.stages_preserved == [ArchitectureStage.REQUIREMENTS_PARSE]
    assert result.actual_duration_seconds > 0.0



@pytest.mark.asyncio
async def test_approval_marks_section_and_skips_later_reevaluation():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)

    approval = await engine.submit(
        job_id, _feedback(TargetSection.DESIGN_PARTNER_SELECTION, FeedbackType.APPROVAL)
    )
    assert approval.status == "approved"
    assert approval.stages_re_evaluated == []
    assert len(approval.execution_log.entries) == 0
    assert TargetSection.DESIGN_PARTNER_SELECTION in approval.approved_sections

    rejection = await engine.submit(job_id, _feedback(TargetSection.QUALITY_SCORES))
    assert ArchitectureStage.DESIGN_PARTNER not in rejection.stages_re_evaluated
    assert ArchitectureStage.DESIGN_PARTNER in rejection.stages_preserved
    approved_entry = next(
        e
        for e in rejection.execution_log.entries
        if e.stage == ArchitectureStage.DESIGN_PARTNER
    )
    assert "approved" in approved_entry.detail.lower()



@pytest.mark.asyncio
async def test_strategy_rejection_preserves_all_approved_downstream_sections():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)

    for section in (
        TargetSection.DESIGN_PARTNER_SELECTION,
        TargetSection.SOLID_FINDINGS,
        TargetSection.PATTERN_RECOMMENDATIONS,
        TargetSection.QUALITY_SCORES,
    ):
        await engine.submit(job_id, _feedback(section, FeedbackType.APPROVAL))

    result = await engine.submit(job_id, _feedback(TargetSection.SOLUTION_STRATEGY))

    assert result.stages_re_evaluated == [
        ArchitectureStage.SOLUTION_STRATEGY,
        ArchitectureStage.FLOW_DIAGRAM,
        ArchitectureStage.VALIDATION,
    ]
    assert set(result.stages_preserved) == {
        ArchitectureStage.REQUIREMENTS_PARSE,
        ArchitectureStage.DESIGN_PARTNER,
        ArchitectureStage.SOLID_ANALYSIS,
        ArchitectureStage.PATTERN_RECOMMENDATION,
        ArchitectureStage.QUALITY_ASSESSMENT,
    }



@pytest.mark.asyncio
async def test_iteration_history_tracks_snapshots_and_accurate_diffs():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)
    state = engine.get_job(job_id)
    assert state is not None
    assert len(state.snapshots) == 1

    first = await engine.submit(job_id, _feedback(TargetSection.QUALITY_SCORES))
    second = await engine.submit(
        job_id,
        _feedback(TargetSection.PATTERN_RECOMMENDATIONS, FeedbackType.REFINEMENT),
    )

    assert len(state.snapshots) == 3
    assert [r.iteration_number for r in state.iterations] == [1, 2]
    assert first.iteration_id != second.iteration_id

    
    quality_diff = next(d for d in first.section_diffs if d.section == TargetSection.QUALITY_SCORES)
    assert quality_diff.changed is False
    assert quality_diff.similarity == pytest.approx(1.0)
    
    evaluated = {d.section for d in second.section_diffs}
    assert evaluated == {TargetSection.PATTERN_RECOMMENDATIONS, TargetSection.QUALITY_SCORES}
    pattern_diff = second.section_diffs[0]
    assert pattern_diff.previous_output != ""
    assert pattern_diff.new_output == pattern_diff.previous_output


@pytest.mark.asyncio
async def test_diff_records_real_changes_when_output_mutates():
    coordinator, engine = _engine(similarity_threshold=1.1)  # never converge-warn here
    job_id = await _seed_job(coordinator, engine)
    state = engine.get_job(job_id)
    assert state is not None

    
    from copy import deepcopy

    latest = deepcopy(state.latest)
    assert latest.decision is not None
    latest.decision.domain = "logistics"
    state.snapshots[-1] = latest

    result = await engine.submit(job_id, _feedback(TargetSection.DESIGN_PARTNER_SELECTION))

    diff = result.section_diffs[0]
    assert diff.section == TargetSection.DESIGN_PARTNER_SELECTION
    assert diff.changed is True
    assert diff.similarity < 1.0
    assert diff.unified_diff != ""
    assert diff.previous_output != diff.new_output


@pytest.mark.asyncio
async def test_convergence_warning_emitted_after_three_similar_outputs():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)

    results = [
        await engine.submit(job_id, _feedback(TargetSection.SOLID_FINDINGS, FeedbackType.REFINEMENT))
        for _ in range(3)
    ]

    assert results[0].convergence_warnings == []
    assert results[1].convergence_warnings == []
    warnings = results[2].convergence_warnings
    assert len(warnings) == 1
    warning = warnings[0]
    assert warning.section == TargetSection.SOLID_FINDINGS
    assert warning.consecutive_similar_outputs == 3
    assert "manually" in warning.message.lower()


@pytest.mark.asyncio
async def test_no_convergence_warning_when_outputs_differ():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)
    state = engine.get_job(job_id)
    assert state is not None

    history = state.section_history[TargetSection.QUALITY_SCORES]
    history.extend(["output-a", "output-b", "output-c"])

    warnings = engine._detect_convergence(state, TargetSection.QUALITY_SCORES)
    assert warnings == []


@pytest.mark.asyncio
async def test_constraint_additions_are_recorded_in_new_snapshot():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)
    state = engine.get_job(job_id)
    assert state is not None

    await engine.submit(
        job_id,
        _feedback(
            TargetSection.SOLID_FINDINGS,
            FeedbackType.REFINEMENT,
            feedback_text="Split the payment module.",
            constraint_additions=["No class longer than 200 lines.", "Extract PaymentGateway port."],
        ),
    )

    ctx = state.latest
    assert ctx.metadata["feedback_constraints"] == [
        "No class longer than 200 lines.",
        "Extract PaymentGateway port.",
    ]
    last_turn = ctx.conversation_history[-1]
    assert last_turn["role"] == "user"
    assert "solid_findings" in last_turn["content"]
    assert "Split the payment module." in last_turn["content"]


@pytest.mark.asyncio
async def test_unknown_job_raises_key_error():
    coordinator, engine = _engine()
    with pytest.raises(KeyError):
        await engine.submit("missing-job", _feedback(TargetSection.QUALITY_SCORES))


@pytest.mark.asyncio
async def test_estimated_reevaluation_time_is_positive_and_improves_with_history():
    coordinator, engine = _engine()
    job_id = await _seed_job(coordinator, engine)

    first = await engine.submit(job_id, _feedback(TargetSection.QUALITY_SCORES))
    assert first.estimated_reevaluation_seconds > 0.0
    assert first.actual_duration_seconds >= 0.0

    second = await engine.submit(job_id, _feedback(TargetSection.QUALITY_SCORES))
    assert second.estimated_reevaluation_seconds > 0.0
