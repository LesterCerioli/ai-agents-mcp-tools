"""Tests for BackendMCPServer — verifies tools are registered and callable."""
import json
import pytest

from app.mcp.backend_mcp import create_backend_mcp
from app.agents.backend_agent import BackendAgent


def _agent() -> BackendAgent:
    return BackendAgent(llm=None)


def _extract_tool_text(result) -> str:
    """FastMCP.call_tool() returns (content_list, ...). Extract text from first content item."""
    content_list = result[0]
    return content_list[0].text


def _extract_resource_text(result) -> str:
    """FastMCP.read_resource() returns list[ReadResourceContents]. Extract .content."""
    return result[0].content


@pytest.mark.asyncio
async def test_backend_mcp_lists_tools():
    agent = _agent()
    mcp = create_backend_mcp(agent)
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "generate_backend_code" in tool_names
    assert "apply_design_pattern" in tool_names
    assert "generate_docker_setup" in tool_names


@pytest.mark.asyncio
async def test_generate_backend_code_tool():
    agent = _agent()
    mcp = create_backend_mcp(agent)
    result = await mcp.call_tool(
        "generate_backend_code",
        {"resource": "user", "skills": ["endpoint"]},
    )
    data = json.loads(_extract_tool_text(result))
    assert isinstance(data, list)
    assert data[0]["skill"] == "backend.fastapi_endpoint"
    assert data[0]["success"] is True


@pytest.mark.asyncio
async def test_apply_design_pattern_tool():
    agent = _agent()
    mcp = create_backend_mcp(agent)
    result = await mcp.call_tool(
        "apply_design_pattern",
        {"pattern": "factory", "context": "Payment"},
    )
    data = json.loads(_extract_tool_text(result))
    assert data["success"] is True
    assert "PaymentFactory" in data["artifacts"][0]["content"]


@pytest.mark.asyncio
async def test_generate_docker_setup_tool():
    agent = _agent()
    mcp = create_backend_mcp(agent)
    result = await mcp.call_tool(
        "generate_docker_setup",
        {"app_name": "myapp", "services": "postgres,redis"},
    )
    data = json.loads(_extract_tool_text(result))
    assert data["success"] is True
    filenames = [a["filename"] for a in data["artifacts"]]
    assert "Dockerfile" in filenames
    assert "docker-compose.yml" in filenames


@pytest.mark.asyncio
async def test_backend_skills_resource():
    agent = _agent()
    mcp = create_backend_mcp(agent)
    result = await mcp.read_resource("backend://skills")
    skills = json.loads(_extract_resource_text(result))
    assert isinstance(skills, list)
    skill_names = [s["name"] for s in skills]
    assert "backend.fastapi_endpoint" in skill_names
    assert "backend.design_patterns" in skill_names
