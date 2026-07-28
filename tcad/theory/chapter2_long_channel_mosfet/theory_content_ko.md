# 2. Long-Channel MOSFET 구조와 동작

## 이 장의 역할

PN 접합에서는 도핑이 공간전하, 전기장, 전위 및 에너지 밴드로 이어지는
과정을 확인했다. 이 장에서는 여기에 **gate 전압에 의한 표면 제어**를
추가한다.

전개 순서는 다음과 같다.

> MOS Capacitor  
> → Silicon 표면의 accumulation / depletion / inversion  
> → Source와 Drain 사이의 inversion channel  
> → Gate 전압에 따른 drain current  
> → Linear / Saturation 동작

MOS capacitor 자체를 깊게 다루기보다 MOSFET의 channel이 어떻게 만들어지는지
이해하는 데 필요한 내용만 사용한다.

---

# 전체 페이지 구성

## 권장 화면 배치

```text
Chapter 2 제목과 핵심 질문
│
├─ [개념 흐름] Gate Voltage → Surface Charge → Channel → Drain Current
│
├─ 2.1 MOS Capacitor: Gate가 Silicon 표면을 바꾸는 방법
│   ├─ 본문
│   ├─ [이미지 A] MOS capacitor 구조
│   ├─ [이미지 B] Accumulation / Flat-band / Depletion / Inversion 비교
│   └─ [Simulation에서 확인] 버튼
│
├─ 2.2 MOSFET 구조
│   ├─ [이미지 C] Gmsh 전체 구조와 mesh
│   └─ Gate / Oxide / Source / Drain / Bulk 설명
│
├─ 2.3 Channel 형성
│   ├─ 본문
│   ├─ [이미지 D] VG별 electron-density field map
│   └─ [Simulation에서 확인] 버튼
│
├─ 2.4 ID–VG
│   ├─ [이미지 E] ID–VG와 channel 형성 시점
│   └─ Threshold voltage 해석
│
├─ 2.5 ID–VD와 Linear / Saturation
│   ├─ [이미지 F] 여러 VG에서의 ID–VD
│   └─ 동작 영역 설명
│
└─ MOSFET 파라미터와 다음 장 연결
```

## 시각 자료 운영 원칙

본문에 작은 스크린샷을 반복해서 넣기보다 다음 두 종류를 구분한다.

1. **정적 비교 이미지**
   - 여러 조건을 한눈에 비교할 때 사용
   - 본문 흐름을 끊지 않음
   - 대표 조건만 표시

2. **인터랙티브 Simulation 탭**
   - 사용자가 \(N_A\), \(t_{ox}\), \(V_G\) 또는 field를 직접 바꿀 때 사용
   - 본문의 `Simulation에서 확인` 버튼과 연결
   - 계산을 수행하지 않고 저장 결과를 로드

---

# 2.1 MOS Capacitor: Gate가 Silicon 표면을 바꾸는 방법

MOS capacitor는 metal gate, oxide, semiconductor로 구성된다. Gate와
silicon 사이에는 oxide가 있으므로 DC gate current는 거의 흐르지 않는다.
대신 gate voltage가 oxide를 사이에 둔 전기장을 만들고 silicon 표면의
전하 분포를 바꾼다.

현재 시뮬레이션은 p-type silicon을 사용한다.

> **[이미지 A 배치] MOS Capacitor 구조**
>
> 권장 위치: 이 절의 첫 번째 문단 오른쪽 또는 바로 아래.
>
> 표시 항목:
>
> - Metal Gate
> - Oxide
> - p-type Silicon
> - Body contact
> - \(t_{ox}\)
> - 깊이 방향 \(x\)
>
> 이미지 형태: 복잡한 mesh보다 단순한 단면 개념도.

Oxide capacitance per unit area는 다음과 같다.

\[
C_{ox}=\frac{\varepsilon_{ox}}{t_{ox}}
\]

따라서 oxide가 얇을수록 같은 gate voltage에서 silicon 표면을 더 강하게
제어할 수 있다.

## Gate voltage에 따른 네 상태

### Accumulation

p-type silicon에 음의 gate voltage를 가하면 정공이 oxide/silicon
interface 쪽으로 끌려온다.

시뮬레이션에서는 다음을 확인한다.

- 표면 정공 농도 증가
- 표면 전자 농도 감소
- interface 부근에 양의 mobile charge 형성
- energy band가 accumulation 방향으로 굽음

### Flat-band

이상적인 work-function-matched 조건에서 \(V_G=0\)을 flat-band 기준으로
사용한다.

- silicon 내부 전위가 거의 일정
- \(E_C\), \(E_i\), \(E_V\)가 거의 평탄
- 표면 공간전하가 작음
- 표면 캐리어 농도가 bulk 값과 유사

### Depletion

작은 양의 gate voltage는 정공을 표면에서 밀어낸다. 이동 정공이 감소한
자리에 음전하를 띠는 이온화 acceptor가 남는다.

- 표면 정공 농도 감소
- 음의 공간전하 영역 형성
- depletion width 증가
- silicon 내부 전위와 band bending 증가

### Inversion

gate voltage를 더 높이면 표면 전자 농도가 계속 증가한다. 표면에서
전자 농도가 정공 농도보다 커지면 p-type silicon 표면이 n-type처럼
동작한다.

- \(n_s>p_s\)
- oxide 바로 아래에 얇은 electron layer 형성
- 이 electron layer가 NMOS의 channel이 됨

> **[이미지 B 배치] 네 상태 비교**
>
> 권장 위치: 네 상태 설명 직후.
>
> 2×2 비교 이미지:
>
> 1. \(V_G=-2\,\mathrm{V}\): Accumulation
> 2. \(V_G=0\,\mathrm{V}\): Flat-band
> 3. \(V_G=1\,\mathrm{V}\): Depletion 또는 inversion 시작
> 4. \(V_G=2\,\mathrm{V}\): Inversion
>
> 각 칸에는 carrier concentration과 energy band를 함께 배치한다.
>
> **현재 데이터로 생성 가능**

> **[Simulation에서 확인]**
>
> MOS Capacitor 탭을 열고 다음 값을 바꾼다.
>
> - \(N_A=10^{16},10^{17},10^{18}\,\mathrm{cm^{-3}}\)
> - \(t_{ox}=5,10,20\,\mathrm{nm}\)
> - \(V_G=-2,-1,0,1,2\,\mathrm{V}\)

---

# 2.2 MOS Capacitor 결과를 읽는 순서

MOS capacitor 그래프는 다음 순서로 읽는다.

> Gate Voltage  
> → Oxide/Silicon Potential  
> → Space Charge  
> → Carrier Concentration  
> → Energy Band

## Potential

전위 그래프에서는 oxide와 silicon에서 전압이 어떻게 분배되는지 확인한다.
Oxide 내부의 전위는 거의 선형으로 변하고, silicon에서는 표면 부근에
전위 변화가 집중된다.

## Carrier Concentration

로그축에서 electron과 hole concentration을 함께 비교한다.

- \(p_s\) 증가: accumulation
- \(p_s\) 감소, \(n_s<p_s\): depletion
- \(n_s>p_s\): inversion

## Space Charge

공간전하 밀도는 다음 관계로 해석한다.

\[
\rho=q(p-n+N_D^+-N_A^-)
\]

p-type depletion 영역에서는 이동 정공이 감소하므로
\(\rho\approx-qN_A\)가 된다.

## Energy Band

전위와 conduction band의 관계는 다음과 같다.

\[
E_C=-q\psi+C
\]

따라서 silicon 표면의 전위 변화는 band bending으로 나타난다. 이 장에서는
band 식을 깊게 유도하기보다 carrier concentration 그래프와 energy band가
같은 surface 상태를 설명하는지 확인한다.

---

# 2.3 도핑과 Oxide 두께를 바꾸면

## Acceptor 농도 증가

\(N_A\)가 증가하면 p-type bulk의 정공 농도가 증가한다. 동시에 inversion을
만들기 위해 더 많은 depletion charge를 감당해야 한다.

Fermi potential은 다음과 같다.

\[
\phi_F
=
\frac{kT}{q}
\ln\left(\frac{N_A}{n_i}\right)
\]

최대 depletion charge의 크기는 대략 다음과 같이 증가한다.

\[
|Q_{dep}|
\approx
\sqrt{4q\varepsilon_sN_A\phi_F}
\]

따라서 \(N_A\)가 증가하면 일반적으로 다음 경향이 나타난다.

- 같은 \(V_G\)에서 depletion charge 증가
- inversion 형성에 더 큰 gate voltage 필요
- threshold voltage 증가
- 같은 gate voltage에서 inversion electron density 감소 가능

## Oxide 두께 증가

\[
C_{ox}=\frac{\varepsilon_{ox}}{t_{ox}}
\]

\(t_{ox}\)가 증가하면 \(C_{ox}\)가 감소하고 gate control이 약해진다.

- oxide에서 더 많은 전압이 소모됨
- 같은 \(V_G\)에서 surface potential 변화 감소
- inversion charge 감소
- threshold 이후 channel charge 증가율 감소

> **[비교 이미지 배치] \(N_A\)와 \(t_{ox}\) 영향**
>
> 권장 위치: 이 절의 마지막.
>
> 왼쪽: \(N_A\) 변화에 따른 표면 electron concentration.
>
> 오른쪽: \(t_{ox}\) 변화에 따른 surface potential 또는 gate charge.
>
> **현재 저장 데이터로 생성 가능**

---

# 2.4 Long-Channel MOSFET 구조

MOSFET은 MOS capacitor 양옆에 n+ source와 n+ drain을 추가한 구조로 볼 수
있다.

현재 시뮬레이션은 Gmsh로 생성한 다음 구조를 사용한다.

- Gate length: \(0.5\,\mu\mathrm{m}\)
- 전체 bulk 폭: \(1.0\,\mu\mathrm{m}\)
- Gate / Oxide / p-type Bulk
- n+ Source / n+ Drain
- Body contact

> **[이미지 C 배치] Gmsh MOSFET 전체 구조**
>
> 권장 위치: 구조 설명 바로 아래, 본문 전체 폭.
>
> 이미지 파일 생성 기준:
>
> - `long_channel_mos2d.geo`
> - `long_channel_mos2d.msh`
>
> 반드시 표시:
>
> - Gate
> - Oxide
> - Source n+
> - Drain n+
> - p-type Bulk
> - Gate length \(L_G=0.5\,\mu\mathrm{m}\)
> - Oxide/Bulk interface
>
> **현재 Gmsh mesh로 생성 가능**

구조 이미지는 potential이나 carrier field를 설명하기 전에 먼저 배치한다.
사용자가 field map에서 어느 영역을 보고 있는지 알아야 이후 그래프를
해석할 수 있기 때문이다.

---

# 2.5 Gate Voltage와 Channel 형성

MOS capacitor의 inversion layer를 source와 drain 사이로 확장하면 MOSFET
channel이 된다.

## 낮은 Gate Voltage

- p-type surface에 전자 channel이 없음
- source와 drain 사이에 높은 전위 장벽 존재
- drain current가 작음

## Threshold 부근

- gate 아래 표면 전자 농도가 증가
- source 쪽 electron distribution이 gate 아래로 확장
- source와 drain 사이의 연결이 시작됨

## 높은 Gate Voltage

- gate 아래에 연속적인 electron channel 형성
- source에서 drain으로 전자가 이동할 수 있음
- drain current 증가

> **[이미지 D 배치] Channel 형성 비교**
>
> 권장 위치: 위 세 상태 설명 직후.
>
> 동일한 색 범위를 사용하는 electron-density field map 세 장:
>
> 1. \(V_G=0\,\mathrm{V}\)
> 2. \(V_G=1\,\mathrm{V}\)
> 3. \(V_G=2\,\mathrm{V}\)
>
> Gate와 oxide가 이미지에 함께 보여야 하며, gate 아래 interface에
> channel이 형성되는 위치를 화살표로 표시한다.
>
> **현재 저장 결과로 생성 가능**

> **[Simulation에서 확인]**
>
> Long-Channel MOSFET 탭에서 field를 `Electrons`로 설정한 뒤
> \(V_G=0,0.5,1,1.5,2\,\mathrm{V}\)를 순서대로 선택한다.

---

# 2.6 Threshold Voltage

Threshold voltage는 강한 inversion channel이 형성되기 시작하는 gate
voltage이다.

이상적인 NMOS의 threshold voltage는 다음 형태로 정리할 수 있다.

\[
V_{TH}
=
V_{FB}
+2\phi_F
+\frac{\sqrt{4q\varepsilon_sN_A\phi_F}}{C_{ox}}
\]

이 식에서 중요한 것은 각 항의 물리적 의미다.

- \(V_{FB}\): gate와 silicon의 기준 전위 차이
- \(2\phi_F\): strong inversion을 위한 surface potential
- 마지막 항: depletion charge를 gate가 감당하기 위한 추가 전압

따라서:

- \(N_A\) 증가 → \(V_{TH}\) 증가
- \(t_{ox}\) 증가 → \(C_{ox}\) 감소 → \(V_{TH}\) 증가

이 관계는 프로젝트의 bulk doping 변화가 on-current에 영향을 주는 이유를
설명하는 핵심 연결점이다.

---

# 2.7 ID–VG: Gate가 Drain Current를 제어하는 방법

현재 long-channel MOSFET 시뮬레이션은
\(V_D=0.05\,\mathrm{V}\)에서 \(I_D-V_G\)를 계산한다.

그래프는 다음과 같이 읽는다.

1. 낮은 \(V_G\): channel이 없어 current가 작다.
2. threshold 부근: surface electron density가 빠르게 증가한다.
3. 높은 \(V_G\): 연속 channel이 형성되어 current가 증가한다.

Threshold 이상에서 inversion charge는 다음과 같이 근사할 수 있다.

\[
Q_{inv}
\approx
-C_{ox}(V_{GS}-V_{TH})
\]

같은 \(V_{GS}\)에서 \(V_{TH}\)가 증가하면 \(V_{GS}-V_{TH}\)가 감소한다.
따라서 inversion charge와 drain current가 감소한다.

> **[이미지 E 배치] ID–VG와 Channel 형성 연결**
>
> 권장 위치: 위 식 바로 아래.
>
> 왼쪽: \(I_D-V_G\) 로그 그래프.
>
> 오른쪽 또는 그래프 위 marker:
>
> - \(V_G=0\,\mathrm{V}\): no channel
> - \(V_G=1\,\mathrm{V}\): channel forming
> - \(V_G=2\,\mathrm{V}\): strong channel
>
> 각 marker를 이미지 D의 electron-density field map과 같은 색 또는
> 번호로 연결한다.
>
> **현재 저장 결과로 생성 가능**

---

# 2.8 ID–VD와 Long-Channel 동작 영역

Long-channel MOSFET의 동작은 linear 영역과 saturation 영역으로 나눌 수
있다.

## Linear 영역

\[
V_{DS}<V_{GS}-V_{TH}
\]

\[
I_D
=
\mu_n C_{ox}\frac{W}{L}
\left[
(V_{GS}-V_{TH})V_{DS}
-\frac{V_{DS}^2}{2}
\right]
\]

작은 \(V_{DS}\)에서는 channel이 source부터 drain까지 유지되며 MOSFET이
gate voltage로 조절되는 저항처럼 동작한다.

## Saturation 영역

\[
V_{DS}\ge V_{GS}-V_{TH}
\]

\[
I_{D,sat}
\approx
\frac{1}{2}
\mu_n C_{ox}\frac{W}{L}
(V_{GS}-V_{TH})^2
\]

Drain 쪽 channel charge가 감소하고 pinch-off가 형성된다. 이상적인
long-channel 모델에서는 이후 drain voltage 증가에 따른 current 변화가
작아진다.

> **[이미지 F 배치] ID–VD family curve**
>
> \(V_G\)별 \(I_D-V_D\) 곡선을 한 그래프에 표시한다.
>
> Linear 영역과 Saturation 영역을 배경 또는 점선으로 구분한다.
>
> **현재 저장 데이터와 GUI에서 확인 가능**

> **[이미지 G 배치] Pinch-off field map**
>
> 같은 \(V_G\)에서 낮은 \(V_D\)와 높은 \(V_D\)의 electron-density 또는
> potential field를 비교한다.
>
> Drain 쪽 channel이 얇아지는 위치를 표시한다.
>
> **현재 저장된 \(V_G,V_D\)별 electron-density field map으로 확인 가능**

---

# 2.9 시뮬레이션에서 확인할 추천 순서

## 실습 A: MOS capacitor 상태 변화

고정:

\[
N_A=10^{17}\,\mathrm{cm^{-3}},
\qquad
t_{ox}=10\,\mathrm{nm}
\]

변화:

\[
V_G=-2,-1,0,1,2\,\mathrm{V}
\]

확인:

- carrier concentration
- space charge
- potential
- energy band
- accumulation / flat-band / depletion / inversion 판정

## 실습 B: Bulk doping 영향

고정:

\[
t_{ox}=10\,\mathrm{nm},
\qquad
V_G=1\,\mathrm{V}
\]

변화:

\[
N_A=10^{16},10^{17},10^{18}\,\mathrm{cm^{-3}}
\]

확인:

- surface electron concentration
- depletion charge
- band bending
- inversion 형성 여부

## 실습 C: Oxide thickness 영향

고정:

\[
N_A=10^{17}\,\mathrm{cm^{-3}},
\qquad
V_G=1\,\mathrm{V}
\]

변화:

\[
t_{ox}=5,10,20\,\mathrm{nm}
\]

확인:

- oxide/silicon 전압 분배
- surface potential
- surface electron concentration

## 실습 D: MOSFET Channel 형성

Long-Channel MOSFET Simulation에서:

\[
V_D=0.05\,\mathrm{V}
\]

\[
V_G=0,0.5,1,1.5,2\,\mathrm{V}
\]

확인:

- gate 아래 electron-density field
- source–drain channel 연결
- \(I_D-V_G\) 변화

---

# 2.10 이 장에서 프로젝트로 가져갈 해석

이 장의 핵심 인과관계는 다음과 같다.

> Bulk doping 증가  
> → MOS capacitor의 depletion charge 증가  
> → Threshold voltage 증가  
> → 같은 \(V_{GS}\)에서 overdrive 감소  
> → Inversion charge 감소  
> → On-current 감소

PN 접합 장에서는 bulk doping 증가에 따라 공핍폭이 감소하는 현상을
확인했다. MOSFET on-current 감소를 설명할 때는 여기서 한 단계 더 나아가
gate가 감당해야 하는 depletion charge와 threshold voltage 변화를 함께
보아야 한다.

---

# 현재 시각 자료 준비 상태

| 시각 자료 | 현재 상태 | 사용 위치 |
|---|---:|---|
| MOS capacitor 구조도 | 제작 필요 | 2.1 |
| Accumulation–Inversion 비교 | 저장 데이터 있음 | 2.1 |
| \(N_A\), \(t_{ox}\) 비교 | 저장 데이터 있음 | 2.3 |
| Gmsh MOSFET 전체 구조 | Gmsh mesh 있음 | 2.4 |
| \(V_G\)별 electron field | 저장 데이터 있음 | 2.5 |
| ID–VG | 저장 데이터 있음 | 2.7 |
| ID–VD family | 저장 데이터 있음 | 2.8 |
| Pinch-off 비교 | \(V_G,V_D\)별 저장 field map 있음 | 2.8 |

---

## 한 문장 정리

MOS capacitor는 gate voltage가 silicon 표면의 전하를 바꾸는 원리를 보여주고,
long-channel MOSFET은 그 inversion charge가 source와 drain을 연결하는
channel이 되어 drain current를 만드는 과정을 보여준다.
