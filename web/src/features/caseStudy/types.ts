// 서버 응답은 snake_case로 온다 (java_service의 SNAKE_CASE 설정).
//
// 학습 세션의 내용은 Python 소유라 여기서 필드를 하나씩 옮겨 적지 않는다.
// 화면이 실제로 읽는 값만 골라 두고 나머지는 그대로 들고 다닌다 — Python이
// 세션 구조를 고쳐도 프론트가 따라 깨지지 않게.

export interface TopicSummary {
  topic_id: string;
  title: string;
  description: string;
  catalog_order: number;
  prerequisite_topic_ids: string[];
  /** 카드의 "변경 조건" 한 줄. 케이스마다 규칙이 달라 서버가 만들어 준다. */
  comparison_caption: string;
  changed_parameters: string[];
  parameter_labels: Record<string, string>;
  baseline_label: string;
  comparison_label: string;
}

export interface SafeQuestion {
  question_id: string;
  type: string;
  prompt: string;
  options: string[];
  reason_required: boolean;
}

export interface ReferenceCondition {
  condition_id: string;
  label: string;
  conditions: Record<string, number>;
}

/** "1. Case 이해" 화면의 내용 */
export interface CaseGuide {
  context: string;
  question: string;
  evidence: string[];
  caution: string;
}

export interface TopicDetail extends TopicSummary {
  learning_objectives: string[];
  baseline_conditions: Record<string, number>;
  comparison_conditions: Record<string, number>;
  condition_descriptions: Record<string, string>;
  theory_concepts: string[];
  theory_reference: string;
  /** 'controlled_pair' | 'two_by_two' | 'candidate_set' */
  comparison_design: string;
  reference_conditions: ReferenceCondition[];
  display_parameters: string[];
  guide: CaseGuide;
  prediction_questions: SafeQuestion[];
  observation_questions: SafeQuestion[];
}

/** 케이스 카드의 상태. 잠금은 선행 케이스를 안 끝냈다는 뜻이다. */
export type CaseStatus = "completed" | "in_progress" | "not_started" | "locked";

export interface CaseProgress {
  topic_id: string;
  title: string;
  status: CaseStatus;
  session_count: number;
  completed_session_count: number;
  latest_step: string | null;
  completed_concepts: string[];
  remaining_concepts: string[];
  updated_at: string | null;
  prerequisites: string[];
  prerequisites_met: boolean;
}

export interface LearningPortfolio {
  cases: CaseProgress[];
  completed_case_count: number;
  total_case_count: number;
  next_topic_id: string | null;
  recommendation_kind: string;
  recommendation_reason: string;
}

/** 학습 기록 목록의 한 줄. 세션 전체(수십 KB)를 싣지 않는다. */
export interface SessionSummary {
  session_id: string;
  topic_id: string;
  display_name: string;
  current_step: string;
  completed: boolean;
  updated_at: string;
}

/** Python이 소유하는 세션. 화면이 읽는 값만 적어 둔다. */
export interface LearningSession {
  session_id: string;
  topic_id: string;
  current_step: string;
  display_name: string;
  [key: string]: unknown;
}

export interface CurveData {
  kind: string;
  grid: number[];
  fixed_biases: number[];
  currents: number[][];
}

/**
 * 실험 한 조건의 곡선. Field Map은 담겨 오지 않는다 — conditions가 곧 소자
 * 파라미터라 화면이 기존 /fields/predict, /fields/display를 그대로 부른다.
 */
export interface ConditionRun {
  label: string;
  conditions: Record<string, number>;
  idvd: CurveData;
  idvg: CurveData;
}

export interface ExperimentResult {
  runs: ConditionRun[];
}

export interface ExperimentReply {
  session: LearningSession;
  result: ExperimentResult;
}

/** 데스크톱 앱의 4단계 (LEARNING_PAGE_LABELS) */
export const LEARNING_PAGES = [
  { id: "understanding", label: "1. Case 이해" },
  { id: "prediction", label: "2. 초기 예측" },
  { id: "observation", label: "3. 결과 관찰" },
  { id: "explanation", label: "4. 최종 설명" },
] as const;

export type LearningPage = (typeof LEARNING_PAGES)[number]["id"];

export const CASE_STATUS_LABELS: Record<CaseStatus, string> = {
  completed: "완료",
  in_progress: "진행 중",
  not_started: "시작 전",
  locked: "선행 학습 필요",
};
