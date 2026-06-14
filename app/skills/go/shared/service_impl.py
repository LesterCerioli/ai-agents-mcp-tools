from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoServiceImplSkill(BaseSkill):
    """Generates services/implementations/resourceService.go.

    Follows the Medical-App-Core pattern:
    - Struct holds *gorm.DB directly (same as DoctorService, PatientService, etc.)
    - safeDB() session disables PrepareStmt and SkipDefaultTransaction
    - Raw SQL queries include 'deleted_at IS NULL' for soft-delete awareness
    - toDTOList() converts entity slice to DTO slice
    - Implements the ServiceContract interface defined in services/contracts/
    """

    name = "go.service_impl"
    description = (
        "Generate services/implementations/{resource}Service.go — concrete service "
        "implementation following the Medical-App-Core pattern. Struct receives *gorm.DB, "
        "uses safeDB() session, raw SQL with soft-delete awareness, and toDTOList() "
        "converter. Implements the {resource}ServiceContract interface."
    )
    category = SkillCategory.GO
    tags = [
        "go", "gorm", "service", "implementation", "business-logic",
        "medical-app-core", "dto", "soft-delete",
    ]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. patient, account, user)"),
        SkillParameter("module_name", "Go module name (e.g. github.com/org/my-service)"),
        SkillParameter(
            "fields",
            "Comma-separated field definitions as name:type "
            "(e.g. name:string,email:string,balance:float64). "
            "Must match the fields used in go.gorm_entity for this resource.",
            required=False,
            default="name:string,description:string",
        ),
    ]

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

    def _parse_fields(self, fields: str) -> list[tuple[str, str]]:
        result = []
        for f in fields.split(","):
            f = f.strip()
            if ":" in f:
                name, typ = f.split(":", 1)
                result.append((name.strip(), typ.strip()))
        return result or [("name", "string"), ("description", "string")]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        module_name: str = "github.com/org/app",
        fields: str = "name:string,description:string",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower().replace("-", "_").replace(" ", "_")
        R = r.capitalize()
        parsed = self._parse_fields(fields)

        code = self._generate(r, R, module_name, parsed)

        return SkillResult(
            success=True,
            summary=f"Generated service implementation for `{R}` (Medical-App-Core pattern)",
            artifacts=[
                CodeArtifact(
                    f"services/implementations/{r}Service.go",
                    code,
                    "go",
                    f"Concrete service implementation for {R}",
                ),
            ],
            dependencies=[
                "gorm.io/gorm",
                "github.com/google/uuid",
            ],
            instructions=[
                f"Add {R}Service to the Services struct in initializers/services.go",
                f"Wire it: {r}Service := implementations.New{R}Service(db)",
            ],
            next_steps=[
                f"go.controller resource={resource} module_name={module_name}",
            ],
        )

    def _generate(self, r: str, R: str, module_name: str, fields: list[tuple[str, str]]) -> str:
        table = r + "s"

        mapping_lines = ""
        for name, _ in fields:
            N = name.capitalize()
            mapping_lines += f"\t\t{N}: input.{N},\n"

        dto_field_lines = ""
        for name, _ in fields:
            N = name.capitalize()
            dto_field_lines += f"\t\t{N}: item.{N},\n"

        return (
            "package implementations\n\n"
            "import (\n"
            '\t"github.com/google/uuid"\n'
            '\t"gorm.io/gorm"\n\n'
            f'\t"{module_name}/domain/entities"\n'
            f'\t"{module_name}/services/contracts"\n'
            ")\n\n"
            f"var _ contracts.{R}ServiceContract = (*{R}Service)(nil)\n\n"
            f"type {R}Service struct {{\n"
            "\tDB *gorm.DB\n"
            "}\n\n"
            f"func New{R}Service(db *gorm.DB) *{R}Service {{\n"
            f"\treturn &{R}Service{{DB: db}}\n"
            "}\n\n"
            f"func (s *{R}Service) safeDB() *gorm.DB {{\n"
            "\treturn s.DB.Session(&gorm.Session{\n"
            "\t\tPrepareStmt:            false,\n"
            "\t\tSkipDefaultTransaction: true,\n"
            "\t})\n"
            "}\n\n"
            f"func (s *{R}Service) Create(input contracts.{R}InputDTO) (uuid.UUID, error) {{\n"
            f"\tnew{R} := entities.{R}{{\n"
            + mapping_lines
            + "\t}\n"
            f"\tif err := s.DB.Create(&new{R}).Error; err != nil {{\n"
            "\t\treturn uuid.Nil, err\n"
            "\t}\n"
            f"\treturn new{R}.ID, nil\n"
            "}\n\n"
            f"func (s *{R}Service) GetByID(id uuid.UUID) (contracts.{R}DTO, error) {{\n"
            f"\tvar item entities.{R}\n"
            "\tdb := s.safeDB()\n"
            f"\terr := db.Raw(\"SELECT * FROM {table} WHERE id = ? AND deleted_at IS NULL\", id).Scan(&item).Error\n"
            "\tif err != nil {\n"
            f"\t\treturn contracts.{R}DTO{{}}, err\n"
            "\t}\n"
            f"\treturn s.toDTO(item), nil\n"
            "}\n\n"
            f"func (s *{R}Service) GetAll() ([]contracts.{R}DTO, error) {{\n"
            f"\tvar items []entities.{R}\n"
            "\tdb := s.safeDB()\n"
            f"\terr := db.Raw(\"SELECT * FROM {table} WHERE deleted_at IS NULL\").Scan(&items).Error\n"
            "\tif err != nil {\n"
            "\t\treturn nil, err\n"
            "\t}\n"
            f"\treturn mapTo{R}DTOList(items), nil\n"
            "}\n\n"
            f"func (s *{R}Service) GetByName(name string) ([]contracts.{R}DTO, error) {{\n"
            f"\tvar items []entities.{R}\n"
            "\tdb := s.safeDB()\n"
            f"\terr := db.Raw(\"SELECT * FROM {table} WHERE name LIKE ? AND deleted_at IS NULL\", \"%\"+name+\"%\").Scan(&items).Error\n"
            "\tif err != nil {\n"
            "\t\treturn nil, err\n"
            "\t}\n"
            f"\treturn mapTo{R}DTOList(items), nil\n"
            "}\n\n"
            f"func (s *{R}Service) Update(id uuid.UUID, input contracts.{R}InputDTO) error {{\n"
            f"\tvar item entities.{R}\n"
            f"\tif err := s.DB.Where(\"id = ?\", id).First(&item).Error; err != nil {{\n"
            "\t\treturn err\n"
            "\t}\n"
            + self._build_update_lines(fields)
            + "\treturn s.DB.Save(&item).Error\n"
            "}\n\n"
            f"func (s *{R}Service) Delete(id uuid.UUID) error {{\n"
            f"\treturn s.DB.Delete(&entities.{R}{{}}, \"id = ?\", id).Error\n"
            "}\n\n"
            f"func (s *{R}Service) toDTO(item entities.{R}) contracts.{R}DTO {{\n"
            f"\treturn contracts.{R}DTO{{\n"
            "\t\tID:        item.ID,\n"
            + dto_field_lines
            + "\t\tCreatedAt: item.CreatedAt,\n"
            "\t\tUpdatedAt: item.UpdatedAt,\n"
            "\t}\n"
            "}\n\n"
            f"func mapTo{R}DTOList(items []entities.{R}) []contracts.{R}DTO {{\n"
            f"\tresult := make([]contracts.{R}DTO, len(items))\n"
            "\tfor i, item := range items {\n"
            f"\t\tresult[i] = contracts.{R}DTO{{\n"
            "\t\t\tID:        item.ID,\n"
            + "".join(f"\t\t\t{n.capitalize()}: item.{n.capitalize()},\n" for n, _ in fields)
            + "\t\t\tCreatedAt: item.CreatedAt,\n"
            "\t\t\tUpdatedAt: item.UpdatedAt,\n"
            "\t\t}\n"
            "\t}\n"
            "\treturn result\n"
            "}\n"
        )

    def _build_update_lines(self, fields: list[tuple[str, str]]) -> str:
        lines = ""
        for name, _ in fields:
            N = name.capitalize()
            lines += f"\titem.{N} = input.{N}\n"
        return lines

    # Satisfy abstract method — not used directly
    def _go_type_unused(self, t: str) -> str:  # pragma: no cover
        return self._go_type(t)
