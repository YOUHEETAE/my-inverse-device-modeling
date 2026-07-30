import { useState, type ReactNode } from "react";
import { FlaskConical, Sigma } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Accordion, AccordionItem, AccordionTrigger, AccordionPanel } from "@/components/ui/accordion";
import { Eq } from "@/components/Eq";
import { PNJunctionTool } from "@/features/theory/PNJunctionTool";

function P({ children }: { children: ReactNode }) {
  return <p className="leading-relaxed">{children}</p>;
}

function Sub({ heading, children }: { heading: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <h4 className="text-sm font-bold">{heading}</h4>
      {children}
    </div>
  );
}

function Chapter1Content() {
  return (
    <div className="flex flex-col gap-5 text-[13px] leading-relaxed text-on-surface-variant">
      <P>
        PN 접합은 p형 반도체와 n형 반도체가 맞닿아 형성되는 가장 기본적인 반도체 구조입니다. MOSFET에서도 n형 Source와 Drain이 p형
        Body와 각각 PN 접합을 형성하므로, PN 접합의 전위와 전기장 분포를 이해하는 것은 MOSFET 내부의 동작을 해석하는 출발점이 됩니다.
      </P>
      <div>
        <P>이 장에서는 도핑 농도와 외부 바이어스에 따라 PN 접합 내부의 다음 물리량이 어떻게 달라지는지 살펴봅니다.</P>
        <ul className="mt-1 list-inside list-disc space-y-0.5 pl-1">
          <li>Electron and Hole Concentration</li>
          <li>Charge Density</li>
          <li>Electric Field</li>
          <li>Electric Potential</li>
          <li>Energy Band</li>
        </ul>
      </div>
      <P>
        각 물리량은 독립적으로 결정되는 것이 아닙니다. 도핑과 캐리어 분포에 의해 공간전하가 형성되고, 공간전하는 전기장과 전위를
        결정하며, 전위 변화는 에너지 밴드의 굽힘으로 나타납니다.
      </P>

      <Sub heading="1.1. PN 접합의 형성">
        <P>
          p형 반도체에는 Acceptor가 도핑되어 정공이 다수 캐리어로 존재하고, n형 반도체에는 Donor가 도핑되어 전자가 다수 캐리어로
          존재합니다.
        </P>
        <P>두 영역을 접합하면 캐리어 농도 차이에 의해 확산이 발생합니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>n형 영역의 전자는 p형 영역으로 확산합니다.</li>
          <li>p형 영역의 정공은 n형 영역으로 확산합니다.</li>
          <li>접합 부근으로 이동한 전자와 정공은 서로 재결합합니다.</li>
        </ul>
        <P>
          이 과정에서 접합 주변의 이동 가능한 전자와 정공은 감소합니다. 그러나 도핑 원자는 결정격자에 고정되어 있으므로 이동하지
          않습니다.
        </P>
        <P>
          n형 쪽에는 전자를 내놓은 양전하의 이온화 Donor가 남고, p형 쪽에는 전자를 받아들인 음전하의 이온화 Acceptor가 남습니다. 이처럼
          이동 캐리어는 부족하지만 고정 전하가 존재하는 영역을 <span className="font-semibold text-foreground">공핍영역(Depletion Region)</span>이라고 합니다.
        </P>
        <P>
          공핍영역에 남은 고정 전하는 <span className="font-semibold text-foreground">공간전하(Space Charge)</span>를 형성하고, 이
          공간전하가 PN 접합 내부의 전기장을 만듭니다.
        </P>
      </Sub>

      <Sub heading="1.2. 평형상태와 Built-in Potential">
        <P>
          캐리어가 확산하면 공핍영역 내부에 전기장이 형성됩니다. 이 전기장은 전자의 추가적인 확산을 억제하는 방향으로 작용합니다.
          따라서 PN 접합에서는 서로 반대되는 두 가지 이동이 동시에 존재합니다.
        </P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>
            <span className="font-semibold text-foreground">Diffusion:</span> 캐리어 농도 차이에 의한 이동
          </li>
          <li>
            <span className="font-semibold text-foreground">Drift:</span> 내부 전기장에 의한 이동
          </li>
        </ul>
        <P>열평형 상태에서는 Drift current와 Diffusion current가 서로 상쇄됩니다.</P>
        <Eq tex={String.raw`\begin{aligned} J_{n,drift} + J_{n,diff} &= 0 \\ J_{p,drift} + J_{p,diff} &= 0 \end{aligned}`} />
        <P>
          따라서 외부 전압이 인가되지 않은 평형상태에서도 접합 내부에는 전기장과 전위 차이가 존재하지만, 전체 단자 전류는 0이
          됩니다. 공핍영역에 형성된 내부 전위 차이를 <span className="font-semibold text-foreground">Built-in Potential</span>이라고
          합니다. 이상적인 급격 접합에서 Built-in Potential은 다음과 같이 표현할 수 있습니다.
        </P>
        <Eq tex="V_{bi} = \frac{kT}{q}\ln\!\left(\frac{N_A N_D}{n_i^2}\right)" />
        <P>
          <span className="font-mono">k</span>: 볼츠만 상수, <span className="font-mono">T</span>: 절대온도,{" "}
          <span className="font-mono">q</span>: 기본 전하량, <span className="font-mono">N_A</span>: Acceptor 농도,{" "}
          <span className="font-mono">N_D</span>: Donor 농도, <span className="font-mono">n_i</span>: 진성 캐리어 농도
        </P>
        <P>
          이 식에 따르면 도핑 농도가 증가하면 Built-in Potential도 증가합니다. 다만 도핑 농도는 로그 함수 안에 포함되므로, 농도가 크게
          증가하더라도 Built-in Potential은 상대적으로 완만하게 증가합니다.
        </P>
      </Sub>

      <Sub heading="1.3. 전하 분포와 포아송 방정식">
        <P>
          반도체 내부의 전위는 공간전하 분포에 의해 결정됩니다. 이를 나타내는 기본 방정식이{" "}
          <span className="font-semibold text-foreground">포아송 방정식(Poisson's Equation)</span>입니다. 1차원 구조에서는 다음과
          같이 표현됩니다.
        </P>
        <Eq tex="\frac{\partial E}{\partial x} = \frac{q(p - n + N_D - N_A)}{\varepsilon_s}" />
        <P>
          <span className="font-mono">ψ(x)</span>: 전위, <span className="font-mono">ρ(x)</span>: 순전하 밀도,{" "}
          <span className="font-mono">ε_s</span>: 반도체의 유전율
        </P>
        <P>반도체 내부의 순전하 밀도는 전자, 정공 및 이온화된 도핑 농도를 모두 포함합니다.</P>
        <P>
          이 식에서 중요한 점은{" "}
          <span className="font-semibold text-foreground">Carrier Concentration과 Charge Density가 동일한 물리량이 아니라는 것</span>
          입니다. Carrier Concentration은 이동 가능한 전자와 정공의 농도를 나타냅니다. 반면 Charge Density는 전자와 정공뿐 아니라
          결정격자에 고정된 이온화 Donor와 Acceptor까지 포함한 순전하입니다. 공핍영역에서는 전자와 정공 농도가 크게 감소하지만,
          고정된 이온화 불순물은 남아 있습니다. 따라서 Carrier Concentration은 낮아져도 Charge Density는 0이 아닌 값을 가집니다.
        </P>
        <P>
          이 공간전하 분포를 포아송 방정식에 적용하면 전위 분포가 계산됩니다. 즉, DEVSIM은 설정된 도핑과 계산된 전자·정공 농도를
          기반으로 공간전하를 구하고, 포아송 방정식을 풀어 소자 내부의 전위를 계산합니다.
        </P>
      </Sub>

      <Sub heading="1.4. 전기장과 전위의 관계">
        <P>
          전기장은 전위가 공간에 따라 얼마나 빠르게 변하는지를 나타냅니다. 전위의 기울기가 큰 영역에서는 전기장의 절댓값이 크게
          나타납니다. 반대로 전위가 거의 일정한 영역에서는 전기장이 작습니다. 또한 전기장을 위치에 대해 미분하면 공간전하와
          연결됩니다.
        </P>
        <Eq tex="\vec{E} = -\nabla V = -\frac{\partial V}{\partial x}" />
        <P>따라서 PN 접합 내부의 물리량은 다음 순서로 해석할 수 있습니다.</P>
        <ol className="list-inside list-decimal space-y-0.5 pl-1">
          <li>고정된 도핑 이온이 공간전하를 형성합니다.</li>
          <li>공간전하가 전기장의 기울기를 결정합니다.</li>
          <li>전기장을 적분하면 전위 차이가 형성됩니다.</li>
          <li>전위 변화는 Energy Band의 굽힘으로 나타납니다.</li>
        </ol>
        <P>
          공핍근사에서는 공핍영역 내부의 전하 밀도를 거의 일정한 값으로 볼 수 있습니다. 이 경우 Electric Field는 공핍영역에서
          위치에 따라 선형적으로 변하고, Electric Potential은 포물선 형태로 변합니다.
        </P>
        <Eq
          tex={String.raw`\begin{aligned}
V(x) &= \frac{qN_A}{2\varepsilon_s}(x_p+x)^2 \quad (-x_p \le x \le 0) \\[4pt]
V(x) &= V_{bi} - \frac{qN_D}{2\varepsilon_s}(x_n-x)^2 \quad (0 \le x \le x_n)
\end{aligned}`}
        />
        <P>
          실제 DEVSIM 결과에서는 캐리어 농도가 경계에서 연속적으로 변하고 수치해석을 통해 방정식을 풀기 때문에, 이상적인
          공핍근사보다 더 매끄러운 분포가 나타날 수 있습니다.
        </P>
      </Sub>

      <Sub heading="1.5. 공핍층 폭과 도핑 농도">
        <P>PN 접합의 전체 공핍층 폭 W는 다음과 같이 근사할 수 있습니다.</P>
        <Eq tex="W = x_n + x_p = \left[\frac{2\varepsilon_s}{q}\frac{N_A+N_D}{N_A N_D}(V_{bi}-V_A)\right]^{1/2}" />
        <P>
          여기서 <span className="font-mono">V_A</span>는 PN 접합에 인가된 외부 전압입니다. 이 식에서는 순방향 바이어스를 양수로
          정의합니다. 도핑 농도가 증가하면 도핑 항이 감소하므로 공핍층 폭도 감소합니다. 반면 동일한 전위 차이가 더 좁은 영역에
          형성되기 때문에, 접합 부근의 최대 전기장은 증가할 수 있습니다.
        </P>
        <P>외부 바이어스가 없는 평형상태(V_A = 0)에서는 다음과 같이 단순화됩니다.</P>
        <Eq tex="W = x_n + x_p = \left[\frac{2\varepsilon_s}{q}\frac{N_A+N_D}{N_A N_D}V_{bi}\right]^{1/2}" />
        <P>
          비대칭 도핑에서는 공핍층이 양쪽으로 동일하게 확장되지 않습니다. 공핍영역 전체의 순전하는 0이어야 하므로, 공핍층은 도핑
          농도가 낮은 영역으로 더 넓게 확장됩니다.
        </P>
        <P>
          이번 UI에서 p형과 n형의 도핑 농도를 동일한 값으로 설정한다면 공핍층은 비교적 대칭적으로 형성됩니다. 이후 서로 다른 도핑
          농도를 독립적으로 설정하도록 확장한다면, 비대칭 접합에서 공핍층이 저농도 쪽으로 확장되는 현상도 확인할 수 있습니다.
        </P>
      </Sub>

      <Sub heading="1.6. Electric Potential과 Energy Band">
        <P>전자의 위치 에너지는 Electric Potential과 다음 관계를 가집니다.</P>
        <Eq tex="U = -q\psi" />
        <P>
          따라서 전위가 증가하는 방향에서는 전자의 에너지 상태가 낮아집니다. 그렇기에 전도대와 가전자대는 전위에 따라 함께
          이동합니다. Electric Potential과 Energy Band는 서로 반대 방향으로 변화합니다.
        </P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Potential 증가 → Ec, Ev 감소</li>
          <li>Potential 감소 → Ec, Ev 증가</li>
        </ul>
        <P>
          PN 접합에서 Energy Band가 위치에 따라 휘어지는 현상을{" "}
          <span className="font-semibold text-foreground">Band Bending</span>이라고 합니다. 이는 공핍영역에 형성된 Built-in
          Potential을 전자의 에너지 관점에서 나타낸 것입니다.
        </P>
      </Sub>

      <Sub heading="1.7. 외부 바이어스의 영향">
        <P>PN 접합에 외부 전압을 인가하면 접합 내부의 전위 장벽, 공핍층 폭 및 전기장 분포가 변합니다.</P>
        <P>
          p형 영역에 n형 영역보다 높은 전위를 인가하면 순방향 바이어스가 됩니다. 순방향 바이어스는 Built-in Potential을 일부
          상쇄하므로 유효 전위 장벽이 낮아집니다. 이에 따라 다음과 같은 변화가 나타납니다.
        </P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Potential Barrier 감소</li>
          <li>공핍층 폭 감소</li>
          <li>최대 Electric Field 감소</li>
          <li>다수 캐리어 주입 증가</li>
          <li>접합을 통과하는 전류 증가</li>
          <li>Energy Band의 장벽 감소</li>
        </ul>
        <P>
          순방향 바이어스에서 핵심은 단순히 공핍층이 좁아지는 것이 아니라, 에너지 장벽이 낮아져 다수 캐리어가 반대편 영역으로
          주입되기 쉬워진다는 점입니다.
        </P>
        <P>p형 영역에 n형 영역보다 낮은 전위를 인가하면 역방향 바이어스가 됩니다. 이에 따라 다음과 같은 변화가 나타납니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Potential Barrier 증가</li>
          <li>공핍층 폭 증가</li>
          <li>최대 Electric Field 증가</li>
          <li>다수 캐리어의 접합 통과 억제</li>
          <li>작은 역방향 누설전류 형성</li>
          <li>Energy Band의 장벽 증가</li>
        </ul>
        <P>
          따라서 역방향 전압이 증가할수록 공핍층은 넓어지지만, 전압에 정비례하지 않고 제곱근 관계로 증가합니다. MOSFET의
          Drain–Body 접합은 정상 동작에서 주로 역바이어스 상태이므로, 이 현상은 이후 DIBL과 Punch-through를 이해하는 데
          중요합니다.
        </P>
      </Sub>

      <Sub heading="1.8. 추천 실습 순서">
        <ul className="list-inside list-disc space-y-1 pl-1">
          <li>실습 A. 대칭 도핑</li>
          <li>실습 B. p측 도핑만 2e18로 증가</li>
          <li>실습 C. p측 도핑만 1e16로 감소</li>
          <li>실습 D. bias 변화</li>
        </ul>
      </Sub>
    </div>
  );
}

interface ChapterPanelProps {
  content: ReactNode;
  tool?: ReactNode;
}

function ChapterPanel({ content, tool }: ChapterPanelProps) {
  const [showTool, setShowTool] = useState(false);

  return (
    <div className="relative">
      {tool && (
        <div className="mb-3 flex justify-end">
          <Button size="sm" variant="outline" className="gap-1.5 text-xs" onClick={() => setShowTool((v) => !v)}>
            <FlaskConical className="h-3.5 w-3.5" />
            {showTool ? "이론 보기" : "시뮬레이션 열기"}
          </Button>
        </div>
      )}
      {showTool && tool ? tool : content}
    </div>
  );
}

const UPCOMING_CHAPTERS = [
  { title: "2. Long-Channel MOSFET", desc: "Long-Channel MOSFET의 구조와 동작 원리 (MOS Capacitor 기초 포함)" },
  { title: "3. Short-Channel MOSFET", desc: "단채널 효과와 DIBL" },
  { title: "4. MOSFET Performance Enhancement", desc: "LDD 등 성능 개선 구조" },
  { title: "5. Python TCAD", desc: "DEVSIM 기반 수치해석 과정" },
];

export default function TheoryPage() {
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-4xl flex-col gap-8 px-6 py-8">
        {/* Hero */}
        <div>
          <h1 className="text-xl font-bold leading-snug">Theory</h1>
          <p className="mt-3 text-sm leading-relaxed text-on-surface-variant">
            MOSFET의 전기적 특성은 단순히 게이트 전압과 드레인 전압만으로 결정되지 않습니다. 채널 길이, 산화막 두께, Source/Drain
            도핑 농도, Body 도핑 농도와 같은 소자 내부 조건이 함께 작용하여 전류와 전위 분포를 결정합니다.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            예를 들어 채널 길이를 줄이면 전류가 증가할 수 있지만, Drain의 영향이 Source 부근까지 전달되어 누설전류와 DIBL이 증가할
            수 있습니다. 산화막을 얇게 만들면 Gate의 채널 제어력이 강해지지만, 실제 소자에서는 누설전류와 신뢰성 문제도 함께
            고려해야 합니다. 또한 도핑 농도를 변경하면 캐리어 농도뿐 아니라 공핍층, 전위 장벽, 전기장 분포와 문턱전압도 달라집니다.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            이 Theory 페이지는 반도체공학의 모든 내용을 다루기 위한 것이 아닙니다. 이 웹페이지에서 MOSFET의 파라미터를 변경하고,
            그 결과로 생성되는 <span className="font-semibold text-foreground">I–V Curve와 Field Map을 해석하는 데 필요한 이론</span>
            을 중심으로 구성되어 있습니다.
          </p>
          <p className="mt-2 text-sm leading-relaxed text-on-surface-variant">
            각 장의 이론은 독립된 내용이 아니라 다음 장으로 연결됩니다.
          </p>
        </div>

        {/* Chapters */}
        <Card>
          <CardContent>
            <Accordion className="flex flex-col">
              <AccordionItem value="chapter1">
                <AccordionTrigger>
                  <span className="flex items-center gap-2">
                    <Sigma className="h-4 w-4 text-primary" />
                    1. PN Junction
                  </span>
                </AccordionTrigger>
                <AccordionPanel>
                  <ChapterPanel content={<Chapter1Content />} tool={<PNJunctionTool />} />
                </AccordionPanel>
              </AccordionItem>

              {UPCOMING_CHAPTERS.map((chapter) => (
                <AccordionItem key={chapter.title} value={chapter.title}>
                  <AccordionTrigger>
                    <span className="flex items-center gap-2">
                      <Sigma className="h-4 w-4 text-primary" />
                      {chapter.title}
                    </span>
                  </AccordionTrigger>
                  <AccordionPanel>
                    <p className="text-[13px] text-on-surface-variant">{chapter.desc} — 준비 중입니다.</p>
                  </AccordionPanel>
                </AccordionItem>
              ))}
            </Accordion>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
