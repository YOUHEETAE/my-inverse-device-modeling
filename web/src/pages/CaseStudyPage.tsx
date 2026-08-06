import { useState } from "react";
import { FlaskConical } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Accordion, AccordionItem, AccordionTrigger, AccordionPanel } from "@/components/ui/accordion";
import { CaseStudyFlow } from "@/features/caseStudy/CaseStudyFlow";

const TEMPLATE_STEPS = [
  "비교 목적",
  "기준 조건",
  "변경 조건",
  "I–V Curve 비교",
  "파라미터 비교",
  "Field Map 비교",
  "물리적 해석",
  "설계 관점의 결론",
];

interface CaseStudy {
  id: string;
  title: string;
  purpose: string;
  caseA: string;
  caseB: string;
  shared: string[];
  checkItems: string[];
  interpretation: string[];
}

const CASE_STUDIES: CaseStudy[] = [
  {
    id: "channel-length",
    title: "Case Study 1. 채널 길이 변화",
    purpose: "채널 길이가 MOSFET의 전류 특성 및 단채널 효과에 미치는 영향을 확인한다.",
    caseA: "Long-channel 조건",
    caseB: "Short-channel 조건",
    shared: ["Oxide Thickness 동일", "Source/Drain Doping 동일", "Body Doping 동일", "LDD Doping 동일"],
    checkItems: [
      "Id–Vg Curve 이동",
      "Vth 변화",
      "Ioff 변화",
      "Ion 변화",
      "SS 변화",
      "DIBL 변화",
      "드레인 측 Electric Field",
      "채널 내부 Potential 분포",
    ],
    interpretation: [
      "채널 길이가 짧아지면 소스와 드레인의 공핍 영역이 채널 내부에 더 큰 영향을 준다.",
      "드레인 전압의 영향이 소스 측까지 전달되면서 에너지 장벽이 낮아질 수 있다.",
      "이에 따라 Vth가 감소하고 DIBL과 Ioff가 증가할 수 있다.",
      "반면 채널 길이 감소로 저항이 줄어들면서 Ion이 증가할 가능성도 있다.",
      "Field Map에서는 드레인 전계가 채널 안쪽으로 더 깊게 확장되는지 확인한다.",
    ],
  },
  {
    id: "oxide-thickness",
    title: "Case Study 2. 산화막 두께 변화",
    purpose: "산화막 두께가 게이트 제어력과 채널 형성에 미치는 영향을 확인한다.",
    caseA: "얇은 산화막",
    caseB: "두꺼운 산화막",
    shared: ["나머지 구조 및 도핑 조건 동일"],
    checkItems: ["Id–Vg Curve 기울기", "Vth 변화", "gm 변화", "SS 변화", "Ion 변화", "채널 전자 농도 분포", "Potential 분포"],
    interpretation: [
      "산화막이 얇아지면 게이트와 채널 사이의 전기적 결합이 강해진다.",
      "따라서 동일한 게이트 전압에서 더 강한 채널이 형성될 수 있으며, gm과 Ion이 증가할 수 있다.",
      "Field Map에서는 게이트 아래 채널의 전위 변화와 전자 농도 증가를 확인한다.",
      "다만 실제 소자에서는 산화막 누설전류와 신뢰성 문제가 발생할 수 있으므로 무조건 얇은 산화막이 유리하다고 판단해서는 안 된다.",
    ],
  },
  {
    id: "body-doping",
    title: "Case Study 3. 바디 도핑 변화",
    purpose: "바디 도핑이 문턱전압, 누설전류 및 단채널 효과에 미치는 영향을 확인한다.",
    caseA: "낮은 Body Doping",
    caseB: "높은 Body Doping",
    shared: ["나머지 조건 동일"],
    checkItems: ["Vth 변화", "Ioff 변화", "SS 변화", "DIBL 변화", "채널 전자 농도", "공핍 영역과 Potential 분포"],
    interpretation: [
      "바디 도핑이 증가하면 채널을 형성하기 위해 더 큰 게이트 전압이 필요할 수 있어 Vth가 증가한다.",
      "공핍 영역의 확장을 제한하여 단채널 효과를 완화할 수 있지만, 이동도 감소와 같은 부작용이 나타날 수 있다.",
      "본 Case Study에서는 Vth 증가와 Ioff 감소가 실제 예측 결과에서 함께 나타나는지 확인한다.",
    ],
  },
  {
    id: "ldd-doping",
    title: "Case Study 4. LDD 도핑 변화",
    purpose: "LDD 도핑이 드레인 전계, Ion 및 Ron에 미치는 영향을 확인한다.",
    caseA: "낮은 LDD Doping",
    caseB: "높은 LDD Doping (또는 LDD 적용 조건과 미적용 조건 비교)",
    shared: ["나머지 조건 동일"],
    checkItems: ["드레인 끝단 Electric Field", "Ion", "Ron", "gds", "Current Density 분포", "Id–Vd Curve"],
    interpretation: [
      "LDD는 고농도 드레인과 채널 사이의 전압 변화를 분산시켜 드레인 끝단 전계를 완화한다.",
      "LDD 도핑이 너무 낮으면 전계 완화에는 유리할 수 있지만 직렬저항이 증가하여 Ion이 감소하고 Ron이 증가할 수 있다.",
      "반대로 LDD 도핑이 높으면 저항은 감소하지만 고농도 드레인과 유사해져 전계 완화 효과가 줄어들 수 있다.",
    ],
  },
];

function ChannelLengthCasePanel({ study }: { study: CaseStudy }) {
  const [showInteractive, setShowInteractive] = useState(false);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex justify-end">
        <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={() => setShowInteractive((v) => !v)}>
          <FlaskConical className="h-3.5 w-3.5" />
          {showInteractive ? "설명 보기" : "직접 예측하고 확인하기"}
        </Button>
      </div>
      {showInteractive ? (
        <CaseStudyFlow topicId="sce_channel_length" />
      ) : (
        <div className="flex flex-col gap-3 text-[13px] leading-relaxed text-on-surface-variant">
          <div>
            <p className="mb-0.5 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">비교 목적</p>
            <p>{study.purpose}</p>
          </div>

          <div>
            <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">조건 설정</p>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-sm border border-outline-variant bg-surface-container px-2.5 py-1 font-mono text-[11px] font-medium">
                Case A — {study.caseA}
              </span>
              <span className="rounded-sm border border-outline-variant bg-surface-container px-2.5 py-1 font-mono text-[11px] font-medium">
                Case B — {study.caseB}
              </span>
            </div>
            <ul className="mt-1.5 list-inside list-disc space-y-0.5 pl-1">
              {study.shared.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>

          <div>
            <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">확인 항목</p>
            <ul className="grid grid-cols-1 gap-x-4 gap-y-0.5 sm:grid-cols-2">
              {study.checkItems.map((item) => (
                <li key={item} className="list-inside list-disc">
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div>
            <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">예상 해석 방향</p>
            <div className="flex flex-col gap-1">
              {study.interpretation.map((line) => (
                <p key={line}>{line}</p>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function CaseStudyPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-8">
        {/* Hero */}
        <div>
          <h1 className="text-xl font-bold leading-snug">Case Study</h1>
          <p className="mt-3 text-sm leading-relaxed text-on-surface-variant">
            Case Study 탭에서는 특정 입력 조건을 예시로 설정하고, 조건 변화에 따라 I–V Curve, 전기적 파라미터, Field Map이 어떻게
            달라지는지 비교합니다. 각 사례는 다음 순서로 구성합니다.
          </p>
          <ol className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 rounded-sm border border-outline-variant bg-surface-container-low p-3 font-mono text-[11px] sm:grid-cols-4">
            {TEMPLATE_STEPS.map((step, index) => (
              <li key={step}>
                <span className="font-semibold text-foreground">{index + 1}.</span> {step}
              </li>
            ))}
          </ol>
          <p className="mt-3 text-sm leading-relaxed text-on-surface-variant">
            각 Case Study는 모든 조건을 한 번에 변경하지 않고 한 가지 변수만 변경하여 결과의 원인을 명확하게 확인할 수 있도록
            구성합니다.
          </p>
        </div>

        {/* Case studies */}
        <Card>
          <CardContent>
            <Accordion className="flex flex-col">
              {CASE_STUDIES.map((study) => (
                <AccordionItem key={study.id} value={study.id}>
                  <AccordionTrigger>
                    <span className="flex items-center gap-2">
                      <FlaskConical className="h-4 w-4 text-primary" />
                      {study.title}
                    </span>
                  </AccordionTrigger>
                  <AccordionPanel>
                    {study.id === "channel-length" ? (
                      <ChannelLengthCasePanel study={study} />
                    ) : (
                      <div className="flex flex-col gap-3 text-[13px] leading-relaxed text-on-surface-variant">
                        <div>
                          <p className="mb-0.5 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">비교 목적</p>
                          <p>{study.purpose}</p>
                        </div>

                        <div>
                          <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">조건 설정</p>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-sm border border-outline-variant bg-surface-container px-2.5 py-1 font-mono text-[11px] font-medium">
                              Case A — {study.caseA}
                            </span>
                            <span className="rounded-sm border border-outline-variant bg-surface-container px-2.5 py-1 font-mono text-[11px] font-medium">
                              Case B — {study.caseB}
                            </span>
                          </div>
                          <ul className="mt-1.5 list-inside list-disc space-y-0.5 pl-1">
                            {study.shared.map((item) => (
                              <li key={item}>{item}</li>
                            ))}
                          </ul>
                        </div>

                        <div>
                          <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">확인 항목</p>
                          <ul className="grid grid-cols-1 gap-x-4 gap-y-0.5 sm:grid-cols-2">
                            {study.checkItems.map((item) => (
                              <li key={item} className="list-inside list-disc">
                                {item}
                              </li>
                            ))}
                          </ul>
                        </div>

                        <div>
                          <p className="mb-1 text-[11px] font-bold uppercase tracking-wide text-on-surface-variant/70">예상 해석 방향</p>
                          <div className="flex flex-col gap-1">
                            {study.interpretation.map((line) => (
                              <p key={line}>{line}</p>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </AccordionPanel>
                </AccordionItem>
              ))}

              <AccordionItem value="sd-doping">
                <AccordionTrigger>
                  <span className="flex items-center gap-2">
                    <FlaskConical className="h-4 w-4 text-primary" />
                    Case Study 5. S/D 도핑 변화
                  </span>
                </AccordionTrigger>
                <AccordionPanel>
                  <p className="text-[13px] text-on-surface-variant">준비 중입니다.</p>
                </AccordionPanel>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
