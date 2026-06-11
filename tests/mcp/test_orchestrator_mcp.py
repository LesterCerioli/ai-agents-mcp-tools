"""Tests for OrchestratorMCPServer — verifies tools and session management."""
import json
import pytest

from app.mcp.orchestrator_mcp import create_orchestrator_mcp
from app.architecture.workflow_coordinator import WorkflowCoordinator
from app.agents.orchestrator import AgentOrchestrator


def _setup():
    orchestrator = AgentOrchestrator(llm=None)
    coordinator = WorkflowCoordinator(orchestrator=orchestrator, llm=None)
    sessions: dict = {}
    mcp = create_orchestrator_mcp(coordinator, orchestrator, sessions)
    return mcp, sessions


def _extract_tool_text(result) -> str:
    """FastMCP.call_tool() returns (content_list, ...). Extract text from first content item."""
    content_list = result[0]
    return content_list[0].text


def _extract_resource_text(result) -> str:
    """FastMCP.read_resource() returns list[ReadResourceContents]. Extract .content."""
    return result[0].content


@pytest.mark.asyncio
async def test_orchestrator_mcp_lists_tools():
    mcp, _ = _setup()
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "run_full_workflow" in tool_names
    assert "run_architecture_pipeline" in tool_names
    assert "get_workflow_status" in tool_names
    assert "list_agents" in tool_names


@pytest.mark.asyncio
async def test_list_agents_tool():
    mcp, _ = _setup()
    result = await mcp.call_tool("list_agents", {})
    agents = json.loads(_extract_tool_text(result))
    assert "backend" in agents
    assert "nextjs" in agents
    assert "design" in agents
    assert agents["backend"]["skill_count"] > 0


@pytest.mark.asyncio
async def test_get_workflow_status_unknown_session():
    mcp, _ = _setup()
    result = await mcp.call_tool("get_workflow_status", {"session_id": "nonexistent-id"})
    data = json.loads(_extract_tool_text(result))
    assert "error" in data


@pytest.mark.asyncio
async def test_run_architecture_pipeline_unknown_session():
    mcp, _ = _setup()
    result = await mcp.call_tool(
        "run_architecture_pipeline",
        {"session_id": "does-not-exist", "scope": "backend"},
    )
    data = json.loads(_extract_tool_text(result))
    assert "error" in data


@pytest.mark.asyncio
async def test_run_full_workflow_returns_workflow_output():
    mcp, _ = _setup()
    result = await mcp.call_tool(
        "run_full_workflow",
        {
            "objective": "Simple task management app with users and tasks. 5 engineers, startup.",
            "scope": "backend",
        },
    )
    data = json.loads(_extract_tool_text(result))
    assert "workflow_id" in data
    assert "session_id" in data
    assert "architecture_pattern" in data
    assert data["scope"] == "backend"
    assert isinstance(data["backend_artifacts"], list)


@pytest.mark.asyncio
async def test_orchestrator_sessions_resource():
    mcp, sessions = _setup()
    result = await mcp.read_resource("orchestrator://sessions")
    session_list = json.loads(_extract_resource_text(result))
    assert isinstance(session_list, list)


@pytest.mark.asyncio
async def test_orchestrator_agents_resource():
    mcp, _ = _setup()
    result = await mcp.read_resource("orchestrator://agents")
    agents_data = json.loads(_extract_resource_text(result))
    assert "backend" in agents_data
