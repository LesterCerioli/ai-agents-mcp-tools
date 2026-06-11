from typing import Any

from ..base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from ..registry import SkillRegistry


@SkillRegistry.register
class GenerateRepositoryPatternSkill(BaseSkill):
    name = "backend.repository_pattern"
    description = (
        "Generate an abstract repository interface and its async SQLAlchemy implementation "
        "following the Repository pattern for clean separation between domain and persistence."
    )
    category = SkillCategory.BACKEND
    tags = ["repository", "design-pattern", "domain", "persistence", "sqlalchemy", "clean-architecture"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. user, product, order)"),
        SkillParameter(
            "operations",
            "Comma-separated operations to include",
            required=False,
            default="get_by_id,get_all,create,update,delete",
        ),
        SkillParameter(
            "extra_queries",
            "Comma-separated extra query methods (e.g. get_by_email, get_active, find_by_name)",
            required=False,
            default="",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        operations: str = "get_by_id,get_all,create,update,delete",
        extra_queries: str = "",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower()
        R = r.capitalize()
        ops = {op.strip() for op in operations.split(",")}
        extras = [q.strip() for q in extra_queries.split(",") if q.strip()]

        # ── Abstract interface ─────────────────────────────────────────────────
        abstract_methods: list[str] = []

        if "get_by_id" in ops:
            abstract_methods.append(
                f"    @abstractmethod\n"
                f"    async def get_by_id(self, id: int) -> {R} | None: ..."
            )
        if "get_all" in ops:
            abstract_methods.append(
                f"    @abstractmethod\n"
                f"    async def get_all(self, skip: int = 0, limit: int = 100) -> list[{R}]: ..."
            )
        if "create" in ops:
            abstract_methods.append(
                f"    @abstractmethod\n"
                f"    async def create(self, entity: {R}) -> {R}: ..."
            )
        if "update" in ops:
            abstract_methods.append(
                f"    @abstractmethod\n"
                f"    async def update(self, entity: {R}) -> {R}: ..."
            )
        if "delete" in ops:
            abstract_methods.append(
                f"    @abstractmethod\n"
                f"    async def delete(self, id: int) -> bool: ..."
            )
        for q in extras:
            abstract_methods.append(
                f"    @abstractmethod\n"
                f"    async def {q}(self, value: str) -> {R} | None: ..."
            )

        abstract_block = "\n\n".join(abstract_methods)

        interface_code = (
            f"from abc import ABC, abstractmethod\n"
            f"from app.models.{r} import {R}\n\n\n"
            f"class {R}Repository(ABC):\n\n"
            f"{abstract_block}\n"
        )

        # ── Concrete SQLAlchemy implementation ────────────────────────────────
        impl_methods: list[str] = []

        if "get_by_id" in ops:
            impl_methods.append(
                f"    async def get_by_id(self, id: int) -> {R} | None:\n"
                f"        return await self._session.get({R}, id)\n"
            )
        if "get_all" in ops:
            impl_methods.append(
                f"    async def get_all(self, skip: int = 0, limit: int = 100) -> list[{R}]:\n"
                f"        result = await self._session.execute(select({R}).offset(skip).limit(limit))\n"
                f"        return list(result.scalars().all())\n"
            )
        if "create" in ops:
            impl_methods.append(
                f"    async def create(self, entity: {R}) -> {R}:\n"
                f"        self._session.add(entity)\n"
                f"        await self._session.commit()\n"
                f"        await self._session.refresh(entity)\n"
                f"        return entity\n"
            )
        if "update" in ops:
            impl_methods.append(
                f"    async def update(self, entity: {R}) -> {R}:\n"
                f"        await self._session.merge(entity)\n"
                f"        await self._session.commit()\n"
                f"        await self._session.refresh(entity)\n"
                f"        return entity\n"
            )
        if "delete" in ops:
            impl_methods.append(
                f"    async def delete(self, id: int) -> bool:\n"
                f"        instance = await self.get_by_id(id)\n"
                f"        if instance is None:\n"
                f"            return False\n"
                f"        await self._session.delete(instance)\n"
                f"        await self._session.commit()\n"
                f"        return True\n"
            )
        for q in extras:
            field = q.replace("get_by_", "").replace("find_by_", "")
            impl_methods.append(
                f"    async def {q}(self, value: str) -> {R} | None:\n"
                f"        result = await self._session.execute(\n"
                f"            select({R}).where({R}.{field} == value)\n"
                f"        )\n"
                f"        return result.scalar_one_or_none()\n"
            )

        impl_block = "\n".join(impl_methods)

        implementation_code = (
            f"from sqlalchemy import select\n"
            f"from sqlalchemy.ext.asyncio import AsyncSession\n"
            f"from app.models.{r} import {R}\n"
            f"from app.repositories.{r}_repository import {R}Repository\n\n\n"
            f"class SQLAlchemy{R}Repository({R}Repository):\n\n"
            f"    def __init__(self, session: AsyncSession) -> None:\n"
            f"        self._session = session\n\n"
            f"{impl_block}"
        )

        return SkillResult(
            success=True,
            summary=f"Generated repository interface and SQLAlchemy implementation for `{R}`",
            artifacts=[
                CodeArtifact(
                    filename=f"app/repositories/{r}_repository.py",
                    content=interface_code,
                    language="python",
                    description=f"Abstract {R}Repository interface",
                ),
                CodeArtifact(
                    filename=f"app/repositories/sqlalchemy_{r}_repository.py",
                    content=implementation_code,
                    language="python",
                    description=f"SQLAlchemy async implementation of {R}Repository",
                ),
            ],
            dependencies=["sqlalchemy>=2.0", "asyncpg"],
            instructions=[
                f"Inject SQLAlchemy{R}Repository via FastAPI Depends: repo = Depends(get_{r}_repo)",
                f"Add factory function in app/dependencies.py: async def get_{r}_repo(db: AsyncSession = Depends(get_db)): return SQLAlchemy{R}Repository(db)",
            ],
            next_steps=[
                f"Generate endpoints: backend.fastapi_endpoint resource={r}",
                "Apply design patterns: backend.design_patterns pattern=unit_of_work",
            ],
        )
