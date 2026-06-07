import uuid
from dataclasses import dataclass, field
from typing import Any

from src.architecture.schemas.requirements import ArchitectureRequirements


@dataclass
class PipelineContext:
    
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requirements: ArchitectureRequirements | None = None
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def store_requirements(self, requirements: ArchitectureRequirements) -> None:
        self.requirements = requirements
        self.conversation_history.append({
            "role": "system",
            "event": "requirements_parsed",
            "content": requirements.model_dump_json(),
        })

    def add_turn(self, role: str, content: str) -> None:
        self.conversation_history.append({"role": role, "content": content})

    def is_ready_for_next_stage(self) -> bool:
        return self.requirements is not None and self.requirements.is_complete

    def turn_count(self) -> int:
        return sum(1 for t in self.conversation_history if t.get("role") in ("user", "assistant"))
