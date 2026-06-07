from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.architecture.context.pipeline_context import PipelineContext

if TYPE_CHECKING:
    from src.llm.base import BaseLLMProvider


class BaseArchitectureAgent(ABC):
    
    name: str
    description: str
    system_prompt: str = ""

    def __init__(self, llm: "BaseLLMProvider | None" = None):
        self.llm = llm

    @abstractmethod
    async def run(self, context: PipelineContext) -> PipelineContext: ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
