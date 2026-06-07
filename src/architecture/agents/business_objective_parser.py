import json
from typing import TYPE_CHECKING, Any

from src.architecture.agents.base import BaseArchitectureAgent
from src.architecture.agents.extraction.clarification import ClarificationEngine
from src.architecture.agents.extraction.keyword_extractor import KeywordExtractor
from src.architecture.context.pipeline_context import PipelineContext
from src.architecture.schemas.requirements import ArchitectureRequirements, SpecificationStatus

if TYPE_CHECKING:
    from src.llm.base import BaseLLMProvider

_SYSTEM_PROMPT = (
    "You are a solution architecture requirements analyst. "
    "Extract structured architecture requirements from business objectives. "
    "Return ONLY valid JSON with the exact schema provided. No markdown, no explanation."
)

_EXTRACTION_TEMPLATE = """Extract architecture requirements from this business objective:

"{objective}"

{history_section}
Return JSON with this exact structure (use null for unknown fields):
{{
  "scalability": {{
    "status": "specified|not_specified|ambiguous",
    "expected_users": "string or null",
    "growth_rate": "string or null",
    "peak_load": "string or null",
    "confidence": 0.0
  }},
  "availability": {{
    "status": "specified|not_specified|ambiguous",
    "target_uptime": "string or null",
    "rto": "string or null",
    "rpo": "string or null",
    "confidence": 0.0
  }},
  "compliance": {{
    "status": "specified|not_specified|ambiguous",
    "frameworks": [],
    "data_residency": "string or null",
    "audit_trail": null,
    "confidence": 0.0
  }},
  "domain_boundaries": {{
    "status": "specified|not_specified|ambiguous",
    "primary_domain": "string or null",
    "subdomains": [],
    "bounded_contexts": [],
    "confidence": 0.0
  }},
  "integration": {{
    "status": "specified|not_specified|ambiguous",
    "external_systems": [],
    "integration_patterns": [],
    "real_time": null,
    "confidence": 0.0
  }},
  "budget": {{
    "status": "specified|not_specified|ambiguous",
    "tier": "startup|mid-market|enterprise or null",
    "cloud_preference": "aws|gcp|azure|agnostic or null",
    "cost_sensitivity": "low|medium|high or null",
    "confidence": 0.0
  }},
  "team_size": {{
    "status": "specified|not_specified|ambiguous",
    "engineering_team_size": "1-5|5-20|20-100|100+ or null",
    "organizational_maturity": "startup|scale-up|enterprise or null",
    "confidence": 0.0
  }}
}}"""


class BusinessObjectiveParserAgent(BaseArchitectureAgent):
    """First pipeline agent: transforms raw business objectives into structured ArchitectureRequirements.

    Supports LLM-powered extraction with rule-based fallback, per-dimension confidence scoring,
    and multi-turn clarification for missing or ambiguous requirement dimensions.

    SRP: orchestrates extraction, confidence aggregation, clarification, and context storage.
    Each sub-responsibility is delegated to a dedicated collaborator class.
    """

    name = "business_objective_parser"
    description = (
        "Parses natural language business objectives into structured ArchitectureRequirements "
        "with per-dimension confidence scoring and multi-turn clarification support."
    )
    system_prompt = _SYSTEM_PROMPT

    def __init__(self, llm: "BaseLLMProvider | None" = None):
        super().__init__(llm)
        self._extractor = KeywordExtractor()
        self._clarifier = ClarificationEngine()

    async def parse(
        self,
        objective: str,
        context: PipelineContext | None = None,
    ) -> ArchitectureRequirements:
        """Parse a natural language business objective into structured requirements.

        Args:
            objective: Raw business objective text from the user.
            context: Optional pipeline context for session tracking and history.

        Returns:
            Validated ArchitectureRequirements with confidence scores and clarification questions.
        """
        if context:
            context.add_turn("user", objective)

        raw_data = await self._extract(objective, context)
        requirements = self._build_requirements(objective, raw_data)
        overall_confidence = self._compute_overall_confidence(requirements)
        requirements = requirements.model_copy(update={
            "overall_confidence": overall_confidence,
            "clarification_questions": self._clarifier.generate_questions(requirements),
            "is_complete": self._check_completeness(requirements, overall_confidence),
        })

        if context:
            context.store_requirements(requirements)

        return requirements

    async def clarify(
        self,
        answer: str,
        context: PipelineContext,
    ) -> ArchitectureRequirements:
        """Incorporate a user clarification answer and refine the requirements.

        Args:
            answer: The user's answer to a clarification question.
            context: Active pipeline context holding prior requirements.

        Returns:
            Refined ArchitectureRequirements merging prior extractions with new information.

        Raises:
            ValueError: If called before parse() has been invoked on this context.
        """
        if context.requirements is None:
            raise ValueError("No prior requirements to clarify. Call parse() first.")

        context.add_turn("user", answer)
        combined_input = self._build_combined_input(context.requirements.raw_input, answer)

        raw_data = await self._extract(combined_input, context)
        current = self._build_requirements(combined_input, raw_data)
        merged = self._merge_with_prior(current, context.requirements)
        overall_confidence = self._compute_overall_confidence(merged)
        merged = merged.model_copy(update={
            "overall_confidence": overall_confidence,
            "clarification_questions": self._clarifier.generate_questions(merged),
            "is_complete": self._check_completeness(merged, overall_confidence),
        })

        context.store_requirements(merged)
        return merged

    async def run(self, context: PipelineContext) -> PipelineContext:
        """Execute as part of the pipeline. Parses the last user turn in conversation history."""
        last_user_input = next(
            (
                t["content"]
                for t in reversed(context.conversation_history)
                if t.get("role") == "user"
            ),
            None,
        )
        if last_user_input:
            await self.parse(last_user_input, context)
        return context

    async def _extract(self, text: str, context: PipelineContext | None) -> dict[str, Any]:
        if self.llm:
            return await self._extract_with_llm(text, context)
        return self._extractor.extract(text)

    async def _extract_with_llm(self, text: str, context: PipelineContext | None) -> dict[str, Any]:
        history_section = ""
        if context and context.requirements:
            history_section = (
                "Prior extracted requirements (refine — do not discard confirmed dimensions):\n"
                f"{context.requirements.model_dump_json(indent=2)}\n\n"
            )

        prompt = _EXTRACTION_TEMPLATE.format(
            objective=text,
            history_section=history_section,
        )

        try:
            response = await self.llm.chat(prompt, system_prompt=self.system_prompt)  # type: ignore[union-attr]
            return json.loads(response)
        except (json.JSONDecodeError, Exception):
            return self._extractor.extract(text)

    def _build_requirements(self, raw_input: str, data: dict[str, Any]) -> ArchitectureRequirements:
        try:
            return ArchitectureRequirements(raw_input=raw_input, **data)
        except Exception:
            fallback = self._extractor.extract(raw_input)
            return ArchitectureRequirements(raw_input=raw_input, **fallback)

    def _merge_with_prior(
        self,
        current: ArchitectureRequirements,
        prior: ArchitectureRequirements,
    ) -> ArchitectureRequirements:
        """Merge current extraction with prior, keeping the highest-confidence SPECIFIED dimension."""
        dims = [
            "scalability", "availability", "compliance",
            "domain_boundaries", "integration", "budget", "team_size",
        ]
        updates: dict[str, Any] = {}

        for dim in dims:
            cur_dim = getattr(current, dim)
            pri_dim = getattr(prior, dim)

            prior_is_better = (
                pri_dim.status == SpecificationStatus.SPECIFIED
                and (
                    cur_dim.status != SpecificationStatus.SPECIFIED
                    or pri_dim.confidence > cur_dim.confidence
                )
            )
            updates[dim] = pri_dim if prior_is_better else cur_dim

        return current.model_copy(update=updates)

    def _compute_overall_confidence(self, requirements: ArchitectureRequirements) -> float:
        scores = list(requirements.dimension_confidences().values())
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 3)

    def _check_completeness(self, requirements: ArchitectureRequirements, overall_confidence: float) -> bool:
        critical_dims = ["domain_boundaries", "scalability"]
        all_critical_specified = all(
            getattr(requirements, dim).status == SpecificationStatus.SPECIFIED
            for dim in critical_dims
        )
        return all_critical_specified and overall_confidence >= 0.3

    @staticmethod
    def _build_combined_input(original: str, clarification: str) -> str:
        return f"{original}\n\nAdditional clarification: {clarification}"
