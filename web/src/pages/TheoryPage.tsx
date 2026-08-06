import { useState, type ReactNode } from "react";
import { FlaskConical, Sigma } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Accordion, AccordionItem, AccordionTrigger, AccordionPanel } from "@/components/ui/accordion";
import { Eq } from "@/components/Eq";
import { PNJunctionTool } from "@/features/theory/PNJunctionTool";
import { LongChannelMOSFETTool } from "@/features/theory/LongChannelMOSFETTool";

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
        <Eq tex="J_{n,drift} + J_{n,diff} = 0" />
        <Eq tex="J_{p,drift} + J_{p,diff} = 0" />
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
        <Eq tex="V(x) = \frac{qN_A}{2\varepsilon_s}(x_p+x)^2 \quad (-x_p \le x \le 0)" />
        <Eq tex="V(x) = V_{bi} - \frac{qN_D}{2\varepsilon_s}(x_n-x)^2 \quad (0 \le x \le x_n)" />
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

function Chapter2Content() {
  return (
    <div className="flex flex-col gap-5 text-[13px] leading-relaxed text-on-surface-variant">
      <P>
        MOSFET는 Gate–Oxide–Body가 만드는 MOS Capacitor 구조를 기반으로 동작합니다. Gate에 전압을 인가하면 Oxide 아래 Body
        표면의 캐리어 분포가 달라지고, 이 표면 상태에 따라 Source와 Drain 사이에 전류가 흐를 수 있는 채널이 형성되거나 차단됩니다.
      </P>

      <Sub heading="2.1. MOS 구조와 표면 상태">
        <P>p형 Body 위에 얇은 Oxide와 Gate를 쌓은 구조에서, Gate 전압 VG에 따라 Body 표면은 세 가지 상태를 거칩니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Accumulation — VG가 충분히 낮으면(음의 방향) 표면에 다수 캐리어(정공)가 모입니다.</li>
          <li>Depletion — VG가 증가하면 표면 근처의 정공이 밀려나며 공핍층이 형성됩니다.</li>
          <li>Inversion — VG가 더 증가하면 표면에 소수 캐리어(전자)가 모여 n형처럼 반전된 얇은 층, 즉 채널이 형성됩니다.</li>
        </ul>
        <P>
          Inversion이 시작되는 경계의 Gate 전압을 문턱전압(Threshold Voltage, Vth)이라고 합니다. VG가 Vth를 넘어야 Source와
          Drain을 연결하는 전자 채널이 만들어집니다.
        </P>
      </Sub>

      <Sub heading="2.2. Long-Channel MOSFET의 구조">
        <P>
          이 장의 실습 소자는 p형 Body 위에 n+ Source, n+ Drain을 배치하고 그 사이 표면을 Gate–Oxide가 덮는 전형적인 NMOS
          구조입니다. Gate 길이(채널 길이)가 충분히 길어 Drain 쪽 공핍층이 Source에 영향을 주지 않는 경우를 Long-channel
          MOSFET이라고 합니다.
        </P>
      </Sub>

      <Sub heading="2.3. 선형 영역과 포화 영역">
        <P>VG가 Vth를 넘어 채널이 형성된 상태에서, Drain 전압 VD를 증가시키면 전류-전압 관계는 두 영역으로 나뉩니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>선형(Linear/Triode) 영역 — VD가 작을 때(VD &lt; VG − Vth), Drain 전류는 VD에 거의 비례해 증가합니다.</li>
          <li>
            포화(Saturation) 영역 — VD가 VG − Vth에 도달하면 Drain 쪽 채널이 좁아지는 Pinch-off가 일어나고, 이후 VD를 더
            높여도 전류는 거의 일정하게 유지됩니다.
          </li>
        </ul>
        <P>이 경계 조건 VD = VG − Vth를 Pinch-off 지점이라고 부르며, ID–VD 곡선에서 선형 구간이 꺾이는 지점으로 나타납니다.</P>
      </Sub>

      <Sub heading="2.4. ID–VG와 ID–VD 특성곡선으로 읽는 법">
        <P>
          ID–VG 곡선(Transfer characteristic)은 고정된 VD에서 VG를 쓸어가며 얻은 전류 곡선으로, Vth 부근에서 전류가 급격히
          증가하기 시작하는 지점을 통해 문턱전압을 확인할 수 있습니다.
        </P>
        <P>
          ID–VD 곡선(Output characteristic)은 여러 VG 값에 대해 VD를 쓸어가며 얻은 전류 곡선 family로, 각 곡선은 낮은 VD에서
          선형으로 증가하다가 Pinch-off 이후 평평해지는 모양을 보입니다. VG가 클수록 채널의 전자 농도가 많아 전류 곡선 전체가
          위로 이동합니다.
        </P>
      </Sub>

      <Sub heading="2.5. 실습에서 확인할 것">
        <ul className="list-inside list-disc space-y-1 pl-1">
          <li>VG를 바꿔가며 Oxide 아래 Electron 농도(채널)가 어떻게 나타나고 사라지는지 관찰합니다.</li>
          <li>ID–VG 곡선에서 선택한 VG 지점의 마커가 채널 형성 여부와 어떻게 연결되는지 확인합니다.</li>
          <li>VD를 바꿔가며 ID–VD 곡선에서 선형 구간과 포화 구간이 어디서 나뉘는지 관찰합니다.</li>
        </ul>
      </Sub>
    </div>
  );
}

function Chapter3Content() {
  return (
    <div className="flex flex-col gap-5 text-[13px] leading-relaxed text-on-surface-variant">
      <P>
        Long-Channel MOSFET에서는 Channel의 Potential과 전하가 주로 Gate voltage에 의해 결정됩니다. Source와 Drain은 Gate에
        비해 멀리 떨어져 있으므로, Drain voltage가 Source 부근의 Energy Barrier에 미치는 영향도 상대적으로 작습니다.
      </P>
      <P>
        그러나 Channel Length가 짧아지면 Source와 Drain의 PN 접합에서 형성된 공핍영역과 전기장이 Gate 아래 Channel의 더 큰
        부분을 차지하게 됩니다. 그 결과 Channel Potential이 Gate뿐 아니라 Source와 Drain의 영향을 함께 받게 됩니다.
      </P>
      <P>
        이를 <span className="font-semibold text-foreground">Short-Channel Effect</span>라고 합니다.
      </P>
      <div>
        <P>이 장에서는 다음 현상을 중심으로 Short-Channel MOSFET을 해석합니다.</P>
        <ol className="mt-1 list-inside list-decimal space-y-0.5 pl-1">
          <li>Charge Sharing</li>
          <li>Threshold-Voltage Roll-off</li>
          <li>Drain-Induced Barrier Lowering</li>
          <li>Subthreshold Swing 및 Off-current 악화</li>
          <li>Punch-through</li>
          <li>Channel-Length Modulation</li>
          <li>Ion–Ioff Trade-off</li>
        </ol>
      </div>

      <Sub heading="3.1. Long Channel과 Short Channel의 구조 비교">
        <P>
          Channel Length가 충분히 긴 소자에서는 Source와 Drain 접합의 공핍영역 사이에 Gate가 독립적으로 제어할 수 있는
          Channel 영역이 충분히 남아 있습니다. 반면 Channel Length가 짧아지면 Source와 Drain의 공핍영역이 Channel 전체에서
          차지하는 비율이 증가합니다. 특히 Drain voltage가 높아지면 Drain의 Potential이 Channel 내부로 더 깊게 침투할 수
          있습니다.
        </P>
        <P>따라서 짧은 Channel에서는 다음과 같은 변화가 나타날 수 있습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Gate가 제어하는 Channel 영역 감소</li>
          <li>Source와 Drain의 전기적 영향 증가</li>
          <li>Threshold Voltage 감소</li>
          <li>Drain bias에 따른 Threshold Voltage 변화 증가</li>
          <li>OFF 상태에서의 누설전류 증가</li>
          <li>출력 포화 특성 악화</li>
        </ul>
      </Sub>

      <Sub heading="3.2. Charge Sharing">
        <P>
          Long-Channel MOSFET에서는 Gate가 Channel 아래의 공핍전하 대부분을 제어합니다. 하지만 Channel Length가 짧아지면
          Source와 Drain 접합의 공핍영역이 Gate 아래로 확장됩니다. 이에 따라 Channel 아래 공핍전하의 일부를 Gate가 아닌
          Source와 Drain이 담당하게 됩니다. 이를 <span className="font-semibold text-foreground">Charge Sharing</span>이라고
          합니다.
        </P>
        <P>개념적으로 Channel 아래의 공핍전하는 다음과 같이 나누어 생각할 수 있습니다.</P>
        <Eq tex="Q_{\text{dep}} = Q_{\text{gate}} + Q_{\text{source}} + Q_{\text{drain}}" />
        <P>
          Channel Length가 짧아지면 Q<sub>source</sub>와 Q<sub>drain</sub>의 상대적 비중이 증가합니다. 따라서 Gate가 직접
          제어해야 하는 공핍전하가 줄어듭니다. Gate가 담당해야 하는 공핍전하가 감소하면 강한 반전층을 형성하는 데 필요한
          Gate voltage도 낮아질 수 있습니다. 즉, Charge Sharing은 Threshold-Voltage Roll-off의 주요 원인입니다.
        </P>
      </Sub>

      <Sub heading="3.3. Threshold-Voltage Roll-off">
        <P>
          Vth Roll-off란 Channel Length가 감소할수록 Threshold Voltage가 낮아지는 현상입니다. Long-Channel MOSFET의
          Threshold Voltage는 Gate가 반도체 표면의 공핍전하를 제어하고 강한 반전을 형성하는 데 필요한 전압으로 설명할 수
          있습니다. Short-channel 소자에서는 Charge Sharing으로 Gate가 담당하는 유효 공핍전하가 감소합니다. 따라서
          Long-Channel 식을 그대로 적용할 수는 없지만, Threshold Voltage가 낮아지는 물리적 방향은 다음처럼 이해할 수
          있습니다.
        </P>
        <P>
          Low Drain bias를 사용하는 이유는 Drain에 의한 추가적인 Barrier Lowering을 줄이고, Channel Length 자체에 따른
          Threshold 변화를 우선 확인하기 위해서입니다. 각 Channel Length에서 동일한 방법으로 Vth를 추출하면 Channel
          Length가 짧아질수록 Vth가 낮아지는 경향이 나타납니다.
        </P>
      </Sub>

      <Sub heading="3.4. Drain-Induced Barrier Lowering (DIBL)">
        <P>
          DIBL은 Drain voltage가 증가할 때 Source와 Channel 사이의 Energy Barrier가 낮아지고, 그 결과 Threshold Voltage가
          감소하는 현상입니다. Long-channel 소자에서는 Drain의 전위 영향이 주로 Drain 부근에 머뭅니다. 그러나 Short-channel
          소자에서는 Drain 전기장이 Source 방향으로 더 쉽게 침투합니다. 그 결과 동일한 Gate voltage에서도 Source의 전자가
          Channel로 더 쉽게 넘어갈 수 있습니다. DIBL은 다음과 같이 정의할 수 있습니다.
        </P>
        <Eq tex="\text{DIBL} = \dfrac{V_{TH}(V_{D,\text{low}}) - V_{TH}(V_{D,\text{high}})}{V_{D,\text{high}} - V_{D,\text{low}}}" />
        <P>
          일반적으로 V/V 또는 mV/V 단위를 사용합니다. 값이 클수록 Drain voltage에 의해 threshold voltage가 더 크게
          변하며, Gate의 electrostatic control이 약하다는 의미입니다.
        </P>
      </Sub>

      <Sub heading="3.5. Punch-through">
        <P>
          Punch-through는 Source와 Drain의 공핍영역이 Channel 내부에서 서로 가까워지거나 연결되면서, Gate가
          Source–Channel Barrier를 충분히 유지하지 못하는 현상입니다. Channel Length가 짧고 Drain bias가 높거나 Body
          doping이 낮으면 공핍층이 Channel 안쪽으로 더 넓게 확장됩니다. Punch-through가 발생하면 Gate voltage가 Threshold
          이하이더라도 Source에서 Drain으로 큰 누설전류가 흐를 수 있습니다.
        </P>
        <P>
          DIBL은 Drain voltage가 Source-side Barrier를 낮추는 현상입니다. Punch-through는 Source와 Drain의 공핍영역이
          Channel에서 강하게 상호작용하여 Gate의 Barrier 제어가 크게 무너진 상태입니다. 즉, 두 현상은 관련되어 있지만
          동일한 의미는 아닙니다.
        </P>
      </Sub>

      <Sub heading="3.6. 시뮬레이션에서 확인하는 방법">
        <P>
          Short-Channel Effect는 Field Map 또는 I–V Curve 하나만으로 판단하지 않고 다음 순서로 연결해서 해석합니다.
        </P>
        <ul className="list-inside list-disc space-y-1.5 pl-1">
          <li>
            <span className="font-semibold text-foreground">구조 확인</span> — Net Doping에서 Channel Length와
            Source/Drain 접합 위치를 확인합니다.
          </li>
          <li>
            <span className="font-semibold text-foreground">Potential 분포 확인</span> — High Drain bias에서 Drain
            Potential이 Source 방향으로 더 크게 침투하는지 확인합니다.
          </li>
          <li>
            <span className="font-semibold text-foreground">Energy Barrier 확인</span> — Silicon 표면의 1D profile에서
            Source-side Barrier가 낮아지는지 확인합니다.
          </li>
          <li>
            <span className="font-semibold text-foreground">Id–Vg 확인</span> — Vth Roll-off, DIBL, SS, Ioff를
            확인합니다.
          </li>
          <li>
            <span className="font-semibold text-foreground">Id–Vd 확인</span> — Saturation 이후의 기울기와 Output
            Conductance 변화를 확인합니다.
          </li>
          <li>
            <span className="font-semibold text-foreground">핵심 지표 비교</span> — Ion 증가와 Ioff 증가를 함께
            비교해 성능 Trade-off를 평가합니다.
          </li>
        </ul>
      </Sub>
    </div>
  );
}

function Chapter4Content() {
  return (
    <div className="flex flex-col gap-5 text-[13px] leading-relaxed text-on-surface-variant">
      <P>
        Short-Channel MOSFET에서는 Source와 Drain의 공핍영역 및 전기장이 Channel 내부로 침투하면서 Gate의 Electrostatic
        Control이 약해집니다. 그 결과 Threshold-Voltage Roll-off, DIBL, SS 악화와 Off-current 증가가 나타날 수 있습니다.
      </P>
      <div>
        <P>Short-Channel Effect를 개선하는 방법은 크게 두 방향으로 구분할 수 있습니다.</P>
        <ul className="mt-1 list-inside list-disc space-y-1 pl-1">
          <li>
            Gate의 Channel 제어력 강화 — Oxide thinning, High-k, FinFET, GAA …
          </li>
          <li>
            Drain과 Source의 Channel 침투 억제 — LDD, Spacer, Higher Body doping, Halo implant, Shallow junction …
          </li>
        </ul>
      </div>
      <P>
        이 장에서는 현재 시뮬레이션 구조에 실제로 포함된{" "}
        <span className="font-semibold text-foreground">LDD 구조</span>를 중심으로 Potential, Electric Field와 I–V
        특성의 변화를 살펴봅니다. 그 밖의 개선 구조는 어떤 원리로 Short-Channel Effect를 줄이는지 이론적으로 소개합니다.
      </P>

      <Sub heading="4.1. Short-Channel Effect의 개선 방향">
        <P>
          Short-Channel Effect의 근본적인 원인은 Channel Potential이 Gate만으로 결정되지 않고 Source와 Drain의 영향을
          함께 받는다는 데 있습니다.
        </P>
        <P>따라서 구조 개선의 목표는 다음과 같습니다.</P>
        <ol className="list-inside list-decimal space-y-0.5 pl-1">
          <li>Gate와 Channel 사이의 Electrostatic coupling 강화</li>
          <li>Drain Potential의 Source 방향 침투 억제</li>
          <li>Source/Drain 공핍영역의 Channel 확장 억제</li>
          <li>Drain edge의 Peak Electric Field 완화</li>
          <li>Ion 감소를 최소화하면서 Ioff와 DIBL 억제</li>
        </ol>
        <P>
          하나의 구조가 모든 성능을 동시에 개선하는 경우는 드뭅니다. Electric Field를 줄이기 위해 저농도 영역을
          추가하면 Series Resistance가 증가할 수 있고, Body doping을 높이면 Punch-through는 줄어들지만 Threshold
          Voltage가 증가할 수 있습니다.
        </P>
        <P>따라서 MOSFET의 개선 구조는 항상 다음 관계로 평가해야 합니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Short-Channel Effect 개선 정도</li>
          <li>On-current 및 저항 특성의 손실</li>
        </ul>
      </Sub>

      <Sub heading="4.2. LDD 구조">
        <P>
          LDD는 <span className="font-semibold text-foreground">Lightly Doped Drain</span>의 약자로, 고농도
          Source/Drain과 Channel 사이에 상대적으로 낮은 농도의 n형 영역을 추가한 구조입니다. 일반적인 NMOS의 Source와
          Drain은 낮은 저항을 확보하기 위해 높은 농도로 도핑됩니다. 그러나 고농도 Drain이 Channel과 급격하게
          연결되면 Drain edge의 짧은 거리에서 Potential이 크게 변할 수 있습니다.
        </P>
        <P>
          동일한 Potential 차이가 좁은 영역에 집중될수록 Electric Field의 절댓값은 커집니다. LDD는 Channel과 고농도
          Drain 사이에 완만한 도핑 전이 영역을 형성하여 Potential 변화가 더 넓은 공간에 분포하도록 합니다. Source
          쪽에도 LDD 영역이 형성될 수 있지만, LDD의 주요 목적은 높은 Drain bias에서 나타나는 Drain edge의 Electric
          Field를 완화하는 것입니다.
        </P>
      </Sub>

      <Sub heading="4.3. LDD가 Electric Field를 완화하는 원리">
        <P>
          Drain에 높은 전압을 인가하면 Channel에서 Drain 방향으로 Potential이 증가합니다. Channel과 Drain 사이의
          Potential 차이와 변화가 일어나는 거리를 보면 LDD가 없는 급격한 접합에서는 변화가 일어나는 거리가 작아
          Drain edge에 높은 Electric Field가 형성될 수 있습니다. LDD를 적용하면 Channel과 고농도 Drain 사이의
          저농도 영역으로 공핍영역이 더 넓게 확장되고, Potential drop이 더 긴 거리에 걸쳐 발생할 수 있습니다.
        </P>
        <P>따라서 LDD 적용 시 기대되는 직접적인 변화는 다음과 같습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Drain edge Peak Electric Field 감소</li>
          <li>Potential contour의 급격한 밀집 완화</li>
          <li>고전계 영역의 공간적 분산</li>
          <li>Hot-carrier 발생 가능성 완화</li>
        </ul>
        <P>
          다만 LDD가 적용되었다고 해서 DIBL이나 모든 Short-Channel Effect가 반드시 크게 개선되는 것은 아닙니다.
          LDD의 가장 직접적인 역할은 <span className="font-semibold text-foreground">Drain edge의 높은 Electric
          Field를 완화하는 것</span>입니다.
        </P>
        <P>
          DIBL은 Source-side Barrier까지 전달되는 Drain Potential의 영향을 나타내므로, LDD의 DIBL 개선 효과는
          Channel Length, LDD 길이, 농도와 전체 구조에 따라 달라질 수 있습니다.
        </P>
        <P>
          Potential Map에서는 Drain voltage가 Channel에서 Drain까지 어떻게 분포하는지 확인합니다. LDD가 Electric
          Field를 분산한다면 Drain 부근의 Potential contour가 하나의 좁은 영역에 집중되기보다 LDD 영역에 걸쳐 더
          넓게 분포할 수 있습니다. 그러나 Potential Map만으로 Peak Electric Field 감소를 정량적으로 판단하기는
          어렵습니다. 전기장은 Potential의 미분값이므로 가능하면 Electric Field를 직접 확인해야 합니다.
        </P>
        <P>
          Electric Field Map 또는 Silicon surface의 1D Electric Field profile은 LDD 효과를 가장 직접적으로
          보여줍니다. Drain-side Peak Electric Field, Peak가 나타나는 위치, 고전계 영역의 폭, Channel–LDD–Drain
          구간의 Field 분포를 비교해보면 LDD의 효과를 직접적으로 확인할 수 있습니다.
        </P>
      </Sub>

      <Sub heading="4.4. LDD와 Series Resistance의 Trade-off">
        <P>
          LDD 영역은 고농도 Source/Drain보다 도핑 농도가 낮기 때문에 저항이 더 큽니다. LDD는 기본적으로 body
          doping보다는 높게, S/D doping보다는 낮게 도핑이 되기에 LDD의 도핑 농도가 낮아지면 전자 농도와 전도도가
          감소하여 저항이 증가할 수 있습니다. Series Resistance가 증가하면 외부에서 인가한 Drain voltage의 일부가
          LDD 영역에 걸리고, 실제 Channel과 Drain 사이에 전달되는 전압이 감소할 수 있습니다.
        </P>
        <P>따라서 다음과 같은 변화가 나타날 수 있습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>On-current 감소</li>
          <li>Linear Region의 기울기 감소</li>
          <li>On-resistance 증가</li>
          <li>Transconductance 감소 가능</li>
        </ul>
        <P>
          LDD 농도가 지나치게 높으면 고전계 완화 효과가 작아질 수 있고 결과적으로 짧아진 채널로 동작할 수 있습니다.
          LDD 농도가 지나치게 낮으면 Series Resistance에 의한 전류 손실이 커질 수 있습니다. LDD 길이도 마찬가지입니다.
          LDD 영역은 Potential drop을 더 넓게 분산하는 방향으로 작용할 수 있지만, 동시에 저항성 영역의 길이를
          증가시킵니다. 따라서 LDD 설계에서는 농도와 길이를 함께 조절해야 합니다.
        </P>
      </Sub>

      <Sub heading="4.5. Oxide Thickness와 Body Doping">
        <P>
          Oxide thickness와 Body Doping은 별도의 새로운 MOSFET 구조가 아니지만, Gate가 Channel Potential을 얼마나
          강하게 제어하는지를 결정하는 핵심 파라미터입니다.
        </P>
        <P>
          Oxide thickness가 감소하면 Cox가 증가합니다. Cox가 증가하면 동일한 Gate voltage에서 더 많은 반전전하를
          유도할 수 있고, Gate voltage 변화가 Channel의 Surface Potential에 더 강하게 전달됩니다.
        </P>
        <P>따라서 얇은 Oxide는 다음 방향으로 작용할 수 있습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Gate control 강화</li>
          <li>반전전하 증가</li>
          <li>SS 개선 가능</li>
          <li>DIBL 억제 방향</li>
          <li>Ion 증가 가능</li>
        </ul>
        <P>
          하지만 실제 SiO₂가 지나치게 얇아지면 직접 터널링에 의한 Gate leakage와 Oxide 신뢰성 문제가 증가합니다.
        </P>
        <P>
          현재 시뮬레이션에서 터널링 모델을 사용하지 않는다면, 얇은 Oxide에 따른 Gate leakage 감소·증가를 결과로
          평가할 수 없습니다. 현재 결과에서는 주로 Electrostatic Control과 I–V 변화만 해석해야 합니다.
        </P>
        <P>
          Body doping은 Source와 Drain 접합의 공핍층 폭과 Threshold Voltage에 영향을 줍니다. PN 접합의 공핍층
          폭은 도핑 농도가 증가할수록 감소합니다. 따라서 Body doping을 증가시키면 Source와 Drain의 공핍영역이
          Channel 내부로 확장되는 것을 줄일 수 있습니다.
        </P>
        <P>이는 다음 현상을 억제하는 방향으로 작용할 수 있습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Charge Sharing</li>
          <li>Threshold-Voltage Roll-off</li>
          <li>Punch-through</li>
          <li>Drain Potential의 Channel 침투</li>
        </ul>
        <P>
          하지만 Body doping 증가는 공핍전하를 증가시키므로 Threshold Voltage도 높아질 수 있습니다. 동일한 Gate
          voltage에서 Vth가 증가하면 Gate overdrive가 감소하여 Ion이 낮아질 수 있습니다. 또한 실제 소자에서는 높은
          Channel doping이 불순물 산란을 증가시켜 Carrier Mobility를 감소시킬 수 있습니다. 다만 현재 Constant
          Mobility 모델에서는 이러한 Mobility degradation이 직접 반영되지 않을 수 있습니다.
        </P>
        <P>따라서 현재 시뮬레이션에서 Body doping 변화는 다음 항목을 중심으로 해석하는 것이 적절합니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>공핍영역 변화</li>
          <li>Potential 분포</li>
          <li>Threshold Voltage</li>
          <li>DIBL</li>
          <li>Ion과 Ioff</li>
        </ul>
      </Sub>

      <Sub heading="4.6. Halo Implantation 또는 Pocket Implant">
        <P>
          Halo implant는 Source와 Drain 근처의 Channel 아래에 국부적으로 높은 Body doping 영역을 형성하는 방법입니다.
          Pocket implant라고도 합니다. 전체 Channel doping을 높이는 대신 Source/Drain 접합 주변만 선택적으로 높은
          농도로 도핑하여 공핍영역의 Channel 침투를 억제합니다.
        </P>
        <P>기대되는 효과는 다음과 같습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Threshold-Voltage Roll-off 억제</li>
          <li>Punch-through 억제</li>
          <li>Source/Drain 공핍층 확장 감소</li>
          <li>Source-side Barrier 유지</li>
        </ul>
        <P>하지만 Halo doping이 지나치게 높으면 다음 문제가 나타날 수 있습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Threshold Voltage 증가</li>
          <li>Channel 내 도핑 불균일 증가</li>
          <li>Mobility 감소 가능</li>
          <li>소자 특성 변동 증가</li>
          <li>Reverse Short-Channel Effect 가능</li>
        </ul>
        <P>현재 프로젝트에서는 Halo profile을 직접 구현하지 않았으므로, 대표적인 도핑 기반 개선 방법으로만 소개합니다.</P>
      </Sub>

      <Sub heading="4.7. High-k Gate Dielectric">
        <P>
          Gate control을 강화하려면 Cox를 증가시켜야 합니다. SiO₂의 두께를 계속 줄이면 Gate tunneling leakage가
          커질 수 있습니다. High-k dielectric은 SiO₂보다 높은 유전율을 가진 재료를 사용하여, 물리적인 절연막
          두께를 유지하면서 큰 Gate capacitance를 확보하는 방법입니다.
        </P>
        <P>High-k dielectric의 목적은 다음과 같습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Gate control 강화</li>
          <li>작은 Equivalent Oxide Thickness 확보</li>
          <li>물리적 절연막 두께 유지</li>
          <li>Gate leakage 완화</li>
        </ul>
        <P>High-k 적용 시에는 재료 계면, 고정전하, Trap과 Mobility degradation 등의 문제가 함께 고려되어야 합니다.</P>
      </Sub>

      <Sub heading="4.8. FinFET과 Gate-All-Around">
        <P>
          Planar MOSFET에서는 Gate가 주로 Channel의 위쪽 표면에서 Potential을 제어합니다. Channel이 짧아질수록
          Drain이 Channel 내부에 미치는 영향이 커지기 때문에 한쪽 방향의 Gate만으로 Electrostatic Control을 유지하기
          어려워집니다.
        </P>
        <P>FinFET은 얇은 Fin 형태의 Channel을 Gate가 여러 면에서 감싸는 구조입니다.</P>
        <P>Gate-All-Around는 Gate가 나노와이어 또는 나노시트 Channel의 전체 둘레를 감싸는 구조입니다.</P>
        <P>
          Gate가 Channel을 감싸는 면이 많아질수록 Channel Potential이 Gate에 더 강하게 결합합니다. 개념적으로
          다음과 같이 정리할 수 있습니다 — Planar Gate는 Channel 한쪽 면 제어, FinFET은 Channel 3면 제어, GAA는
          Channel 4면 제어.
        </P>
        <P>기대되는 효과는 다음과 같습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Electrostatic Control 강화</li>
          <li>DIBL 감소</li>
          <li>SS 개선</li>
          <li>Ioff 감소</li>
          <li>더 짧은 Channel에서의 동작 가능</li>
        </ul>
        <P>
          다만 FinFET과 Gate-All-Around는 현재의 2D Planar MOSFET과 Geometry 및 전류 정규화 방식이 크게 다릅니다.
          시뮬레이션에서 단순한 2D 구조 변경으로 실제 3D Gate wrapping의 전류를 예측할 수 없으며 다양한 심화
          모델을 통해야만 이를 구현할 수 있습니다.
        </P>
      </Sub>
    </div>
  );
}

function Chapter5Content() {
  return (
    <div className="flex flex-col gap-5 text-[13px] leading-relaxed text-on-surface-variant">
      <P>
        본 프로젝트에서는 Python 기반 오픈소스 TCAD인 <span className="font-semibold text-foreground">DEVSIM</span>을
        이용해 MOSFET을 시뮬레이션합니다.
      </P>
      <P>
        먼저 Gmsh에서 소자 구조와 Mesh를 생성하고, 이를 DEVSIM으로 불러옵니다. 이후 Silicon과 Oxide의 물성, Doping,
        Contact, 물리 방정식을 설정한 뒤 Gate와 Drain voltage를 변화시키며 Potential, Carrier Concentration과
        Current를 계산합니다.
      </P>
      <div>
        <P>전체 과정은 다음과 같습니다.</P>
        <ol className="mt-1 list-inside list-decimal space-y-0.5 pl-1">
          <li>Mesh 생성</li>
          <li>Material, Doping 설정</li>
          <li>물리 방정식 정의</li>
          <li>Contact과 Boundary Condition 설정</li>
          <li>비선형 연립방정식 계산</li>
          <li>Potential, Carrier, Current 추출</li>
          <li>Field Map과 I–V Curve 생성</li>
        </ol>
      </div>
      <P>
        DEVSIM은 입력된 구조를 보고 자동으로 MOSFET의 동작을 판단하는 프로그램이 아닙니다. Python 코드에서 어떤
        영역이 Silicon과 Oxide인지, 어느 경계가 Gate·Source·Drain인지, 어떤 물리식을 적용할지를 사용자가 직접
        정의해야 합니다.
      </P>

      <Sub heading="5.1. Geometry와 Mesh">
        <P>
          실제 MOSFET 내부의 Potential과 Carrier Concentration은 공간에 따라 연속적으로 변합니다. 그러나 컴퓨터는
          모든 위치의 값을 무한히 계산할 수 없습니다. 따라서 TCAD에서는 소자 영역을 유한한 수의 작은 격자로
          나눕니다. 이를 <span className="font-semibold text-foreground">Mesh</span>라고 합니다.
        </P>
        <P>Mesh는 주로 다음 요소로 구성됩니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>
            <span className="font-semibold text-foreground">Node</span> — Potential과 Carrier Concentration 등이
            저장되는 점
          </li>
          <li>
            <span className="font-semibold text-foreground">Edge</span> — 인접한 Node를 연결하는 선
          </li>
          <li>
            <span className="font-semibold text-foreground">Element</span> — 여러 Node와 Edge로 구성된 작은 면적
          </li>
          <li>
            <span className="font-semibold text-foreground">Region</span> — Silicon, Oxide와 같이 물성이 동일한 영역
          </li>
          <li>
            <span className="font-semibold text-foreground">Contact</span> — 외부 전압이 연결되는 경계
          </li>
          <li>
            <span className="font-semibold text-foreground">Interface</span> — 서로 다른 Material이 만나는 경계
          </li>
        </ul>
        <P>
          본 프로젝트에서는 Gmsh에서 MOSFET의 2D Geometry와 Mesh를 생성한 뒤, Gmsh 2.2 형식의 Mesh를 DEVSIM으로
          불러옵니다.
        </P>
        <P>Gmsh 단계에서는 다음 영역을 구분해야 합니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Silicon Body</li>
          <li>Gate Oxide</li>
          <li>Gate</li>
          <li>Source</li>
          <li>Drain</li>
          <li>Body contact</li>
          <li>Silicon–Oxide Interface</li>
        </ul>
        <P>
          DEVSIM은 각 Region과 Contact의 이름을 기준으로 재료 파라미터, 방정식과 Boundary Condition을 적용합니다.
        </P>
        <P>
          Mesh가 너무 거칠면 Potential이나 Carrier Concentration이 급격하게 변하는 영역을 정확히 표현하기
          어렵습니다.
        </P>
        <P>MOSFET에서는 다음 영역에 상대적으로 조밀한 Mesh가 필요합니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Silicon–Oxide Interface</li>
          <li>Source–Channel junction</li>
          <li>Drain–Channel junction</li>
          <li>LDD 경계</li>
          <li>Gate edge</li>
          <li>공핍영역</li>
          <li>높은 Electric Field가 형성되는 영역</li>
        </ul>
        <P>
          예를 들어 Gate 아래 반전층은 Silicon 표면의 얇은 영역에 형성됩니다. 표면 방향 Mesh가 지나치게 크면
          Electron Concentration의 급격한 변화를 충분히 표현하지 못할 수 있습니다.
        </P>
        <P>
          반대로 소자 전체에 지나치게 조밀한 Mesh를 사용하면 미지수의 수가 증가해 계산시간과 메모리 사용량이
          커집니다.
        </P>
      </Sub>

      <Sub heading="5.2. Material과 Doping">
        <P>
          Mesh를 불러온 뒤에는 각 Region이 어떤 물질인지 설정해야 합니다. Silicon과 Oxide는 서로 다른 물성을
          가지므로 각각 다른 파라미터와 방정식이 적용됩니다.
        </P>
        <P>Silicon에는 일반적으로 다음 파라미터가 필요합니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Permittivity</li>
          <li>Intrinsic carrier concentration</li>
          <li>Electron mobility</li>
          <li>Hole mobility</li>
          <li>Temperature</li>
          <li>Generation–Recombination 관련 파라미터</li>
        </ul>
        <P>
          Oxide에는 주로 Permittivity와 Potential equation을 설정합니다. 이상적인 Oxide 내부에서는 이동 가능한
          Electron과 Hole을 계산하지 않고 Potential만 계산할 수 있습니다.
        </P>
        <P>MOSFET의 Body, Source, Drain과 LDD는 Doping 분포로 구분됩니다.</P>
        <P>
          Net Doping은 N<sub>net</sub> = N<sub>D</sub> − N<sub>A</sub>입니다. N<sub>D</sub>는 Donor Concentration,
          N<sub>A</sub>는 Acceptor Concentration입니다.
        </P>
        <P>
          반도체 내부의 전체 Charge Density는 다음과 같습니다. 각 항은 순서대로 hole, electron, ionized Donor,
          ionized Acceptor입니다.
        </P>
        <Eq tex="\rho = q\left(p - n + N_D^{+} - N_A^{-}\right)" />
        <P>
          따라서 Doping이 변하면 Charge Density가 변하고, 그 결과 Potential, Electric Field와 Carrier Concentration도
          달라집니다.
        </P>
      </Sub>

      <Sub heading="5.3. DEVSIM이 푸는 핵심 방정식">
        <P>
          기본적인 Drift–Diffusion 해석은 소자 내부 각 위치의 Potential, Electron Concentration과 Hole
          Concentration을 계산합니다.
        </P>

        <h5 className="text-[13px] font-bold text-foreground">5.3.1. Poisson Equation</h5>
        <P>Poisson equation은 Charge Density와 Potential을 연결합니다.</P>
        <Eq tex="\nabla \cdot \left(\varepsilon \nabla \psi\right) = -\rho" />
        <P>Charge Density를 대입하면 다음과 같습니다.</P>
        <Eq tex="\nabla \cdot \left(\varepsilon \nabla \psi\right) = -q\left(p - n + N_D^{+} - N_A^{-}\right)" />
        <P>Permittivity가 일정한 2차원 영역에서는 다음과 같이 나타낼 수 있습니다.</P>
        <Eq tex="\varepsilon\left(\frac{\partial^2 \psi}{\partial x^2} + \frac{\partial^2 \psi}{\partial y^2}\right) = -q\left(p - n + N_D^{+} - N_A^{-}\right)" />
        <P>Electric Field는 Potential의 공간적 기울기로부터 계산됩니다.</P>
        <Eq tex="\vec{E} = -\nabla \psi" />
        <P>즉, DEVSIM은 Doping과 Carrier가 만든 Charge Density를 이용해 Potential과 Electric Field를 계산합니다.</P>

        <h5 className="text-[13px] font-bold text-foreground">5.3.2. Drift–Diffusion Current</h5>
        <P>
          Carrier Current는 Electric Field에 의한 <span className="font-semibold text-foreground">Drift</span>와
          Carrier 농도 차이에 의한 <span className="font-semibold text-foreground">Diffusion</span>으로
          구성됩니다.
        </P>
        <P>Electron과 Hole Current Density는 다음과 같습니다.</P>
        <Eq tex="\vec{J}_n = q\mu_n n \vec{E} + qD_n \nabla n, \qquad \vec{J}_p = q\mu_p p \vec{E} - qD_p \nabla p" />
        <P>
          여기서 μ는 mobility고, D는 Diffusion Coefficient입니다. Mobility와 Diffusion Coefficient는 Einstein
          relation으로 연결됩니다.
        </P>
        <Eq tex="D_n = \frac{kT}{q}\mu_n, \qquad D_p = \frac{kT}{q}\mu_p" />
        <P>
          MOSFET의 ON 상태에서는 Drain voltage가 만드는 Electric Field에 의한 Drift가 중요합니다. 반면
          Subthreshold 영역에서는 Source와 Channel 사이의 Carrier 농도 차이에 의한 Diffusion의 영향이 중요합니다.
        </P>

        <h5 className="text-[13px] font-bold text-foreground">5.3.3. Continuity Equation</h5>
        <P>
          Carrier는 소자 내부에서 임의로 사라지거나 생성되지 않고 보존되어야 합니다. DC 정상상태에서 Electron과
          Hole Continuity Equation은 다음과 같습니다.
        </P>
        <Eq tex="\frac{\partial n}{\partial t} = \frac{1}{q}\nabla \cdot \vec{J}_n + G - R, \qquad \frac{\partial p}{\partial t} = -\frac{1}{q}\nabla \cdot \vec{J}_p + G - R" />
        <P>
          여기서 G는 Generation rate, R은 Recombination rate입니다. Generation과 Recombination을 무시하면 다음과
          같이 단순화됩니다.
        </P>
        <Eq tex="\nabla \cdot \vec{J}_n = 0, \qquad \nabla \cdot \vec{J}_p = 0" />
        <P>이는 소자 내부의 작은 영역에서 들어오는 Current와 나가는 Current가 같아야 한다는 의미입니다.</P>
      </Sub>

      <Sub heading="5.4. Self-Consistent Calculation">
        <P>
          Poisson equation과 Continuity equation은 각각 따로 한 번씩 풀어서 끝낼 수 없습니다. Potential이 변하면
          Electric Field와 Current가 변하고, Carrier Concentration이 변하면 Charge Density가 변합니다. 바뀐 Charge
          Density는 다시 Potential을 변화시킵니다.
        </P>
        <Eq tex="\psi \;\Rightarrow\; (n, p) \;\Rightarrow\; \rho \;\Rightarrow\; \psi" />
        <P>따라서 DEVSIM은 다음 방정식을 동시에 만족하는 해를 구합니다.</P>
        <Eq tex="\nabla \cdot \left(\varepsilon \nabla \psi\right) = -q\left(p - n + N_D^{+} - N_A^{-}\right)" />
        <Eq tex="\nabla \cdot \vec{J}_n = q(R-G)" />
        <Eq tex="\nabla \cdot \vec{J}_p = -q(R-G)" />
        <P>
          이처럼 Potential과 Carrier가 서로 일치하도록 반복 계산하는 것을{" "}
          <span className="font-semibold text-foreground">Self-consistent solution</span>이라고 합니다.
        </P>
      </Sub>

      <Sub heading="5.5. Mesh 위의 수치해석">
        <P>
          Poisson equation과 Continuity equation은 연속적인 미분방정식입니다. DEVSIM은 이 식을 Mesh 위의 유한한
          연립방정식으로 변환합니다.
        </P>
        <P>
          Finite Volume Method에서는 각 Node 주변에 작은 Control Volume을 두고, 경계를 통과하는 Flux를
          계산합니다.
        </P>
        <Eq tex="\iiint_V \nabla \cdot \vec{J} \, dV = \iiint_V S \, dV" />
        <P>Divergence theorem을 적용하면 다음과 같습니다.</P>
        <Eq tex="\oiint_{\partial V} \vec{J} \cdot \hat{n} \, dA = \iiint_V S \, dV" />
        <P>이를 Mesh 위의 식으로 단순화하면 다음과 같이 볼 수 있습니다.</P>
        <Eq tex="\sum_{j} J_{ij} A_{ij} = S_i V_i" />
        <P>여기서</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>
            J<sub>ij</sub>: Node i와 인접 Node j 사이의 Flux
          </li>
          <li>
            A<sub>ij</sub>: Control Volume 사이의 경계 크기
          </li>
          <li>
            S<sub>i</sub>: 내부 Source 항
          </li>
          <li>
            V<sub>i</sub>: Node i가 담당하는 Control Volume
          </li>
        </ul>
        <P>입니다.</P>
        <P>즉, 각 Node 주변에서 다음 보존 조건을 만족하도록 방정식을 만듭니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>들어오는 Flux − 나가는 Flux + 내부 Source = 0</li>
        </ul>
        <P>
          Potential, Electron과 Hole은 주로 Node에 저장됩니다. Electric Field와 Current는 인접한 Node 사이의 값
          차이를 이용하므로 Edge에서 계산됩니다.
        </P>

        <h5 className="text-[13px] font-bold text-foreground">5.5.1. Newton Method</h5>
        <P>Poisson equation과 Carrier equation은 비선형이므로 반복 계산이 필요합니다.</P>
        <P>전체 방정식을 다음과 같이 나타냅니다.</P>
        <Eq tex="F(u) = 0" />
        <P>여기서 u에는 모든 Node의 Potential, Electron Concentration과 Hole Concentration이 포함됩니다.</P>
        <P>Newton Method에서는 현재 해에서 다음 선형 연립방정식을 풉니다.</P>
        <Eq tex="J(u_k)\, \Delta u = -F(u_k)" />
        <P>여기서 J는 Jacobian Matrix입니다. 계산된 보정값을 현재 해에 더합니다.</P>
        <Eq tex="u_{k+1} = u_k + \Delta u" />
        <P>이 과정을 Residual이 충분히 작아질 때까지 반복합니다.</P>
      </Sub>

      <Sub heading="5.6. Contact, Bias Sweep과 결과 생성">
        <P>미분방정식만으로는 해를 하나로 정할 수 없으므로 Contact에 Boundary Condition을 설정해야 합니다.</P>
        <P>기본적인 NMOS Bias는 다음과 같습니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>V<sub>S</sub> = 0, V<sub>B</sub> = 0, V<sub>G</sub> = V<sub>GS</sub>, V<sub>D</sub> = V<sub>DS</sub></li>
        </ul>
        <P>
          Source, Drain과 Body에는 Carrier를 공급하거나 제거할 수 있는 Ohmic Contact 조건을 적용합니다. Gate는
          Oxide로 Silicon과 절연되어 있으므로 Gate voltage가 Surface Potential을 바꾸지만, 이상적인 경우 Gate에서
          Silicon으로 직접적인 전도전류는 흐르지 않습니다. Silicon–Oxide Interface에서는 Potential이 연결되어야
          합니다.
        </P>
        <Eq tex="\psi_{Si} = \psi_{ox}" />
        <P>계면전하가 없다면 Interface에 수직인 Electric Displacement도 연속입니다.</P>
        <Eq tex="\varepsilon_{Si}\, E_{Si,\perp} = \varepsilon_{ox}\, E_{ox,\perp}" />
        <P>
          MOSFET에서는 처음부터 높은 Gate 또는 Drain voltage를 인가하면 Newton Solver가 수렴하지 못할 수 있습니다.
        </P>
        <P>따라서 일반적으로 다음 순서로 계산합니다.</P>
        <ol className="list-inside list-decimal space-y-0.5 pl-1">
          <li>Contact voltage가 0 V인 초기상태 계산</li>
          <li>Poisson equation만 풀어 초기 Potential 계산</li>
          <li>Electron과 Hole equation 추가</li>
          <li>Drift–Diffusion 해 계산</li>
          <li>Gate 또는 Drain voltage를 작은 Step으로 증가</li>
          <li>이전 Bias의 수렴해를 다음 Bias의 초기값으로 사용</li>
        </ol>
        <P>각 단계의 해가 서로 가까우므로 목표 Bias를 한 번에 인가하는 것보다 수렴이 안정적입니다.</P>
        <P>Solver가 수렴했다고 해서 결과가 반드시 물리적으로 올바른 것은 아닙니다.</P>
        <P>다음 항목을 함께 확인해야 합니다.</P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Region과 Contact가 올바르게 생성되었는가?</li>
          <li>Junction과 Interface의 Mesh가 충분히 조밀한가?</li>
          <li>Doping의 농도와 단위가 올바른가?</li>
          <li>Gate voltage 증가에 따라 Channel Electron Concentration이 증가하는가?</li>
          <li>Source와 Drain의 Current가 일관되게 보존되는가?</li>
          <li>Mesh와 Bias step을 변경해도 주요 결과가 유지되는가?</li>
        </ul>
        <P>
          또한 현재 모델은 기본적인 Drift–Diffusion과 Constant Mobility에 가깝습니다. 따라서 다음 현상을 현재
          결과로 직접 검증했다고 표현해서는 안 됩니다.
        </P>
        <ul className="list-inside list-disc space-y-0.5 pl-1">
          <li>Velocity Saturation</li>
          <li>High-field Mobility Degradation</li>
          <li>Surface Mobility Degradation</li>
          <li>Gate Tunneling</li>
          <li>Quantum Confinement</li>
          <li>Hot-carrier Degradation</li>
        </ul>
        <P>
          TCAD 결과는 <span className="font-semibold text-foreground">코드에 실제로 포함한 Physics Model의 범위
          안에서만</span> 해석해야 합니다.
        </P>
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

              <AccordionItem value="chapter2">
                <AccordionTrigger>
                  <span className="flex items-center gap-2">
                    <Sigma className="h-4 w-4 text-primary" />
                    2. Long-Channel MOSFET
                  </span>
                </AccordionTrigger>
                <AccordionPanel>
                  <ChapterPanel content={<Chapter2Content />} tool={<LongChannelMOSFETTool />} />
                </AccordionPanel>
              </AccordionItem>

              <AccordionItem value="chapter3">
                <AccordionTrigger>
                  <span className="flex items-center gap-2">
                    <Sigma className="h-4 w-4 text-primary" />
                    3. Short-Channel MOSFET
                  </span>
                </AccordionTrigger>
                <AccordionPanel>
                  <ChapterPanel content={<Chapter3Content />} />
                </AccordionPanel>
              </AccordionItem>

              <AccordionItem value="chapter4">
                <AccordionTrigger>
                  <span className="flex items-center gap-2">
                    <Sigma className="h-4 w-4 text-primary" />
                    4. MOSFET Performance Enhancement
                  </span>
                </AccordionTrigger>
                <AccordionPanel>
                  <ChapterPanel content={<Chapter4Content />} />
                </AccordionPanel>
              </AccordionItem>

              <AccordionItem value="chapter5">
                <AccordionTrigger>
                  <span className="flex items-center gap-2">
                    <Sigma className="h-4 w-4 text-primary" />
                    5. Python TCAD
                  </span>
                </AccordionTrigger>
                <AccordionPanel>
                  <ChapterPanel content={<Chapter5Content />} />
                </AccordionPanel>
              </AccordionItem>
            </Accordion>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
