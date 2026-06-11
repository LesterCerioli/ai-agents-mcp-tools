import pytest

from src.skills.backend.repository_pattern import GenerateRepositoryPatternSkill
from src.skills.base import SkillCategory


def _skill() -> GenerateRepositoryPatternSkill:
    return GenerateRepositoryPatternSkill(llm=None)


def test_skill_metadata():
    s = _skill()
    assert s.name == "backend.repository_pattern"
    assert s.category == SkillCategory.BACKEND
    assert "repository" in s.tags


@pytest.mark.asyncio
async def test_generates_two_artifacts():
    result = await _skill().execute(resource="user")
    assert result.success
    assert len(result.artifacts) == 2


@pytest.mark.asyncio
async def test_interface_is_abstract():
    result = await _skill().execute(resource="order")
    interface_code = result.artifacts[0].content
    assert "abstractmethod" in interface_code
    assert "OrderRepository" in interface_code


@pytest.mark.asyncio
async def test_implementation_uses_sqlalchemy():
    result = await _skill().execute(resource="product")
    impl_code = result.artifacts[1].content
    assert "AsyncSession" in impl_code
    assert "SQLAlchemyProductRepository" in impl_code


@pytest.mark.asyncio
async def test_selected_operations_only():
    result = await _skill().execute(resource="item", operations="get_by_id,create")
    interface_code = result.artifacts[0].content
    assert "get_by_id" in interface_code
    assert "create" in interface_code
    assert "delete" not in interface_code


@pytest.mark.asyncio
async def test_extra_queries_added():
    result = await _skill().execute(resource="user", extra_queries="get_by_email,find_by_username")
    interface_code = result.artifacts[0].content
    assert "get_by_email" in interface_code
    assert "find_by_username" in interface_code


@pytest.mark.asyncio
async def test_file_names_match_resource():
    result = await _skill().execute(resource="customer")
    filenames = [a.filename for a in result.artifacts]
    assert any("customer_repository" in f for f in filenames)
    assert any("sqlalchemy_customer_repository" in f for f in filenames)
