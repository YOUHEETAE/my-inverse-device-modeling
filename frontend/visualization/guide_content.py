from __future__ import annotations


_LEGACY_CHAPTERS = (
    ("1. App Guide", """Integrated Device Model Visualization 사용법

1. I–V Curve

• 상단에서 L, T, B, SD, LDD를 설정합니다.
• Add Curve는 현재 조건으로 새 Curve를 생성합니다.
• Update Selected는 선택한 Curve에 변경된 조건을 적용합니다.
• Curve 앞 체크 표시는 그래프에 표시할 Curve를 선택합니다.
• Analyze는 체크된 Curve의 원본 전류 배열과 추출된 전기 파라미터를 설명합니다.
• 여러 Curve를 선택하면 첫 Curve를 primary baseline으로 사용하고 모든 pair를 비교합니다.

2. Field Map

• Field comparison에서 최대 두 Curve를 선택하고 Generate All을 누릅니다.
• Field map, Scale, Range를 선택한 후 Analyze를 누릅니다.
• 해설은 현재 보고 있는 Field 화면 하나만 대상으로 합니다.
• 화면을 바꾸면 해당 Field에 저장된 해설이 다시 표시됩니다.
• 두 그림은 동일한 color scale을 사용하므로 색상과 공간적 분포를 직접 비교할 수 있습니다.

3. 해설의 성격

• I–V 해설은 전류와 전기 파라미터의 수치 비교가 중심입니다.
• Field Map 해설은 물리적 원인과 contour, 색상 영역, hotspot, 분포 폭 같은 시각적 변화가 중심입니다.
• 해설은 모델 예측 결과이며 TCAD 재계산이나 측정 검증을 대신하지 않습니다.
"""),
    ("2. MOSFET Basics", """MOSFET 기본 이론

1. Gate control

Gate voltage는 Oxide를 사이에 두고 semiconductor 표면의 Potential과 carrier density를 제어합니다. 충분한 Gate bias가 인가되면 Source와 Drain 사이에 Channel이 형성되어 Drain current가 흐릅니다.

2. Threshold voltage, Vth

Vth는 Channel이 본격적으로 형성되기 시작하는 Gate voltage의 대표값입니다. Geometry, Oxide thickness, Bulk doping, Drain bias에 따라 달라질 수 있습니다.

3. Subthreshold 영역과 SS

Vth 아래에서도 diffusion과 electrostatic coupling 때문에 작은 전류가 흐릅니다. SS는 Drain current를 한 decade 변화시키는 데 필요한 Gate voltage를 나타내며, 작을수록 Gate가 Channel을 더 급격하게 제어하는 경향을 의미합니다.

4. Short-channel effect와 DIBL

Channel이 짧아지면 Drain 전계가 Source 쪽 barrier에 더 강하게 영향을 줄 수 있습니다. DIBL은 Drain bias 증가에 따른 Vth 저하를 나타내며 short-channel electrostatics의 대표 지표입니다.

5. Linear 및 Saturation 영역

낮은 Drain bias에서는 Channel이 저항처럼 동작하는 Linear 영역이 나타납니다. Drain bias가 커지면 Drain 쪽 Channel이 pinch-off되고 전류 증가가 완만해지는 Saturation 영역으로 이동합니다. 실제 출력 곡선에는 gds와 Channel-length modulation이 남을 수 있습니다.

6. Electric field와 Potential

Electric field는 Potential의 공간 gradient로 정의됩니다: E = -∇V. Potential contour 사이의 간격이 좁을수록 같은 Potential 변화가 더 짧은 거리에서 발생하므로 강한 Electric field 경향을 의미합니다.

7. Carrier와 Current density

Electron/Hole density는 국소 carrier 농도를, Current density는 carrier 이동에 따른 전류의 공간적 경로를 나타냅니다. 높은 density가 반드시 높은 current를 의미하지는 않으며 mobility와 Electric field도 함께 작용합니다.
"""),
    ("3. Device Parameters", """Device Parameters

1. Channel length (L) [nm]

L은 Gate 아래 Source와 Drain 사이의 Channel 길이입니다.

L 증가의 일반적 경향:
• Drain이 Source barrier에 미치는 electrostatic 영향이 감소할 수 있습니다.
• Short-channel effect, DIBL, Ioff가 완화될 수 있습니다.
• Channel resistance가 증가해 Ion과 gm이 감소하고 Ron이 증가할 수 있습니다.

Field Map에서 확인할 점:
• Channel을 따라 Potential 변화가 더 긴 거리에 분포하는지
• Drain-side contour 집중이 완화되는지
• Electron 및 Current path가 길어진 Channel을 따라 어떻게 변하는지

2. Oxide thickness (T 또는 Tox) [nm]

T는 Gate와 semiconductor 사이 Oxide 두께입니다.

Tox 감소의 일반적 경향:
• Gate-to-channel electrostatic coupling이 강해집니다.
• Channel surface Potential과 carrier density 제어가 강화될 수 있습니다.
• gm, SS, short-channel control이 개선될 수 있습니다.
• Oxide 내부 Electric field와 실제 소자의 Gate leakage 부담이 커질 수 있습니다.

Field Map에서 확인할 점:
• Gate 아래 contour와 Channel surface 분포 변화
• Oxide를 가로지르는 Potential drop과 band bending
• Channel near-surface의 Electron density 영역 변화

3. Bulk doping (B) [cm⁻³]

B는 Body 또는 substrate의 기본 doping 농도입니다.

B 증가의 일반적 경향:
• Depletion width가 감소하고 Vth가 변할 수 있습니다.
• Source/Drain junction의 space-charge 분포와 Electric field가 변할 수 있습니다.
• Channel surface carrier 형성과 mobility, junction leakage에 Trade-off가 생길 수 있습니다.

Field Map에서 확인할 점:
• Bulk에서 surface 방향으로 depletion 분포가 달라지는지
• PN junction 주변 contour가 더 좁게 모이거나 넓게 퍼지는지
• Energy band의 Bulk 및 Channel bending이 어떻게 변하는지

4. Source/Drain doping (SD) [cm⁻³]

SD는 Source와 Drain 고농도 영역의 doping입니다.

SD 증가의 일반적 경향:
• Source/Drain series resistance가 감소할 수 있습니다.
• Carrier 공급과 Drive current가 증가하고 Ron이 감소할 수 있습니다.
• PN junction의 Electric field, leakage, recombination 분포가 달라질 수 있습니다.

Field Map에서 확인할 점:
• Source/Drain에서 Channel로 이어지는 carrier 및 Current path
• Junction corner의 Electric field 집중
• SRH hotspot과 고전류 영역의 위치

5. LDD doping [cm⁻³]

LDD는 Channel과 고농도 Source/Drain 사이 extension 영역의 doping입니다.

LDD 감소의 일반적 경향:
• Drain-side Potential drop을 더 넓은 공간에 분산해 peak Electric field를 완화할 수 있습니다.
• Extension resistance가 증가해 Ion과 gm이 감소하고 Ron이 증가할 수 있습니다.

LDD 증가의 일반적 경향:
• Extension resistance가 감소해 Drive current가 증가할 수 있습니다.
• Drain-side contour와 Electric field가 좁은 영역에 집중될 수 있습니다.
• Leakage와 신뢰성 측면에서 Trade-off가 발생할 수 있습니다.

Field Map에서 확인할 점:
• Drain-side LDD의 contour 간격
• 고전계 색상 영역의 폭과 hotspot 위치
• LDD를 지나는 Current path와 current crowding

해석 원칙

한 번에 하나의 Device parameter만 변경한 경우 controlled comparison으로 해석할 수 있습니다. 여러 parameter가 동시에 변경되면 시각적 변화의 원인을 하나로 단정하지 않습니다.
"""),
    ("4. I–V Curves", """I–V Curve 해석

1. Id–Vg

Gate voltage 변화에 따른 Drain current를 보여줍니다. Turn-on, Vth, SS, Ioff, Ion/Ioff, gm을 확인하는 데 사용합니다.

2. Id–Vd

Drain voltage 변화에 따른 Drain current를 보여줍니다. Linear 영역, Saturation 영역, Ron, gds, Channel-length modulation을 확인합니다.

3. 주요 전기 파라미터

• Ion: On-state drive current
• Ioff: Off-state leakage current
• Ion/Ioff: Switching dynamic range
• Vth: Channel turn-on의 대표 Gate voltage
• SS: Subthreshold gate control
• DIBL: Drain bias에 따른 Vth 변화
• gm: Gate voltage가 Drain current를 변화시키는 능력
• gds: Saturation 영역에서 Drain voltage에 대한 current 변화
• Ron: On-state resistance
• λ (CLM): Saturation 영역의 Channel-length modulation

4. 비교 원칙

첫 Curve를 primary baseline으로 사용합니다. 세 Curve라면 1→2, 1→3, 2→3을 비교합니다. Controlled comparison에서는 변경 parameter의 일반 원리와 실제 전류 변화를 연결하고, 개선과 악화가 함께 나타나면 Trade-off로 표현합니다.
"""),
    ("5. Field Maps", """Field Map 시각 해석

1. Potential

Potential contour의 길이보다 간격이 중요합니다. Contour 간격이 좁아지면 Potential gradient와 Electric field가 강해지는 경향을 눈으로 확인할 수 있습니다. Contour 위치 이동은 barrier 또는 Potential drop 위치의 이동을 의미할 수 있습니다.

2. Electric field

동일한 color scale에서 더 강한 색상은 더 큰 Field magnitude를 나타냅니다. 밝은 영역이 넓어지면 고전계 영향 범위가 확대된 것이고, 좁은 corner에 집중되면 Field crowding이 강화된 경향을 의미합니다.

3. Electron/Hole density

Log color scale에서 고농도 색상 영역의 생성, 소멸, 폭, 연결성을 봅니다. Gate 아래 Electron 영역의 확대는 inversion layer 형성 경향을, surface Hole 영역의 감소는 depletion 경향을 시각적으로 보여줄 수 있습니다.

4. Current density

Source에서 Channel을 거쳐 Drain으로 이어지는 Current path를 봅니다. 고전류 색상이 좁은 영역이나 corner에 집중되면 current crowding 경향을 의미합니다. Density 증가와 Current 증가를 동일하게 취급하지 않고 Electric field와 이동 경로를 함께 봅니다.

5. SRH recombination

강한 색상 hotspot의 위치와 공간적 범위를 봅니다. Junction 또는 interface 부근 hotspot의 확대는 해당 영역에서 recombination/generation 활동이 더 넓게 나타나는 경향을 의미합니다.

6. Energy band

Horizontal cut에서는 Source에서 Channel로 넘어가는 barrier 높이와 위치를 봅니다. Barrier가 높아지거나 낮아지는 변화는 Channel 진입 경향의 변화를 시각적으로 보여줍니다. Vertical Gate–Oxide–Bulk cut에서는 band bending 방향과 기울기 변화를 통해 Gate control과 Potential 분포 변화를 확인합니다.

Field Map 해설 원칙

• 정확한 통계값을 나열하기보다 그림에서 확인할 수 있는 contour, 색상 영역, hotspot, 분포 폭과 위치를 설명합니다.
• 내부 계산값은 시각적 판단의 근거로만 사용합니다.
• 물리적 원리와 모델에서 실제 관찰된 시각적 결과를 분리합니다.
• 동일한 color scale을 사용한 비교에서만 색상 강도를 직접 비교합니다.
"""),
)


# Application documentation stays separate from semiconductor fundamentals.
# The existing detailed device/plot chapters are retained without duplication.
GUIDE_CHAPTERS = (
    ("App Guide", _LEGACY_CHAPTERS[0][1]),
    ("Device Parameters", _LEGACY_CHAPTERS[2][1]),
    ("I–V Curves", _LEGACY_CHAPTERS[3][1]),
    ("Field Maps", _LEGACY_CHAPTERS[4][1]),
)


THEORY_CHAPTERS = (
    ("PN Junction", """PN Junction

1. Junction formation

p-type과 n-type semiconductor가 접촉하면 majority carrier가 농도 차이에 의해 서로 확산합니다. 접합 부근에는 이동 가능한 carrier가 줄어든 depletion region이 형성되고, ionized donor와 acceptor가 남아 built-in electric field를 만듭니다.

2. Equilibrium

확산하려는 carrier와 built-in electric field에 의한 drift가 평형을 이루면 순전류가 사라집니다. Energy band에서는 접합을 가로질러 band bending과 potential barrier가 형성된 모습으로 확인됩니다.

3. Bias response

Forward bias는 barrier와 depletion width를 줄여 carrier injection을 증가시킵니다. Reverse bias는 barrier와 depletion width를 키우며, junction 부근의 Electric field를 강화합니다.

4. MOSFET에서의 의미

Source/Drain과 Body는 PN junction을 형성합니다. Body doping과 Source/Drain doping 변화는 depletion 폭, junction contour 간격, peak Electric field, leakage 및 recombination 위치에 영향을 줍니다.
"""),
    ("MOS Capacitor", """MOS Capacitor

1. Structure

Metal–Oxide–Semiconductor 구조에서 Gate와 semiconductor 사이의 Oxide는 DC gate current를 차단하면서 Electric field를 통해 surface Potential을 제어합니다.

2. Accumulation, depletion, inversion

Gate bias에 따라 semiconductor 표면에는 majority carrier가 모이는 accumulation, carrier가 밀려나는 depletion, 반대 종류 carrier가 형성되는 inversion이 나타납니다. nMOS에서는 충분한 positive Gate bias가 electron inversion layer를 만듭니다.

3. Oxide thickness

Tox가 얇아지면 oxide capacitance가 증가하여 동일한 Gate voltage에서 surface에 대한 electrostatic control이 강해집니다. Field map에서는 Gate 아래 Potential contour, surface carrier 분포, vertical Energy band bending의 변화로 확인할 수 있습니다.

4. Threshold connection

Strong inversion이 시작되는 Gate voltage가 MOSFET의 Threshold voltage와 연결됩니다. Tox, Body doping, fixed charge 및 work-function 차이가 이 조건을 변화시킵니다.
"""),
    ("MOSFET Basics", """MOSFET Basics

1. Gate-controlled channel

MOSFET은 MOS capacitor의 surface control을 이용해 Source와 Drain 사이에 conductive channel을 형성합니다. nMOS에서는 Gate voltage가 증가하면서 electron inversion layer가 연결되고 Drain current가 흐릅니다.

2. Operating regions

낮은 Drain voltage에서는 channel이 저항처럼 동작하는 Linear region이 나타납니다. Drain voltage가 증가해 Drain 쪽 channel이 pinch-off되면 Saturation region으로 이동합니다.

3. Transfer and output curves

Id–Vg는 turn-on, Vth, SS, Ioff와 gm을 보여줍니다. Id–Vd는 Linear resistance, saturation current, gds와 Channel-length modulation을 보여줍니다.

4. Current formation

Drain current는 channel의 carrier density, mobility와 lateral Electric field가 함께 결정합니다. 따라서 carrier density가 높아져도 mobility 저하나 series resistance가 커지면 current가 같은 비율로 증가하지 않을 수 있습니다.
"""),
    ("Short-Channel MOSFET", """Short-Channel MOSFET

1. Loss of Gate control

Channel length가 짧아지면 Drain과 Source의 depletion region 및 Electric field가 channel 내부에 더 크게 영향을 줍니다. Gate만으로 barrier를 제어한다는 long-channel 가정이 약해집니다.

2. DIBL and Vth roll-off

높은 Drain bias가 Source-side barrier를 낮추는 현상이 DIBL입니다. Field map에서는 Drain의 Potential contour가 channel과 Source 방향으로 침투하고, Energy band에서는 source-to-channel barrier가 낮아지는 경향으로 확인됩니다.

3. Leakage and field concentration

Barrier control이 약해지면 off-state current가 증가할 수 있습니다. Drain-side junction과 LDD 부근에서는 Potential drop이 짧은 거리에 집중되어 Electric field hotspot이 강해질 수 있습니다.

4. Main trade-offs

짧은 L은 channel resistance를 줄여 drive current에 유리할 수 있지만 SS, DIBL, Ioff와 reliability에는 불리할 수 있습니다. Tox, Body doping, LDD와 junction 설계를 함께 조정해 electrostatic control과 resistance 사이의 trade-off를 다룹니다.
"""),
)
