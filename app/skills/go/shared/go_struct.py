from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoStructSkill(BaseSkill):
    name = "go.go_struct"
    description = (
        "Generate Go domain structs and request/response DTOs with json, validate, "
        "and db struct tags."
    )
    category = SkillCategory.GO
    tags = ["go", "struct", "domain", "dto", "model", "pydantic", "schema"]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. user, product, order)"),
        SkillParameter(
            "fields",
            "Comma-separated field definitions as name:type (e.g. name:string,email:string,age:int)",
            required=False,
            default="name:string,description:string",
        ),
        SkillParameter("package_name", "Go package name", required=False, default="domain"),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        fields: str = "name:string,description:string",
        package_name: str = "domain",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower().replace("-", "_").replace(" ", "_")
        R = r.capitalize()

        parsed = self._parse_fields(fields)
        struct_fields = self._render_struct_fields(parsed)
        create_fields = self._render_create_fields(parsed)
        update_fields = self._render_update_fields(parsed)
        response_fields = self._render_response_fields(parsed)

        code = (
            f"package {package_name}\n\n"
            "import \"time\"\n\n"
            f"// {R} is the domain entity.\n"
            f"type {R} struct {{\n"
            f"\tID          int64     `json:\"id\"          db:\"id\"`\n"
            f"{struct_fields}"
            f"\tCreatedAt   time.Time `json:\"created_at\"  db:\"created_at\"`\n"
            f"\tUpdatedAt   time.Time `json:\"updated_at\"  db:\"updated_at\"`\n"
            f"}}\n\n"
            f"// Create{R}Request is the DTO for creating a {r}.\n"
            f"type Create{R}Request struct {{\n"
            f"{create_fields}"
            f"}}\n\n"
            f"// Update{R}Request is the DTO for updating a {r}.\n"
            f"type Update{R}Request struct {{\n"
            f"{update_fields}"
            f"}}\n\n"
            f"// {R}Response is the DTO returned to the client.\n"
            f"type {R}Response struct {{\n"
            f"\tID        int64  `json:\"id\"`\n"
            f"{response_fields}"
            f"\tCreatedAt string `json:\"created_at\"`\n"
            f"\tUpdatedAt string `json:\"updated_at\"`\n"
            f"}}\n\n"
            f"// From{R} converts a domain entity to the response DTO.\n"
            f"func From{R}(e *{R}) {R}Response {{\n"
            f"\treturn {R}Response{{\n"
            f"\t\tID:        e.ID,\n"
            + self._render_response_mapping(parsed, R)
            + f"\t\tCreatedAt: e.CreatedAt.Format(time.RFC3339),\n"
            f"\t\tUpdatedAt: e.UpdatedAt.Format(time.RFC3339),\n"
            f"\t}}\n"
            f"}}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated domain structs + DTOs for `{R}`",
            artifacts=[
                CodeArtifact(
                    filename=f"internal/domain/{r}.go",
                    content=code,
                    language="go",
                    description=f"Domain entity and DTOs for {R}",
                )
            ],
            instructions=[
                f"Place in internal/domain/{r}.go",
                "Add additional validation tags as needed",
            ],
            next_steps=[
                f"go.repository resource={resource}",
                f"go.service resource={resource}",
            ],
        )

    def _parse_fields(self, fields: str) -> list[tuple[str, str]]:
        result = []
        for f in fields.split(","):
            f = f.strip()
            if ":" in f:
                name, typ = f.split(":", 1)
                result.append((name.strip(), typ.strip()))
        return result or [("name", "string"), ("description", "string")]

    def _go_type(self, t: str) -> str:
        mapping = {
            "string": "string",
            "int": "int64",
            "int64": "int64",
            "float": "float64",
            "bool": "bool",
            "time": "time.Time",
        }
        return mapping.get(t.lower(), "string")

    def _render_struct_fields(self, fields: list[tuple[str, str]]) -> str:
        lines = []
        for name, typ in fields:
            n = name.capitalize()
            gt = self._go_type(typ)
            tag = f'`json:"{name}" db:"{name}" validate:"required"`'
            lines.append(f"\t{n:<12} {gt:<10} {tag}")
        return "\n".join(lines) + "\n"

    def _render_create_fields(self, fields: list[tuple[str, str]]) -> str:
        lines = []
        for name, typ in fields:
            n = name.capitalize()
            gt = self._go_type(typ)
            tag = f'`json:"{name}" validate:"required"`'
            lines.append(f"\t{n:<12} {gt:<10} {tag}")
        return "\n".join(lines) + "\n"

    def _render_update_fields(self, fields: list[tuple[str, str]]) -> str:
        lines = []
        for name, typ in fields:
            n = name.capitalize()
            gt = self._go_type(typ)
            ptr = "*" + gt if gt != "string" else "*string"
            tag = f'`json:"{name}"`'
            lines.append(f"\t{n:<12} {ptr:<12} {tag}")
        return "\n".join(lines) + "\n"

    def _render_response_fields(self, fields: list[tuple[str, str]]) -> str:
        lines = []
        for name, typ in fields:
            n = name.capitalize()
            gt = self._go_type(typ)
            tag = f'`json:"{name}"`'
            lines.append(f"\t{n:<12} {gt:<10} {tag}")
        return "\n".join(lines) + "\n"

    def _render_response_mapping(self, fields: list[tuple[str, str]], R: str) -> str:
        lines = []
        for name, _ in fields:
            n = name.capitalize()
            lines.append(f"\t\t{n}:        e.{n},")
        return "\n".join(lines) + "\n"
