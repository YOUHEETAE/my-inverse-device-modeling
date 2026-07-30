"""Case Study learning-domain primitives.

Importing this package performs no GUI construction, model inference, network
request, or filesystem write.
"""

from .schemas import (
    AnswerRecord,
    FollowupTurn,
    LearningSession,
    LearningStep,
    NextActionSpec,
    QuestionSpec,
    TopicConfig,
    UnderstandingLevel,
)
from .analysis_adapter import LearningAnalysisAdapter
from .analysis_schemas import (
    ElectricalChange,
    LearningAnalysisContext,
    LearningObservation,
    LearningWarning,
)
from .llm_service import LearningLLMService
from .intent_interpreter import QuestionIntent
from .dialogue_state import DialogueState, DialogueStateManager
from .knowledge_layers import (
    LearningKnowledgeAssembler,
    LearningKnowledgeLayers,
)
from .question_router import QuestionRoute, TutorQuestionRouter
from .response_planner import LearningResponsePlan, build_response_plan
from .quality_audit import (
    TutorQualityReport,
    TutorAuditScenario,
    TutorScenarioAuditReport,
    TutorScenarioResult,
    TutorTurnAudit,
    audit_followup_history,
    audit_learning_session,
    run_tutor_scenarios,
)
from .knowledge_base import (
    TheoryConcept,
    TheoryKnowledgeBase,
    load_theory_knowledge_base,
)
from .theory_answerer import GroundedTheoryAnswerer, TheoryAnswerDraft
from .tutor_schemas import (
    AnswerEvaluation,
    FollowupResponse,
    LearningFeedback,
    LearningSessionSummary,
    NextActionDecision,
)
from .session_repository import (
    InMemorySessionRepository,
    JsonSessionRepository,
    LearningSessionRepository,
    SessionStorageError,
)
from .state_machine import InvalidLearningTransition, LearningStateMachine
from .topics import TopicConfigError, load_topic, load_topics
from .validation import (
    ConditionValidationError,
    compare_experiment_conditions,
    validate_model_conditions,
)
from .workflow import (
    ObservationReview,
    apply_observation_review,
    combine_evaluations,
    review_observations,
)

__all__ = [
    "AnswerRecord",
    "AnswerEvaluation",
    "ConditionValidationError",
    "ElectricalChange",
    "DialogueState",
    "DialogueStateManager",
    "FollowupTurn",
    "FollowupResponse",
    "InMemorySessionRepository",
    "InvalidLearningTransition",
    "JsonSessionRepository",
    "LearningSession",
    "LearningSessionRepository",
    "LearningAnalysisAdapter",
    "LearningAnalysisContext",
    "LearningFeedback",
    "LearningLLMService",
    "LearningKnowledgeAssembler",
    "LearningKnowledgeLayers",
    "LearningObservation",
    "LearningResponsePlan",
    "LearningSessionSummary",
    "LearningStateMachine",
    "LearningStep",
    "LearningWarning",
    "NextActionSpec",
    "NextActionDecision",
    "ObservationReview",
    "QuestionSpec",
    "QuestionIntent",
    "QuestionRoute",
    "GroundedTheoryAnswerer",
    "SessionStorageError",
    "TopicConfig",
    "TopicConfigError",
    "TutorQuestionRouter",
    "TutorQualityReport",
    "TutorAuditScenario",
    "TutorScenarioAuditReport",
    "TutorScenarioResult",
    "TutorTurnAudit",
    "TheoryAnswerDraft",
    "TheoryConcept",
    "TheoryKnowledgeBase",
    "UnderstandingLevel",
    "compare_experiment_conditions",
    "build_response_plan",
    "audit_followup_history",
    "audit_learning_session",
    "run_tutor_scenarios",
    "apply_observation_review",
    "combine_evaluations",
    "load_topic",
    "load_topics",
    "load_theory_knowledge_base",
    "review_observations",
    "validate_model_conditions",
]
