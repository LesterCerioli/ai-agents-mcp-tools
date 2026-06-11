from typing import Any

from ..base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from ..registry import SkillRegistry


@SkillRegistry.register
class GeneratePytestSuiteSkill(BaseSkill):
    name = "backend.pytest_suite"
    description = (
        "Generate a pytest test suite with async fixtures, TestClient integration tests, "
        "repository unit tests, and factory_boy factories for a FastAPI/SQLAlchemy resource."
    )
    category = SkillCategory.BACKEND
    tags = ["pytest", "testing", "test", "integration-test", "fixtures", "factory-boy", "fastapi"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. user, product, order)"),
        SkillParameter(
            "operations",
            "Comma-separated CRUD operations to test",
            required=False,
            default="create,read,update,delete,list",
        ),
        SkillParameter(
            "with_auth",
            "Include authentication header in requests (true/false)",
            required=False,
            default="false",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        operations: str = "create,read,update,delete,list",
        with_auth: str = "false",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower()
        R = r.capitalize()
        plural = f"{r}s"
        ops = {op.strip() for op in operations.split(",")}
        auth_header = 'headers={"Authorization": "Bearer test-token"}' if with_auth.lower() == "true" else ""

        conftest_code = (
            f"import pytest\n"
            f"import pytest_asyncio\n"
            f"from httpx import AsyncClient, ASGITransport\n"
            f"from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker\n"
            f"from app.models.{r} import Base\n"
            f"from app.db.session import get_db\n"
            f"from app.api.main import app\n\n"
            f"TEST_DATABASE_URL = 'sqlite+aiosqlite:///./test.db'\n\n\n"
            f"@pytest.fixture(scope='session')\n"
            f"def event_loop_policy():\n"
            f"    import asyncio\n"
            f"    return asyncio.DefaultEventLoopPolicy()\n\n\n"
            f"@pytest_asyncio.fixture(scope='function')\n"
            f"async def db_session():\n"
            f"    engine = create_async_engine(TEST_DATABASE_URL, echo=False)\n"
            f"    async with engine.begin() as conn:\n"
            f"        await conn.run_sync(Base.metadata.create_all)\n"
            f"    session_factory = async_sessionmaker(engine, expire_on_commit=False)\n"
            f"    async with session_factory() as session:\n"
            f"        yield session\n"
            f"    async with engine.begin() as conn:\n"
            f"        await conn.run_sync(Base.metadata.drop_all)\n"
            f"    await engine.dispose()\n\n\n"
            f"@pytest_asyncio.fixture(scope='function')\n"
            f"async def client(db_session: AsyncSession):\n"
            f"    async def override_get_db():\n"
            f"        yield db_session\n"
            f"    app.dependency_overrides[get_db] = override_get_db\n"
            f"    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c:\n"
            f"        yield c\n"
            f"    app.dependency_overrides.clear()\n"
        )

        factory_code = (
            f"import factory\n"
            f"from factory.alchemy import SQLAlchemyModelFactory\n"
            f"from app.models.{r} import {R}\n\n\n"
            f"class {R}Factory(SQLAlchemyModelFactory):\n"
            f"    class Meta:\n"
            f"        model = {R}\n"
            f"        sqlalchemy_session_persistence = 'commit'\n\n"
            f"    name = factory.Faker('name')\n"
            f"    description = factory.Faker('sentence')\n"
        )

        test_methods: list[str] = []

        if "create" in ops:
            test_methods.append(
                f"async def test_create_{r}(client):\n"
                f'    payload = {{"name": "Test {R}", "description": "Test description"}}\n'
                f"    response = await client.post('/{plural}', json=payload{', ' + auth_header if auth_header else ''})\n"
                f"    assert response.status_code == 201\n"
                f"    data = response.json()\n"
                f"    assert data['name'] == payload['name']\n"
                f"    assert 'id' in data\n"
            )

        if "list" in ops:
            test_methods.append(
                f"async def test_list_{plural}(client):\n"
                f"    response = await client.get('/{plural}'{', ' + auth_header if auth_header else ''})\n"
                f"    assert response.status_code == 200\n"
                f"    assert isinstance(response.json(), list)\n"
            )

        if "read" in ops:
            test_methods.append(
                f"async def test_get_{r}(client):\n"
                f'    create_resp = await client.post("/{plural}", json={{"name": "Target"}})\n'
                f"    item_id = create_resp.json()['id']\n"
                f"    response = await client.get(f'/{plural}/{{item_id}}'{', ' + auth_header if auth_header else ''})\n"
                f"    assert response.status_code == 200\n"
                f"    assert response.json()['id'] == item_id\n"
            )
            test_methods.append(
                f"async def test_get_{r}_not_found(client):\n"
                f"    response = await client.get('/{plural}/99999'{', ' + auth_header if auth_header else ''})\n"
                f"    assert response.status_code == 404\n"
            )

        if "update" in ops:
            test_methods.append(
                f"async def test_update_{r}(client):\n"
                f'    create_resp = await client.post("/{plural}", json={{"name": "Original"}})\n'
                f"    item_id = create_resp.json()['id']\n"
                f'    response = await client.patch(f"/{plural}/{{item_id}}", json={{"name": "Updated"}}{", " + auth_header if auth_header else ""})\n'
                f"    assert response.status_code == 200\n"
                f"    assert response.json()['name'] == 'Updated'\n"
            )

        if "delete" in ops:
            test_methods.append(
                f"async def test_delete_{r}(client):\n"
                f'    create_resp = await client.post("/{plural}", json={{"name": "ToDelete"}})\n'
                f"    item_id = create_resp.json()['id']\n"
                f"    response = await client.delete(f'/{plural}/{{item_id}}'{', ' + auth_header if auth_header else ''})\n"
                f"    assert response.status_code == 204\n"
                f"    get_resp = await client.get(f'/{plural}/{{item_id}}')\n"
                f"    assert get_resp.status_code == 404\n"
            )

        tests_code = (
            f"import pytest\n"
            f"from httpx import AsyncClient\n\n\n"
            + "\n\n".join(f"@pytest.mark.asyncio\n{m}" for m in test_methods)
            + "\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated pytest suite for `{R}` with {len(test_methods)} test cases",
            artifacts=[
                CodeArtifact(
                    filename="tests/conftest.py",
                    content=conftest_code,
                    language="python",
                    description="pytest fixtures with async TestClient and in-memory SQLite",
                ),
                CodeArtifact(
                    filename=f"tests/factories/{r}_factory.py",
                    content=factory_code,
                    language="python",
                    description=f"factory_boy factory for {R} model",
                ),
                CodeArtifact(
                    filename=f"tests/integration/test_{plural}.py",
                    content=tests_code,
                    language="python",
                    description=f"Integration tests for {R} CRUD endpoints",
                ),
            ],
            dev_dependencies=["pytest", "pytest-asyncio", "httpx", "aiosqlite", "factory-boy"],
            instructions=[
                "pip install -e '.[dev]'",
                "pytest tests/ -v",
                "pytest tests/ --cov=app --cov-report=html for coverage",
            ],
        )
