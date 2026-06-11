import json
import pytest

from app.mcp.architecture_mcp import create_architecture_mcp


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mcp_and_sessions():
    sessions = {}
    mcp = create_architecture_mcp(sessions, llm=None)
    return mcp, sessions


async def _call(mcp, tool_name: str, **kwargs) -> dict:
    """Invoke a FastMCP tool by name and return parsed JSON."""
    tool_fn = next(t for t in mcp._tool_manager.list_tools() if t.name == tool_name)
    raw = await tool_fn.fn(**kwargs)
    return json.loads(raw)


# ── parse_requirements ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_parse_requirements_creates_session():
    mcp, sessions = _mcp_and_sessions()
    result = await _call(mcp, "parse_requirements", objective="Build an e-commerce platform")

    assert "session_id" in result
    assert result["session_id"] in sessions


@pytest.mark.asyncio
async def test_parse_requirements_returns_domain():
    mcp, sessions = _mcp_and_sessions()
    result = await _call(
        mcp, "parse_requirements",
        objective="Build an order management system for a retail company",
    )

    assert "domain" in result
    assert isinstance(result["domain"], str)


@pytest.mark.asyncio
async def test_parse_requirements_returns_next_action():
    mcp, sessions = _mcp_and_sessions()
    result = await _call(mcp, "parse_requirements", objective="Build a payment service")

    assert result["next_action"] in ("clarify_requirements", "decide_architecture")


@pytest.mark.asyncio
async def test_parse_requirements_resumes_existing_session():
    mcp, sessions = _mcp_and_sessions()
    first = await _call(mcp, "parse_requirements", objective="Build a CRM")
    sid = first["session_id"]

    second = await _call(
        mcp, "parse_requirements",
        objective="Add reporting features",
        session_id=sid,
    )
    assert second["session_id"] == sid
    assert len(sessions) == 1


# ── clarify_requirements ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_clarify_requirements_returns_error_for_unknown_session():
    mcp, _ = _mcp_and_sessions()
    result = await _call(
        mcp, "clarify_requirements",
        session_id="nonexistent-id",
        answer="We need high availability",
    )

    assert "error" in result


@pytest.mark.asyncio
async def test_clarify_requirements_updates_session():
    mcp, sessions = _mcp_and_sessions()
    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a logistics tracking system",
    )
    sid = parse_result["session_id"]

    clarify_result = await _call(
        mcp, "clarify_requirements",
        session_id=sid,
        answer="We expect 10,000 users with 99.9% uptime and PCI-DSS compliance",
    )

    assert clarify_result["session_id"] == sid
    assert "is_complete" in clarify_result
    assert "next_action" in clarify_result


# ── decide_architecture ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_decide_architecture_returns_error_without_session():
    mcp, _ = _mcp_and_sessions()
    result = await _call(mcp, "decide_architecture", session_id="missing")

    assert "error" in result


@pytest.mark.asyncio
async def test_decide_architecture_returns_error_without_requirements():
    from app.architecture.context.pipeline_context import PipelineContext

    mcp, sessions = _mcp_and_sessions()
    ctx = PipelineContext()
    sessions[ctx.session_id] = ctx

    result = await _call(mcp, "decide_architecture", session_id=ctx.session_id)
    assert "error" in result


@pytest.mark.asyncio
async def test_decide_architecture_produces_decision():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective=(
            "Build a microservices-based order management system "
            "with 100k users, Stripe integration, and 99.9% uptime"
        ),
    )
    sid = parse_result["session_id"]

    result = await _call(mcp, "decide_architecture", session_id=sid)

    assert "error" not in result
    assert "decision_id" in result
    assert "primary_pattern" in result
    assert result["primary_pattern"] is not None
    assert "design_confidence" in result
    assert "next_action" in result
    assert result["next_action"] == "select_design_partner"


@pytest.mark.asyncio
async def test_decide_architecture_stores_decision_in_session():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a hexagonal architecture for a payment service with domain isolation",
    )
    sid = parse_result["session_id"]
    await _call(mcp, "decide_architecture", session_id=sid)

    ctx = sessions[sid]
    assert ctx.decision is not None
    assert ctx.diagram is not None


@pytest.mark.asyncio
async def test_decide_architecture_includes_validation_results():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a user authentication service with identity and session management",
    )
    sid = parse_result["session_id"]
    result = await _call(mcp, "decide_architecture", session_id=sid)

    assert "validation_passed" in result
    assert isinstance(result["validation_passed"], bool)
    assert "validation_gaps" in result
    assert isinstance(result["validation_gaps"], list)


@pytest.mark.asyncio
async def test_decide_architecture_returns_components():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a notification dispatch system for email and SMS",
    )
    sid = parse_result["session_id"]
    result = await _call(mcp, "decide_architecture", session_id=sid)

    assert "components" in result
    assert isinstance(result["components"], list)
    for comp in result["components"]:
        assert "name" in comp
        assert "type" in comp
        assert "layer" in comp


# ── select_design_partner ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_select_design_partner_returns_error_without_decision():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a system",
    )
    sid = parse_result["session_id"]

    result = await _call(mcp, "select_design_partner", session_id=sid)
    assert "error" in result


@pytest.mark.asyncio
async def test_select_design_partner_returns_active_partner():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build an order management system with bounded contexts for cart and fulfillment",
    )
    sid = parse_result["session_id"]
    await _call(mcp, "decide_architecture", session_id=sid)
    result = await _call(mcp, "select_design_partner", session_id=sid)

    assert "error" not in result
    assert "active_partner" in result
    assert result["active_partner"] in (
        "hexagonal_design_partner",
        "microservices_design_partner",
        "monolith_design_partner",
    )


@pytest.mark.asyncio
async def test_select_design_partner_returns_backend_invocations():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a payment processing system with billing and refund bounded contexts",
    )
    sid = parse_result["session_id"]
    await _call(mcp, "decide_architecture", session_id=sid)
    result = await _call(mcp, "select_design_partner", session_id=sid)

    assert "recommended_backend_invocations" in result
    invocations = result["recommended_backend_invocations"]
    assert len(invocations) >= 1
    for inv in invocations:
        assert inv["mcp_server"] == "/mcp/backend"
        assert "tool" in inv
        assert "params" in inv
        assert "reason" in inv


@pytest.mark.asyncio
async def test_select_design_partner_returns_frontend_invocations():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a CRM system with contact and opportunity management",
    )
    sid = parse_result["session_id"]
    await _call(mcp, "decide_architecture", session_id=sid)
    result = await _call(mcp, "select_design_partner", session_id=sid)

    assert "recommended_frontend_agent" in result
    assert result["recommended_frontend_agent"] == "nextjs"
    assert "recommended_frontend_invocations" in result
    frontend = result["recommended_frontend_invocations"]
    assert len(frontend) >= 1
    for inv in frontend:
        assert inv["mcp_server"] == "/mcp/frontend"


@pytest.mark.asyncio
async def test_select_design_partner_returns_next_actions():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build an e-commerce platform with product catalog and shopping cart",
    )
    sid = parse_result["session_id"]
    await _call(mcp, "decide_architecture", session_id=sid)
    result = await _call(mcp, "select_design_partner", session_id=sid)

    assert "next_actions" in result
    assert len(result["next_actions"]) >= 1


# ── get_session_state ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_session_state_unknown_session():
    mcp, _ = _mcp_and_sessions()
    result = await _call(mcp, "get_session_state", session_id="unknown")

    assert "error" in result


@pytest.mark.asyncio
async def test_get_session_state_after_parse():
    mcp, sessions = _mcp_and_sessions()
    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a logistics platform",
    )
    sid = parse_result["session_id"]

    state = await _call(mcp, "get_session_state", session_id=sid)

    assert state["has_requirements"] is True
    assert state["has_decision"] is False
    assert state["has_system_design"] is False
    assert "parse_requirements" in state["stages_completed"]


@pytest.mark.asyncio
async def test_get_session_state_after_decide():
    mcp, sessions = _mcp_and_sessions()
    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a notification service with email and push channels",
    )
    sid = parse_result["session_id"]
    await _call(mcp, "decide_architecture", session_id=sid)

    state = await _call(mcp, "get_session_state", session_id=sid)

    assert state["has_decision"] is True
    assert state["has_diagram"] is True
    assert state["primary_pattern"] is not None
    assert "decide_architecture" in state["stages_completed"]


@pytest.mark.asyncio
async def test_get_session_state_after_full_pipeline():
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective="Build a user authentication service with identity and session domains",
    )
    sid = parse_result["session_id"]
    await _call(mcp, "decide_architecture", session_id=sid)
    await _call(mcp, "select_design_partner", session_id=sid)

    state = await _call(mcp, "get_session_state", session_id=sid)

    assert state["has_system_design"] is True
    assert state["active_design_partner"] is not None
    assert "select_design_partner" in state["stages_completed"]
    assert state["next_step"] == "invoke /mcp/backend and /mcp/frontend tools"


# ── Full pipeline flow ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_pipeline_order_management():
    """End-to-end: parse → decide → design partner for an order management system."""
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective=(
            "Build an order management system with cart, catalog, and fulfillment bounded contexts, "
            "integrating with Inventory and Shipping services in real time"
        ),
    )
    sid = parse_result["session_id"]
    assert "error" not in parse_result

    decide_result = await _call(mcp, "decide_architecture", session_id=sid)
    assert "error" not in decide_result
    assert decide_result["primary_pattern"] is not None

    design_result = await _call(mcp, "select_design_partner", session_id=sid)
    assert "error" not in design_result
    assert design_result["active_partner"] is not None
    assert len(design_result["recommended_backend_invocations"]) >= 1


@pytest.mark.asyncio
async def test_full_pipeline_payment_processing():
    """End-to-end: parse → decide → design partner for a payment processing system."""
    mcp, sessions = _mcp_and_sessions()

    parse_result = await _call(
        mcp, "parse_requirements",
        objective=(
            "Build a payment processing system with billing, refund, and reconciliation "
            "domains, integrating with Stripe and PayPal, PCI-DSS compliant"
        ),
    )
    sid = parse_result["session_id"]

    await _call(mcp, "decide_architecture", session_id=sid)
    design_result = await _call(mcp, "select_design_partner", session_id=sid)

    assert "error" not in design_result
    invocations = design_result["recommended_backend_invocations"]
    tools_called = [inv["tool"] for inv in invocations]
    assert "generate_backend_code" in tools_called


@pytest.mark.asyncio
async def test_full_pipeline_sessions_are_isolated():
    """Two parallel sessions must not interfere with each other."""
    mcp, sessions = _mcp_and_sessions()

    r1 = await _call(mcp, "parse_requirements", objective="Build a CRM system")
    r2 = await _call(mcp, "parse_requirements", objective="Build a logistics platform")

    assert r1["session_id"] != r2["session_id"]
    assert len(sessions) == 2
