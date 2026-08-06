export interface TopicSummary {
  topic_id: string;
  title: string;
  description: string;
  catalog_order: number;
  prerequisite_topic_ids: string[];
}

export interface ExperimentConditions {
  L: number;
  T: number;
  B: number;
  SD: number;
  LDD: number;
}

export interface SafeQuestion {
  question_id: string;
  type: string;
  prompt: string;
  options: string[];
  reason_required: boolean;
}

export interface TopicDetail {
  topic_id: string;
  title: string;
  description: string;
  learning_objectives: string[];
  baseline: ExperimentConditions;
  comparison: ExperimentConditions;
  prediction_questions: SafeQuestion[];
  observation_questions: SafeQuestion[];
}

export interface AnswerSubmission {
  question_id: string;
  selected: string[];
  reason: string;
}

export interface QuestionResult {
  question_id: string;
  prompt: string;
  correct_options: string[];
  selected: string[];
  fully_correct: boolean;
}

export interface GradeResponse {
  positive_feedback: string[];
  corrections: string[];
  summary: string;
  question_results: QuestionResult[];
}
