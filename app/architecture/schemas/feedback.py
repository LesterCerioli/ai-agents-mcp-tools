import uuid
from enum import Enum

from pydantic import BaseModel, Field


class TargetSection(str, Enum):
    
    SOLUTION_STRATEGY = "solution_strategy"
    DESIGN_PARTNER_SELECTION = "design_partner_selection"
    SOLID_FINDINGS = "solid_findings"
    PATTERN_RECOMMENDATIONS = "pattern_recommendations"
    QUALITY_SCORES = "quality_scores"


class FeedbackType(str, Enum):
    REJECTION = "rejection"
    REFINEMENT = "refinement"
    APPROVAL = "approval"


class ArchitectureStage(str, Enum):
    
    REQUIREMENTS_PARSE = "requirements_parse"
    SOLUTION_STRATEGY = "solution_strategy"
    FLOW_DIAGRAM = "flow_diagram"
    VALIDATION = "validation"
    DESIGN_PARTNER = "design_partner"
    SOLID_ANALYSIS = "solid_analysis"
    PATTERN_RECOMMENDATION = "pattern_recommendation"
    QUALITY_ASSESSMENT = "quality_assessment"


STAGE_PIPELINE_ORDER: list[ArchitectureStage] = [
    ArchitectureStage.REQUIREMENTS_PARSE,
    ArchitectureStage.SOLUTION_STRATEGY,
    ArchitectureStage.FLOW_DIAGRAM,
    ArchitectureStage.VALIDATION,
    ArchitectureStage.DESIGN_PARTNER,
    ArchitectureStage.SOLID_ANALYSIS,
    ArchitectureStage.PATTERN_RECOMMENDATION,
    ArchitectureStage.QUALITY_ASSESSMENT,
]


class ArchitectureFeedback(BaseModel):
    
    target_section: TargetSection
    feedback_type: FeedbackType
    feedback_text: str = ""
    constraint_additions: list[str] = Field(default_factory=list)


class StageExecutionStatus(str, Enum):
    EXECUTED = "executed"
    PRESERVED = "preserved"


class StageExecutionEntry(BaseModel):
    stage: ArchitectureStage
    status: StageExecutionStatus
    duration_seconds: float = 0.0
    detail: str = ""


class PipelineExecutionLog(BaseModel):
    
    job_id: str
    iteration_id: str
    entries: list[StageExecutionEntry] = Field(default_factory=list)

    def executed_stages(self) -> list[ArchitectureStage]:
        return [e.stage for e in self.entries if e.status == StageExecutionStatus.EXECUTED]

    def preserved_stages(self) -> list[ArchitectureStage]:
        return [e.stage for e in self.entries if e.status == StageExecutionStatus.PRESERVED]


class SectionDiff(BaseModel):
    
    section: TargetSection
    changed: bool
    similarity: float = 1.0
    previous_output: str = ""
    new_output: str = ""
    unified_diff: str = ""


class ConvergenceWarning(BaseModel):
    
    section: TargetSection
    consecutive_similar_outputs: int
    similarity_threshold: float
    message: str


class IterationRecord(BaseModel):
    
    iteration_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    iteration_number: int
    feedback: ArchitectureFeedback
    execution_log: PipelineExecutionLog
    section_diffs: list[SectionDiff] = Field(default_factory=list)
    convergence_warnings: list[ConvergenceWarning] = Field(default_factory=list)
    approved_sections: list[TargetSection] = Field(default_factory=list)
    status: str = "re_evaluated"


class FeedbackProcessingResult(BaseModel):
    job_id: str
    iteration_id: str
    iteration_number: int
    status: str
    target_section: TargetSection
    feedback_type: FeedbackType
    stages_re_evaluated: list[ArchitectureStage] = Field(default_factory=list)
    stages_preserved: list[ArchitectureStage] = Field(default_factory=list)
    approved_sections: list[TargetSection] = Field(default_factory=list)
    section_diffs: list[SectionDiff] = Field(default_factory=list)
    convergence_warnings: list[ConvergenceWarning] = Field(default_factory=list)
    execution_log: PipelineExecutionLog
    estimated_reevaluation_seconds: float = 0.0
    actual_duration_seconds: float = 0.0
