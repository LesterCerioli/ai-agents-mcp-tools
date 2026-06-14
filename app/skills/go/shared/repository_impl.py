from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoRepositoryImplSkill(BaseSkill):
    """Generates infra/repositories/resourceRepository.go.

    GORM implementation of the domain repository contract.
    Follows the Medical-App-Core pattern: struct holds *gorm.DB,
    constructor is NewResourceRepository(db *gorm.DB).
    """

    name = "go.repository_impl"
    description = (
        "Generate infra/repositories/{resource}Repository.go — GORM implementation "
        "of the domain repository contract following the Medical-App-Core pattern. "
        "Struct receives *gorm.DB, implements Create, GetByID, GetAll, GetByName, "
        "Update, and Delete using GORM ORM methods."
    )
    category = SkillCategory.GO
    tags = [
        "go", "gorm", "repository", "implementation", "infra",
        "postgres", "medical-app-core",
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
            summary=f"Generated GORM repository implementation for `{R}`",
            artifacts=[
                CodeArtifact(
                    f"infra/repositories/{r}Repository.go",
                    code,
                    "go",
                    f"GORM implementation of {R}RepositoryContract (Medical-App-Core pattern)",
                ),
            ],
            dependencies=["gorm.io/gorm", "github.com/google/uuid"],
            instructions=[
                f"Wire it in initializers/services.go: {r}Repo := repositories.New{R}Repository(db)",
                f"Pass {r}Repo to New{R}Service if your service depends on the contract",
            ],
            next_steps=[
                f"go.service_impl resource={resource} module_name={module_name}",
            ],
        )

    def _generate(self, r: str, R: str, module_name: str) -> str:
        return (
            "package repositories\n\n"
            "import (\n"
            '\t"github.com/google/uuid"\n'
            '\t"gorm.io/gorm"\n\n'
            f'\t"{module_name}/domain/entities"\n'
            ")\n\n"
            f"type Gorm{R}Repository struct {{\n"
            "\tdb *gorm.DB\n"
            "}\n\n"
            f"func New{R}Repository(db *gorm.DB) *Gorm{R}Repository {{\n"
            f"\treturn &Gorm{R}Repository{{db: db}}\n"
            "}\n\n"
            f"func (r *Gorm{R}Repository) Create({r} *entities.{R}) error {{\n"
            f"\treturn r.db.Create({r}).Error\n"
            "}\n\n"
            f"func (r *Gorm{R}Repository) GetByID(id uuid.UUID) (*entities.{R}, error) {{\n"
            f"\tvar {r} entities.{R}\n"
            f"\terr := r.db.Where(\"id = ?\", id).First(&{r}).Error\n"
            f"\treturn &{r}, err\n"
            "}\n\n"
            f"func (r *Gorm{R}Repository) GetAll() ([]*entities.{R}, error) {{\n"
            f"\tvar items []*entities.{R}\n"
            f"\terr := r.db.Find(&items).Error\n"
            "\treturn items, err\n"
            "}\n\n"
            f"func (r *Gorm{R}Repository) GetByName(name string) ([]*entities.{R}, error) {{\n"
            f"\tvar items []*entities.{R}\n"
            f"\terr := r.db.Where(\"name LIKE ?\", \"%\"+name+\"%\").Find(&items).Error\n"
            "\treturn items, err\n"
            "}\n\n"
            f"func (r *Gorm{R}Repository) Update({r} *entities.{R}) error {{\n"
            f"\treturn r.db.Save({r}).Error\n"
            "}\n\n"
            f"func (r *Gorm{R}Repository) Delete(id uuid.UUID) error {{\n"
            f"\treturn r.db.Delete(&entities.{R}{{}}, \"id = ?\", id).Error\n"
            "}\n"
        )
