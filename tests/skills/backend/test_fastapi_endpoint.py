import pytest

from app.skills.backend.fastapi_endpoint import GenerateFastAPIEndpointSkill
from app.skills.base import SkillCategory


def _skill() -> GenerateFastAPIEndpointSkill:
    return GenerateFastAPIEndpointSkill(llm=None)


def test_skill_metadata():
    s = _skill()
    assert s.name == "backend.fastapi_endpoint"
    assert s.category == SkillCategory.BACKEND
    assert "fastapi" in s.tags


@pytest.mark.asyncio
async def test_default_crud_operations():
    result = await _skill().execute(resource="product")
    assert result.success
    assert len(result.artifacts) == 1
    code = result.artifacts[0].content
    assert "router" in code
    assert "products" in code
    assert "ProductCreate" in code
    assert "ProductResponse" in code


@pytest.mark.asyncio
async def test_selected_operations_only():
    result = await _skill().execute(resource="order", operations="create,list")
    assert result.success
    code = result.artifacts[0].content
    assert "create_order" in code
    assert "list_orders" in code
    assert "update_order" not in code
    assert "delete_order" not in code


@pytest.mark.asyncio
async def test_router_prefix_respected():
    result = await _skill().execute(resource="user", prefix="/api/v2")
    assert result.success
    assert "/api/v2" in result.artifacts[0].content


@pytest.mark.asyncio
async def test_artifact_filename_matches_resource():
    result = await _skill().execute(resource="invoice")
    assert result.artifacts[0].filename == "app/routers/invoice.py"


@pytest.mark.asyncio
async def test_dependencies_include_fastapi():
    result = await _skill().execute(resource="payment")
    assert any("fastapi" in dep for dep in result.dependencies)


@pytest.mark.asyncio
async def test_next_steps_suggest_model():
    result = await _skill().execute(resource="category")
    assert any("sqlalchemy_model" in step or "model" in step.lower() for step in result.next_steps)
