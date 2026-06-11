import uuid
from enum import Enum

from pydantic import BaseModel, Field

from app.skills.base import CodeArtifact


class WorkflowScope(str, Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    FULLSTACK = "fullstack"


class IntegrationContract(BaseModel):
    openapi_stub: str = Field(description="YAML OpenAPI 3.1 spec stub for the backend API")
    typescript_types: str = Field(description="TypeScript .d.ts type definitions for frontend consumption")
    pydantic_schemas: str = Field(description="Shared Pydantic request/response schemas")


class WorkflowOutput(BaseModel):
    workflow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    scope: WorkflowScope
    system_design_summary: str = Field(description="Human-readable summary of the chosen architecture")
    architecture_pattern: str = Field(description="Primary architecture pattern selected (e.g. MICROSERVICES)")
    backend_artifacts: list[CodeArtifact] = Field(default_factory=list)
    frontend_artifacts: list[CodeArtifact] = Field(default_factory=list)
    integration_contracts: IntegrationContract | None = None
    all_dependencies: list[str] = Field(default_factory=list)
    all_dev_dependencies: list[str] = Field(default_factory=list)
    summary: str = ""
    confidence: float = 0.0

    model_config = {"arbitrary_types_allowed": True}
