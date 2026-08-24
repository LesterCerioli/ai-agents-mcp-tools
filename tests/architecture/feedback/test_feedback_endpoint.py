
import asyncio

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.agents.orchestrator import AgentOrchestrator
from app.architecture.context.pipeline_context import PipelineContext
from app.architecture.feedback.engine import FeedbackEngine
from app.architecture.schemas.workflow import WorkflowScope
from app.architecture.workflow_coordinator import WorkflowCoordinator

_OBJECTIVE = (
    "E-commerce platform with catalog, cart, orders and payments. "
    "1M users, compliance required, team of 30."
)


@pytest.fixture
def make_client(monkeypatch):
    def _install(job_id: str) -> TestClient:
        orchestrator = AgentOrchestrator(llm=None)
        coordinator = WorkflowCoordinator(orchestrator=orchestrator, llm=None)
        engine = FeedbackEngine(coordinator=coordinator)
        ctx = PipelineContext()
        asyncio.run(
            coordinator.run(objective=_OBJECTIVE, scope=WorkflowScope.BACKEND, existing_context=ctx)
        )
        engine.register_job(job_id, ctx)
        monkeypatch.setattr(main_module, "_feedback_engine", engine)
        return TestClient(main_module.app)

    return _install


def test_feedback_endpoint_returns_feedback_processing_result(make_client):
    client = make_client("endpoint-job-1")

    response = client.post(
        "/architecture/feedback/endpoint-job-1",
        json={
            "target_section": "quality_scores",
            "feedback_type": "rejection",
            "feedback_text": "Scalability score is too low for 1M users.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "re_evaluated"
    assert data["iteration_id"]
    assert data["iteration_number"] == 1
    assert data["target_section"] == "quality_scores"
    assert data["feedback_type"] == "rejection"
    assert data["stages_re_evaluated"] == ["quality_assessment"]
    assert data["execution_log"]["entries"]
    assert data["estimated_reevaluation_seconds"] > 0.0


def test_feedback_endpoint_approval_round_trip(make_client):
    client = make_client("endpoint-job-2")

    response = client.post(
        "/architecture/feedback/endpoint-job-2",
        json={
            "target_section": "solid_findings",
            "feedback_type": "approval",
            "feedback_text": "Looks good.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
    assert data["stages_re_evaluated"] == []
    assert data["approved_sections"] == ["solid_findings"]


def test_feedback_endpoint_unknown_job_returns_404(make_client):
    client = make_client("endpoint-job-real")

    response = client.post(
        "/architecture/feedback/does-not-exist",
        json={"target_section": "quality_scores", "feedback_type": "rejection"},
    )

    assert response.status_code == 404


def test_feedback_endpoint_invalid_section_returns_400(make_client):
    client = make_client("endpoint-job-3")

    response = client.post(
        "/architecture/feedback/endpoint-job-3",
        json={"target_section": "bogus_section", "feedback_type": "rejection"},
    )

    assert response.status_code == 400
