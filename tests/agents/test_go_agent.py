import pytest

from app.agents.go_agent import GoAgent
from app.skills.base import SkillCategory


def _agent() -> GoAgent:
    return GoAgent(llm=None)


# ── Agent metadata ────────────────────────────────────────────────────────────

def test_agent_name():
    assert _agent().name == "go"


def test_agent_category():
    assert _agent().category == SkillCategory.GO


def test_agent_has_27_skills():
    agent = _agent()
    assert len(agent.available_skills) == 27


def test_agent_appears_in_orchestrator():
    from app.agents.orchestrator import AgentOrchestrator
    orch = AgentOrchestrator(llm=None)
    assert "go" in orch.agents


# ── Shared skills ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_setup_project():
    result = await _agent().execute_skill(
        "go.setup_project", module_name="github.com/org/app", app_name="myapp"
    )
    assert result.success
    assert len(result.artifacts) >= 1
    filenames = [a.filename for a in result.artifacts]
    assert any("go.mod" in f for f in filenames)
    assert all(a.language in ("go", "makefile") for a in result.artifacts)


@pytest.mark.asyncio
async def test_go_struct():
    result = await _agent().execute_skill("go.go_struct", resource="product")
    assert result.success
    assert len(result.artifacts) >= 1
    code = result.artifacts[0].content
    assert "Product" in code
    assert "CreateProductRequest" in code
    assert "ProductResponse" in code
    assert result.artifacts[0].language == "go"


@pytest.mark.asyncio
async def test_go_struct_custom_fields():
    result = await _agent().execute_skill(
        "go.go_struct", resource="order", fields="total:float,status:string"
    )
    assert result.success
    code = result.artifacts[0].content
    assert "Order" in code
    assert "Total" in code
    assert "Status" in code


@pytest.mark.asyncio
async def test_repository():
    result = await _agent().execute_skill(
        "go.repository", resource="user", module_name="github.com/org/app"
    )
    assert result.success
    assert len(result.artifacts) >= 2
    languages = {a.language for a in result.artifacts}
    assert "go" in languages


@pytest.mark.asyncio
async def test_service():
    result = await _agent().execute_skill(
        "go.service", resource="order", module_name="github.com/org/app"
    )
    assert result.success
    assert len(result.artifacts) >= 1
    code = result.artifacts[0].content
    assert "OrderService" in code
    assert "go" == result.artifacts[0].language


@pytest.mark.asyncio
async def test_docker_setup():
    result = await _agent().execute_skill("go.docker_setup", app_name="myapp", services="postgres,redis")
    assert result.success
    filenames = [a.filename for a in result.artifacts]
    assert any("Dockerfile" in f for f in filenames)
    assert any("docker-compose" in f for f in filenames)


@pytest.mark.asyncio
async def test_test_suite():
    result = await _agent().execute_skill(
        "go.test_suite", resource="product", module_name="github.com/org/app"
    )
    assert result.success
    assert len(result.artifacts) >= 2
    filenames = [a.filename for a in result.artifacts]
    assert any("mock" in f for f in filenames)
    assert any("test" in f for f in filenames)


@pytest.mark.asyncio
async def test_generate_migration():
    result = await _agent().execute_skill("go.generate_migration", resource="product")
    assert result.success
    filenames = [a.filename for a in result.artifacts]
    assert any(".up.sql" in f for f in filenames)
    assert any(".down.sql" in f for f in filenames)


@pytest.mark.asyncio
async def test_config():
    result = await _agent().execute_skill("go.config", app_name="myapp")
    assert result.success
    assert len(result.artifacts) >= 1
    code = result.artifacts[0].content
    assert "Config" in code
    assert "DATABASE_URL" in code


@pytest.mark.asyncio
async def test_logger():
    result = await _agent().execute_skill("go.logger")
    assert result.success
    assert len(result.artifacts) >= 1
    assert any("zap" in a.content for a in result.artifacts)


# ── Fiber skills ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_fiber_app():
    result = await _agent().execute_skill("go.fiber_app", app_name="myapp")
    assert result.success
    assert len(result.artifacts) >= 1
    code = result.artifacts[0].content
    assert "fiber" in code.lower()
    assert result.artifacts[0].language == "go"


@pytest.mark.asyncio
async def test_fiber_handler():
    result = await _agent().execute_skill("go.fiber_handler", resource="product")
    assert result.success
    code = result.artifacts[0].content
    assert "ProductHandler" in code
    assert "fiber.Ctx" in code


@pytest.mark.asyncio
async def test_fiber_routes():
    result = await _agent().execute_skill("go.fiber_routes", resource="product")
    assert result.success
    code = result.artifacts[0].content
    assert "RegisterProductRoutes" in code
    assert "fiber" in code.lower()


@pytest.mark.asyncio
async def test_fiber_middleware():
    result = await _agent().execute_skill("go.fiber_middleware")
    assert result.success
    code = result.artifacts[0].content
    assert "JWTAuth" in code


# ── Gin skills ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gin_app():
    result = await _agent().execute_skill("go.gin_app", app_name="myapp")
    assert result.success
    assert "gin" in result.artifacts[0].content.lower()


@pytest.mark.asyncio
async def test_gin_handler():
    result = await _agent().execute_skill("go.gin_handler", resource="order")
    assert result.success
    assert "OrderHandler" in result.artifacts[0].content
    assert "gin.Context" in result.artifacts[0].content


@pytest.mark.asyncio
async def test_gin_routes():
    result = await _agent().execute_skill("go.gin_routes", resource="order")
    assert result.success
    assert "RegisterOrderRoutes" in result.artifacts[0].content


@pytest.mark.asyncio
async def test_gin_middleware():
    result = await _agent().execute_skill("go.gin_middleware")
    assert result.success
    assert "JWTAuth" in result.artifacts[0].content


# ── Gorilla skills ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_gorilla_app():
    result = await _agent().execute_skill("go.gorilla_app", app_name="myapp")
    assert result.success
    assert "mux" in result.artifacts[0].content.lower()


@pytest.mark.asyncio
async def test_gorilla_handler():
    result = await _agent().execute_skill("go.gorilla_handler", resource="user")
    assert result.success
    assert "UserHandler" in result.artifacts[0].content
    assert "mux.Vars" in result.artifacts[0].content


@pytest.mark.asyncio
async def test_gorilla_routes():
    result = await _agent().execute_skill("go.gorilla_routes", resource="user")
    assert result.success
    assert "RegisterUserRoutes" in result.artifacts[0].content


# ── Echo skills ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_echo_app():
    result = await _agent().execute_skill("go.echo_app", app_name="myapp")
    assert result.success
    assert "echo" in result.artifacts[0].content.lower()


@pytest.mark.asyncio
async def test_echo_handler():
    result = await _agent().execute_skill("go.echo_handler", resource="product")
    assert result.success
    assert "ProductHandler" in result.artifacts[0].content
    assert "echo.Context" in result.artifacts[0].content


@pytest.mark.asyncio
async def test_echo_routes():
    result = await _agent().execute_skill("go.echo_routes", resource="product")
    assert result.success
    assert "RegisterProductRoutes" in result.artifacts[0].content


@pytest.mark.asyncio
async def test_echo_middleware():
    result = await _agent().execute_skill("go.echo_middleware")
    assert result.success
    assert "JWTAuth" in result.artifacts[0].content


# ── Chi skills ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chi_app():
    result = await _agent().execute_skill("go.chi_app", app_name="myapp")
    assert result.success
    assert "chi" in result.artifacts[0].content.lower()


@pytest.mark.asyncio
async def test_chi_handler():
    result = await _agent().execute_skill("go.chi_handler", resource="category")
    assert result.success
    assert "CategoryHandler" in result.artifacts[0].content
    assert "chi.URLParam" in result.artifacts[0].content


@pytest.mark.asyncio
async def test_chi_routes():
    result = await _agent().execute_skill("go.chi_routes", resource="category")
    assert result.success
    assert "RegisterCategoryRoutes" in result.artifacts[0].content


# ── Quick shortcut API ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_quick_shortcut_struct():
    result = await _agent().quick("struct", resource="invoice")
    assert result.success
    assert result.agent_name == "go"
    assert len(result.skill_results) == 1


@pytest.mark.asyncio
async def test_quick_shortcut_fiber_handler():
    result = await _agent().quick("fiber_handler", resource="invoice")
    assert result.success
    assert "InvoiceHandler" in result.skill_results[0].artifacts[0].content
