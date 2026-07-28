# 3. Short-Channel MOSFET

## 이 장의 역할

Long-channel MOSFET에서는 channel의 전위를 Gate가 주로 제어한다고
가정했다. 하지만 channel length가 짧아지면 Source와 Drain의 depletion
영역과 전기장이 channel 내부까지 영향을 미치기 시작한다. 그 결과 Gate가
channel barrier를 독립적으로 제어하기 어려워진다.

이 장의 목적은 short-channel effect의 모든 물리 모델을 깊게 유도하는 것이
아니다. 기존 시뮬레이션 GUI에서 다음 흐름을 직접 확인하는 것이 핵심이다.

> Channel Length 감소  
> → Source/Drain 전계의 Channel 침투  
> → Gate의 전위 제어력 감소  
> → Threshold Voltage 감소와 DIBL  
> → Off-current 증가  
> → 성능과 누설전류 사이의 Trade-off

---

# 전체 페이지 구성

```text
Chapter 3 제목과 핵심 질문
└─ “Channel이 짧아지면 왜 Gate가 소자를 완전히 끄기 어려워질까?”

3.1 Long-Channel과 Short-Channel의 차이
├─ [이미지 A] 두 구조의 길이 비교
└─ Gate control의 의미

3.2 Charge Sharing과 VTH Roll-off
├─ [이미지 B] Long/Short Potential field 비교
└─ [이미지 C] VTH vs. Channel Length

3.3 Drain-Induced Barrier Lowering
├─ [이미지 D] 낮은 VD와 높은 VD의 Potential field
├─ [이미지 E] Silicon 표면의 Energy barrier
└─ DIBL 식과 그래프 해석

3.4 Subthreshold 특성과 Off-current
├─ [이미지 F] 길이별 ID–VG 로그 그래프
└─ SS, Ioff 해석

3.5 Output 특성과 Channel-Length Modulation
├─ [이미지 G] 길이별 ID–VD
└─ 포화영역 기울기 비교

3.6 Short-Channel 설계 Trade-off
├─ [이미지 H] Length에 따른 핵심 지표 요약
└─ 다음 장의 MOSFET 성능 개선 구조로 연결
```

## 시각 자료 운영 원칙

본문에는 조건을 한눈에 비교할 수 있는 정적 이미지를 배치하고, 더 많은
조건은 기존 GUI에서 직접 선택하도록 한다.

- 비교 이미지에서는 바꾸는 변수를 하나로 제한한다.
- 두 field map의 color range는 동일하게 고정한다.
- 구조의 가로 배율을 억지로 같게 늘리지 않는다.
- 그래프에는 사용한 \(L_G\), \(t_{ox}\), \(N_A\), \(V_G\), \(V_D\)를 표시한다.
- 선택한 field map의 동작점은 아래 I–V 그래프에도 marker로 표시한다.

---

# 권장 기준 조건

Short-channel effect를 비교할 때는 channel length 이외의 조건을 먼저
고정한다.

| 항목 | 권장 조건 |
|---|---:|
| Channel length | 100, 200, 500, 1000 nm |
| 대표 Long / Short 비교 | 1000 nm / 100 nm |
| Oxide thickness | 10 nm |
| Bulk doping | \(1\times10^{16}\,\mathrm{cm^{-3}}\) |
| Source/Drain doping | \(1\times10^{20}\,\mathrm{cm^{-3}}\) |
| LDD doping | \(1\times10^{18}\,\mathrm{cm^{-3}}\) |
| 낮은 Drain bias | \(V_D=0.05\,\mathrm{V}\) |
| 높은 Drain bias | \(V_D=1.0\,\mathrm{V}\) |

정확히 위 조건을 사용하기 어렵다면 GUI에서 공통으로 존재하는 가장 가까운
조건을 사용한다. 중요한 것은 절대적인 수치보다 **channel length만 바뀐
두 결과를 비교하는 것**이다.

---

# 3.1 Long-Channel과 Short-Channel의 차이

MOSFET은 Gate voltage를 이용하여 silicon 표면에 inversion channel을
만들고, Source와 Drain 사이의 전류를 제어한다. Long-channel 소자에서는
channel 중앙이 Source와 Drain junction으로부터 충분히 멀기 때문에 channel
전위가 Gate voltage에 주로 의해 결정된다.

Channel length가 짧아지면 상황이 달라진다. Source와 Drain의 depletion
영역이 channel에서 차지하는 비율이 커지고, Drain에서 발생한 전기장이
Source 방향으로 더 쉽게 침투한다. 따라서 channel 전위는 더 이상 Gate만의
영향을 받지 않는다.

> **[이미지 A 배치] Long-Channel과 Short-Channel 구조 비교**
>
> 위치: 3.1 첫 번째 설명 바로 아래.
>
> 이미지 구성:
>
> - 왼쪽: \(L_G=1000\,\mathrm{nm}\)
> - 오른쪽: \(L_G=100\,\mathrm{nm}\)
> - Field: `Net Doping` 또는 mesh/structure
> - Gate, Oxide, Source, Drain, p-type Bulk 표시
> - Gate length 화살표 표시
>
> 이 이미지의 목적은 물리량 비교가 아니라 길이 차이를 먼저 인식시키는
> 것이다. Color bar보다 구조와 길이 표기가 중요하다.

이 장에서 말하는 Gate control의 약화는 Gate가 작동하지 않는다는 뜻이
아니다. 같은 Gate voltage에서도 Source와 Drain bias가 channel barrier에
미치는 영향이 상대적으로 커진다는 의미다.

---

# 3.2 Charge Sharing과 Threshold-Voltage Roll-off

Long-channel MOSFET에서는 inversion 이전에 형성되는 depletion charge를
Gate가 대부분 제어한다고 볼 수 있다. Short-channel MOSFET에서는 Source와
Drain junction의 depletion 영역이 channel 아래로 들어오면서 이 전하의
일부를 함께 담당한다.

\[
Q_{\mathrm{dep}}
=Q_G+Q_S+Q_D
\]

- \(Q_G\): Gate가 제어하는 depletion charge
- \(Q_S\): Source junction이 담당하는 부분
- \(Q_D\): Drain junction이 담당하는 부분

Channel이 짧아질수록 \(Q_S\)와 \(Q_D\)의 상대적인 비중이 커진다. 따라서
Gate가 inversion을 만들기 위해 추가로 공급해야 하는 전하가 줄어들고,
threshold voltage가 낮아질 수 있다.

\[
L_G\downarrow
\quad\Rightarrow\quad
V_{TH}\downarrow
\]

이를 **threshold-voltage roll-off**라고 한다.

> **[이미지 B 배치] Long/Short Potential Field 비교**
>
> 위치: charge sharing 설명 다음.
>
> 캡처 조건:
>
> - \(L_G=1000\,\mathrm{nm}\)와 \(100\,\mathrm{nm}\)
> - 동일한 \(t_{ox}\), doping, \(V_G\), \(V_D\)
> - \(V_D=0.05\,\mathrm{V}\)
> - \(V_G\): 두 소자의 threshold 부근 또는 subthreshold 조건
> - Field: `Potential`
> - 두 field map의 color-bar 범위 고정
>
> 확인할 부분:
>
> - Source와 Drain의 potential contour가 channel 내부로 들어오는 범위
> - Gate 아래 channel 중앙이 Source/Drain의 영향을 받는 정도

Field map에서 short-channel 소자의 contour가 channel 중앙까지 더 크게
휘어 있다면 Source와 Drain이 channel electrostatics에 더 강하게 참여하고
있다는 뜻이다.

> **[이미지 C 배치] \(V_{TH}\) vs. Channel Length**
>
> 위치: 3.2 마지막.
>
> 그래프 구성:
>
> - x축: Channel length \(L_G\) (nm, 필요하면 log scale)
> - y축: Threshold voltage \(V_{TH}\) (V)
> - \(V_D=0.05\,\mathrm{V}\) 조건
> - 100, 200, 500, 1000 nm 지점 표시
>
> 그래프 아래 한 줄 해석:
>
> “Channel length가 감소할수록 \(V_{TH}\)가 감소하여 소자가 더 작은
> Gate voltage에서 켜지기 시작한다.”

---

# 3.3 Drain-Induced Barrier Lowering

NMOS가 꺼져 있을 때 Source의 전자가 channel로 이동하려면 Source와 channel
사이의 potential barrier를 넘어야 한다. Long-channel 소자에서는 이
barrier를 Gate가 주로 제어한다.

Short-channel 소자에서 Drain voltage가 증가하면 Drain의 전위가 channel을
통해 Source 쪽까지 영향을 미칠 수 있다. 이때 Source-side barrier가
낮아지고, Gate voltage를 높이지 않아도 전자가 channel로 유입되기 쉬워진다.
이 현상을 **Drain-Induced Barrier Lowering, DIBL**이라고 한다.

\[
\mathrm{DIBL}
=
\frac{
V_{TH}(V_{D,\mathrm{low}})
-
V_{TH}(V_{D,\mathrm{high}})
}{
V_{D,\mathrm{high}}-V_{D,\mathrm{low}}
}
\]

일반적으로 \(\mathrm{V/V}\) 또는 \(\mathrm{mV/V}\) 단위를 사용한다. 값이
클수록 Drain voltage에 의해 threshold voltage가 더 크게 변하며, Gate의
electrostatic control이 약하다는 의미다.

> **[이미지 D 배치] Drain Bias에 따른 Potential Field**
>
> 위치: DIBL 정의 바로 아래.
>
> 한 장을 2×2로 구성:
>
> | | \(V_D=0.05\,\mathrm{V}\) | \(V_D=1.0\,\mathrm{V}\) |
> |---|---|---|
> | Long | Potential field | Potential field |
> | Short | Potential field | Potential field |
>
> 공통 조건:
>
> - 같은 \(V_G\), preferably off/subthreshold
> - 같은 doping과 oxide thickness
> - 네 그림의 color range 고정
>
> 확인할 부분:
>
> - 높은 \(V_D\)에서 Drain potential이 Source 방향으로 침투하는 정도
> - 이 변화가 short-channel 소자에서 더 큰지 여부

Potential field만으로 barrier의 높이를 정확하게 읽기 어려울 수 있다.
따라서 silicon 표면을 따라 1D profile을 함께 제시하면 DIBL을 훨씬
직관적으로 설명할 수 있다.

\[
E_C(x)\approx -q\psi(x)+C
\]

절대적인 energy 기준보다 Source에서 channel로 진입할 때 나타나는 barrier의
상대적인 높이를 비교한다.

> **[이미지 E 배치] Surface Energy Barrier**
>
> 위치: 이미지 D 바로 아래.
>
> 그래프 구성:
>
> - x축: Source에서 Drain 방향의 위치
> - y축: Conduction-band energy \(E_C\) 또는 surface potential
> - 같은 short-channel 구조
> - \(V_D=0.05\,\mathrm{V}\)와 \(1.0\,\mathrm{V}\) 중첩
> - Source-side barrier 위치에 화살표 표시
> - 두 barrier 높이의 차이를 \(\Delta E_B\)로 표시
>
> 핵심 캡션:
>
> “Drain voltage가 증가하면서 Source-side barrier가 낮아지고, 같은
> Gate voltage에서도 carrier injection이 증가한다.”

---

# 3.4 Subthreshold 특성과 Off-Current

Threshold voltage 아래에서도 drain current가 완전히 0이 되지는 않는다.
이 영역의 전류는 \(I_D-V_G\)를 log scale로 표시했을 때 비교하기 쉽다.

Subthreshold swing은 drain current를 10배 증가시키는 데 필요한 Gate
voltage 변화량이다.

\[
SS
=
\frac{dV_G}
{d\left(\log_{10}I_D\right)}
\qquad [\mathrm{mV/dec}]
\]

SS가 작을수록 Gate voltage로 전류를 빠르게 끌 수 있다. 반대로 SS가
증가하면 더 넓은 Gate-voltage 범위에 걸쳐 leakage current가 남는다.

Short-channel에서 확인할 핵심은 다음 세 가지다.

1. \(I_D-V_G\) 곡선이 낮은 \(V_G\) 방향으로 이동하는가?
2. 높은 Drain bias에서 이동량이 더 커지는가?
3. Off 조건에서 drain current가 증가하는가?

> **[이미지 F 배치] Channel Length별 \(I_D-V_G\)**
>
> 위치: 3.4 중앙.
>
> 권장 구성: 좌우 두 그래프.
>
> - 왼쪽: \(V_D=0.05\,\mathrm{V}\)
> - 오른쪽: \(V_D=1.0\,\mathrm{V}\)
> - y축: \(|I_D|\) log scale
> - 곡선: \(L_G=100,200,500,1000\,\mathrm{nm}\)
> - 같은 channel length는 두 그래프에서 같은 색 사용
> - \(V_G=0\,\mathrm{V}\)의 \(I_\mathrm{off}\) 위치 표시
>
> 그래프에서 읽을 항목:
>
> - 곡선의 수평 이동: \(V_{TH}\) 변화
> - 낮은 전류 영역의 기울기: SS
> - \(V_G=0\)의 전류: \(I_\mathrm{off}\)
> - Drain bias에 따른 두 곡선의 차이: DIBL

Drive current가 증가한 결과만 보고 short-channel이 무조건 더 좋은
소자라고 판단하면 안 된다. Channel resistance 감소로 \(I_\mathrm{on}\)이
증가할 수 있지만, 동시에 \(I_\mathrm{off}\)도 증가할 수 있기 때문이다.

\[
\text{짧은 }L_G
\quad\Rightarrow\quad
I_\mathrm{on}\uparrow
\;\text{가능},
\qquad
I_\mathrm{off}\uparrow
\;\text{가능}
\]

따라서 \(I_\mathrm{on}/I_\mathrm{off}\) 비율도 함께 확인하는 것이 좋다.

---

# 3.5 Output 특성과 Channel-Length Modulation

Long-channel의 이상적인 saturation 영역에서는 \(V_D\)가 증가해도 drain
current가 거의 일정하다고 설명했다. 실제 소자에서는 Drain depletion
영역이 channel 안쪽으로 확장되면서 유효 channel length가 감소할 수 있다.

\[
L_{\mathrm{eff}}
=L_G-\Delta L
\]

이 때문에 saturation 이후에도 \(I_D-V_D\) 곡선에 기울기가 남는다. 이를
간단한 식으로 표현하면 다음과 같다.

\[
I_D
\approx
I_{D,\mathrm{sat}}
\left(1+\lambda V_{DS}\right)
\]

\(\lambda\)가 클수록 saturation 영역의 output conductance가 크다.

> **[이미지 G 배치] Long/Short \(I_D-V_D\) 비교**
>
> 위치: 3.5 식 아래.
>
> 그래프 구성:
>
> - 대표 길이: 1000 nm와 100 nm
> - \(V_G=0.5,1.0,1.5,2.0\,\mathrm{V}\)
> - 동일한 \(V_G\)는 같은 색
> - Long-channel은 실선, short-channel은 점선
> - saturation 이후의 기울기를 확대 inset으로 표시해도 좋음
>
> 확인할 부분:
>
> - Linear 영역의 전류 차이
> - 포화 시작 위치
> - 포화 이후 기울기

현재 사용 중인 모델이 constant-mobility drift-diffusion 모델이라면 이
결과를 **velocity saturation의 직접적인 증거로 해석하지 않는다**.
Velocity saturation을 정량적으로 설명하려면 high-field 또는
field-dependent mobility 모델이 별도로 필요하다. 현재 장에서는
electrostatic short-channel effect와 channel-length modulation을 중심으로
해석한다.

---

# 3.6 Short-Channel 설계 Trade-off

Channel length 감소는 집적도와 drive current 측면에서 유리할 수 있지만,
Gate의 electrostatic control을 약화시킨다. 따라서 하나의 지표만 최대화하는
것이 아니라 여러 특성을 함께 비교해야 한다.

> **[이미지 H 배치] Channel Length에 따른 핵심 지표**
>
> 위치: 장의 마지막 요약.
>
> 2×2 그래프 권장:
>
> 1. \(V_{TH}\) vs. \(L_G\)
> 2. DIBL vs. \(L_G\)
> 3. SS vs. \(L_G\)
> 4. \(I_\mathrm{off}\) 또는 \(I_\mathrm{on}/I_\mathrm{off}\) vs. \(L_G\)
>
> 모든 그래프에서:
>
> - x축 범위와 길이 순서를 동일하게 사용
> - Short 방향을 눈에 잘 보이도록 표시
> - 좋은 방향과 나쁜 방향을 작은 화살표로 표시

일반적으로 channel length가 감소할 때 기대되는 방향은 다음과 같다.

| 지표 | 예상 변화 | 의미 |
|---|---|---|
| \(V_{TH}\) | 감소 | 더 작은 Gate voltage에서 turn-on |
| DIBL | 증가 | Drain이 Source barrier에 더 큰 영향 |
| SS | 증가 가능 | Subthreshold Gate control 악화 |
| \(I_\mathrm{off}\) | 증가 | 대기전력 증가 |
| \(I_\mathrm{on}\) | 증가 가능 | Channel resistance 감소 |
| \(I_\mathrm{on}/I_\mathrm{off}\) | 악화 가능 | On 성능과 누설의 trade-off |

이 결과는 다음 장의 질문으로 연결된다.

> Channel을 계속 짧게 만들면서도 Drain 전계의 침투와 leakage를 줄이려면
> 구조와 doping을 어떻게 바꿔야 하는가?

다음 장에서는 oxide thickness, bulk doping, LDD, junction profile 및
Gate 구조가 short-channel effect를 어떻게 완화하는지 살펴본다.

---

# GUI에서 확인하는 순서

## 실습 A: Channel Length만 변경

고정:

\[
t_{ox},\;N_A,\;N_{S/D},\;N_{LDD},\;V_G,\;V_D
\]

변경:

\[
L_G=1000,\;500,\;200,\;100\,\mathrm{nm}
\]

먼저 Net Doping으로 구조를 확인하고, Potential과 Electron density로
전환한다.

## 실습 B: DIBL 확인

1. Short-channel 구조를 선택한다.
2. \(V_G\)를 off/subthreshold 조건으로 고정한다.
3. \(V_D=0.05\,\mathrm{V}\)와 \(1.0\,\mathrm{V}\)를 비교한다.
4. Potential contour와 Source-side surface barrier를 확인한다.
5. 두 \(I_D-V_G\)에서 추출한 \(V_{TH}\) 차이로 DIBL을 계산한다.

## 실습 C: Length Trend 확인

각 channel length에서 다음 값을 기록한다.

- \(V_{TH}\)
- DIBL
- SS
- \(I_\mathrm{off}\)
- \(I_\mathrm{on}\)

마지막에는 이미지 H처럼 length trend를 한 화면에서 비교한다.

---

# 최소 이미지 세트

본문을 너무 길게 만들고 싶지 않다면 아래 다섯 장만 사용해도 된다.

1. **이미지 A** — Long/Short 구조 비교
2. **이미지 D** — Long/Short × Low/High \(V_D\) Potential field
3. **이미지 E** — Source-side barrier lowering
4. **이미지 F** — Length별 \(I_D-V_G\)
5. **이미지 H** — \(V_{TH}\), DIBL, SS, \(I_\mathrm{off}\) 요약

이미지 B와 C는 D와 H에 통합할 수 있고, 이미지 G의 \(I_D-V_D\)는 페이지가
길어질 경우 접을 수 있는 보조 설명 또는 Simulation 탭으로 이동할 수 있다.

---

# 이미지 파일명 권장

```text
figures/
├─ ch3_a_long_vs_short_structure.png
├─ ch3_b_charge_sharing_potential.png
├─ ch3_c_vth_rolloff.png
├─ ch3_d_dibl_potential_comparison.png
├─ ch3_e_surface_barrier_lowering.png
├─ ch3_f_idvg_length_comparison.png
├─ ch3_g_idvd_length_comparison.png
└─ ch3_h_short_channel_metrics.png
```
