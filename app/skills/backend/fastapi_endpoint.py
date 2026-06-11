from typing import Any

from ..base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from ..registry import SkillRegistry


@SkillRegistry.register
class GenerateFastAPIEndpointSkill(BaseSkill):
    name = "backend.fastapi_endpoint"
    description = (
        "Generate a FastAPI router with full CRUD endpoints, Pydantic request/response schemas, "
        "dependency injection stubs, and OpenAPI documentation annotations."
    )
    category = SkillCategory.BACKEND
    tags = ["fastapi", "endpoint", "router", "pydantic", "crud", "rest", "api"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. user, product, order)"),
        SkillParameter(
            "operations",
            "Comma-separated CRUD operations to generate",
            required=False,
            default="create,read,update,delete,list",
        ),
        SkillParameter(
            "auth",
            "Authentication dependency to inject (e.g. oauth2_scheme, api_key, none)",
            required=False,
            default="none",
        ),
        SkillParameter(
            "prefix",
            "URL prefix for the router (e.g. /api/v1)",
            required=False,
            default="/api/v1",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        operations: str = "create,read,update,delete,list",
        auth: str = "none",
        prefix: str = "/api/v1",
        **_: Any,
    ) -> SkillResult:
        ops = {op.strip() for op in operations.split(",")}
        r = resource.lower()
        R = r.capitalize()
        plural = f"{r}s"

        auth_import = ""
        auth_dep = ""
        if auth != "none":
            auth_import = f"from app.core.security import {auth}\n"
            auth_dep = f", _token: str = Depends({auth})"

        schemas = (
            f"class {R}Base(BaseModel):\n"
            f"    name: str\n"
            f"    description: str | None = None\n\n"
            f"class {R}Create({R}Base):\n"
            f"    pass\n\n"
            f"class {R}Update(BaseModel):\n"
            f"    name: str | None = None\n"
            f"    description: str | None = None\n\n"
            f"class {R}Response({R}Base):\n"
            f"    id: int\n"
            f"    created_at: datetime\n"
            f"    updated_at: datetime\n\n"
            f"    model_config = ConfigDict(from_attributes=True)\n"
        )

        routes: list[str] = []

        if "list" in ops:
            routes.append(
                f'@router.get("/{plural}", response_model=list[{R}Response], summary="List {plural}")\n'
                f"async def list_{plural}(\n"
                f"    skip: int = Query(0, ge=0),\n"
                f"    limit: int = Query(20, ge=1, le=100),\n"
                f"    db: AsyncSession = Depends(get_db){auth_dep},\n"
                f") -> list[{R}Response]:\n"
                f"    result = await db.execute(select({R}Model).offset(skip).limit(limit))\n"
                f"    return list(result.scalars().all())\n"
            )

        if "read" in ops:
            routes.append(
                f'@router.get("/{plural}/{{item_id}}", response_model={R}Response, summary="Get {r} by id")\n'
                f"async def get_{r}(\n"
                f"    item_id: int,\n"
                f"    db: AsyncSession = Depends(get_db){auth_dep},\n"
                f") -> {R}Response:\n"
                f"    instance = await db.get({R}Model, item_id)\n"
                f"    if instance is None:\n"
                f'        raise HTTPException(status_code=404, detail="{R} not found")\n'
                f"    return instance\n"
            )

        if "create" in ops:
            routes.append(
                f'@router.post("/{plural}", response_model={R}Response, status_code=201, summary="Create {r}")\n'
                f"async def create_{r}(\n"
                f"    payload: {R}Create,\n"
                f"    db: AsyncSession = Depends(get_db){auth_dep},\n"
                f") -> {R}Response:\n"
                f"    instance = {R}Model(**payload.model_dump())\n"
                f"    db.add(instance)\n"
                f"    await db.commit()\n"
                f"    await db.refresh(instance)\n"
                f"    return instance\n"
            )

        if "update" in ops:
            routes.append(
                f'@router.patch("/{plural}/{{item_id}}", response_model={R}Response, summary="Update {r}")\n'
                f"async def update_{r}(\n"
                f"    item_id: int,\n"
                f"    payload: {R}Update,\n"
                f"    db: AsyncSession = Depends(get_db){auth_dep},\n"
                f") -> {R}Response:\n"
                f"    instance = await db.get({R}Model, item_id)\n"
                f"    if instance is None:\n"
                f'        raise HTTPException(status_code=404, detail="{R} not found")\n'
                f"    for field, value in payload.model_dump(exclude_unset=True).items():\n"
                f"        setattr(instance, field, value)\n"
                f"    await db.commit()\n"
                f"    await db.refresh(instance)\n"
                f"    return instance\n"
            )

        if "delete" in ops:
            routes.append(
                f'@router.delete("/{plural}/{{item_id}}", status_code=204, summary="Delete {r}")\n'
                f"async def delete_{r}(\n"
                f"    item_id: int,\n"
                f"    db: AsyncSession = Depends(get_db){auth_dep},\n"
                f") -> None:\n"
                f"    instance = await db.get({R}Model, item_id)\n"
                f"    if instance is None:\n"
                f'        raise HTTPException(status_code=404, detail="{R} not found")\n'
                f"    await db.delete(instance)\n"
                f"    await db.commit()\n"
            )

        routes_code = "\n\n".join(routes)

        code = (
            f"from datetime import datetime\n"
            f"from fastapi import APIRouter, Depends, HTTPException, Query\n"
            f"from pydantic import BaseModel, ConfigDict\n"
            f"from sqlalchemy import select\n"
            f"from sqlalchemy.ext.asyncio import AsyncSession\n"
            f"{auth_import}"
            f"from app.db.session import get_db\n"
            f"from app.models.{r} import {R} as {R}Model\n\n"
            f"router = APIRouter(prefix=\"{prefix}/{plural}\", tags=[\"{R}\"])\n\n"
            f"# ── Schemas ──────────────────────────────────────────────────────────────────\n\n"
            f"{schemas}\n"
            f"# ── Routes ───────────────────────────────────────────────────────────────────\n\n"
            f"{routes_code}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated FastAPI router for `{R}` with operations: {', '.join(sorted(ops))}",
            artifacts=[
                CodeArtifact(
                    filename=f"app/routers/{r}.py",
                    content=code,
                    language="python",
                    description=f"FastAPI router for {R} resource",
                )
            ],
            dependencies=["fastapi", "pydantic", "sqlalchemy[asyncio]", "asyncpg"],
            instructions=[
                f"Register router in main.py: app.include_router({r}.router)",
                f"Create app/models/{r}.py with the {R} SQLAlchemy model",
                "Configure get_db dependency in app/db/session.py",
            ],
            next_steps=[
                f"Generate SQLAlchemy model: backend.sqlalchemy_model resource={r}",
                f"Generate repository pattern: backend.repository_pattern resource={r}",
            ],
        )
