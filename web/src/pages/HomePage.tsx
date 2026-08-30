import type { ComponentType } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  FlaskConical,
  Layers,
  Sigma,
  Sparkles,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { FlowSteps } from "@/components/FlowSteps";
import { cn } from "@/lib/utils";

/**
 * 첫 화면.
 *
 * 처음 온 사람이 "이게 뭘 하는 물건인지"를 스크롤 없이 알아야 하는 자리다.
 * 그래서 설명을 문단으로 쌓지 않고, 한 문장과 실제 화면 사진을 먼저 놓는다 —
 * 이 도구의 결과물은 그래프라서, 그래프 한 장이 문단 다섯 개보다 빠르다.
 *
 * 자세한 설명은 지우지 않고 아래로 내렸다. 읽을 사람은 읽고, 바로 써볼 사람은
 * 위에서 버튼을 누르면 된다.
 */

interface Tool {
  icon: ComponentType<{ className?: string }>;
  title: string;
  to: string;
  summary: string;
  detail: string;
}

// 카드 순서는 사이드바와 같게 둔다. 처음 본 화면의 순서가 곧 메뉴 순서여야
// 다음에 찾을 때 헤매지 않는다.
const TOOLS: Tool[] = [
  {
    icon: Sigma,
    title: "Theory",
    to: "/theory",
    summary: "곡선을 읽는 기준",
    detail:
      "MOSFET의 구조와 동작 원리, I–V 특성, 단채널 효과를 6개 장으로 다룹니다. PN 접합과 MOS Capacitor는 값을 바꿔가며 직접 돌려볼 수 있습니다.",
  },
  {
    icon: BarChart3,
    title: "I–V Curve",
    to: "/curves",
    summary: "밖에서 본 소자",
    detail:
      "구조와 도핑 조건에서 Id–Vg, Id–Vd 곡선을 예측하고 여러 조건을 겹쳐 비교합니다. Vth, Ion, Ioff, SS, DIBL 등 전기적 파라미터를 자동으로 뽑아 나란히 놓습니다.",
  },
  {
    icon: Layers,
    title: "Field Map",
    to: "/fields",
    summary: "안에서 본 소자",
    detail:
      "소자 내부의 Potential, Electric Field, 캐리어 분포를 공간 분포로 봅니다. I–V Curve가 결과라면 여기는 그 결과가 생긴 원인입니다.",
  },
  {
    icon: FlaskConical,
    title: "Case Study",
    to: "/case-study",
    summary: "예측하고 맞춰보기",
    detail:
      "결과를 보기 전에 먼저 답을 적습니다. 실제 곡선을 관찰한 뒤 예측이 맞았는지 문항마다 확인하고, 근거와 함께 정리된 해설을 받습니다.",
  },
];

const ELECTRICAL_PARAMETERS = [
  { symbol: "Vth", name: "Threshold Voltage" },
  { symbol: "Ion", name: "On Current" },
  { symbol: "Ioff", name: "Off Current" },
  { symbol: "SS", name: "Subthreshold Swing" },
  { symbol: "DIBL", name: "Drain-Induced Barrier Lowering" },
  { symbol: "gm_max", name: "Maximum Transconductance" },
  { symbol: "gds", name: "Output Conductance" },
  { symbol: "Ron", name: "On-resistance" },
  { symbol: "λ", name: "Channel Length Modulation Parameter" },
];

const AI_ROLES = [
  {
    label: "예측",
    body: "구조와 도핑 조건에서 I–V Curve와 Field Map을 만듭니다. TCAD 환경을 구성하고 수치해석을 돌리지 않아도 결과를 볼 수 있게 하는 자리입니다.",
  },
  {
    label: "분석",
    body: "예측 결과에서 전기적 파라미터와 주요 변화를 뽑습니다. 기준 조건과 변경 조건의 차이, 곡선의 이동, Field Map의 특징과 trade-off를 정리합니다.",
  },
  {
    label: "학습",
    body: "Case Study에서 사전 예측과 실제 결과를 맞춰 봅니다. 이해 수준과 오개념에 따라 피드백을 주고, 원인을 더 확인할 후속 실험을 제안합니다.",
  },
];

const APPROPRIATE_USES = [
  "구조 변수에 따른 변화 경향 확인",
  "I–V Curve와 Field Map의 해석 연습",
  "전기적 파라미터 사이의 Trade-off 학습",
  "MOSFET 이론과 시뮬레이션 결과의 연결",
  "주요 소자 현상에 대한 비교 실습",
];

export default function HomePage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-5xl flex-col gap-10 px-6 py-10">
        {/* ── 히어로 ────────────────────────────────────────────────── */}
        <section className="flex flex-col gap-5">
          <div className="flex flex-col gap-3">
            <p className="font-mono text-[11px] uppercase tracking-wide text-primary">
              Semiconductor Device Learning Tool
            </p>
            {/* 첫 문장에 숫자와 현상을 넣는다. "AI 기반 학습 플랫폼"은 어떤
                서비스나 쓸 수 있는 말이라 아무것도 전달하지 못한다. 이 조건은
                Case Study 1번이 실제로 다루는 것이다. */}
            <h1 className="max-w-3xl text-pretty text-2xl font-bold leading-snug sm:text-3xl">
              채널 길이를 700 nm에서 300 nm로 줄이면
              <br className="hidden sm:block" /> 소자 안에서 무슨 일이 생길까요?
            </h1>
            <p className="max-w-2xl text-base leading-relaxed text-on-surface-variant">
              구조와 도핑 조건을 바꾸면 I–V Curve와 Field Map이 어떻게 달라지는지 바로
              비교합니다. TCAD 설치도, 라이선스도, 수렴 조정도 없이.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Link to="/curves" className={cn(buttonVariants({ size: "sm" }), "gap-1.5 text-xs")}>
              I–V Curve 시작하기
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              to="/case-study"
              className={cn(buttonVariants({ variant: "outline", size: "sm" }), "gap-1.5 text-xs")}
            >
              Case Study 둘러보기
            </Link>
            <Link
              to="/guide"
              className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "gap-1.5 text-xs")}
            >
              사용법 보기
            </Link>
          </div>

          {/* 화면 전체가 아니라 그래프만 싣는다. 전체 UI를 축소하면 휴대폰에서
              글자가 뭉개져 무엇을 보라는 것인지 알 수 없다. 이 도구가 내놓는
              것은 곡선이므로 곡선이 크게 보여야 한다.

              캡션으로 어느 선이 어느 조건인지 밝힌다. I–V Curve 화면의 범례는
              위치 기반 이름(Curve 1, 2)이라 그림만으로는 위 문장의 700/300과
              이어지지 않는다. */}
          <figure className="flex flex-col gap-2">
            <div className="overflow-hidden rounded-md border border-outline-variant bg-surface-container-lowest p-2 shadow-sm">
              <img
                src="/home/hero-curves.png"
                alt="채널 길이 700 nm와 300 nm의 Id–Vd, Id–Vg 곡선이 한 화면에 겹쳐 그려진 모습"
                className="w-full"
                width={1520}
                height={642}
                loading="eager"
              />
            </div>
            <figcaption className="text-xs text-on-surface-variant">
              채널 길이만 <span className="font-mono text-foreground">700 nm</span>(파랑) →{" "}
              <span className="font-mono text-foreground">300 nm</span>(빨강)로 바꾸고 나머지 조건은
              고정했습니다. 전류가 크게 늘었습니다 — 그 대가로 off 상태에서 무엇을 잃었는지는 Log
              축으로 바꾸면 드러납니다.
            </figcaption>
          </figure>
        </section>

        {/* ── 왜 필요한가 ──────────────────────────────────────────── */}
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-primary">왜 필요한가</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {[
              {
                head: "TCAD는 느립니다",
                body: "구조 생성, Mesh 설정, 물리 모델, 수렴 조정을 거쳐야 조건 하나의 결과가 나옵니다. 바꿔보며 배우기에는 한 번의 시도가 너무 비쌉니다.",
              },
              {
                head: "TCAD는 비쌉니다",
                body: "상용 도구는 고가의 라이선스와 별도 실행 환경이 필요합니다. 대학·연구기관에 소속되지 않으면 만져볼 기회 자체가 없습니다.",
              },
              {
                head: "그래서 못 배웁니다",
                body: "이론은 배웠는데 소자 안에서 무슨 일이 일어나는지 한 번도 못 본 채로 넘어갑니다. 이 도구는 그 사이를 메우려 합니다.",
              },
            ].map((item) => (
              <Card key={item.head}>
                <CardContent className="flex flex-col gap-1.5 py-4">
                  <h3 className="text-sm font-bold">{item.head}</h3>
                  <p className="text-xs leading-relaxed text-on-surface-variant">{item.body}</p>
                </CardContent>
              </Card>
            ))}
          </div>
          <p className="text-sm leading-relaxed text-on-surface-variant">
            예측 모델이 TCAD 결과를 대신 내놓기 때문에, 조건을 바꾸고 그 자리에서 비교할 수
            있습니다. 단순한 결과 조회가 아니라 다음 관계를 하나의 흐름으로 잇는 것이 목표입니다.
          </p>
          <FlowSteps steps={["소자 구조 및 도핑 조건", "내부 물리 현상", "I–V 특성", "전기적 파라미터"]} />
        </section>

        {/* ── 무엇을 하나 ──────────────────────────────────────────── */}
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-primary">무엇을 하나</h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {TOOLS.map((tool) => (
              <Link
                key={tool.title}
                to={tool.to}
                className="group rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Card className="h-full transition-colors group-hover:border-primary/40 motion-reduce:transition-none">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <tool.icon className="h-4 w-4 text-primary" />
                      {tool.title}
                      <span className="text-xs font-normal text-on-surface-variant">
                        {tool.summary}
                      </span>
                      <ArrowRight className="ml-auto h-3.5 w-3.5 shrink-0 text-on-surface-variant transition-transform group-hover:translate-x-0.5 motion-reduce:transition-none" />
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs leading-relaxed text-on-surface-variant">{tool.detail}</p>
                  </CardContent>
                </Card>
              </Link>
            ))}
          </div>

          {/* 격자 밖에 둔다. 카드 하나에 넣으면 그 칸만 길어져서 짝이 되는
              카드가 빈 채로 늘어난다. */}
          <div className="rounded-md border border-outline-variant bg-surface-container-low p-3">
            <h3 className="mb-2 text-xs font-bold">자동으로 추출되는 전기적 파라미터</h3>
            <ul className="grid grid-cols-1 gap-x-6 gap-y-1 font-mono text-[11px] sm:grid-cols-2 lg:grid-cols-3">
              {ELECTRICAL_PARAMETERS.map((param) => (
                <li key={param.symbol}>
                  <span className="font-semibold text-foreground">{param.symbol}</span>
                  <span className="text-on-surface-variant"> — {param.name}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ── 어떻게 배우나 ────────────────────────────────────────── */}
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-primary">어떻게 배우나</h2>
          <Card>
            <CardContent className="flex flex-col gap-3 py-4">
              <p className="text-sm leading-relaxed">
                결과만 보여주면 <span className="font-semibold">&ldquo;그렇구나&rdquo;</span> 하고
                넘어갑니다. 그래서 Case Study는 결과를 보기 전에 먼저 답을 적게 합니다. 틀린 지점이
                분명해야 무엇을 다시 봐야 하는지 알 수 있습니다.
              </p>
              <FlowSteps steps={["예측", "실험", "관찰", "채점"]} />
              <p className="text-xs leading-relaxed text-on-surface-variant">
                채점은 케이스마다 정해둔 정답과 대조하는 계산이고, 모범 답안은 케이스 정의와 실제
                계산 결과로 조립합니다. 문항마다 예측이 맞았는지 따로 표시됩니다.
              </p>
            </CardContent>
          </Card>
        </section>

        {/* ── AI의 자리 ────────────────────────────────────────────── */}
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-primary">AI의 자리</h2>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <Sparkles className="h-4 w-4 text-primary" />
                예측 · 분석 · 학습
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              <div className="flex flex-col gap-2">
                {AI_ROLES.map((role) => (
                  <p key={role.label} className="text-sm leading-relaxed">
                    <span className="font-mono text-xs font-semibold text-primary">
                      {role.label}
                    </span>
                    <span className="text-on-surface-variant"> — {role.body}</span>
                  </p>
                ))}
              </div>
              {/* 이 문단이 이 페이지에서 제일 중요한 차별점이라 상자로 세운다.
                  "LLM 붙였습니다"와 "LLM이 숫자를 만들지 못하게 막았습니다"는
                  전혀 다른 이야기다. */}
              <p className="rounded-sm border-l-2 border-primary bg-surface-container-low px-3 py-2 text-sm leading-relaxed">
                수치 계산과 결과 판정은 분석 코드가 합니다. LLM은 계산된 내용을 문장으로 옮기는
                역할이며, 근거에 없는 수치를 말하면 그 답변은 폐기됩니다.
              </p>
            </CardContent>
          </Card>
        </section>

        {/* ── 주의사항 ─────────────────────────────────────────────── */}
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-bold uppercase tracking-wide text-primary">주의사항</h2>
          <Card className="border-accent-orange/40 bg-accent-orange/5">
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base text-accent-orange">
                <AlertTriangle className="h-4 w-4" />
                교육용 도구 안내
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2 text-xs leading-relaxed text-on-surface-variant">
              <p>
                본 플랫폼은 MOSFET의 구조와 전기적 특성 사이의 관계를 학습하기 위한 교육용
                도구입니다. 정밀한 소자 설계나 실제 공정 조건 결정을 위한 상용 TCAD 대체 도구를
                목적으로 하지 않습니다.
              </p>
              <p>
                예측 모델은 DEVSIM으로 생성된 데이터와 사전에 정의된 입력 범위를 기반으로 합니다.
                학습 및 검증 범위를 벗어난 조건에서는 예측 정확도가 낮아질 수 있으며, 입력 범위
                내부의 결과도 실제 제작 소자 또는 다른 TCAD 환경의 결과와 차이가 발생할 수
                있습니다.
              </p>
              <p>
                시뮬레이션 조건에는 실제 소자 특성에 영향을 주는 모든 요소가 포함되어 있지
                않습니다. 공정 변동성, 계면 결함, 접촉 저항, 자가 발열, 양자 효과와 같은 일부
                현상은 단순화되거나 제외될 수 있습니다.
              </p>
              <p className="mt-1 font-medium text-foreground">
                따라서 본 플랫폼의 결과는 다음 목적으로 활용하는 것이 적절합니다.
              </p>
              <ul className="list-inside list-disc space-y-0.5 pl-1">
                {APPROPRIATE_USES.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <p className="mt-1">
                실제 소자 설계, 공정 최적화 또는 정밀한 성능 검증에는 별도의 TCAD 시뮬레이션과
                실험적 검증이 필요합니다.
              </p>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
