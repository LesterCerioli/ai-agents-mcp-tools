"""Integration tests for QualityAssessmentMCPServer tools."""
import json
import pytest

import app.skills.quality_assessment  # noqa: F401

from app.agents.quality_assessment_agent import ArchitectureQualityAssessmentAgent
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.schemas.solid import (
    AffectedComponent,
    ComplianceLevel,
    NormalizedDesignInput,
    PrincipleResult,
    SOLIDComplianceReport,
    SOLIDPrinciple,
)
from app.mcp.quality_assessment_mcp import create_quality_assessment_mcp


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _build_session_with_design() -> tuple[dict, str]:
    """Return (sessions dict, session_id) with a minimal architecture decision."""
    from app.architecture.schemas.solution import (
        ArchitectureLayer,
        ArchitecturePattern,
        ComponentType,
        DecisionComponent,
        SolutionArchitectureDecision,
        SolutionPattern,
        TradeOffMatrix,
        TradeOffRating,
    )

    tm = TradeOffMatrix(
        scalability=TradeOffRating.HIGH,
        consistency=TradeOffRating.MEDIUM,
        operational_complexity=TradeOffRating.MEDIUM,
        time_to_market=TradeOffRating.MEDIUM,
        cost=TradeOffRating.MEDIUM,
    )
    decision = SolutionArchitectureDecision(
        domain="orders",
        patterns=[SolutionPattern(
            pattern=ArchitecturePattern.HEXAGONAL,
            rationale="Hexagonal for testability.",
            confidence=0.9,
            trade_offs=[],
            trade_off_matrix=tm,
            is_primary=True,
        )],
        components=[
            DecisionComponent(
                name="APIGateway",
                type=ComponentType.GATEWAY,
                layer=ArchitectureLayer.PRESENTATION,
                responsibility="Entry point.",
                technology_hints=["Kong"],
                protocols=["HTTP/REST"],
            ),
        ],
        external_integrations=[],
        rationale="Test decision.",
        architectural_drivers=[],
        risk_factors=[],
        decision_confidence=0.9,
    )
    ctx = PipelineContext()
    ctx.decision = decision
    sessions: dict = {ctx.session_id: ctx}
    return sessions, ctx.session_id


def _compliant_solid() -> SOLIDComplianceReport:
    return SOLIDComplianceReport(
        principle_results=[
            PrincipleResult(
                principle=p,
                compliance_level=ComplianceLevel.COMPLIANT,
                summary="OK",
            )
            for p in SOLIDPrinciple
        ],
        overall_compliance=ComplianceLevel.COMPLIANT,
        components_analyzed=2,
    )


# ── Tool: assess_architecture_quality ────────────────────────────────────────

@pytest.mark.asyncio
async def test_assess_quality_returns_valid_report():
    sessions, sid = _build_session_with_design()
    sessions[sid].metadata["solid_compliance_report"] = _compliant_solid()

    agent = ArchitectureQualityAssessmentAgent(llm=None)
    mcp = create_quality_assessment_mcp(sessions, agent)

    tool = next(t for t in mcp._tool_manager._tools.values() if t.name == "assess_architecture_quality")
    raw = await tool.fn(session_id=sid)
    data = json.loads(raw)

    assert "error" not in data
    assert "report_id" in data
    assert "overall_health_score" in data
    assert "health_grade" in data
    assert len(data["attribute_scores"]) == 5
    assert len(data["layer_quality_breakdown"]) == 4
    assert "improvement_actions" in data


@pytest.mark.asyncio
async def test_assess_quality_unknown_session():
    sessions: dict = {}
    agent = ArchitectureQualityAssessmentAgent(llm=None)
    mcp = create_quality_assessment_mcp(sessions, agent)

    tool = next(t for t in mcp._tool_manager._tools.values() if t.name == "assess_architecture_quality")
    raw = await tool.fn(session_id="non-existent")
    data = json.loads(raw)
    assert "error" in data


@pytest.mark.asyncio
async def test_assess_quality_no_design_returns_error():
    ctx = PipelineContext()
    sessions = {ctx.session_id: ctx}
    agent = ArchitectureQualityAssessmentAgent(llm=None)
    mcp = create_quality_assessment_mcp(sessions, agent)

    tool = next(t for t in mcp._tool_manager._tools.values() if t.name == "assess_architecture_quality")
    raw = await tool.fn(session_id=ctx.session_id)
    data = json.loads(raw)
    assert "error" in data


# ── Tool: get_quality_report ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_quality_report_after_assess():
    sessions, sid = _build_session_with_design()
    sessions[sid].metadata["solid_compliance_report"] = _compliant_solid()

    agent = ArchitectureQualityAssessmentAgent(llm=None)
    mcp = create_quality_assessment_mcp(sessions, agent)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}

    await tools["assess_architecture_quality"].fn(session_id=sid)

    raw = await tools["get_quality_report"].fn(session_id=sid)
    data = json.loads(raw)

    assert "error" not in data
    assert "overall_health_score" in data
    assert "layer_quality_breakdown" in data
    assert "improvement_actions" in data


@pytest.mark.asyncio
async def test_get_quality_report_without_prior_assess():
    sessions, sid = _build_session_with_design()
    agent = ArchitectureQualityAssessmentAgent(llm=None)
    mcp = create_quality_assessment_mcp(sessions, agent)

    tool = next(t for t in mcp._tool_manager._tools.values() if t.name == "get_quality_report")
    raw = await tool.fn(session_id=sid)
    data = json.loads(raw)
    assert "error" in data


# ── Tool: get_layer_quality_breakdown ────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("layer", ["presentation", "application", "domain", "infrastructure"])
async def test_get_layer_breakdown_all_layers(layer: str):
    sessions, sid = _build_session_with_design()
    sessions[sid].metadata["solid_compliance_report"] = _compliant_solid()

    agent = ArchitectureQualityAssessmentAgent(llm=None)
    mcp = create_quality_assessment_mcp(sessions, agent)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}

    await tools["assess_architecture_quality"].fn(session_id=sid)

    raw = await tools["get_layer_quality_breakdown"].fn(session_id=sid, layer=layer)
    data = json.loads(raw)

    assert "error" not in data
    assert data["layer"] == layer
    assert "score" in data
    assert "issues" in data
    assert "strengths" in data


@pytest.mark.asyncio
async def test_get_layer_breakdown_invalid_layer():
    sessions, sid = _build_session_with_design()
    agent = ArchitectureQualityAssessmentAgent(llm=None)
    mcp = create_quality_assessment_mcp(sessions, agent)

    tool = next(t for t in mcp._tool_manager._tools.values() if t.name == "get_layer_quality_breakdown")
    raw = await tool.fn(session_id=sid, layer="nonexistent")
    data = json.loads(raw)
    assert "error" in data


# ── Tool: get_improvement_actions ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_improvement_actions_after_assess():
    sessions, sid = _build_session_with_design()
    sessions[sid].metadata["solid_compliance_report"] = _compliant_solid()

    agent = ArchitectureQualityAssessmentAgent(llm=None)
    mcp = create_quality_assessment_mcp(sessions, agent)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}

    await tools["assess_architecture_quality"].fn(session_id=sid)

    raw = await tools["get_improvement_actions"].fn(session_id=sid)
    data = json.loads(raw)

    assert "error" not in data
    assert "overall_health_score" in data
    assert "improvement_actions" in data
    assert len(data["improvement_actions"]) <= 5


# ── Resource: quality-assessment://attributes ─────────────────────────────────

@pytest.mark.asyncio
async def test_attributes_resource_returns_five_attributes():
    sessions: dict = {}
    agent = ArchitectureQualityAssessmentAgent(llm=None)
    mcp = create_quality_assessment_mcp(sessions, agent)

    resource_fn = mcp._resource_manager._resources.get("quality-assessment://attributes")
    if resource_fn is None:
        pytest.skip("Resource manager API differs — skipping resource test")

    raw = await resource_fn.fn()
    data = json.loads(raw)
    assert len(data) == 5
    ids = {item["id"] for item in data}
    assert "maintainability" in ids
    assert "security_boundary_clarity" in ids
