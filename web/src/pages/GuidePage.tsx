import { AlertTriangle, BarChart3, FlaskConical, Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FlowSteps } from "@/components/FlowSteps";
import { AnnotatedScreenshot } from "@/components/AnnotatedScreenshot";

const CASE_STUDY_TOPICS = [
  "Channel Length와 Short Channel Effect",
  "Oxide Thickness와 Gate Control",
  "Body Doping과 Threshold Voltage",
  "LDD와 Drain Electric Field",
  "Ion–Ioff Trade-off",
];

const CASE_STUDY_FEEDBACK = [
  "정확하게 이해한 부분",
  "보완이 필요한 부분",
  "잘못 연결한 개념",
  "실제 결과에서 확인할 근거",
  "Curve와 Field Map에서 관찰할 위치",
  "핵심 개념 정리",
];

const TROUBLESHOOTING = [
  "모든 입력값이 설정되어 있는지 확인합니다.",
  "입력값이 허용 범위 안에 있는지 확인합니다.",
  "단위가 올바른지 확인합니다.",
  "이전 예측이 진행 중인지 확인합니다.",
  "페이지를 새로고침한 뒤 다시 실행합니다.",
];

export default function GuidePage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-8">
        {/* Hero */}
        <div>
          <h1 className="text-xl font-bold leading-snug">Guide</h1>
          <p className="mt-3 text-sm leading-relaxed text-on-surface-variant">
            본 Guide에서는 MOSFET AI Prediction and Learning Platform의 기본 이용 방법과 각 페이지의 주요 기능을 설명합니다.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            플랫폼은 Theory, I–V Curve, Field Map, Case Study로 구성되며, 사용자는 학습 목적에 따라 원하는 기능을 선택하여 이용할 수
            있습니다.
          </p>
          <p className="mt-3 text-sm leading-relaxed text-on-surface-variant">MOSFET을 처음 학습하는 경우 다음 순서를 권장합니다.</p>
          <FlowSteps steps={["Theory", "Case Study", "I–V Curve", "Field Map"]} className="my-2" />
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            Theory에서는 MOSFET의 기본 구조와 동작 원리를 학습합니다. 이후 Case Study에서는 주요 구조 변수를 중심으로 결과를 예상하고
            실제 예측값과 비교하며 학습 내용을 점검합니다. I–V Curve에서는 구조 변화에 따른 외부 전기적 특성을 확인하고, Field Map에서는
            소자 내부의 Potential, Electric Field와 Carrier Distribution을 관찰할 수 있습니다.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            이미 MOSFET의 기본 개념을 알고 있는 경우 I–V Curve 또는 Field Map에서 원하는 조건을 직접 입력하여 자유롭게 결과를 확인할 수
            있습니다.
          </p>
        </div>

        {/* Case Study */}
        <section>
          <h2 className="mb-2 text-xs font-bold uppercase tracking-wide text-on-surface-variant">Case Study</h2>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-primary" />
                비교 실험으로 학습하기
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-[13px] leading-relaxed text-on-surface-variant">
              <p>Case Study는 주요 MOSFET 현상을 비교 실험을 통해 학습하는 기능입니다.</p>
              <div>
                <p className="mb-1">다음과 같은 학습 주제를 선택할 수 있습니다.</p>
                <ul className="list-inside list-disc space-y-0.5 pl-1">
                  {CASE_STUDY_TOPICS.map((topic) => (
                    <li key={topic}>{topic}</li>
                  ))}
                </ul>
              </div>
              <p>
                Case Study에서는 결과를 바로 제공하지 않습니다. 먼저 구조 조건의 변화에 따라 Ion, Ioff, Vth, DIBL 또는 Field Map이
                어떻게 변할지 예상합니다. 선택형 질문과 서술형 질문을 통해 예상 결과와 판단 근거를 입력합니다.
              </p>
              <p>
                사전 예측을 제출하면 기준 구조와 비교 구조의 I–V Curve, 전기적 파라미터와 Field Map이 제공됩니다. 결과를 확인할 때는
                전체 그래프만 보는 것이 아니라 화면에서 제시하는 관찰 지점을 중심으로 비교합니다.
              </p>
              <div>
                <p className="mb-1">학습 AI는 사용자의 예상과 실제 분석 결과를 비교하여 다음 내용을 제공합니다.</p>
                <ul className="list-inside list-disc space-y-0.5 pl-1">
                  {CASE_STUDY_FEEDBACK.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <p>
                AI 피드백은 사용자의 답변을 평가하기 위한 절대적인 채점 결과가 아니라, 학습 과정에서 놓친 부분을 확인하기 위한 보조
                자료로 활용합니다.
              </p>
            </CardContent>
          </Card>
        </section>

        {/* I-V Curve */}
        <section>
          <h2 className="mb-2 text-xs font-bold uppercase tracking-wide text-on-surface-variant">I-V Curve</h2>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-primary" />
                I-V Curve 화면
              </CardTitle>
            </CardHeader>
            <CardContent>
              <AnnotatedScreenshot
                src="/guide/iv-curve.png"
                alt="I-V Curve 페이지 화면"
                callouts={[
                  { xPct: 21.4, yPct: 15.5, label: "디바이스 파라미터(L, T, B, SD, LDD)를 입력합니다." },
                  { xPct: 97.2, yPct: 7.9, label: "Add를 눌러 입력한 조건을 커브 목록에 추가합니다." },
                  { xPct: 82.5, yPct: 17.2, label: "체크박스로 비교할 커브를 선택·해제합니다." },
                  { xPct: 90, yPct: 61.1, label: "선택한 커브에서 추출된 Vth, Ion, Ioff 등 물리 파라미터를 확인합니다." },
                  { xPct: 75.2, yPct: 67, label: "Analyze를 누르면 AI가 그래프 변화의 원인을 해석해 줍니다." },
                ]}
              />
            </CardContent>
          </Card>
        </section>

        {/* Field Map */}
        <section>
          <h2 className="mb-2 text-xs font-bold uppercase tracking-wide text-on-surface-variant">Field Map</h2>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-4 w-4 text-primary" />
                Field Map 화면
              </CardTitle>
            </CardHeader>
            <CardContent>
              <AnnotatedScreenshot
                src="/guide/field-map.png"
                alt="Field Map 페이지 화면"
                callouts={[
                  { xPct: 21.3, yPct: 16.7, label: "동일하게 디바이스 파라미터를 입력합니다." },
                  { xPct: 63.3, yPct: 8.5, label: "표시할 필드 종류와 컬러 스케일을 선택합니다." },
                  { xPct: 47.5, yPct: 47, label: "선택한 조건으로 생성된 디바이스 단면과 필드 분포를 확인합니다." },
                  { xPct: 97.2, yPct: 8.2, label: "Add로 다른 조건의 디바이스를 추가해 비교합니다." },
                ]}
              />
            </CardContent>
          </Card>
        </section>

        {/* Interpretation note (shared by both pages above) */}
        <div className="text-sm leading-relaxed text-on-surface-variant">
          <p>I–V Curve는 외부 전기적 결과를 나타내고, Field Map은 내부 물리적 원인을 해석하는 데 활용됩니다.</p>
          <p className="mt-2">
            예측값 하나만 확인하기보다 기준 조건과 변경 조건 사이의 변화 방향과 크기를 비교합니다. 특정 파라미터가 개선되더라도 다른
            특성이 악화될 수 있습니다. 예를 들어 Channel Length 감소로 Ion이 증가하더라도 Ioff와 DIBL이 함께 증가할 수 있습니다.
          </p>
        </div>

        {/* 주의사항 */}
        <section>
          <h2 className="mb-2 text-xs font-bold uppercase tracking-wide text-on-surface-variant">주의사항</h2>
          <Card className="border-accent-orange/40 bg-accent-orange/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-accent-orange">
                <AlertTriangle className="h-4 w-4" />
                문제 해결
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-[13px] leading-relaxed text-on-surface-variant">
              <p>예측 버튼이 동작하지 않거나 결과가 생성되지 않는 경우 다음 항목을 확인합니다.</p>
              <ul className="list-inside list-disc space-y-0.5 pl-1">
                {TROUBLESHOOTING.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <p>
                AI 분석 또는 Case Study 피드백 생성에 실패하더라도 I–V Curve, Field Map과 추출 파라미터가 정상적으로 생성되었다면 해당
                결과는 직접 확인할 수 있습니다.
              </p>
              <p>
                본 플랫폼은 교육용 예측 도구이며 실제 소자 설계나 공정 조건 결정을 위한 상용 TCAD 대체 도구가 아닙니다. 예측 결과는 구조
                변화에 따른 경향 비교와 학습 목적으로 활용해야 합니다.
              </p>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
