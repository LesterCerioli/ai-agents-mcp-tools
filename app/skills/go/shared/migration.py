from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoGenerateMigrationSkill(BaseSkill):
    name = "go.generate_migration"
    description = (
        "Generate SQL migration files (up/down) compatible with golang-migrate/migrate/v4."
    )
    category = SkillCategory.GO
    tags = ["go", "migration", "sql", "postgres", "golang-migrate", "database"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. user, product, order)"),
        SkillParameter(
            "fields",
            "Comma-separated field definitions as name:type",
            required=False,
            default="name:varchar(255),description:text",
        ),
        SkillParameter(
            "version",
            "Migration version prefix (e.g. 000001)",
            required=False,
            default="000001",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        fields: str = "name:varchar(255),description:text",
        version: str = "000001",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower().replace("-", "_").replace(" ", "_")
        table = self._pluralize(r)
        parsed = self._parse_fields(fields)
        column_defs = self._render_columns(parsed)

        up_sql = (
            f"-- Migration: create {table} table\n"
            f"CREATE TABLE IF NOT EXISTS {table} (\n"
            f"    id          BIGSERIAL PRIMARY KEY,\n"
            f"{column_defs}"
            f"    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),\n"
            f"    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()\n"
            f");\n\n"
            f"CREATE INDEX IF NOT EXISTS idx_{table}_created_at ON {table} (created_at DESC);\n"
        )

        down_sql = (
            f"-- Rollback: drop {table} table\n"
            f"DROP TABLE IF EXISTS {table} CASCADE;\n"
        )

        migrate_main = (
            "package main\n\n"
            "import (\n"
            "\t\"log\"\n"
            "\t\"os\"\n\n"
            "\t\"github.com/golang-migrate/migrate/v4\"\n"
            "\t_ \"github.com/golang-migrate/migrate/v4/database/postgres\"\n"
            "\t_ \"github.com/golang-migrate/migrate/v4/source/file\"\n"
            ")\n\n"
            "func main() {\n"
            "\tdbURL := os.Getenv(\"DATABASE_URL\")\n"
            "\tif dbURL == \"\" {\n"
            "\t\tlog.Fatal(\"DATABASE_URL is required\")\n"
            "\t}\n\n"
            "\tm, err := migrate.New(\"file://migrations\", dbURL)\n"
            "\tif err != nil {\n"
            "\t\tlog.Fatalf(\"init migrate: %v\", err)\n"
            "\t}\n\n"
            "\tdirection := \"up\"\n"
            "\tif len(os.Args) > 1 {\n"
            "\t\tdirection = os.Args[1]\n"
            "\t}\n\n"
            "\tswitch direction {\n"
            "\tcase \"up\":\n"
            "\t\tif err := m.Up(); err != nil && err != migrate.ErrNoChange {\n"
            "\t\t\tlog.Fatalf(\"migrate up: %v\", err)\n"
            "\t\t}\n"
            "\tcase \"down\":\n"
            "\t\tif err := m.Down(); err != nil && err != migrate.ErrNoChange {\n"
            "\t\t\tlog.Fatalf(\"migrate down: %v\", err)\n"
            "\t\t}\n"
            "\tdefault:\n"
            "\t\tlog.Fatalf(\"unknown direction: %s\", direction)\n"
            "\t}\n"
            "\tlog.Println(\"migration complete\")\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated up/down SQL migrations for `{table}`",
            artifacts=[
                CodeArtifact(
                    filename=f"migrations/{version}_create_{table}.up.sql",
                    content=up_sql,
                    language="sql",
                    description=f"Create {table} table",
                ),
                CodeArtifact(
                    filename=f"migrations/{version}_create_{table}.down.sql",
                    content=down_sql,
                    language="sql",
                    description=f"Drop {table} table",
                ),
                CodeArtifact(
                    filename="cmd/migrate/main.go",
                    content=migrate_main,
                    language="go",
                    description="golang-migrate CLI runner",
                ),
            ],
            dependencies=["github.com/golang-migrate/migrate/v4"],
            instructions=[
                "Place SQL files in migrations/",
                "Run `make migrate-up` to apply",
                "Run `make migrate-down` to roll back",
            ],
        )

    def _pluralize(self, word: str) -> str:
        if word.endswith(("s", "x", "z", "ch", "sh")):
            return word + "es"
        if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
            return word[:-1] + "ies"
        return word + "s"

    def _parse_fields(self, fields: str) -> list[tuple[str, str]]:
        result = []
        for f in fields.split(","):
            f = f.strip()
            if ":" in f:
                name, typ = f.split(":", 1)
                result.append((name.strip(), typ.strip()))
        return result or [("name", "varchar(255)"), ("description", "text")]

    def _render_columns(self, fields: list[tuple[str, str]]) -> str:
        lines = []
        for name, sql_type in fields:
            nullable = "" if "varchar" in sql_type.lower() else ""
            lines.append(f"    {name:<16} {sql_type.upper()} NOT NULL{nullable},")
        return "\n".join(lines) + "\n"
