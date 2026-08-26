import { AlertTriangle, BarChart3, FlaskConical, Layers, MessageSquare } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FlowSteps } from "@/components/FlowSteps";
import { AnnotatedScreenshot } from "@/components/AnnotatedScreenshot";

// backend/learning/configs/*.json 의 catalog_order 순서. 목록이 어긋나면
// 화면에 있는 Case를 안내서에서 찾을 수 없게 되므로 케이스를 늘리거나
// 제목을 바꿀 때 여기도 함께 고쳐야 한다.
const CASE_STUDY_TOPICS = [
  "Channel Length와 Short Channel Effect",
  "Gate Oxide Thickness와 Gate Control",
  "Body Doping과 Vth–Ioff Design Window",
  "Source/Drain Doping과 On-State Conduction",
  "LDD와 Drain Field–Access Resistance Trade-off",
  "Channel Length × Oxide Thickness: Electrostatic Compensation",
  "Source/Drain × LDD: Junction Engineering",
  "Integrated Device Design: Target-Based Selection",
];

// "4. 최종 설명" 화면이 실제로 보여주는 항목들 (SummaryPage.tsx).
const CASE_STUDY_RESULTS = [
  "핵심 정리 — 이 Case에서 확인해야 할 결론",
  "초기 예측 → 실제 결과 — 내가 고른 답과 지표의 실제 변화",
  "결과를 보고 제출한 관찰",
  "모범 답안 — 케이스 조건과 실제 결과로 작성된 해설",
  "내 학습 피드백 — 잘 이해한 부분과 보완할 부분",
  "다시 확인할 근거 — Curve와 Field Map에서 볼 위치",
];

const TROUBLESHOOTING = [
  "모든 입력값이 설정되어 있는지 확인합니다.",
  "입력값이 허용 범위 안에 있는지 확인합니다.",
  "단위가 올바른지 확인합니다.",
  "이전 예측이 진행 중인지 확인합니다.",
  "화면을 빠르게 여러 번 옮기면 잠시 요청이 제한될 수 있습니다. 몇 초 뒤 다시 시도합니다.",
  "페이지를 새로고침한 뒤 다시 실행합니다.",
];

export default function GuidePage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-8">
        {/* Hero */}
        <div>
          <h1 className="text-2xl font-bold leading-snug">Guide</h1>
          <p className="mt-3 text-base leading-[1.8] text-foreground">
            본 Guide에서는 MOSFET AI Prediction and Learning Platform의 기본 이용 방법과 각 페이지의 주요 기능을 설명합니다.
          </p>
          <p className="mt-2 text-base leading-[1.8] text-foreground">
            플랫폼은 Theory, I–V Curve, Field Map, Case Study로 구성되며, 사용자는 학습 목적에 따라 원하는 기능을 선택하여 이용할 수
            있습니다.
          </p>
          <p className="mt-3 text-base leading-[1.8] text-foreground">MOSFET을 처음 학습하는 경우 다음 순서를 권장합니다.</p>
          <FlowSteps steps={["Theory", "Case Study", "I–V Curve", "Field Map"]} className="my-2" />
          <p className="mt-2 text-base leading-[1.8] text-foreground">
            Theory에서는 MOSFET의 기본 구조와 동작 원리를 학습합니다. 이후 Case Study에서는 주요 구조 변수를 중심으로 결과를 예상하고
            실제 예측값과 비교하며 학습 내용을 점검합니다. I–V Curve에서는 구조 변화에 따른 외부 전기적 특성을 확인하고, Field Map에서는
            소자 내부의 Potential, Electric Field와 Carrier Distribution을 관찰할 수 있습니다.
          </p>
          <p className="mt-2 text-base leading-[1.8] text-foreground">
            이미 MOSFET의 기본 개념을 알고 있는 경우 I–V Curve 또는 Field Map에서 원하는 조건을 직접 입력하여 자유롭게 결과를 확인할 수
            있습니다.
          </p>
          <p className="mt-3 text-base leading-[1.8] text-foreground">
            <span className="font-semibold">로그인</span>은 Case Study와 AI 기능에만 필요합니다. 소자 조건을 바꾸어 I–V Curve와 Field
            Map을 예측하고 비교하는 것, Theory를 보는 것은 로그인 없이 그대로 이용할 수 있습니다. Case Study는 진행 상황이 계정에 저장되어야
            이어서 학습할 수 있고, AI 설명과 AI 질문은 호출 한 번마다 비용이 발생하므로 계정 단위로 사용량을 관리합니다.
          </p>
        </div>

        {/* Case Study */}
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">Case Study</h2>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FlaskConical className="h-4 w-4 text-primary" />
                비교 실험으로 학습하기
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm leading-[1.8] text-foreground">
              <p>Case Study는 주요 MOSFET 현상을 비교 실험을 통해 학습하는 기능이며, 8개의 Case로 구성되어 있습니다.</p>
              <div>
                <ul className="list-inside list-decimal space-y-0.5 pl-1">
                  {CASE_STUDY_TOPICS.map((topic) => (
                    <li key={topic}>{topic}</li>
                  ))}
                </ul>
              </div>
              <p>
                각 Case에는 선행 Case가 지정되어 있어 앞의 Case를 완료해야 다음 Case가 열립니다. 뒤로 갈수록 변수를 두 개씩 함께 바꾸거나
                목표 특성을 만족하는 조건을 고르는 형태로 넓어지므로, 순서대로 진행하는 것을 권장합니다.
              </p>

              <p className="pt-1 font-semibold">학습은 네 단계로 진행됩니다.</p>
              <FlowSteps
                steps={["1. Case 이해", "2. 초기 예측", "3. 결과 관찰", "4. 최종 설명"]}
                className="my-1"
              />
              <p>
                <span className="font-semibold">1. Case 이해</span> 단계에서 이번 Case의 배경과 핵심 질문, 학습 목표, 그리고 기준 조건과
                비교 조건이 무엇인지 확인합니다. 어떤 변수가 바뀌고 어떤 변수가 고정되는지가 여기서 정해집니다.
              </p>
              <p>
                <span className="font-semibold">2. 초기 예측</span> 단계에서는 결과를 보기 전에 먼저 답합니다. 구조 조건의 변화에 따라 Ion,
                Ioff, Vth, DIBL 또는 Field Map이 어떻게 변할지 선택형 질문으로 답하고, 그렇게 판단한 근거를 서술형으로 입력합니다. 결과를
                보기 전에 근거를 적는 순서가 이 기능의 핵심입니다.
              </p>
              <p>
                <span className="font-semibold">3. 결과 관찰</span> 단계에서 기준 조건과 비교 조건의 I–V Curve, 전기적 파라미터, Field Map이
                제공됩니다. 전체 그래프만 보는 것이 아니라 화면이 제시하는 관찰 지점을 중심으로 비교한 뒤, 관찰한 내용을 다시 제출합니다.
              </p>
              <p>
                <span className="font-semibold">4. 최종 설명</span> 단계에서는 제출한 답변과 실제 결과를 대조한 결과가 정리됩니다.
              </p>
              <div>
                <ul className="list-inside list-disc space-y-0.5 pl-1">
                  {CASE_STUDY_RESULTS.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <p>
                AI 피드백은 사용자의 답변을 평가하기 위한 절대적인 채점 결과가 아니라, 학습 과정에서 놓친 부분을 확인하기 위한 보조 자료로
                활용합니다.
              </p>
              <p>
                진행 상황은 자동으로 저장되므로 중간에 나갔다가 이어서 학습할 수 있습니다. 같은 Case를 여러 번 학습할 수 있으며, 기록마다
                이름을 바꾸어 구분하거나 필요 없는 기록을 지울 수 있습니다. 결과 화면에서는 그 Case의 내용에 대해 AI에게 추가로 질문할 수도
                있습니다.
              </p>
            </CardContent>
          </Card>
        </section>

        {/* I-V Curve */}
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">I-V Curve</h2>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-4 w-4 text-primary" />
                I-V Curve 화면
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* 설명 문구는 현재 화면 기준이지만 이미지와 마커 좌표(xPct/yPct)는
                  다시 찍어 맞춰야 한다 — 아래 Field Map도 같다. */}
              <AnnotatedScreenshot
                src="/guide/iv-curve.png"
                alt="I-V Curve 페이지 화면"
                callouts={[
                  { xPct: 21.4, yPct: 15.5, label: "디바이스 파라미터(L, T, B, SD, LDD)를 입력합니다." },
                  { xPct: 97.2, yPct: 7.9, label: "Add를 눌러 입력한 조건을 커브 목록에 추가합니다." },
                  { xPct: 82.5, yPct: 17.2, label: "체크박스로 비교할 커브를 선택·해제합니다." },
                  { xPct: 90, yPct: 61.1, label: "선택한 커브에서 추출된 Vth, Ion, Ioff 등 전기적 파라미터를 확인합니다." },
                  { xPct: 75.2, yPct: 67, label: "자동 설명 탭에서 Analyze를 누르면 AI가 변화의 원인과 trade-off를 해석합니다." },
                ]}
              />
            </CardContent>
          </Card>
        </section>

        {/* Field Map */}
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">Field Map</h2>
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
                  { xPct: 63.3, yPct: 8.5, label: "표시할 물리량과 컬러 스케일, 표시 범위를 선택합니다." },
                  { xPct: 47.5, yPct: 47, label: "선택한 조건으로 생성된 소자 단면과 물리량 분포를 확인합니다." },
                  { xPct: 97.2, yPct: 8.2, label: "Add로 다른 조건의 소자를 추가해 나란히 비교합니다." },
                ]}
              />
            </CardContent>
          </Card>
        </section>

        {/* Interpretation note (shared by both pages above) */}
        <div className="text-base leading-[1.8] text-foreground">
          <p>I–V Curve는 외부 전기적 결과를 나타내고, Field Map은 내부 물리적 원인을 해석하는 데 활용됩니다.</p>
          <p className="mt-2">
            예측값 하나만 확인하기보다 기준 조건과 변경 조건 사이의 변화 방향과 크기를 비교합니다. 특정 파라미터가 개선되더라도 다른
            특성이 악화될 수 있습니다. 예를 들어 Channel Length 감소로 Ion이 증가하더라도 Ioff와 DIBL이 함께 증가할 수 있습니다.
          </p>
        </div>

        {/* AI 설명과 AI 질문 */}
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">AI 설명과 AI 질문</h2>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-primary" />
                결과 해석에 AI 활용하기
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3 text-sm leading-[1.8] text-foreground">
              <p>
                I–V Curve와 Field Map 화면 아래의 AI Explanation 카드는 두 개의 탭으로 나뉩니다.{" "}
                <span className="font-semibold">자동 설명</span>은 현재 선택한 조건들의 비교 결과를 한 번에 정리해 주고,{" "}
                <span className="font-semibold">AI 질문</span>은 그 결과에 대해 자유롭게 묻고 답을 받는 대화입니다.
              </p>
              <p>
                두 기능 모두 AI가 임의로 서술하지 않습니다. 예측 결과에서 뽑아낸 수치와 조건 변화를 근거로 먼저 정리한 뒤 그 근거 안에서만
                설명을 만들며, 근거에 없는 값은 답변에 등장하지 않습니다. 학습 모델이 예측한 값에는 그것이 예측값임을 함께 표시합니다.
              </p>
              <p>
                AI 질문에서 첫 질문을 보내면 그때의 소자 조건이 대화에 고정됩니다. 이후 화면에서 조건을 바꾸어도 대화는 처음 조건을 기준으로
                이어지므로, 바뀐 조건에 대해 묻고 싶을 때는 새 대화를 시작합니다. 한 대화에는 질문을 20개까지 담을 수 있고, 이전 대화 목록에서
                지난 대화를 다시 열어볼 수 있습니다.
              </p>
              <p>
                AI 응답은 계정당 하루 사용량이 정해져 있습니다. 한도에 도달하면 안내 문구가 표시되며, 조건을 바꾸어 예측하고 비교하는 기능은
                한도와 무관하게 계속 사용할 수 있습니다.
              </p>
            </CardContent>
          </Card>
        </section>

        {/* 주의사항 */}
        <section>
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide text-primary">주의사항</h2>
          <Card className="border-accent-orange/40 bg-accent-orange/5">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-accent-orange">
                <AlertTriangle className="h-4 w-4" />
                문제 해결
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-sm leading-[1.8] text-foreground">
              <p>예측 버튼이 동작하지 않거나 결과가 생성되지 않는 경우 다음 항목을 확인합니다.</p>
              <ul className="list-inside list-disc space-y-0.5 pl-1">
                {TROUBLESHOOTING.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <p>
                로그인이 필요하다는 안내가 표시되면 로그인 후 다시 시도합니다. 화면을 오래 열어 두면 로그인이 만료될 수 있으며, 이 경우
                작성 중이던 내용이 아니라 저장된 학습 기록은 그대로 남아 있습니다.
              </p>
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
