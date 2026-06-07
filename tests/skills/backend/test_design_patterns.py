import pytest

from src.skills.backend.design_patterns import GenerateDesignPatternSkill
from src.skills.base import SkillCategory


def _skill() -> GenerateDesignPatternSkill:
    return GenerateDesignPatternSkill(llm=None)


def test_skill_metadata():
    s = _skill()
    assert s.name == "backend.design_patterns"
    assert s.category == SkillCategory.BACKEND
    assert "cqrs" in s.tags


@pytest.mark.asyncio
async def test_factory_pattern():
    result = await _skill().execute(pattern="factory", context="Payment")
    assert result.success
    code = result.artifacts[0].content
    assert "PaymentFactory" in code
    assert "abstractmethod" in code


@pytest.mark.asyncio
async def test_strategy_pattern():
    result = await _skill().execute(pattern="strategy", context="Pricing")
    assert result.success
    code = result.artifacts[0].content
    assert "PricingStrategy" in code
    assert "PricingContext" in code


@pytest.mark.asyncio
async def test_observer_pattern():
    result = await _skill().execute(pattern="observer", context="Order")
    assert result.success
    code = result.artifacts[0].content
    assert "OrderObserver" in code
    assert "OrderSubject" in code


@pytest.mark.asyncio
async def test_cqrs_pattern():
    result = await _skill().execute(pattern="cqrs", context="Order")
    assert result.success
    code = result.artifacts[0].content
    assert "CreateOrderCommand" in code
    assert "GetOrderQuery" in code
    assert "CommandBus" in code
    assert "QueryBus" in code


@pytest.mark.asyncio
async def test_unit_of_work_pattern():
    result = await _skill().execute(pattern="unit_of_work")
    assert result.success
    code = result.artifacts[0].content
    assert "UnitOfWork" in code
    assert "SQLAlchemyUnitOfWork" in code
    assert "commit" in code
    assert "rollback" in code


@pytest.mark.asyncio
async def test_event_bus_pattern():
    result = await _skill().execute(pattern="event_bus")
    assert result.success
    code = result.artifacts[0].content
    assert "InMemoryEventBus" in code
    assert "subscribe" in code
    assert "publish" in code


@pytest.mark.asyncio
async def test_saga_pattern():
    result = await _skill().execute(pattern="saga", context="Order")
    assert result.success
    code = result.artifacts[0].content
    assert "OrderSaga" in code
    assert "execute" in code


@pytest.mark.asyncio
async def test_command_pattern():
    result = await _skill().execute(pattern="command", context="Order")
    assert result.success
    code = result.artifacts[0].content
    assert "CreateOrderCommand" in code
    assert "CommandBus" in code


@pytest.mark.asyncio
async def test_unknown_pattern_returns_failure():
    result = await _skill().execute(pattern="unknown_xyz")
    assert not result.success
    assert result.error is not None
    assert "unknown_xyz" in result.error
