import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CurveChart } from "@/features/curves/components/CurveChart";
import { FieldCompareChart } from "@/features/fields/components/FieldCompareChart";
import { fetchFieldDisplayCompare } from "@/features/fields/api";
import type { DeviceParameters } from "@/features/curves/types";
import type { CurveEntry } from "@/features/curves/types";
import type { FieldCompareResponse, FieldDisplay } from "@/features/fields/types";
import { predictCurve } from "@/features/curves/api";
import { fetchCaseStudyTopic, gradeCaseStudy, getErrorMessage } from "./api";
import type { ExperimentConditions, GradeResponse, SafeQuestion, TopicDetail } from "./types";

const FIELD_TOGGLE: FieldDisplay[] = ["Potential", "Electric field"];

type Step = "intro" | "predict" | "loading" | "results" | "feedback";

interface AnswerState {
  selected: string[];
  reason: string;
}

function toDeviceParameters(conditions: ExperimentConditions): DeviceParameters {
  const formatCount = (value: number): string => {
    const exponent = Math.floor(Math.log10(value));
    const mantissa = Math.round(value / 10 ** exponent);
    return `${mantissa}e${exponent}`;
  };
  return {
    L: String(Math.round(conditions.L)),
    T: String(Math.round(conditions.T)),
    B: formatCount(conditions.B),
    SD: formatCount(conditions.SD),
    LDD: formatCount(conditions.LDD),
  };
}

function conditionRows(conditions: ExperimentConditions): { label: string; value: string }[] {
  const params = toDeviceParameters(conditions);
  return [
    { label: "Channel length L", value: `${params.L} nm` },
    { label: "Oxide thickness T", value: `${params.T} nm` },
    { label: "Body doping B", value: `${params.B} cm⁻³` },
    { label: "S/D doping SD", value: `${params.SD} cm⁻³` },
    { label: "LDD doping", value: `${params.LDD} cm⁻³` },
  ];
}

function QuestionForm({
  question,
  answer,
  onChange,
}: {
  question: SafeQuestion;
  answer: AnswerState;
  onChange: (next: AnswerState) => void;
}) {
  const singleSelect = question.type.startsWith("single_select");

  function toggleOption(option: string) {
    if (singleSelect) {
      onChange({ ...answer, selected: [option] });
      return;
    }
    const selected = answer.selected.includes(option)
      ? answer.selected.filter((item) => item !== option)
      : [...answer.selected, option];
    onChange({ ...answer, selected });
  }

  return (
    <div className="flex flex-col gap-2 rounded-md border border-outline-variant bg-surface-container-low p-3">
      <p className="text-[13px] font-medium text-foreground">{question.prompt}</p>
      <div className="flex flex-col gap-1.5">
        {question.options.map((option) => (
          <label key={option} className="flex items-center gap-2 text-[12.5px] text-on-surface-variant">
            <Checkbox checked={answer.selected.includes(option)} onCheckedChange={() => toggleOption(option)} />
            {option}
          </label>
        ))}
      </div>
      {question.reason_required && (
        <div className="flex flex-col gap-1">
          <label className="text-[10px] uppercase text-on-surface-variant">근거</label>
          <Textarea
            value={answer.reason}
            onChange={(e) => onChange({ ...answer, reason: e.target.value })}
            placeholder="왜 그렇게 예상했는지 적어보세요."
            className="text-[12.5px]"
          />
        </div>
      )}
    </div>
  );
}

export function CaseStudyFlow({ topicId }: { topicId: string }) {
  const [topic, setTopic] = useState<TopicDetail | null>(null);
  const [step, setStep] = useState<Step>("intro");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [predictionAnswers, setPredictionAnswers] = useState<Record<string, AnswerState>>({});
  const [observationAnswers, setObservationAnswers] = useState<Record<string, AnswerState>>({});
  const [curves, setCurves] = useState<CurveEntry[]>([]);
  const [compareData, setCompareData] = useState<FieldCompareResponse | null>(null);
  const [display, setDisplay] = useState<FieldDisplay>("Potential");
  const [feedback, setFeedback] = useState<GradeResponse | null>(null);

  useEffect(() => {
    fetchCaseStudyTopic(topicId)
      .then((data) => {
        setTopic(data);
        const emptyPrediction: Record<string, AnswerState> = {};
        data.prediction_questions.forEach((q) => (emptyPrediction[q.question_id] = { selected: [], reason: "" }));
        setPredictionAnswers(emptyPrediction);
        const emptyObservation: Record<string, AnswerState> = {};
        data.observation_questions.forEach((q) => (emptyObservation[q.question_id] = { selected: [], reason: "" }));
        setObservationAnswers(emptyObservation);
      })
      .catch((err) => setError(getErrorMessage(err)));
  }, [topicId]);

  const baselineParams = useMemo(() => (topic ? toDeviceParameters(topic.baseline) : null), [topic]);
  const comparisonParams = useMemo(() => (topic ? toDeviceParameters(topic.comparison) : null), [topic]);

  async function runExperiment() {
    if (!topic || !baselineParams || !comparisonParams) return;
    const unanswered = topic.prediction_questions.some((q) => predictionAnswers[q.question_id]?.selected.length === 0);
    if (unanswered) {
      setError("모든 예측 질문에 하나 이상 답해주세요.");
      return;
    }
    setError(null);
    setStep("loading");
    setBusy(true);
    try {
      const [baselineCurve, comparisonCurve] = await Promise.all([
        predictCurve(baselineParams),
        predictCurve(comparisonParams),
      ]);
      setCurves([
        { id: 1, label: "Baseline", visible: true, parameters: baselineParams, result: baselineCurve },
        { id: 2, label: "Comparison", visible: true, parameters: comparisonParams, result: comparisonCurve },
      ]);
      const compare = await fetchFieldDisplayCompare(
        [
          { label: "Baseline", ...baselineParams },
          { label: "Comparison", ...comparisonParams },
        ],
        display,
        "Auto",
        "Robust 1-99%",
      );
      setCompareData(compare);
      setStep("results");
    } catch (err) {
      setError(getErrorMessage(err));
      setStep("predict");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (step !== "results" || !baselineParams || !comparisonParams) return;
    fetchFieldDisplayCompare(
      [
        { label: "Baseline", ...baselineParams },
        { label: "Comparison", ...comparisonParams },
      ],
      display,
      "Auto",
      "Robust 1-99%",
    )
      .then(setCompareData)
      .catch((err) => setError(getErrorMessage(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [display]);

  async function submitFeedback() {
    if (!topic) return;
    const unanswered = topic.observation_questions.some((q) => observationAnswers[q.question_id]?.selected.length === 0);
    if (unanswered) {
      setError("모든 관찰 질문에 하나 이상 답해주세요.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const predictionSubmissions = topic.prediction_questions.map((q) => ({
        question_id: q.question_id,
        selected: predictionAnswers[q.question_id]?.selected ?? [],
        reason: predictionAnswers[q.question_id]?.reason ?? "",
      }));
      const observationSubmissions = topic.observation_questions.map((q) => ({
        question_id: q.question_id,
        selected: observationAnswers[q.question_id]?.selected ?? [],
        reason: observationAnswers[q.question_id]?.reason ?? "",
      }));
      const result = await gradeCaseStudy(topic.topic_id, predictionSubmissions, observationSubmissions);
      setFeedback(result);
      setStep("feedback");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function restart() {
    if (!topic) return;
    const emptyPrediction: Record<string, AnswerState> = {};
    topic.prediction_questions.forEach((q) => (emptyPrediction[q.question_id] = { selected: [], reason: "" }));
    setPredictionAnswers(emptyPrediction);
    const emptyObservation: Record<string, AnswerState> = {};
    topic.observation_questions.forEach((q) => (emptyObservation[q.question_id] = { selected: [], reason: "" }));
    setObservationAnswers(emptyObservation);
    setFeedback(null);
    setCurves([]);
    setCompareData(null);
    setStep("intro");
  }

  if (!topic) {
    return (
      <Card>
        <CardContent className="p-4 text-[13px] text-on-surface-variant">
          {error ?? "Case를 불러오는 중입니다…"}
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <p className="text-[12px] text-destructive">{error}</p>}

      {step === "intro" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-[15px]">{topic.title}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-[13px] text-on-surface-variant">
            <p>{topic.description}</p>
            <div>
              <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">학습 목표</p>
              <ul className="list-inside list-disc space-y-0.5">
                {topic.learning_objectives.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-md border border-outline-variant p-2">
                <p className="mb-1 text-[11px] font-bold uppercase text-on-surface-variant/70">Baseline</p>
                {conditionRows(topic.baseline).map((row) => (
                  <p key={row.label} className="text-[12px]">
                    {row.label}: <span className="font-mono">{row.value}</span>
                  </p>
                ))}
              </div>
              <div className="rounded-md border border-outline-variant p-2">
                <p className="mb-1 text-[11px] font-bold uppercase text-on-surface-variant/70">Comparison</p>
                {conditionRows(topic.comparison).map((row) => (
                  <p key={row.label} className="text-[12px]">
                    {row.label}: <span className="font-mono">{row.value}</span>
                  </p>
                ))}
              </div>
            </div>
            <Button size="sm" className="self-end" onClick={() => setStep("predict")}>
              사전 예측 시작
            </Button>
          </CardContent>
        </Card>
      )}

      {step === "predict" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-[14px]">결과를 실행하기 전에 예상해보세요</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {topic.prediction_questions.map((q) => (
              <QuestionForm
                key={q.question_id}
                question={q}
                answer={predictionAnswers[q.question_id] ?? { selected: [], reason: "" }}
                onChange={(next) => setPredictionAnswers((prev) => ({ ...prev, [q.question_id]: next }))}
              />
            ))}
            <Button size="sm" className="self-end" onClick={runExperiment} disabled={busy}>
              예측 제출 후 모델 실행
            </Button>
          </CardContent>
        </Card>
      )}

      {step === "loading" && (
        <Card>
          <CardContent className="p-6 text-center text-[13px] text-on-surface-variant">
            예측 모델을 실행하는 중입니다…
          </CardContent>
        </Card>
      )}

      {step === "results" && (
        <div className="flex flex-col gap-3">
          <div className="h-72">
            <CurveChart curves={curves} combined />
          </div>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-[13px]">Field Map 비교</CardTitle>
              <Select value={display} onValueChange={(v) => setDisplay(v as FieldDisplay)}>
                <SelectTrigger size="sm" className="w-40 text-xs">
                  <SelectValue>{display}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {FIELD_TOGGLE.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardHeader>
            <CardContent className="h-72">
              <FieldCompareChart
                devices={(compareData?.items ?? []).map((item) => ({
                  label: item.label,
                  mesh: item.mesh,
                  toxNm: Number(topic.baseline.T),
                }))}
                display={display}
                compareData={compareData}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle className="text-[14px]">그래프와 Field Map을 관찰한 뒤 답하세요</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {topic.observation_questions.map((q) => (
                <QuestionForm
                  key={q.question_id}
                  question={q}
                  answer={observationAnswers[q.question_id] ?? { selected: [], reason: "" }}
                  onChange={(next) => setObservationAnswers((prev) => ({ ...prev, [q.question_id]: next }))}
                />
              ))}
              <Button size="sm" className="self-end" onClick={submitFeedback} disabled={busy}>
                관찰 답변 제출하고 피드백 보기
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {step === "feedback" && feedback && (
        <Card>
          <CardHeader>
            <CardTitle className="text-[14px]">학습 피드백</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 text-[13px]">
            <p className="font-medium text-foreground">{feedback.summary}</p>
            <div>
              <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">
                잘 이해한 부분
              </p>
              <ul className="list-inside list-disc space-y-0.5 text-on-surface-variant">
                {feedback.positive_feedback.length === 0 && <li>정확히 선택한 항목이 없습니다.</li>}
                {feedback.positive_feedback.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">
                보완할 부분
              </p>
              <ul className="list-inside list-disc space-y-0.5 text-on-surface-variant">
                {feedback.corrections.length === 0 && <li>보완할 사항이 없습니다.</li>}
                {feedback.corrections.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </div>
            <Button size="sm" variant="outline" className="self-end" onClick={restart}>
              처음부터 다시 하기
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
