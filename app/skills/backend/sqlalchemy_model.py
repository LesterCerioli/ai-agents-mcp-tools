from typing import Any

from ..base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from ..registry import SkillRegistry


@SkillRegistry.register
class GenerateSQLAlchemyModelSkill(BaseSkill):
    name = "backend.sqlalchemy_model"
    description = (
        "Generate an async SQLAlchemy 2.0 ORM model with mapped columns, relationships, "
        "Alembic-ready table definition, and a matching async database session factory."
    )
    category = SkillCategory.BACKEND
    tags = ["sqlalchemy", "orm", "database", "model", "async", "alembic", "migration"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. user, product, order)"),
        SkillParameter(
            "fields",
            "Comma-separated fields with optional type annotation (e.g. name:str, price:float, is_active:bool)",
            required=False,
            default="name:str",
        ),
        SkillParameter(
            "relationships",
            "Comma-separated relationships (e.g. orders:Order:one-to-many, user:User:many-to-one)",
            required=False,
            default="",
        ),
        SkillParameter(
            "soft_delete",
            "Include soft-delete support (deleted_at column)",
            required=False,
            default="false",
        ),
    ]

    _TYPE_MAP: dict[str, tuple[str, str]] = {
        "str": ("String(255)", "str"),
        "string": ("String(255)", "str"),
        "text": ("Text", "str"),
        "int": ("Integer", "int"),
        "integer": ("Integer", "int"),
        "float": ("Float", "float"),
        "decimal": ("Numeric(10, 2)", "Decimal"),
        "bool": ("Boolean", "bool"),
        "boolean": ("Boolean", "bool"),
        "date": ("Date", "date"),
        "datetime": ("DateTime(timezone=True)", "datetime"),
        "uuid": ("UUID(as_uuid=True)", "uuid.UUID"),
        "json": ("JSON", "dict"),
    }

    def _parse_fields(self, fields_str: str) -> list[tuple[str, str, str]]:
        """Returns list of (name, sa_type, py_type)."""
        result = []
        for f in fields_str.split(","):
            f = f.strip()
            if not f:
                continue
            if ":" in f:
                fname, ftype = f.split(":", 1)
            else:
                fname, ftype = f, "str"
            sa_type, py_type = self._TYPE_MAP.get(ftype.lower(), ("String(255)", "str"))
            result.append((fname.strip(), sa_type, py_type))
        return result

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        fields: str = "name:str",
        relationships: str = "",
        soft_delete: str = "false",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower()
        R = r.capitalize()
        parsed_fields = self._parse_fields(fields)

        needs_decimal = any(f[2] == "Decimal" for f in parsed_fields)
        needs_uuid = any(f[2] == "uuid.UUID" for f in parsed_fields)
        needs_date = any(f[2] in ("date", "datetime") for f in parsed_fields)

        extra_imports: list[str] = []
        if needs_decimal:
            extra_imports.append("from decimal import Decimal")
        if needs_uuid:
            extra_imports.append("import uuid")
        if needs_date:
            extra_imports.append("from datetime import date, datetime")
        else:
            extra_imports.append("from datetime import datetime")

        columns = "\n".join(
            f"    {fname}: Mapped[{py_type}] = mapped_column({sa_type}, nullable=False)"
            for fname, sa_type, py_type in parsed_fields
        )

        rel_lines: list[str] = []
        rel_imports: list[str] = []
        for rel in (relationships or "").split(","):
            rel = rel.strip()
            if not rel:
                continue
            parts = rel.split(":")
            if len(parts) < 3:
                continue
            rel_name, rel_model, rel_type = parts[0], parts[1], parts[2]
            if "one-to-many" in rel_type:
                rel_lines.append(
                    f'    {rel_name}: Mapped[list["{rel_model}"]] = relationship(back_populates="{r}")'
                )
            elif "many-to-one" in rel_type:
                rel_lines.append(
                    f"    {rel_name}_id: Mapped[int] = mapped_column(ForeignKey(\"{rel_model.lower()}s.id\"))"
                )
                rel_lines.append(
                    f'    {rel_name}: Mapped["{rel_model}"] = relationship(back_populates="{r}s")'
                )
            rel_imports.append(rel_model)

        soft_delete_col = (
            "\n    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)"
            if soft_delete.lower() == "true"
            else ""
        )

        rel_block = ("\n" + "\n".join(rel_lines)) if rel_lines else ""

        model_code = (
            f"from datetime import datetime\n"
            f"{chr(10).join(extra_imports)}\n"
            f"from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text\n"
            f"from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship\n\n"
            f"class Base(DeclarativeBase):\n"
            f"    pass\n\n\n"
            f"class {R}(Base):\n"
            f'    __tablename__ = "{r}s"\n\n'
            f"    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)\n"
            f"{columns}\n"
            f"    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)\n"
            f"    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)"
            f"{soft_delete_col}"
            f"{rel_block}\n"
        )

        session_code = (
            "from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine\n"
            "from app.core.config import settings\n\n"
            "engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)\n"
            "AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)\n\n\n"
            "async def get_db():\n"
            "    async with AsyncSessionLocal() as session:\n"
            "        yield session\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated async SQLAlchemy 2.0 model for `{R}` with {len(parsed_fields)} column(s)",
            artifacts=[
                CodeArtifact(
                    filename=f"app/models/{r}.py",
                    content=model_code,
                    language="python",
                    description=f"SQLAlchemy ORM model for {R}",
                ),
                CodeArtifact(
                    filename="app/db/session.py",
                    content=session_code,
                    language="python",
                    description="Async SQLAlchemy session factory and get_db dependency",
                ),
            ],
            dependencies=["sqlalchemy>=2.0", "asyncpg", "alembic"],
            instructions=[
                "Set DATABASE_URL in .env: postgresql+asyncpg://user:pass@localhost/db",
                "Run: alembic init alembic && alembic revision --autogenerate -m 'init'",
                "Run: alembic upgrade head",
            ],
            next_steps=[
                f"Generate repository: backend.repository_pattern resource={r}",
                f"Generate endpoints: backend.fastapi_endpoint resource={r}",
            ],
        )
