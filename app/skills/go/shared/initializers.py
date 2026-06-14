from typing import Any

from app.skills.base import BaseSkill, CodeArtifact, SkillCategory, SkillParameter, SkillResult
from app.skills.registry import SkillRegistry


@SkillRegistry.register
class GoInitializersSkill(BaseSkill):
    """Generates the centralised initializers/ package following the Medical-App-Core pattern.

    This is the dependency-injection bootstrap layer that wires together the
    database connection, all service implementations, auto-migrations, and
    custom validators — all in one place so main.go stays thin and readable.
    """

    name = "go.initializers"
    description = (
        "Generate the centralised initializers/ package for a Fiber v2 + GORM + PostgreSQL project: "
        "database.go (GORM connection with pooling), services.go (Services DI container + InitServices), "
        "migrations.go (UUID-ossp extension + AutoMigrate), validators.go (custom field validators). "
        "Follows the Medical-App-Core pattern of centralised service initialisation."
    )
    category = SkillCategory.GO
    tags = [
        "go", "fiber", "gorm", "initializers", "bootstrap", "di",
        "dependency-injection", "postgres", "services", "migrations",
    ]
    parameters = [
        SkillParameter("module_name", "Go module name (e.g. github.com/org/my-service)"),
        SkillParameter(
            "resources",
            "Comma-separated resource names to wire in Services struct (e.g. patient,user,appointment). "
            "Leave empty to generate a minimal stub.",
            required=False,
            default="",
        ),
        SkillParameter("app_name", "Application name for comments and logs", required=False, default="app"),
    ]

    async def execute(  # type: ignore[override]
        self,
        module_name: str,
        resources: str = "",
        app_name: str = "app",
        **_: Any,
    ) -> SkillResult:
        resource_list = [r.strip() for r in resources.split(",") if r.strip()]

        artifacts = [
            CodeArtifact(
                "initializers/database.go",
                self._database_go(),
                "go",
                "GORM + PostgreSQL connection with connection pooling",
            ),
            CodeArtifact(
                "initializers/services.go",
                self._services_go(module_name, resource_list),
                "go",
                "Centralised Services DI container and InitServices wiring",
            ),
            CodeArtifact(
                "initializers/migrations.go",
                self._migrations_go(module_name, resource_list),
                "go",
                "UUID-ossp extension + GORM AutoMigrate",
            ),
            CodeArtifact(
                "initializers/validators.go",
                self._validators_go(),
                "go",
                "Custom field validators (CPF, SSN, CNPJ)",
            ),
        ]

        n = len(resource_list)
        return SkillResult(
            success=True,
            summary=(
                f"Generated initializers/ package for `{app_name}` "
                f"with {n} service{'s' if n != 1 else ''} wired"
                + (f": {', '.join(resource_list)}" if resource_list else " (stub — add resources to expand)")
            ),
            artifacts=artifacts,
            dependencies=[
                "gorm.io/gorm",
                "gorm.io/driver/postgres",
                "github.com/golang-jwt/jwt/v4",
                "github.com/google/uuid",
                "github.com/go-playground/validator/v10",
            ],
            instructions=[
                "Set DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT, DB_SSL_MODE, DB_TIMEZONE in .env",
                "Set JWT_SECRET (32+ chars), CLIENT_ID_1, SECRET_1 in .env for auth",
                "In main.go: db := initializers.InitialDB()",
                "In main.go: initializers.RunMigrations(db)",
                "In main.go: services := initializers.InitServices(db)",
                "Pass *initializers.Services to route initialisation and controllers",
            ],
            next_steps=[
                "go.fiber_full_project module_name=" + module_name,
                "go.gorm_entity resource=<resource> module_name=" + module_name,
                "go.swagger_fiber module_name=" + module_name,
            ],
        )

    # ------------------------------------------------------------------
    # database.go
    # ------------------------------------------------------------------

    def _database_go(self) -> str:
        return (
            "package initializers\n\n"
            "import (\n"
            '\t"fmt"\n'
            '\t"log"\n'
            '\t"os"\n'
            '\t"strings"\n'
            '\t"time"\n\n'
            '\t"gorm.io/driver/postgres"\n'
            '\t"gorm.io/gorm"\n'
            '\t"gorm.io/gorm/logger"\n'
            ")\n\n"
            "func InitialDB() *gorm.DB {\n"
            '\tdbHost := getEnvOrDefault("DB_HOST", "")\n'
            '\tdbUser := getEnvOrDefault("DB_USER", "")\n'
            '\tdbPassword := getEnvOrDefault("DB_PASSWORD", "")\n'
            '\tdbName := getEnvOrDefault("DB_NAME", "")\n'
            '\tdbPort := getEnvOrDefault("DB_PORT", "5432")\n'
            '\tsslMode := getEnvOrDefault("DB_SSL_MODE", "disable")\n'
            '\tdbTimezone := getEnvOrDefault("DB_TIMEZONE", "UTC")\n\n'
            '\tif dbHost == "" || dbUser == "" || dbPassword == "" || dbName == "" {\n'
            '\t\tlog.Fatal("Missing required database configuration: DB_HOST, DB_USER, DB_PASSWORD, DB_NAME")\n'
            "\t}\n\n"
            "\tdsn := fmt.Sprintf(\n"
            '\t\t"host=%s user=%s password=%s dbname=%s port=%s sslmode=%s TimeZone=%s default_query_exec_mode=simple_protocol",\n'
            "\t\tdbHost, dbUser, dbPassword, dbName, dbPort, sslMode, dbTimezone,\n"
            "\t)\n\n"
            "\tmaskedDsn := strings.ReplaceAll(dsn, dbPassword, \"*****\")\n"
            '\tlog.Printf("Connecting to database: %s", maskedDsn)\n\n'
            "\tgormLogger := logger.New(\n"
            "\t\tlog.New(os.Stdout, \"\\r\\n\", log.LstdFlags),\n"
            "\t\tlogger.Config{\n"
            "\t\t\tSlowThreshold: time.Second,\n"
            "\t\t\tLogLevel:      logger.Warn,\n"
            "\t\t\tColorful:      false,\n"
            "\t\t},\n"
            "\t)\n\n"
            "\tdb, err := gorm.Open(postgres.Open(dsn), &gorm.Config{\n"
            "\t\tLogger:               gormLogger,\n"
            "\t\tDisableAutomaticPing: false,\n"
            "\t\tPrepareStmt:          false,\n"
            "\t})\n"
            "\tif err != nil {\n"
            '\t\tlog.Fatalf("Error connecting to the database: %v", err)\n'
            "\t}\n\n"
            "\tsqlDB, err := db.DB()\n"
            "\tif err != nil {\n"
            '\t\tlog.Fatalf("Error getting DB instance: %v", err)\n'
            "\t}\n\n"
            "\tsqlDB.SetMaxIdleConns(0)\n"
            "\tsqlDB.SetMaxOpenConns(50)\n"
            "\tsqlDB.SetConnMaxLifetime(30 * time.Second)\n\n"
            '\tlog.Println("Successfully connected to database")\n'
            "\treturn db\n"
            "}\n\n"
            "func getEnvOrDefault(key, fallback string) string {\n"
            "\tif v := os.Getenv(key); v != \"\" {\n"
            "\t\treturn v\n"
            "\t}\n"
            "\treturn fallback\n"
            "}\n"
        )

    # ------------------------------------------------------------------
    # services.go
    # ------------------------------------------------------------------

    def _services_go(self, module_name: str, resources: list[str]) -> str:
        if not resources:
            return (
                "package initializers\n\n"
                "import (\n"
                '\t"log"\n\n'
                '\t"gorm.io/gorm"\n'
                ")\n\n"
                "type Services struct {\n"
                "\t// Add service contract fields here, e.g.:\n"
                "\t// UserService contracts.UserServiceContract\n"
                "}\n\n"
                "func InitServices(db *gorm.DB) *Services {\n"
                '\tlog.Println("Initializing services...")\n'
                "\t_ = db\n"
                '\tlog.Println("All services initialized successfully.")\n'
                "\treturn &Services{}\n"
                "}\n"
            )

        struct_fields = ""
        init_lines = ""
        return_fields = ""

        for r in resources:
            name = r.strip().lower()
            Name = name.capitalize()
            struct_fields += f"\t{Name}Service    contracts.{Name}ServiceContract\n"
            init_lines += (
                f"\t{name}Svc := implementations.New{Name}Service(db)\n"
                f'\tlog.Println("{Name}Service initialized successfully.")\n'
            )
            return_fields += f"\t\t{Name}Service: {name}Svc,\n"

        return (
            "package initializers\n\n"
            "import (\n"
            '\t"log"\n\n'
            '\t"gorm.io/gorm"\n\n'
            f'\t"{module_name}/services/contracts"\n'
            f'\t"{module_name}/services/implementations"\n'
            ")\n\n"
            "type Services struct {\n"
            + struct_fields
            + "}\n\n"
            "func InitServices(db *gorm.DB) *Services {\n"
            '\tlog.Println("Initializing services...")\n'
            + init_lines
            + '\tlog.Println("All services initialized successfully.")\n'
            "\treturn &Services{\n"
            + return_fields
            + "\t}\n"
            "}\n"
        )

    # ------------------------------------------------------------------
    # migrations.go
    # ------------------------------------------------------------------

    def _migrations_go(self, module_name: str, resources: list[str]) -> str:
        if resources:
            entity_import = f'\t"{module_name}/domain/entities"\n'
            models = ", ".join(f"&entities.{r.strip().capitalize()}{{}}" for r in resources)
            migrate_call = f"\tif err := db.AutoMigrate({models}); err != nil {{\n" \
                           f'\t\tpanic("auto-migrate failed: " + err.Error())\n' \
                           f"\t}}\n"
        else:
            entity_import = ""
            migrate_call = (
                "\t// Uncomment and add your entities:\n"
                "\t// db.AutoMigrate(&entities.User{}, &entities.Patient{})\n"
            )

        return (
            "package initializers\n\n"
            "import (\n"
            '\t"gorm.io/gorm"\n'
            + entity_import
            + ")\n\n"
            "// RunMigrations enables the uuid-ossp PostgreSQL extension and\n"
            "// runs GORM AutoMigrate for all registered entities.\n"
            "func RunMigrations(db *gorm.DB) {\n"
            '\tdb.Exec(`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`)\n'
            + migrate_call
            + "}\n"
        )

    # ------------------------------------------------------------------
    # validators.go
    # ------------------------------------------------------------------

    def _validators_go(self) -> str:
        return (
            "package initializers\n\n"
            "import (\n"
            '\t"regexp"\n\n'
            '\t"github.com/go-playground/validator/v10"\n'
            ")\n\n"
            "// RegisterCustomValidators adds domain-specific validation rules to\n"
            "// a go-playground/validator instance. Call once during app startup.\n"
            "func RegisterCustomValidators(v *validator.Validate) {\n"
            '\tv.RegisterValidation("cpf", validateCPF)\n'
            '\tv.RegisterValidation("ssn", validateSSN)\n'
            '\tv.RegisterValidation("cnpj", validateCNPJ)\n'
            '\tv.RegisterValidation("npi", validateNPI)\n'
            "}\n\n"
            "// validateCPF accepts an 11-digit Brazilian tax ID (digits only).\n"
            "func validateCPF(fl validator.FieldLevel) bool {\n"
            '\treturn regexp.MustCompile(`^\\d{11}$`).MatchString(fl.Field().String())\n'
            "}\n\n"
            "// validateSSN accepts the US Social Security Number format (###-##-####).\n"
            "func validateSSN(fl validator.FieldLevel) bool {\n"
            '\treturn regexp.MustCompile(`^\\d{3}-\\d{2}-\\d{4}$`).MatchString(fl.Field().String())\n'
            "}\n\n"
            "// validateCNPJ accepts a 14-digit Brazilian company tax ID (digits only).\n"
            "func validateCNPJ(fl validator.FieldLevel) bool {\n"
            '\treturn regexp.MustCompile(`^\\d{14}$`).MatchString(fl.Field().String())\n'
            "}\n\n"
            "// validateNPI accepts a 10-digit US National Provider Identifier.\n"
            "func validateNPI(fl validator.FieldLevel) bool {\n"
            '\treturn regexp.MustCompile(`^\\d{10}$`).MatchString(fl.Field().String())\n'
            "}\n"
        )
