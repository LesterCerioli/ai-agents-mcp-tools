from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoRepositoryContractSkill(BaseSkill):
    """Generates domain/repositories/contracts/resourceRepository.go.

    Follows the Medical-App-Core pattern: the repository interface lives inside
    the domain layer so that infra implementations depend inward, not outward.
    """

    name = "go.repository_contract"
    description = (
        "Generate domain/repositories/contracts/{resource}Repository.go — "
        "the repository interface that lives inside the domain layer following the "
        "Medical-App-Core pattern. Declares Create, GetByID, GetAll, GetByName, "
        "Update, and Delete operations against the GORM entity."
    )
    category = SkillCategory.GO
    tags = [
        "go", "gorm", "repository", "contract", "interface",
        "domain", "ddd", "medical-app-core",
    ]
    parameters = [
        SkillParameter("resource", "Resource name in singular form (e.g. patient, account, user)"),
        SkillParameter("module_name", "Go module name (e.g. github.com/org/my-service)"),
    ]

    async def execute(  # type: ignore[override]
        self,
        resource: str,
        module_name: str = "github.com/org/app",
        **_: Any,
    ) -> SkillResult:
        r = resource.lower().replace("-", "_").replace(" ", "_")
        R = r.capitalize()

        code = self._generate(r, R, module_name)

        return SkillResult(
            success=True,
            summary=f"Generated repository contract interface for `{R}`",
            artifacts=[
                CodeArtifact(
                    f"domain/repositories/contracts/{r}Repository.go",
                    code,
                    "go",
                    f"Repository contract interface for {R} (Medical-App-Core pattern)",
                ),
            ],
            dependencies=["gorm.io/gorm", "github.com/google/uuid"],
            instructions=[
                f"Implement {R}RepositoryContract in infra/repositories/{r}Repository.go",
            ],
            next_steps=[
                f"go.repository_impl resource={resource} module_name={module_name}",
            ],
        )

    def _generate(self, r: str, R: str, module_name: str) -> str:
        return (
            "package contracts\n\n"
            "import (\n"
            '\t"github.com/google/uuid"\n\n'
            f'\t"{module_name}/domain/entities"\n'
            ")\n\n"
            f"// {R}RepositoryContract defines the persistence operations for {R}.\n"
            "// Implementations live in infra/repositories and receive a *gorm.DB.\n"
            f"type {R}RepositoryContract interface {{\n"
            f"\tCreate({r} *entities.{R}) error\n"
            f"\tGetByID(id uuid.UUID) (*entities.{R}, error)\n"
            f"\tGetAll() ([]*entities.{R}, error)\n"
            f"\tGetByName(name string) ([]*entities.{R}, error)\n"
            f"\tUpdate({r} *entities.{R}) error\n"
            f"\tDelete(id uuid.UUID) error\n"
            "}\n"
        )
