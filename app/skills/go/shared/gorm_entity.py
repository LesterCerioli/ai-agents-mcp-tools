from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoGormEntitySkill(BaseSkill):
    """Generates GORM entity + service contract + DTOs following Medical-App-Core patterns.

    Produces three files per resource:
    - domain/entities/{resource}.go      — GORM model with UUID pk, timestamps, foreign keys
    - services/contracts/{resource}ContractService.go — service interface
    - domain/dtos/{resource}DTO.go       — InputDTO and DTO for inter-layer transfer
    """

    name = "go.gorm_entity"
    description = (
        "Generate a GORM entity (UUID primary key, timestamps, gorm tags), "
        "a service contract interface, and DTOs (InputDTO + DTO) following the "
        "Medical-App-Core layered pattern. "
        "Produces: domain/entities/{resource}.go, "
        "services/contracts/{resource}ContractService.go, "
        "domain/dtos/{resource}DTO.go."
    )
    category = SkillCategory.GO
    tags = [
        "go", "gorm", "entity", "model", "uuid", "postgres",
        "dto", "contract", "service", "ddd", "domain",
    ]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. patient, user, appointment)"),
        SkillParameter("module_name", "Go module name (e.g. github.com/org/my-service)"),
        SkillParameter(
            "fields",
            "Comma-separated field definitions as name:type "
            "(e.g. name:string,email:string,age:int,active:bool). "
            "Supported types: string, int, int64, float64, bool, time, uuid.",
            required=False,
            default="name:string,description:string",
        ),
        SkillParameter(
            "has_organization",
            "Add OrganizationID foreign key (true/false)",
            required=False,
            default="false",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        module_name: str = "github.com/org/app",
        fields: str = "name:string,description:string",
        has_organization: str = "false",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower().replace("-", "_").replace(" ", "_")
        R = r.capitalize()
        with_org = has_organization.lower() in ("true", "1", "yes")
        parsed = self._parse_fields(fields)

        entity_code = self._entity_go(r, R, parsed, module_name, with_org)
        contract_code = self._contract_go(r, R, module_name, parsed)

        return SkillResult(
            success=True,
            summary=f"Generated GORM entity and service contract (DTOs + interface) for `{R}`",
            artifacts=[
                CodeArtifact(
                    f"domain/entities/{r}.go",
                    entity_code,
                    "go",
                    f"GORM entity for {R} with UUID primary key",
                ),
                CodeArtifact(
                    f"services/contracts/{r}ContractService.go",
                    contract_code,
                    "go",
                    f"DTOs ({R}DTO, {R}InputDTO) and service contract interface for {R}",
                ),
            ],
            dependencies=[
                "gorm.io/gorm",
                "github.com/google/uuid",
            ],
            instructions=[
                f"Register &entities.{R}{{}} in initializers/migrations.go AutoMigrate call",
                f"Implement {R}ServiceContract in services/implementations/{r}Service.go",
                f"Add {R}Service to the Services struct in initializers/services.go",
            ],
            next_steps=[
                f"go.fiber_handler resource={resource} module_name={module_name}",
                f"go.fiber_routes resource={resource} module_name={module_name}",
                f"go.swagger_fiber module_name={module_name}",
            ],
        )

    # ------------------------------------------------------------------
    # Field parsing helpers
    # ------------------------------------------------------------------

    def _parse_fields(self, fields: str) -> list[tuple[str, str]]:
        result = []
        for f in fields.split(","):
            f = f.strip()
            if ":" in f:
                name, typ = f.split(":", 1)
                result.append((name.strip(), typ.strip()))
        return result or [("name", "string"), ("description", "string")]

    _GO_TYPES: dict[str, str] = {
        "string":  "string",
        "int":     "int64",
        "int64":   "int64",
        "float":   "float64",
        "float64": "float64",
        "bool":    "bool",
        "time":    "time.Time",
        "uuid":    "uuid.UUID",
    }

    def _go_type(self, t: str) -> str:
        return self._GO_TYPES.get(t.lower(), "string")

    # ------------------------------------------------------------------
    # domain/entities/{resource}.go
    # ------------------------------------------------------------------

    def _entity_go(
        self,
        r: str,
        R: str,
        fields: list[tuple[str, str]],
        module_name: str,
        with_org: bool,
    ) -> str:
        needs_time = any(self._go_type(t) == "time.Time" for _, t in fields)
        has_uuid_field = any(self._go_type(t) == "uuid.UUID" for _, t in fields)

        imports = ["gorm.io/gorm", "github.com/google/uuid"]
        if needs_time:
            imports.append("time")
        import_block = "\n".join(f'\t"{imp}"' for imp in imports)

        # Build struct fields
        field_lines = ""
        if with_org:
            field_lines += (
                "\tOrganizationID uuid.UUID    "
                '`json:"organization_id" gorm:"type:uuid;not null;index"`\n'
            )
        for name, typ in fields:
            N = name.capitalize()
            gt = self._go_type(typ)
            gorm_tag = 'type:uuid;' if gt == "uuid.UUID" else ""
            field_lines += (
                f"\t{N:<16} {gt:<12} "
                f'`json:"{name}" gorm:"{gorm_tag}column:{name}"`\n'
            )

        # Validate method
        validate_body = f'\t// Add {R}-specific validations here.\n\treturn nil\n'

        return (
            "package entities\n\n"
            "import (\n"
            + import_block + "\n"
            ")\n\n"
            f"// {R} is the GORM database entity for the {r} resource.\n"
            f"type {R} struct {{\n"
            "\tgorm.Model\n"
            f"\tID uuid.UUID `json:\"id\" gorm:\"type:uuid;default:uuid_generate_v4();primaryKey\"`\n"
            + field_lines
            + "}\n\n"
            f"// Validate runs domain-level validation before persistence.\n"
            f"func (e *{R}) Validate() error {{\n"
            + validate_body
            + "}\n"
        )

    # ------------------------------------------------------------------
    # services/contracts/{resource}ContractService.go
    # ------------------------------------------------------------------

    def _contract_go(self, r: str, R: str, module_name: str, fields: list[tuple[str, str]]) -> str:
        dto_fields = ""
        input_fields = ""
        for name, typ in fields:
            N = name.capitalize()
            gt = self._go_type(typ)
            dto_fields += f'\t{N:<16} {gt:<12} `json:"{name}"`\n'
            input_fields += f'\t{N:<16} {gt:<12} `json:"{name}" validate:"required"`\n'

        return (
            "package contracts\n\n"
            "import (\n"
            '\t"time"\n\n'
            '\t"github.com/google/uuid"\n'
            ")\n\n"
            f"type {R}DTO struct {{\n"
            f'\tID        uuid.UUID `json:"id"`\n'
            + dto_fields
            + f'\tCreatedAt time.Time `json:"created_at"`\n'
            f'\tUpdatedAt time.Time `json:"updated_at"`\n'
            "}\n\n"
            f"type {R}InputDTO struct {{\n"
            + input_fields
            + "}\n\n"
            f"type {R}ServiceContract interface {{\n"
            f"\tCreate(input {R}InputDTO) (uuid.UUID, error)\n"
            f"\tGetByID(id uuid.UUID) ({R}DTO, error)\n"
            f"\tGetAll() ([]{R}DTO, error)\n"
            f"\tGetByName(name string) ([]{R}DTO, error)\n"
            f"\tUpdate(id uuid.UUID, input {R}InputDTO) error\n"
            f"\tDelete(id uuid.UUID) error\n"
            "}\n"
        )

