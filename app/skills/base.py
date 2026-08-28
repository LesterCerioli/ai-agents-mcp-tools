from abc import ABC, abstractmethod
from dataclasses import dataclass, field, Field
from enum import Enum
from typing import Any, TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.llm.base import BaseLLMProvider


class SkillCategory(str, Enum):
    NEXTJS = "nextjs"
    DESIGN = "design"
    FRONTEND = "frontend"
    VERCEL = "vercel"
    BACKEND = "backend"
    GO = "go"
    DIAGNOSTIC = "diagnostic"
    SOLID = "solid"
    DESIGN_PATTERNS = "design_patterns"
    QUALITY_ASSESSMENT = "quality_assessment"
    PLANNING = "planning"


class SkillDomain(str, Enum):
    CODE = "code"
    PLANNING = "planning"
    DIAGNOSTIC = "diagnostic"
    DOCS = "docs"
    ARCHITECTURE = "architecture"


class SkillComplexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class SkillMetadata:
    domain: SkillDomain = SkillDomain.CODE
    complexity: SkillComplexity = SkillComplexity.MEDIUM
    inputs: list[str] = field(default_factory=list)      
    outputs: list[str] = field(default_factory=list)     
    prerequisites: list[str] = field(default_factory=list)  
    tags: list[str] = field(default_factory=list)        
    estimated_duration_seconds: int = 30


@dataclass
class SkillParameter:
    name: str
    description: str
    type: str = "string"
    required: bool = True
    default: Any = None
    enum: list[str] = field(default_factory=list)


@dataclass
class CodeArtifact:
    filename: str
    content: str
    language: str
    description: str = ""


@dataclass
class SkillResult:
    success: bool
    summary: str
    artifacts: list[CodeArtifact] = field(default_factory=list)
    instructions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    dev_dependencies: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    error: str | None = None

    @classmethod
    def failure(cls, error: str) -> "SkillResult":
        return cls(success=False, summary="Skill execution failed", error=error)


class BaseSkill(ABC):
    
    name: str
    description: str
    category: SkillCategory
    parameters: list[SkillParameter] = []
    tags: list[str] = []
    # Rich metadata for planning/orchestration
    metadata: SkillMetadata = field(default_factory=SkillMetadata)

    def __init__(self, llm: "BaseLLMProvider | None" = None):
        self.llm = llm
        
        if isinstance(self.metadata, Field):
            self.metadata = SkillMetadata()

    @abstractmethod
    async def execute(self, **kwargs: Any) -> SkillResult: ...

    def schema(self) -> dict[str, Any]:
        base = {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "tags": self.tags,
            "parameters": [
                {
                    "name": p.name,
                    "description": p.description,
                    "type": p.type,
                    "required": p.required,
                    **({"default": p.default} if p.default is not None else {}),
                    **({"enum": p.enum} if p.enum else {}),
                }
                for p in self.parameters
            ],
        }
        
        base["metadata"] = {
            "domain": self.metadata.domain.value,
            "complexity": self.metadata.complexity.value,
            "inputs": self.metadata.inputs,
            "outputs": self.metadata.outputs,
            "prerequisites": self.metadata.prerequisites,
            "tags": self.metadata.tags,
            "estimated_duration_seconds": self.metadata.estimated_duration_seconds,
        }
        return base

    def __repr__(self) -> str:
        return f"<Skill {self.name} [{self.category.value}]>"
