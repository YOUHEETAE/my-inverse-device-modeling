"""Case Study 학습 콘텐츠와 조건 표기.

데스크톱 앱의 case_study/panel.py에 있던 것을 옮겨왔다. 위젯이 아니라 학습
콘텐츠이고, 이제 웹도 같은 문구를 써야 해서 두 앱이 공유하는 자리로 내렸다 —
한쪽에서 문구를 고치면 다른 쪽이 조용히 뒤처지는 걸 막는다.

panel.py는 여기서 다시 내보내므로 기존 import 경로는 그대로 동작한다.
"""

from __future__ import annotations

from typing import Any

CASE_UNDERSTANDING_GUIDES = {
    "sce_channel_length": {
        "context": (
            "MOSFET의 채널이 짧아지면 전류가 흐르는 경로뿐 아니라 Drain 전계가 "
            "Source 쪽 장벽에 미치는 영향도 달라집니다. 이 Case는 구동 성능과 "
            "꺼짐 상태 제어가 함께 어떻게 변하는지 비교합니다."
        ),
        "question": (
            "채널 길이를 줄였을 때 얻는 전류 이점과 누설·전계 제어의 손실은 "
            "어떻게 함께 나타날까?"
        ),
        "evidence": (
            "I–V Curve · Ion, Ioff와 subthreshold 구간의 변화",
            "Potential Map · Drain 영향이 Source 장벽 쪽으로 퍼지는 범위",
            "Electric Field · 채널 내부 전계의 크기와 공간 분포",
        ),
        "caution": "채널이 짧다는 이유만으로 모든 특성이 좋아진다고 단정하지 않습니다.",
    },
    "oxide_gate_control": {
        "context": (
            "Gate oxide 두께는 Gate와 channel 사이의 정전기적 결합을 좌우합니다. "
            "이 Case는 Gate 제어력의 변화가 전류 응답에 주는 이점과 누설·Oxide "
            "전계 측면에서 확인해야 할 trade-off를 함께 비교합니다."
        ),
        "question": (
            "산화막을 얇게 했을 때 Gate 제어와 I–V 응답은 어떻게 달라지며, "
            "어떤 전계·누설 변화까지 함께 확인해야 할까?"
        ),
        "evidence": (
            "I–V Curve · gm, SS와 Ioff의 변화",
            "Potential Map · Gate-to-channel 결합에 따른 전위 분포",
            "Electric Field · Oxide와 인접 영역의 전계 분포",
        ),
        "caution": "강한 Gate 제어만 보고 신뢰성이나 누설 trade-off가 없다고 단정하지 않습니다.",
    },
    "body_doping_design_window": {
        "context": (
            "Body doping은 채널 아래의 공핍 전하와 정전기적 조건을 바꾸어 Vth와 "
            "고정 bias에서의 전류를 함께 이동시킵니다. 이 Case는 누설 억제와 "
            "구동 성능 사이에서 목표에 맞는 조건을 판단하는 방법을 비교합니다."
        ),
        "question": (
            "Body doping을 높였을 때 Vth 이동은 Ion과 Ioff를 어떻게 동시에 "
            "바꾸며, 어떤 설계 목표에서 그 조건이 적절할까?"
        ),
        "evidence": (
            "I–V Curve · Vth의 가로 이동과 고정 bias의 Ion·Ioff",
            "Potential Map · Channel 표면 부근 전위 분포의 변화",
            "Electric Field · Body 전하 변화에 따른 Channel 인접 전계 재분포",
        ),
        "caution": "Vth가 높거나 Ioff가 낮다는 한 가지 사실만으로 최적 설계라고 단정하지 않습니다.",
    },
    "source_drain_on_state_conduction": {
        "context": (
            "Source와 Drain은 외부 단자와 Channel 사이에서 carrier가 출입하는 "
            "영역입니다. 이 Case는 Source/Drain doping 변화가 on-state 전류 경로와 "
            "유효 저항에 주는 이득, 그리고 Drain-side 전기적 제어에 미치는 영향을 "
            "함께 비교합니다."
        ),
        "question": (
            "Source/Drain doping을 높였을 때 on-state conduction은 어떻게 달라지며, "
            "그 이득과 함께 확인해야 할 Drain-side 전기적 비용은 무엇일까?"
        ),
        "evidence": (
            "I–V Curve · Ion, 유효 Ron과 포화영역 gds의 변화",
            "두 Drain bias의 Id–Vg · DIBL과 Drain 제어 변화",
            "Field Map · Drain-side LDD 인접 Potential과 Electric Field 재분포",
        ),
        "caution": "Ron 감소를 순수한 contact resistance 감소로 단정하거나 Ion 증가를 모든 특성의 개선으로 확장하지 않습니다.",
    },
    "ldd_field_resistance_tradeoff": {
        "context": (
            "LDD는 고농도 Drain과 Channel 사이의 전위 변화를 분산시키기 위한 "
            "영역이지만, 그 doping은 Drain-side 전계뿐 아니라 전류가 통과하는 "
            "access 경로의 저항도 바꿉니다. 이 Case는 전계 완화와 구동 손실을 "
            "같은 비교에서 판단합니다."
        ),
        "question": (
            "LDD doping을 낮춰 Drain-side 전계를 완화할 때 access resistance와 "
            "on-state 구동 성능에는 어떤 비용이 생길까?"
        ),
        "evidence": (
            "I–V Curve · Ion, gm과 유효 Ron의 변화",
            "Id–Vd 포화영역 · gds와 출력 저항 방향",
            "Field Map · Drain 인접 Potential과 Electric Field의 크기·위치 변화",
        ),
        "caution": "낮은 Field만으로 신뢰성 개선을 확정하거나 Ron 변화를 LDD 저항 하나로만 설명하지 않습니다.",
    },
    "channel_oxide_electrostatic_compensation": {
        "context": (
            "Channel Length와 Gate oxide 두께는 모두 channel의 정전기적 제어에 "
            "영향을 주지만 그 효과를 단순히 더해서 해석할 수는 없습니다. 이 Case는 "
            "Long·Short Channel과 Thick·Thin Oxide의 네 조건을 함께 비교합니다."
        ),
        "question": (
            "짧은 Channel에서 얇은 Oxide가 SS와 DIBL을 얼마나 보상하며, 그 개선은 "
            "Long-Channel 수준의 회복과 어떻게 구분해야 할까?"
        ),
        "evidence": (
            "네 I–V Curve · Long과 Short에서 Oxide 20→10 nm 효과의 차이",
            "SS·DIBL·Ioff · 제어 개선, 남은 Short-Channel Effect와 누설의 구분",
            "네 Field Map · 대응 조건끼리 비교한 Potential·Electric Field 재분포",
        ),
        "caution": "대각선 두 조건의 차이나 Field 최대값 하나로 두 파라미터의 상호작용을 확정하지 않습니다.",
    },
    "source_drain_ldd_junction_engineering": {
        "context": (
            "Source/Drain과 LDD는 단자에서 Channel로 이어지는 전류 경로와 Drain-side "
            "전위 강하를 함께 결정합니다. 이 Case는 Low·High SD와 Low·High LDD의 "
            "네 접합 조건을 대응 비교합니다."
        ),
        "question": (
            "SD와 LDD를 함께 높여 얻는 최대 구동 이득은 누설·Drain 제어·Field "
            "측면에서 어떤 비용을 만들며, 목표에 맞는 접합 조건은 어떻게 고를까?"
        ),
        "evidence": (
            "네 I–V Curve · 각 SD 수준에서 LDD 변화의 Ion·Ron 차이",
            "Ioff·DIBL·gds · 최대 구동 조건에 동반되는 Drain 제어 비용",
            "네 Field Map · 대응 LDD pair의 Drain 인접 Potential·Electric Field 변화",
        ),
        "caution": "대각선 두 접합 조건이나 최대 Ion 하나로 SD와 LDD의 효과 및 최적 조건을 확정하지 않습니다.",
    },
    "integrated_device_design": {
        "context": (
            "실제 설계에서는 한 지표의 최대값보다 여러 사양을 동시에 만족하는지가 "
            "중요합니다. 이 Case는 Drive·Leakage·Control·Balanced 네 후보를 앞선 "
            "Case에서 학습한 Curve와 Field 근거로 선별합니다."
        ),
        "question": (
            "Ion·Ioff·DIBL·SS의 네 목표를 모두 만족하는 후보는 무엇이며, 전기적 "
            "사양 통과 후 Field Map에서는 어떤 설계 여유를 추가로 확인해야 할까?"
        ),
        "evidence": (
            "후보별 파라미터 표 · 네 설계 조건과 목표 사양의 대응",
            "I–V Curve · Ion·Ioff·DIBL·SS의 절대값과 통과 여부",
            "Field Map · Balanced와 Control의 Drain 인접 분포 및 남은 공간적 비용",
        ),
        "caution": "후보 이름이나 한 지표의 우수성으로 선택하지 않고 모든 제약을 적용한 뒤 Field 근거를 별도로 검토합니다.",
    },
}
CASE_CORE_SUMMARIES = {
    "sce_channel_length": (
        "채널 길이 감소는 Ion 증가와 Ron 감소라는 구동 성능 이점을 만들 수 있습니다.",
        "동시에 Ioff, DIBL, SS 증가로 단채널 효과와 off-state 제어 열화가 나타납니다.",
        "따라서 구동 성능과 누설·전기적 제어의 trade-off를 함께 판단해야 합니다.",
    ),
    "oxide_gate_control": (
        "Gate oxide가 20 nm에서 10 nm로 얇아지면 Cox와 Gate-to-channel 결합이 커져 gm은 증가하고 SS는 감소합니다.",
        "SS는 subthreshold Curve의 기울기이고 Vth는 Curve의 가로 위치입니다. 이번 결과에서는 SS가 좋아졌어도 Vth가 낮아진 영향이 더 커 고정 off-bias의 Ioff가 증가했습니다.",
        "Field Map에서는 실제로 감소한 Drain 인접 전계를 DIBL 감소와 연결하고, Oxide 전계 부담은 같은 bias와 color scale의 Gate–Oxide–Channel 영역에서 따로 비교합니다.",
    ),
    "body_doping_design_window": (
        "Body doping이 1×10¹⁶ cm⁻³에서 5×10¹⁶ cm⁻³로 증가한 현재 결과에서 Vth는 증가하고 I–V Curve는 높은 Vg 방향으로 이동했습니다.",
        "고정 bias에서 Ioff는 크게 감소했지만 Ion도 감소했습니다. 따라서 누설 억제 이득과 구동 성능 손실을 함께 판단해야 합니다.",
        "Field Map의 Channel 표면 부근 Potential·Electric Field 변화는 Body 전하와 공핍 정전기의 변화를 보여주며, Vth·Ion·Ioff의 실제 방향과 연결해 해석합니다.",
    ),
    "source_drain_on_state_conduction": (
        "Source/Drain doping이 1×10¹⁹ cm⁻³에서 1×10²⁰ cm⁻³로 증가한 현재 결과에서 Ion은 증가하고 유효 Ron은 감소했습니다.",
        "동시에 DIBL과 gds가 증가했으므로 on-state conduction 이득과 Drain bias 민감도·포화영역 출력 저항의 비용을 분리해 판단해야 합니다.",
        "Drain-side LDD 인접 Potential·Electric Field 증가는 접합 주변 정전기 재분포를 보여주며 DIBL 방향과 연결합니다. Field 크기를 Ion 증가량으로 직접 환산하지 않습니다.",
    ),
    "ldd_field_resistance_tradeoff": (
        "LDD doping이 5×10¹⁷ cm⁻³에서 5×10¹⁸ cm⁻³로 증가한 현재 결과에서 Ion·gm은 증가하고 유효 Ron은 감소했습니다.",
        "동시에 gds와 Drain 인접 Potential·Electric Field가 증가했습니다. 따라서 낮은 LDD의 전계 완화 이득은 더 큰 access resistance와 구동 전류 손실을 동반합니다.",
        "Field Map은 낮은 LDD에서 감소한 Drain 인접 전계를 확인하는 공간 근거이며, 신뢰성 개선 자체를 확정하는 지표는 아닙니다.",
    ),
    "channel_oxide_electrostatic_compensation": (
        "L=300 nm에서 Oxide를 20 nm에서 10 nm로 얇게 하면 SS는 93.13→75.48 mV/dec, DIBL은 114.21→59.28 mV/V로 감소합니다.",
        "Oxide 두께 감소의 SS·DIBL 완화 폭은 L=700 nm보다 L=300 nm에서 더 컸습니다. 따라서 Oxide 효과는 Channel Length와 독립적이지 않고 짧은 Channel에서 보상 작용이 더 크게 나타났습니다.",
        "Short·Thin 조건도 Long·Thin보다 DIBL이 높고 Ioff가 증가했습니다. 이는 부분적 보상이지 Long-Channel 수준의 완전한 회복이나 전체 특성 개선은 아닙니다.",
    ),
    "source_drain_ldd_junction_engineering": (
        "LDD를 높이면 Low SD와 High SD 모두에서 Ion이 증가하고 유효 Ron이 감소했으며, Ion 증가율은 High SD에서 약 6.68%로 Low SD의 약 5.14%보다 컸습니다.",
        "HighSD·HighLDD는 네 조건 중 Ion이 가장 크고 Ron이 가장 작지만 Ioff와 DIBL도 가장 큽니다. 최대 구동 조건이 모든 목표의 최적 조건은 아닙니다.",
        "접합 효과는 각 SD 수준의 LowLDD→HighLDD 대응 차이로 분리하고, Drain 인접 Field를 Ion·Ron·DIBL과 교차 확인합니다.",
    ),
    "integrated_device_design": (
        "목표는 Ion≥10 mA/µm, Ioff≤0.001 mA/µm, DIBL≤30 mV/V, SS≤80 mV/dec이며 Balanced만 네 기준을 모두 만족했습니다.",
        "Drive는 Ioff·DIBL, Leakage는 Ion·SS, Control은 Ion 기준을 만족하지 못했습니다. 한 지표의 최고값은 실패한 제약을 상쇄하지 않습니다.",
        "Balanced는 전기적 사양을 통과하지만 Control보다 짧은 Channel로 DIBL과 Drain-side Field가 증가합니다. Field 검토는 통과 여부를 대신하지 않고 남은 공간적 설계 여유를 기록합니다.",
    ),
}
QUESTION_REVIEW_GUIDES = {
    "sce_pred_ion": {
        "title": "Ion 변화 예측",
        "metric_keys": ("ion",),
        "model_sections": (
            ("결과", "채널 길이가 700 nm에서 300 nm로 감소한 결과 Ion은 증가했습니다."),
            (
                "물리적 근거",
                "짧아진 전도 경로와 감소한 채널 저항 성분은 같은 bias에서 on-state 전류를 증가시킬 수 있습니다.",
            ),
            (
                "해석 범위",
                "Ion 증가는 구동 성능의 이점이지만 모든 소자 특성이 개선됐다는 뜻은 아닙니다. Ioff, DIBL, SS를 함께 확인해야 합니다.",
            ),
        ),
    },
    "sce_pred_ioff": {
        "title": "Ioff 변화 예측",
        "metric_keys": ("ioff",),
        "model_sections": (
            ("결과", "채널 길이가 700 nm에서 300 nm로 감소한 결과 Ioff는 증가했습니다."),
            (
                "물리적 근거",
                "짧은 채널에서는 Drain 전위가 Source 측 장벽에 더 강하게 영향을 주어 장벽을 낮추고 off-state carrier 주입과 누설을 증가시킬 수 있습니다.",
            ),
            (
                "결과의 의미",
                "Ioff 증가는 대기 상태의 누설과 off-state 제어 측면의 손실이며, 짧은 전도 경로가 곧 낮은 Ioff를 뜻하지는 않습니다.",
            ),
        ),
    },
    "sce_pred_dibl": {
        "title": "DIBL 변화 예측",
        "metric_keys": ("dibl",),
        "model_sections": (
            ("결과", "채널 길이가 700 nm에서 300 nm로 감소한 결과 DIBL은 증가했습니다."),
            (
                "정의와 물리적 근거",
                "DIBL은 Drain 전압 증가에 따른 문턱전압 감소량을 나타내며 단위는 mV/V입니다. 값이 클수록 Drain이 Source 측 장벽과 채널 전위에 더 강하게 영향을 줍니다. 짧은 채널에서는 Drain 전위가 Source 쪽으로 더 깊게 침투해 Source-channel 장벽을 낮춥니다.",
            ),
            (
                "결과의 의미",
                "DIBL 증가는 Gate의 정전기적 채널 제어가 약해지고 Short Channel Effect가 강해졌음을 의미합니다.",
            ),
        ),
    },
    "sce_obs_subthreshold": {
        "title": "Subthreshold 전류 증가 조건",
        "metric_keys": (),
        "model_sections": (
            ("관찰 결과", "300 nm 조건에서 subthreshold 전류가 더 이른 Vg 구간부터 증가합니다."),
            (
                "물리적 근거",
                "채널이 짧아지면 Drain 전위가 Source 측 장벽과 채널 전위에 더 강하게 영향을 줍니다. 장벽이 낮아지면서 낮은 Gate 전압에서도 전류가 증가하기 쉬워집니다.",
            ),
            (
                "결과의 의미",
                "이는 300 nm 소자의 off-state 제어가 상대적으로 약해졌음을 보여주며 증가한 Ioff와 DIBL 결과에 연결됩니다.",
            ),
            (
                "해석 시 주의점",
                "전류가 더 먼저 증가한다는 관찰만으로 SS까지 열화됐다고 판단해서는 안 됩니다. Curve의 좌우 이동과 subthreshold 기울기를 구분해 확인해야 합니다.",
            ),
        ),
    },
    "sce_obs_tradeoff": {
        "title": "단채널화에 따른 열화 항목",
        "metric_keys": ("ioff", "dibl", "ss"),
        "model_sections": (
            ("결과", "채널 길이가 700 nm에서 300 nm로 감소하면서 Ioff, DIBL, SS가 모두 증가했으므로 세 항목 모두 열화됐습니다."),
            (
                "물리적 근거",
                "채널이 짧아질수록 Drain의 전기적 영향이 Source 측 장벽까지 강하게 전달됩니다. 이에 따라 Gate의 채널 제어력이 상대적으로 약해지고 off-state 누설과 Drain 전압에 대한 문턱전압 민감도가 증가합니다.",
            ),
            (
                "항목별 의미",
                "Ioff 증가는 대기 누설 증가, DIBL 증가는 Drain에 의한 장벽 제어 증가, SS 증가는 subthreshold 영역의 Gate 제어 효율 저하를 의미합니다.",
            ),
            (
                "Trade-off",
                "Ion 증가나 Ron 감소처럼 on-state 성능은 좋아질 수 있지만 이를 소자 전체 성능의 일방적인 개선으로 볼 수는 없습니다. 구동 성능 향상과 off-state 제어 열화를 함께 판단해야 합니다.",
            ),
        ),
    },
    "sce_obs_field_coupling": {
        "title": "Field로 확인한 Drain–Source 결합",
        "metric_keys": ("ioff", "dibl"),
        "model_sections": (
            (
                "관찰 결과",
                "300 nm 조건에서는 Drain 쪽 전위 영향이 Channel을 따라 Source 장벽 방향으로 더 깊게 이어지며 Ioff와 DIBL이 함께 증가했습니다.",
            ),
            (
                "물리적 근거",
                "Channel이 짧아지면 Drain 전위가 Source–Channel 장벽까지 전달되는 거리가 줄어 Gate가 장벽을 단독으로 제어하기 어려워집니다. 낮아진 장벽은 낮은 Gate bias의 carrier 주입을 늘립니다.",
            ),
            (
                "근거 연결",
                "Potential·Electric Field는 Drain 결합의 공간적 위치를, DIBL은 Drain bias에 따른 Vth 민감도를, Ioff는 고정 off-bias 누설을 보여줍니다. 세 근거를 같은 인과 흐름으로 연결합니다.",
            ),
        ),
    },
    "oxide_pred_gm": {
        "title": "gm 변화 예측",
        "metric_keys": ("gm_max",),
        "model_sections": (
            ("결과", "Gate oxide가 20 nm에서 10 nm로 감소한 결과 gm은 증가했습니다."),
            (
                "물리적 근거",
                "얇아진 Oxide는 Cox를 키우고 Gate-to-channel 정전기적 결합을 강화합니다. 따라서 Vg 변화에 대한 Id 응답인 dId/dVg가 커질 수 있습니다.",
            ),
            (
                "해석 범위",
                "gm 증가는 Gate 구동 응답의 이점이지만 누설과 전계 부담까지 모두 개선됐다는 뜻은 아닙니다.",
            ),
        ),
    },
    "oxide_pred_ss": {
        "title": "SS 변화 예측",
        "metric_keys": ("ss",),
        "model_sections": (
            ("결과", "Gate oxide가 20 nm에서 10 nm로 감소한 결과 SS는 감소했습니다."),
            (
                "물리적 근거",
                "강해진 Gate-to-channel 결합은 subthreshold 영역에서 Gate 전압이 channel barrier를 더 효과적으로 조절하게 합니다.",
            ),
            (
                "결과의 의미",
                "더 작은 SS는 전류를 한 decade 바꾸는 데 필요한 Gate 전압이 줄었다는 뜻이며, subthreshold Gate 제어 측면의 이점입니다.",
            ),
        ),
    },
    "oxide_pred_ioff": {
        "title": "Ioff 변화 예측",
        "metric_keys": ("ioff",),
        "model_sections": (
            ("결과", "현재 모델과 고정된 조건에서 Gate oxide가 20 nm에서 10 nm로 감소한 결과 Ioff는 증가했습니다."),
            (
                "물리적 근거",
                "Ioff는 고정된 off-bias에서 읽는 전류입니다. SS 감소는 Curve를 더 가파르게 만들지만 Vth 감소는 Curve 전체를 낮은 Vg 쪽으로 옮깁니다. 이번 결과에서는 이 가로 이동의 영향이 더 커 off-bias가 상대적으로 전도 영역에 가까워졌습니다.",
            ),
            (
                "해석 범위",
                "따라서 SS 개선과 Ioff 증가는 모순이 아닙니다. 기울기는 좋아졌지만 Curve의 위치가 더 크게 이동한 결과이며, 현재 모델은 이 증가를 Oxide tunneling 전류로 분해해 보여주지는 않습니다.",
            ),
        ),
    },
    "oxide_obs_iv_gate_control": {
        "title": "I–V로 확인한 Gate 제어",
        "metric_keys": ("gm_max", "ss"),
        "model_sections": (
            ("관찰 결과", "10 nm 조건에서 gm은 증가하고 SS는 감소했습니다. 두 변화가 함께 Gate 제어 강화의 직접 근거가 됩니다."),
            (
                "물리적 근거",
                "Cox 증가로 Gate 전압이 channel charge와 barrier를 더 강하게 조절하므로 최대 dId/dVg는 커지고 subthreshold 전류 전이는 더 가팔라집니다.",
            ),
            (
                "해석 시 주의점",
                "단순한 전류 크기 차이만으로 Gate 제어를 판단하지 않고, 선형 Curve의 gm과 로그 Curve의 SS를 각각 확인해야 합니다.",
            ),
        ),
    },
    "oxide_obs_iv_tradeoff": {
        "title": "I–V에서 드러난 Trade-off",
        "metric_keys": ("gm_max", "ss", "ioff"),
        "model_sections": (
            ("관찰 결과", "10 nm 조건은 gm 증가와 SS 감소로 Gate 제어 이점을 보였지만 Ioff는 함께 증가했습니다."),
            (
                "통합 해석",
                "gm 증가는 Gate 응답, SS 감소는 subthreshold 기울기의 개선입니다. 그러나 Vth가 낮은 Vg 쪽으로 크게 이동하면 고정된 off-bias는 전도 시작점에 더 가까워집니다. 이번 Case에서는 이 위치 이동이 SS 개선 효과보다 커 Ioff가 증가했습니다.",
            ),
            (
                "해석 범위",
                "Gate 제어의 기울기와 off-state 누설은 같은 축의 좋고 나쁨이 아닙니다. 현재 결과는 Vth·SS·Ioff의 경쟁을 보여주며, 구체적인 누설 경로는 사용된 물리 모델과 전류 성분을 추가로 확인해야 구분할 수 있습니다.",
            ),
        ),
    },
    "oxide_obs_field_evidence": {
        "title": "Field Map의 올바른 비교",
        "metric_keys": (),
        "model_sections": (
            (
                "관찰 방법",
                "현재 Drain 인접 Electric Field 감소는 DIBL 감소와 같은 방향의 공간 근거로 읽을 수 있습니다. Oxide 전계 부담은 20 nm와 10 nm 결과의 bias와 color scale을 맞춘 뒤 Gate–Oxide–Channel 인접 영역에서 따로 비교합니다.",
            ),
            (
                "물리적 근거",
                "Drain 쪽 전계와 DIBL은 Drain이 channel barrier에 미치는 영향에 가깝고, Gate–Oxide 경계의 전계는 절연막에 걸리는 국부 부담에 가깝습니다. 두 위치를 나누면 Gate 제어 개선과 Oxide 신뢰성 검토를 같은 결론으로 섞지 않을 수 있습니다.",
            ),
            (
                "해석 범위",
                "따라서 이번 Field 결과는 Drain-side 제어 개선을 뒷받침하지만 Oxide 내부 전계의 정량 결론까지 대신하지는 않습니다. Oxide 영역의 분포와 재료 한계가 추가되면 신뢰성 해석으로 확장할 수 있습니다.",
            ),
        ),
    },
    "body_pred_vth": {
        "title": "Vth 변화 예측",
        "metric_keys": ("vth_low", "vth_high"),
        "model_sections": (
            ("결과", "Body doping이 1×10¹⁶ cm⁻³에서 5×10¹⁶ cm⁻³로 증가한 결과 두 Drain bias에서 추출한 Vth가 모두 증가했습니다."),
            (
                "물리적 근거",
                "더 높은 Body doping은 공핍영역의 이온화 전하와 표면 전위를 바꾸므로 inversion channel을 형성하기 위해 더 큰 Gate bias가 필요할 수 있습니다.",
            ),
            (
                "해석 범위",
                "Vth 증가는 Curve가 높은 Vg 쪽으로 이동했다는 뜻입니다. 목표 Vth와 공급 전압을 정하지 않은 상태에서는 증가 자체를 일방적인 개선으로 판단하지 않습니다.",
            ),
        ),
    },
    "body_pred_ioff": {
        "title": "Ioff 변화 예측",
        "metric_keys": ("ioff",),
        "model_sections": (
            ("결과", "현재 모델의 고정 off-state bias에서 Body doping 증가 후 Ioff는 감소했습니다."),
            (
                "물리적 근거",
                "높아진 Vth로 Id–Vg Curve가 높은 Vg 쪽으로 이동하면서 동일한 off bias가 전도 시작점에서 더 멀어졌고 subthreshold 전류가 감소했습니다.",
            ),
            (
                "해석 범위",
                "이번 Ioff 감소는 현재 구조와 bias에서 확인된 결과입니다. SS, 접합 누설과 다른 구조 효과를 분리하지 않은 채 모든 조건의 보편적인 결론으로 확장하지 않습니다.",
            ),
        ),
    },
    "body_pred_ion": {
        "title": "Ion 변화 예측",
        "metric_keys": ("ion",),
        "model_sections": (
            ("결과", "현재 모델의 고정 on-state bias에서 Body doping 증가 후 Ion은 감소했습니다."),
            (
                "물리적 근거",
                "Vth가 높아지면 같은 Gate bias에서 사용할 수 있는 overdrive가 줄어 inversion charge와 구동 전류가 감소할 수 있습니다.",
            ),
            (
                "결과의 의미",
                "누설 감소와 동시에 발생한 구동 전류 손실입니다. 따라서 Ioff만 보지 않고 목표 속도와 전력 조건에서 Ion을 함께 판단해야 합니다.",
            ),
        ),
    },
    "body_obs_iv_shift": {
        "title": "Vth 이동과 Ioff의 연결",
        "metric_keys": ("vth_low", "vth_high", "ioff"),
        "model_sections": (
            ("관찰 결과", "5×10¹⁶ cm⁻³ 조건은 두 Drain bias에서 Vth가 증가했고 고정 off bias의 Ioff가 감소했습니다."),
            (
                "Curve 근거",
                "동일한 전류 기준과 축에서 Id–Vg Curve의 교차점이 높은 Vg 쪽으로 이동합니다. 이 가로 이동 때문에 동일한 off bias가 turn-on 지점에서 더 멀어집니다.",
            ),
            (
                "해석 시 주의점",
                "Vth는 Curve 위치이고 SS는 subthreshold 기울기입니다. 이번 결과에서 SS는 오히려 증가했으므로 Ioff 감소를 SS 개선으로 설명하지 않습니다.",
            ),
        ),
    },
    "body_obs_iv_tradeoff": {
        "title": "누설–구동 설계 균형",
        "metric_keys": ("ion", "ioff", "ion_ioff_ratio"),
        "model_sections": (
            ("관찰 결과", "Body doping 증가 후 Ion과 Ioff가 모두 감소했지만 Ioff의 상대 감소폭이 더 커 Ion/Ioff ratio는 증가했습니다."),
            (
                "설계 해석",
                "낮은 Ioff와 큰 Ion/Ioff ratio는 저전력·off-state 분리에 유리하지만, 감소한 Ion은 on-state 구동 성능의 비용입니다. 어느 조건이 적합한지는 허용 누설과 요구 성능으로 결정합니다.",
            ),
            (
                "판단 경계",
                "비율 하나가 커졌다는 이유로 모든 bias와 회로 목표에서 우수하다고 결론내리지 않습니다. 절대 Ion, Ioff와 목표 Vth를 함께 봅니다.",
            ),
        ),
    },
    "body_obs_field_evidence": {
        "title": "Field로 확인한 Body 정전기",
        "metric_keys": ("vth_low", "ion", "ioff"),
        "model_sections": (
            (
                "관찰 결과",
                "5×10¹⁶ cm⁻³ 조건에서 Channel 표면 부근 Potential과 Electric Field가 증가했고, 동시에 Vth 증가와 Ion·Ioff 감소가 확인됐습니다.",
            ),
            (
                "물리적 연결",
                "높아진 Body doping은 공핍영역의 고정 전하와 Channel 인접 정전기 분포를 바꿉니다. 이 공간 변화는 inversion에 필요한 Gate bias가 커지고 고정 bias 전류가 감소한 결과와 같은 물리적 흐름을 이룹니다.",
            ),
            (
                "해석 방법",
                "두 조건을 같은 bias와 color scale에서 비교한 뒤 Channel 인접 분포의 위치와 방향을 Vth·Ion·Ioff에 교차 연결합니다. Field 크기 하나를 곧바로 구동 전류의 크기로 치환하지 않습니다.",
            ),
        ),
    },
    "sd_pred_ion": {
        "title": "Ion 변화 예측",
        "metric_keys": ("ion",),
        "model_sections": (
            ("결과", "Source/Drain doping이 1×10¹⁹ cm⁻³에서 1×10²⁰ cm⁻³로 증가한 결과 Ion은 증가했습니다."),
            (
                "물리적 근거",
                "Source/Drain과 인접 접근영역의 전도 조건이 달라지면 단자에서 Channel로 이어지는 전류 경로의 유효 저항 성분이 변할 수 있습니다. 현재 결과에서는 같은 on bias의 전류가 증가했습니다.",
            ),
            (
                "해석 범위",
                "Ion 증가는 현재 on-state 구동 이득이지만 이동도 자체의 증가를 직접 입증하지는 않습니다. Ron과 Drain-side 제어 지표를 함께 확인합니다.",
            ),
        ),
    },
    "sd_pred_ron": {
        "title": "유효 Ron 변화 예측",
        "metric_keys": ("ron",),
        "model_sections": (
            ("결과", "동일한 on-state 추출 조건에서 Source/Drain doping 증가 후 유효 Ron은 감소했습니다."),
            (
                "물리적 근거",
                "더 높은 Source/Drain doping은 단자와 Channel 사이 전류 경로의 전도 조건을 바꾸며, 현재 Curve에서는 낮은 Vd의 on-state 기울기가 커져 유효 저항이 감소했습니다.",
            ),
            (
                "해석 범위",
                "여기서 Ron은 접촉저항만이 아니라 Channel과 Source/Drain 접근영역을 포함한 유효 on-state 저항입니다. 한 성분의 변화로 단정하지 않습니다.",
            ),
        ),
    },
    "sd_pred_dibl": {
        "title": "DIBL 변화 예측",
        "metric_keys": ("dibl",),
        "model_sections": (
            ("결과", "현재 모델에서 Source/Drain doping 증가 후 DIBL은 증가했습니다."),
            (
                "물리적 근거",
                "Source/Drain 접합과 인접 공핍·전위 분포가 달라지면서 높은 Drain bias가 Channel 장벽에 전달되는 정도도 변할 수 있습니다. 두 Drain bias의 Vth 간격이 커진 결과가 DIBL 증가로 추출됐습니다.",
            ),
            (
                "결과의 의미",
                "DIBL 증가는 Drain bias에 대한 장벽 민감도가 커졌다는 뜻입니다. Ion 증가와 Ron 감소의 on-state 이득과 다른 평가 축입니다.",
            ),
        ),
    },
    "sd_obs_iv_conduction": {
        "title": "I–V로 확인한 On-State Conduction",
        "metric_keys": ("ion", "ron"),
        "model_sections": (
            ("관찰 결과", "1×10²⁰ cm⁻³ 조건에서 Ion은 증가하고 유효 Ron은 감소했습니다. 두 결과가 on-state conduction 강화의 직접 근거입니다."),
            (
                "Curve 근거",
                "정의된 on bias의 Drain 전류와 낮은 Vd on-state Id–Vd 기울기를 각각 비교하면 더 큰 Ion과 더 작은 Ron을 확인할 수 있습니다.",
            ),
            (
                "해석 시 주의점",
                "Field 최대값이나 DIBL은 on-state conduction을 직접 측정한 지표가 아닙니다. 또한 Ron을 순수 contact resistance로 축소하지 않습니다.",
            ),
        ),
    },
    "sd_obs_iv_tradeoff": {
        "title": "구동 이득과 Drain 제어의 Trade-off",
        "metric_keys": ("ion", "ron", "dibl", "gds"),
        "model_sections": (
            ("관찰 결과", "Source/Drain doping 증가 후 Ion 증가·Ron 감소와 함께 DIBL·gds 증가가 나타났습니다."),
            (
                "통합 해석",
                "Ion과 Ron은 on-state 전류 전달과 유효 저항을 보여줍니다. DIBL은 Drain bias에 따른 장벽 이동, gds는 Drain 전압에 대한 포화영역 전류 민감도를 나타냅니다. 따라서 구동 이득과 Drain 제어 비용을 분리해 평가합니다.",
            ),
            (
                "설계 의미",
                "낮은 Ron과 큰 Ion이 필요한 설계에는 이점이 있지만, 작은 DIBL과 높은 출력 저항이 중요한 설계에서는 증가한 DIBL·gds가 비용이 될 수 있습니다.",
            ),
        ),
    },
    "sd_obs_field_evidence": {
        "title": "Field로 확인한 Drain-Side 변화",
        "metric_keys": ("dibl",),
        "model_sections": (
            (
                "관찰 결과",
                "1×10²⁰ cm⁻³ 조건에서 Drain-side LDD 인접 Potential과 Electric Field가 증가했고 DIBL도 증가했습니다.",
            ),
            (
                "물리적 연결",
                "Source/Drain doping 변화는 Drain 접합과 인접 공핍·전위 분포를 바꿀 수 있습니다. 현재 공간 변화는 Drain bias가 Channel 장벽에 더 크게 반영된 DIBL 증가와 같은 흐름의 근거입니다.",
            ),
            (
                "해석 방법",
                "같은 bias와 color scale에서 Drain-side 인접 분포의 위치와 방향을 비교하고 DIBL과 교차 확인합니다. Field 크기를 Ion 증가량으로 환산하거나 hotspot 하나로 breakdown을 확정하지 않습니다.",
            ),
        ),
    },
    "ldd_pred_ion": {
        "title": "Ion 변화 예측",
        "metric_keys": ("ion",),
        "model_sections": (
            ("결과", "LDD doping이 5×10¹⁷ cm⁻³에서 5×10¹⁸ cm⁻³로 증가한 결과 Ion은 증가했습니다."),
            (
                "물리적 근거",
                "높아진 LDD doping은 Channel과 고농도 Drain 사이 access 경로의 전도 조건을 바꾸고 유효 저항 성분을 줄일 수 있습니다. 현재 결과에서는 같은 on bias의 전류가 증가했습니다.",
            ),
            (
                "해석 범위",
                "Ion 증가는 구동 이득이지만 Drain-side Field까지 완화됐다는 뜻은 아닙니다. Ron과 Field 분포를 함께 확인합니다.",
            ),
        ),
    },
    "ldd_pred_ron": {
        "title": "유효 Ron 변화 예측",
        "metric_keys": ("ron",),
        "model_sections": (
            ("결과", "동일한 on-state 추출 조건에서 LDD doping 증가 후 유효 Ron은 감소했습니다."),
            (
                "물리적 근거",
                "더 높은 LDD doping은 access 영역의 전도성을 높일 수 있으며, 현재 Id–Vd에서는 낮은 Vd on-state 기울기가 커져 유효 Ron이 감소했습니다.",
            ),
            (
                "해석 범위",
                "추출된 Ron에는 Channel과 Source/Drain을 포함한 전체 전류 경로가 반영됩니다. 감소량을 LDD 영역 저항 하나의 정량 변화로 간주하지 않습니다.",
            ),
        ),
    },
    "ldd_pred_drain_field": {
        "title": "Drain 인접 Field 변화 예측",
        "metric_keys": (),
        "model_sections": (
            ("결과", "같은 bias에서 LDD doping 증가 후 Drain 인접 Electric Field와 hotspot 크기는 증가했습니다."),
            (
                "물리적 근거",
                "낮은 doping의 LDD 영역은 Drain 전위가 Channel 방향으로 변하는 구간을 완화하는 역할을 할 수 있습니다. doping이 높아지면 이 완화가 줄어 Drain 인접 전계가 더 집중될 수 있습니다.",
            ),
            (
                "결과의 의미",
                "반대로 낮은 LDD 조건은 현재 Field를 완화하지만 access resistance 증가와 Ion 감소를 동반합니다. Field 감소만으로 breakdown이나 수명을 확정하지 않습니다.",
            ),
        ),
    },
    "ldd_obs_iv_conduction": {
        "title": "I–V로 확인한 Access Conduction",
        "metric_keys": ("ion", "ron"),
        "model_sections": (
            ("관찰 결과", "5×10¹⁸ cm⁻³ 조건에서 Ion은 증가하고 유효 Ron은 감소했습니다. 두 결과가 access conduction 강화의 직접 근거입니다."),
            (
                "Curve 근거",
                "정의된 on bias의 Drain 전류와 낮은 Vd on-state Id–Vd 기울기를 각각 비교하면 더 큰 Ion과 더 작은 Ron을 확인할 수 있습니다.",
            ),
            (
                "해석 시 주의점",
                "gm 증가는 Gate 입력에 대한 전류 응답이고 Field 증가는 공간적 전계 변화입니다. Ion·Ron과 관련은 있지만 같은 지표로 대체하지 않습니다.",
            ),
        ),
    },
    "ldd_obs_iv_tradeoff": {
        "title": "구동 이득과 출력 특성의 Trade-off",
        "metric_keys": ("ion", "gm_max", "ron", "gds"),
        "model_sections": (
            ("관찰 결과", "높은 LDD 조건에서 Ion·gm은 증가하고 Ron은 감소했지만 gds도 증가했습니다."),
            (
                "통합 해석",
                "Ion과 Ron은 on-state 전류 전달, gm은 Gate 입력에 대한 전류 응답을 보여줍니다. gds 증가는 포화영역에서 Drain 전압에 대한 전류 민감도가 커져 출력 저항이 낮아지는 방향입니다.",
            ),
            (
                "설계 의미",
                "구동과 Gate 응답에는 이점이지만 높은 출력 저항이 필요한 동작에서는 gds 증가가 비용입니다. gds를 Ion과 같은 종류의 이득으로 합치지 않습니다.",
            ),
        ),
    },
    "ldd_obs_field_tradeoff": {
        "title": "Drain Field–Resistance Trade-off",
        "metric_keys": ("ion", "ron"),
        "model_sections": (
            (
                "관찰 결과",
                "5×10¹⁸ cm⁻³ 조건은 Drain 인접 Potential·Electric Field가 더 크고, 5×10¹⁷ cm⁻³ 조건은 Ion이 더 작고 Ron이 더 큽니다.",
            ),
            (
                "물리적 연결",
                "낮은 LDD doping은 Drain 전위 변화와 국부 전계를 완화하는 대신 access 영역의 전도성을 낮춰 유효 저항을 키우고 on-state 전류를 줄일 수 있습니다.",
            ),
            (
                "판단 범위",
                "같은 bias와 color scale에서 Drain 인접 영역을 비교해 Field 방향을 확인합니다. 낮은 Field는 공간적 완화의 근거이지만 breakdown·hot-carrier 수명 개선의 정량 결론은 아닙니다.",
            ),
        ),
    },
    "comp_pred_ss": {
        "title": "Short-Channel에서 SS 변화 예측",
        "metric_keys": ("ss",),
        "model_sections": (
            ("결과", "L=300 nm에서 Oxide를 20 nm에서 10 nm로 줄인 결과 SS는 93.13 mV/dec에서 75.48 mV/dec로 감소했습니다."),
            ("물리적 근거", "얇은 Oxide는 Gate-to-channel 결합을 강화해 짧은 Channel에서도 subthreshold barrier를 더 효율적으로 제어할 수 있습니다."),
            ("해석 범위", "SS 감소는 Gate 제어의 개선 근거이지만 Ioff 감소나 Short-Channel Effect의 완전한 제거를 뜻하지 않습니다."),
        ),
    },
    "comp_pred_dibl": {
        "title": "Short-Channel에서 DIBL 변화 예측",
        "metric_keys": ("dibl",),
        "model_sections": (
            ("결과", "L=300 nm에서 Oxide를 20 nm에서 10 nm로 줄인 결과 DIBL은 114.21 mV/V에서 59.28 mV/V로 감소했습니다."),
            ("물리적 근거", "강해진 Gate coupling은 Drain bias가 channel barrier에 미치는 상대적 영향을 줄이는 방향으로 작용합니다."),
            ("해석 범위", "DIBL은 크게 완화됐지만 Long·Thin 조건의 13.62 mV/V보다 여전히 높아 완전한 회복은 아닙니다."),
        ),
    },
    "comp_pred_recovery": {
        "title": "Long-Channel 수준 회복 예측",
        "metric_keys": ("ss", "dibl"),
        "model_sections": (
            ("결과", "Short·Thin의 SS와 DIBL은 Short·Thick보다 개선됐지만 DIBL은 Long·Thin보다 높은 수준에 남았습니다."),
            ("비교 근거", "회복 여부는 Short 조건 내부의 개선뿐 아니라 동일한 Thin Oxide를 사용한 Long·Thin 기준과의 잔여 차이까지 확인해야 합니다."),
            ("결론", "얇은 Oxide는 Short-Channel Effect를 부분적으로 보상하지만 Channel Length 자체의 영향을 제거하지는 못했습니다."),
        ),
    },
    "comp_obs_iv_interaction": {
        "title": "Oxide 효과의 Channel-Length 의존성",
        "metric_keys": ("ss", "dibl"),
        "model_sections": (
            ("관찰 결과", "T 20→10 nm에서 SS 감소 폭은 Long에서 약 8.05, Short에서 약 17.65 mV/dec였고 DIBL 감소 폭은 각각 약 11.21, 54.94 mV/V였습니다."),
            ("상호작용 해석", "같은 Oxide 변화의 효과가 Channel Length에 따라 달랐으므로 두 파라미터는 현재 결과에서 독립적인 고정 효과로 나타나지 않았습니다."),
            ("비교 방법", "Long·Thick→Long·Thin과 Short·Thick→Short·Thin의 두 대응 차이를 비교해야 하며 대각선 조건 하나로 상호작용을 판단하지 않습니다."),
        ),
    },
    "comp_obs_iv_boundary": {
        "title": "보상 효과와 남은 한계",
        "metric_keys": ("ss", "dibl", "ioff"),
        "model_sections": (
            ("관찰 결과", "Short·Thin은 Short·Thick보다 SS·DIBL이 감소했지만 Ioff는 증가했고 DIBL은 Long·Thin보다 높았습니다."),
            ("통합 해석", "Gate 제어 개선, 남아 있는 Drain coupling, 고정 off-bias의 누설은 서로 다른 결과이므로 한 지표로 전체 회복을 선언할 수 없습니다."),
            ("설계 의미", "얇은 Oxide는 짧은 Channel의 정전기적 열화를 완화하는 수단이지만 목표 Ioff와 DIBL을 동시에 충족하는지는 별도로 판단해야 합니다."),
        ),
    },
    "comp_obs_field_pairing": {
        "title": "2×2 Field Map 대응 비교",
        "metric_keys": ("dibl",),
        "model_sections": (
            ("관찰 방법", "같은 bias와 color scale에서 Long의 Thick→Thin 변화와 Short의 Thick→Thin 변화를 각각 확인한 뒤 공간 변화의 크기와 위치를 비교합니다."),
            ("물리적 연결", "Channel–Drain 방향의 Potential·Electric Field 재분포를 SS·DIBL 변화와 교차 확인하면 Oxide 보상 효과가 Channel Length에 따라 달라지는 근거를 얻을 수 있습니다."),
            ("해석 경계", "global Field 최대값이나 대각선 두 조건의 차이는 L과 T의 효과를 분리하지 못하므로 상호작용의 단독 근거로 사용하지 않습니다."),
        ),
    },
    "junction_pred_ion": {
        "title": "High SD에서 Ion 변화 예측", "metric_keys": ("ion",),
        "model_sections": (
            ("결과", "High SD에서 LDD를 5×10¹⁷→5×10¹⁸ cm⁻³로 높이면 Ion은 2.9795→3.1786 mA/µm로 증가했습니다."),
            ("물리적 근거", "높은 LDD는 Channel–Drain access 경로의 전도성을 높이며 High SD의 단자 전도 조건과 함께 구동 전류를 키웠습니다."),
            ("해석 범위", "Ion 증가는 구동 이득이지만 Ioff·DIBL·Field 비용까지 개선됐다는 뜻은 아닙니다."),
        ),
    },
    "junction_pred_ron": {
        "title": "High SD에서 유효 Ron 변화 예측", "metric_keys": ("ron",),
        "model_sections": (
            ("결과", "High SD에서 LDD 증가 후 유효 Ron은 0.53536→0.49495 kΩ·µm로 감소했습니다."),
            ("물리적 근거", "access 영역의 전도 개선으로 낮은 Vd on-state 기울기가 커져 전체 전류 경로의 유효 Ron이 감소했습니다."),
            ("해석 범위", "유효 Ron은 SD 저항과 LDD 저항의 단순 합이나 개별 영역 저항의 직접 측정값이 아닙니다."),
        ),
    },
    "junction_pred_best_drive": {
        "title": "최대 구동 접합 조건 예측", "metric_keys": ("ion", "ron"),
        "model_sections": (
            ("결과", "HighSD·HighLDD가 네 조건 중 가장 큰 Ion과 가장 작은 유효 Ron을 보였습니다."),
            ("비교 근거", "SD와 LDD가 모두 높은 조건에서 단자–Channel과 access 경로의 전도 이득이 함께 나타났습니다."),
            ("판단 범위", "최대 구동 조건은 Ioff와 DIBL도 가장 컸으므로 목표와 무관한 보편적 최적 조건은 아닙니다."),
        ),
    },
    "junction_obs_iv_interaction": {
        "title": "SD 수준에 따른 LDD 구동 효과", "metric_keys": ("ion", "ron"),
        "model_sections": (
            ("관찰 결과", "LDD 증가의 Ion 증가율은 Low SD에서 약 5.14%, High SD에서 약 6.68%였습니다."),
            ("상호작용 해석", "두 SD 수준 모두 LDD 이득이 나타났지만 크기는 같지 않아 현재 결과에서 SD와 LDD 효과를 고정된 독립 효과로 볼 수 없습니다."),
            ("비교 방법", "각 SD 수준의 LowLDD→HighLDD 대응 차이를 비교하며 대각선 조건으로 두 효과를 분리하지 않습니다."),
        ),
    },
    "junction_obs_iv_tradeoff": {
        "title": "최대 구동과 Drain 제어 Trade-off", "metric_keys": ("ion", "ron", "ioff", "dibl"),
        "model_sections": (
            ("관찰 결과", "HighSD·HighLDD는 Ion 3.1786 mA/µm, Ron 0.49495 kΩ·µm로 구동 지표가 가장 좋지만 Ioff와 DIBL도 네 조건 중 가장 큽니다."),
            ("통합 해석", "Ion·Ron은 on-state 전달을, Ioff·DIBL은 off-state 누설과 Drain 장벽 제어를 나타내므로 서로 다른 설계 축입니다."),
            ("설계 의미", "최대 구동이 필요한 경우 이점이 있지만 누설·DIBL 제한이 엄격하면 다른 접합 조건이 더 적합할 수 있습니다."),
        ),
    },
    "junction_obs_field_pairs": {
        "title": "접합 Field의 대응 비교", "metric_keys": ("ion", "ron", "dibl"),
        "model_sections": (
            ("관찰 방법", "Low SD와 High SD에서 각각 LowLDD→HighLDD의 Drain 인접 Potential·Electric Field 변화를 같은 bias와 color scale로 비교합니다."),
            ("물리적 연결", "공간 분포를 Ion·Ron의 access conduction과 DIBL의 Drain coupling 변화에 교차 연결합니다."),
            ("해석 경계", "global hotspot 순위나 Ron 변화량은 네 접합 조건의 전체 성능 또는 Field 변화량을 대신하지 않습니다."),
        ),
    },
    "design_pred_highest_ion": {
        "title": "최대 Ion 후보 예측", "metric_keys": ("ion",),
        "model_sections": (
            ("결과", "Drive 후보가 19.226 mA/µm로 가장 큰 Ion을 보였습니다."),
            ("조건 근거", "짧은 Channel, 얇은 Oxide, 낮은 Body doping과 높은 SD·LDD가 구동 전류를 크게 만드는 방향으로 조합됐습니다."),
            ("해석 범위", "Drive는 Ioff와 DIBL 목표를 초과하므로 최대 Ion이 통합 설계의 자동 선택 근거는 아닙니다."),
        ),
    },
    "design_pred_lowest_ioff": {
        "title": "최소 Ioff 후보 예측", "metric_keys": ("ioff",),
        "model_sections": (
            ("결과", "Leakage 후보가 1.564×10⁻⁸ mA/µm로 가장 작은 Ioff를 보였습니다."),
            ("조건 근거", "긴 Channel, 두꺼운 Oxide, 높은 Body doping과 낮은 SD·LDD 조건이 누설 억제 방향으로 조합됐습니다."),
            ("해석 범위", "Leakage는 Ion과 SS 목표를 만족하지 못하므로 최소 Ioff 하나로 선택할 수 없습니다."),
        ),
    },
    "design_pred_target_choice": {
        "title": "목표 사양 통과 후보 예측", "metric_keys": ("ion", "ioff", "dibl", "ss"),
        "model_sections": (
            ("결과", "Balanced만 Ion·Ioff·DIBL·SS의 네 목표를 모두 만족했습니다."),
            ("선별 원칙", "모든 제약은 동시에 적용하며 한 지표의 큰 여유가 다른 지표의 실패를 상쇄하지 않습니다."),
            ("설계 의미", "Balanced는 각 지표의 절대 최고 후보가 아니라 현재 목표 집합의 feasible candidate입니다."),
        ),
    },
    "design_obs_constraint_filter": {
        "title": "동시 제약을 이용한 후보 선별", "metric_keys": ("ion", "ioff", "dibl", "ss"),
        "model_sections": (
            ("관찰 결과", "Balanced는 Ion 12.982, Ioff 0.0006135, DIBL 22.67, SS 76.30으로 네 기준을 모두 통과했습니다."),
            ("판단 방법", "후보별 실제 값을 각 상·하한과 대조해 하나라도 실패하면 해당 목표 집합에서는 제외합니다."),
            ("결론", "현재 목표에서는 Balanced가 유일한 통과 후보이며 목표가 바뀌면 선택도 달라질 수 있습니다."),
        ),
    },
    "design_obs_rejection_reasons": {
        "title": "탈락 후보의 미달 사유", "metric_keys": (),
        "model_sections": (
            ("Drive", "Ioff 0.08003 mA/µm와 DIBL 70.03 mV/V로 두 상한을 초과했습니다."),
            ("Leakage", "Ion 1.8549 mA/µm로 하한에 미달하고 SS 92.63 mV/dec로 상한을 초과했습니다."),
            ("Control", "Ioff·DIBL·SS는 통과했지만 Ion 4.8972 mA/µm로 구동 전류 하한에 미달했습니다."),
        ),
    },
    "design_obs_field_margin": {
        "title": "전기적 통과 후 Field 설계 여유", "metric_keys": ("dibl",),
        "model_sections": (
            ("관찰 결과", "Balanced는 Control보다 Channel이 짧아 DIBL이 6.12→22.67 mV/V로 증가하고 Drain-side Field도 커졌지만 현재 DIBL 상한은 만족했습니다."),
            ("Field 역할", "같은 bias와 color scale에서 Drain 인접 분포의 증가 위치와 범위를 확인해 통과 후 남은 electrostatic margin을 기록합니다."),
            ("판단 경계", "전기적 사양 통과가 Field·신뢰성의 자동 통과를 뜻하지 않으며 Field Map도 정량 사양 검사를 대체하지 않습니다."),
        ),
    },
}
MODEL_ANSWER_SECTION_TITLES = {
    "현재 Case의 핵심 메커니즘": "현재 Case의 핵심 메커니즘",
    "전기적 파라미터별 변화와 원인": "전기적 파라미터별 변화와 원인",
    "현재 Case의 I–V 근거": "I–V Curve에서 확인된 근거",
    "현재 Case의 Field Map 근거": "Field Map에서 확인된 근거",
    "Curve–파라미터–Field 통합 해석": "Curve–파라미터–Field 통합 해석",
    "Trade-off와 해석 한계": "성능 Trade-off와 해석 한계",
    "일반 해석 원칙": "다른 Case에도 적용할 해석 원칙",
}
CONCEPT_FEEDBACK_LABELS = {
    "ion_can_increase": "채널 길이 감소에 따른 Ion 증가",
    "ioff_increases": "단채널화에 따른 Ioff 증가",
    "vth_decreases": "단채널화에 따른 Vth 감소",
    "dibl_increases": "단채널화에 따른 DIBL 증가",
    "ss_increases": "단채널화에 따른 SS 증가",
    "drain_field_affects_source_barrier": "Drain 전위와 Source 측 장벽의 결합",
    "shorter_channel_improves_everything": "짧은 채널이 모든 특성을 개선한다는 해석",
    "shorter_path_always_reduces_off_current": "짧은 전도 경로가 Ioff도 낮춘다는 해석",
    "dibl_is_only_a_curve_shift_without_physical_cause": "DIBL을 물리적 원인 없는 Curve 이동으로만 보는 해석",
    "vth_decrease_is_inherently_worse": "목표값과 무관하게 Vth 감소를 곧바로 열화로 보는 해석",
    "thinner_oxide_strengthens_gate_control": "얇은 Oxide에 따른 Gate 제어력 강화",
    "gm_can_increase": "Gate 제어력 강화에 따른 gm 증가",
    "ss_can_decrease": "Gate 제어력 강화에 따른 SS 감소",
    "oxide_field_distribution_requires_check": "Oxide 및 인접 영역의 전계 분포 확인",
    "ioff_increases_in_current_result": "현재 결과에서 확인된 Ioff 증가",
    "gate_control_reliability_tradeoff": "Gate 제어와 누설·전계의 Trade-off",
    "thinner_oxide_only_changes_current": "얇은 Oxide가 전류만 바꾼다는 해석",
    "stronger_gate_control_has_no_tradeoff": "강한 Gate 제어에는 Trade-off가 없다는 해석",
    "field_hotspot_alone_proves_breakdown": "Field hotspot만으로 breakdown을 확정하는 해석",
    "ioff_increase_proves_oxide_tunneling": "Ioff 증가만으로 Oxide tunneling을 확정하는 해석",
    "field_peak_alone_proves_gate_control": "Field 최대값만으로 Gate 제어 개선을 확정하는 해석",
    "field_map_alone_proves_overall_tradeoff": "Field Map만으로 전체 Trade-off를 판단하는 해석",
    "ss_improvement_guarantees_lower_ioff": "SS 개선이 항상 Ioff 감소를 보장한다는 해석",
    "dibl_improvement_explains_away_ioff": "DIBL 개선을 근거로 Ioff 증가를 유효하지 않다고 보는 해석",
    "ioff_increase_is_gate_control_benefit": "Ioff 증가를 Gate 제어의 성능 이득으로 보는 해석",
    "drain_field_represents_oxide_stress": "Drain 인접 전계를 Oxide 전계 부담과 동일시하는 해석",
    "potential_shift_quantifies_oxide_field": "Potential과 Vth 변화로 Oxide 전계를 정량화하는 해석",
    "electrical_improvement_settles_field_tradeoff": "전기적 지표 개선을 Field 부담 개선으로 그대로 확장하는 해석",
    "body_doping_raises_vth_in_current_result": "현재 Body doping 비교에서 확인된 Vth 증가",
    "ioff_decreases_in_current_result": "현재 Body doping 비교에서 확인된 Ioff 감소",
    "ion_decreases_in_current_result": "현재 Body doping 비교에서 확인된 Ion 감소",
    "ion_ioff_design_tradeoff": "누설 억제와 구동 전류의 설계 Trade-off",
    "body_doping_changes_depletion_electrostatics": "Body doping에 따른 공핍 전하와 정전기 변화",
    "field_redistribution_supports_body_effect": "Channel 인접 Field 재분포와 Vth 이동의 연결",
    "higher_vth_is_always_better": "목표 조건과 무관하게 높은 Vth를 항상 좋다고 보는 해석",
    "lower_ioff_means_all_metrics_improve": "낮은 Ioff가 모든 특성의 개선을 뜻한다는 해석",
    "ss_and_vth_are_the_same_metric": "SS와 Vth를 같은 Curve 특성으로 보는 해석",
    "field_increase_means_higher_drive_current": "Field 증가를 곧바로 Ion 증가로 치환하는 해석",
    "vth_shift_is_only_extraction_artifact": "Field 근거가 있는 Vth 이동을 추출 오차로만 보는 해석",
    "sd_doping_increases_ion_in_current_result": "현재 Source/Drain doping 비교에서 확인된 Ion 증가",
    "sd_doping_decreases_effective_ron_in_current_result": "현재 비교에서 확인된 유효 Ron 감소",
    "dibl_increases_in_current_result": "현재 Source/Drain doping 비교에서 확인된 DIBL 증가",
    "sd_doping_changes_terminal_conduction": "Source/Drain doping에 따른 단자–Channel 전도 변화",
    "drive_and_drain_control_tradeoff": "On-state 구동 이득과 Drain 제어의 Trade-off",
    "drain_field_redistribution_supports_tradeoff": "Drain-side Field 재분포와 DIBL 변화의 연결",
    "ron_is_pure_contact_resistance": "유효 Ron을 순수한 contact resistance로만 보는 해석",
    "higher_sd_doping_improves_everything": "높은 Source/Drain doping이 모든 특성을 개선한다는 해석",
    "ion_increase_proves_mobility_increase": "Ion 증가를 이동도 증가의 직접 증거로 보는 해석",
    "dibl_and_gds_are_the_same_metric": "DIBL과 gds를 같은 현상의 중복 지표로 보는 해석",
    "field_increase_directly_equals_current_increase": "Field 증가량을 전류 증가량으로 직접 치환하는 해석",
    "higher_ldd_increases_ion_in_current_result": "현재 LDD 비교에서 확인된 Ion 증가",
    "higher_ldd_decreases_effective_ron_in_current_result": "현재 LDD 비교에서 확인된 유효 Ron 감소",
    "higher_ldd_increases_drain_field_in_current_result": "현재 비교에서 확인된 Drain 인접 Field 증가",
    "higher_ldd_increases_gds_in_current_result": "현재 LDD 비교에서 확인된 gds 증가",
    "ldd_changes_access_conduction": "LDD doping에 따른 access conduction 변화",
    "ldd_field_resistance_tradeoff": "Drain Field 완화와 access resistance의 Trade-off",
    "lower_ldd_is_always_better": "낮은 LDD doping이 모든 목표에 유리하다는 해석",
    "higher_ldd_improves_everything": "높은 LDD doping이 모든 특성을 개선한다는 해석",
    "ron_is_only_ldd_resistance": "유효 Ron을 LDD 영역 저항만으로 보는 해석",
    "field_reduction_proves_reliability": "Field 감소만으로 신뢰성 개선을 확정하는 해석",
    "gds_increase_is_drive_benefit": "gds 증가를 구동 성능 이득으로 보는 해석",
    "field_magnitude_directly_predicts_ion": "Field 크기로 Ion 변화량을 직접 설명하는 해석",
    "thin_oxide_improves_short_channel_ss_in_current_result": "짧은 Channel에서 확인된 Thin Oxide의 SS 개선",
    "thin_oxide_reduces_short_channel_dibl_in_current_result": "짧은 Channel에서 확인된 Thin Oxide의 DIBL 완화",
    "oxide_compensation_depends_on_channel_length": "Channel Length에 따라 달라지는 Oxide 보상 효과",
    "thin_oxide_partially_compensates_short_channel_effect": "Thin Oxide의 부분적 Short-Channel 보상",
    "compensation_does_not_equal_full_recovery": "보상과 Long-Channel 수준 회복의 구분",
    "interaction_requires_matched_pair_comparison": "2×2 조건의 대응 차이를 이용한 상호작용 판단",
    "thin_oxide_fully_restores_long_channel_behavior": "Thin Oxide가 Long-Channel 특성을 완전히 복원한다는 해석",
    "channel_and_oxide_effects_are_independent": "Channel과 Oxide 효과가 조건과 무관하게 독립적이라는 해석",
    "diagonal_comparison_proves_interaction": "대각선 두 조건의 차이로 상호작용을 확정하는 해석",
    "field_peak_alone_quantifies_compensation": "Field 최대값만으로 보상 정도를 정량화하는 해석",
    "lower_ss_guarantees_lower_ioff_in_interaction_case": "SS 개선이 Ioff 감소를 보장한다는 해석",
    "thin_oxide_eliminates_short_channel_effect": "Thin Oxide가 Short-Channel Effect를 제거한다는 해석",
    "high_ldd_improves_conduction_at_both_sd_levels": "두 SD 수준에서 확인된 High LDD의 전도 이득",
    "high_sd_strengthens_high_ldd_drive_gain": "High SD에서 더 크게 나타난 LDD 구동 이득",
    "high_high_junction_maximizes_drive_in_current_result": "현재 결과의 최대 구동 HighSD·HighLDD 조건",
    "high_high_junction_has_drain_control_cost": "최대 구동 접합의 누설·Drain 제어 비용",
    "junction_tradeoff_requires_matched_pairs": "SD별 LDD 대응 차이를 이용한 접합 비교",
    "field_and_curve_jointly_support_junction_choice": "Curve와 Field를 결합한 접합 조건 판단",
    "sd_and_ldd_effects_are_fully_independent": "SD와 LDD 효과가 완전히 독립적이라는 해석",
    "maximum_drive_is_universal_optimum": "최대 구동 조건을 보편적 최적 조건으로 보는 해석",
    "diagonal_junction_comparison_is_controlled": "대각선 접합 비교를 controlled comparison으로 보는 해석",
    "effective_ron_is_sum_of_isolated_region_resistances": "유효 Ron을 개별 영역 저항의 단순 합으로 보는 해석",
    "field_hotspot_ranks_all_junction_performance": "Field hotspot으로 접합 전체 성능을 순위화하는 해석",
    "higher_doping_always_improves_junction": "높은 doping이 모든 접합 목표를 개선한다는 해석",
    "design_targets_require_simultaneous_constraints": "여러 설계 제약의 동시 적용",
    "drive_candidate_has_highest_ion": "Drive 후보의 최대 Ion",
    "leakage_candidate_has_lowest_ioff": "Leakage 후보의 최소 Ioff",
    "balanced_candidate_meets_all_current_targets": "현재 목표를 모두 만족한 Balanced 후보",
    "drive_candidate_fails_leakage_and_dibl_targets": "Drive 후보의 Ioff·DIBL 기준 초과",
    "leakage_candidate_fails_drive_and_ss_targets": "Leakage 후보의 Ion·SS 기준 미달",
    "control_candidate_fails_drive_target": "Control 후보의 Ion 기준 미달",
    "field_review_checks_spatial_design_margin": "Field Map으로 확인하는 공간적 설계 여유",
    "highest_ion_is_best_integrated_design": "최대 Ion 후보를 통합 최적 설계로 보는 해석",
    "lowest_ioff_is_best_integrated_design": "최소 Ioff 후보를 통합 최적 설계로 보는 해석",
    "one_passing_metric_outweighs_failed_constraints": "한 지표의 여유로 실패한 제약을 상쇄하는 해석",
    "field_map_replaces_electrical_spec_check": "Field Map이 전기적 사양 검사를 대체한다는 해석",
    "electrical_pass_proves_reliability": "전기적 사양 통과로 신뢰성을 확정하는 해석",
    "candidate_labels_are_performance_proof": "후보 이름을 성능의 증거로 사용하는 해석",
}
QUESTION_TYPE_LABELS = {
    "current_result": "현재 결과",
    "case_theory": "Case 이론",
    "adjacent_theory": "인접 반도체 이론",
    "hypothetical": "가상 조건",
    "new_experiment": "새 실험",
    "out_of_scope": "학습 범위 밖",
    # Backward-compatible labels for sessions saved before Tutor Core v2.
    "general_theory": "일반 이론",
    "unsupported": "근거 부족",
}
RELEVANCE_LABELS = {
    "direct": "직접 관련",
    "related": "관련",
    "domain_adjacent": "간접 관련",
    "unrelated": "관련 없음",
}
FALLBACK_LABELS = {
    "external_timeout": "AI 응답 시간 초과",
    "external_validation_failed": "AI 응답 확인 실패",
    "external_request_failed": "AI 요청 실패",
    "external_response_unavailable": "AI 응답 사용 불가",
    "external_network_error": "AI 서비스 연결 실패",
    "external_provider_error": "AI 서비스 오류",
    "external_http_400": "AI 요청 처리 실패",
    "external_http_401": "AI 서비스 인증 실패",
    "external_http_403": "AI 서비스 접근 권한 없음",
    "external_http_404": "AI 서비스 설정 오류",
    "external_http_413": "AI 요청 정보 과다",
    "external_http_422": "AI 요청 처리 실패",
    "external_http_429": "AI 요청 한도 초과",
    "external_http_500": "AI 서비스 일시 오류",
    "external_http_502": "AI 서비스 일시 오류",
    "external_http_503": "AI 서비스 일시 오류",
    "external_http_504": "AI 서비스 응답 시간 초과",
}
FOLLOWUP_EXAMPLES = (
    ("현재 결과", "이번 결과에서 Vth가 왜 감소했나요?"),
    ("후속 원리", "그 변화가 생기는 물리적 이유는 무엇인가요?"),
    ("인접 이론", "PN 접합이 무엇이며 공핍영역은 어떻게 형성되나요?"),
    ("가상 조건", "Body doping을 높이면 DIBL은 어떻게 달라질까요?"),
)
ERROR_GUIDANCE = {
    "learning_feedback_failed": (
        "저장된 관찰 답변과 분석 결과로 피드백 생성을 다시 시도합니다."
    ),
    "simulation_failed": (
        "저장된 예측 답변을 유지한 채 현재 Case 실험을 다시 실행합니다."
    ),
}
CONDITION_LABELS = {
    "L": "Channel length",
    "T": "Oxide thickness",
    "B": "Body doping",
    "SD": "Source/Drain doping",
    "LDD": "LDD doping",
}
CONDITION_UNITS = {
    "L": "nm",
    "T": "nm",
    "B": "cm⁻³",
    "SD": "cm⁻³",
    "LDD": "cm⁻³",
}
METRIC_LABELS = {
    "vth": "Vth",
    "vth_low": "Vth (low Vd)",
    "vth_high": "Vth (high Vd)",
    "dibl": "DIBL",
    "ss": "SS",
    "ion": "Ion",
    "ioff": "Ioff",
    "ron": "Ron",
    "gm": "gm",
    "gm_max": "gm max",
    "gds": "gds",
    "lambda_clm": "λ (CLM)",
    "ion_ioff_ratio": "Ion/Ioff ratio",
    "ratio": "Ion/Ioff ratio",
}
METRIC_TABLE_SPECS = (
    ("vth_low", "vth_low_v", "V", 1.0),
    ("vth_high", "vth_high_v", "V", 1.0),
    ("ion", "ion_ma_per_um", "mA/µm", 1.0),
    ("ioff", "ioff_ma_per_um", "mA/µm", 1.0),
    ("ion_ioff_ratio", "ion_ioff_ratio", "", 1.0),
    ("ss", "ss_mv_per_dec", "mV/dec", 1.0),
    ("dibl", "dibl_gm_v_per_v", "mV/V", 1000.0),
    ("gm_max", "gm_max_ms_per_um", "mS/µm", 1.0),
    ("gds", "gds_ms_per_um", "mS/µm", 1.0),
    ("ron", "ron_kohm_um", "kΩ·µm", 1.0),
    ("lambda_clm", "lambda_per_v", "1/V", 1.0),
)
COMPACT_PARAMETER_PANEL_WIDTH = 360
OBSERVATION_PANEL_WIDTH = 560

PLANNED_CASES = ()


CONDITION_LABELS = {
    "L": "Channel length",
    "T": "Oxide thickness",
    "B": "Body doping",
    "SD": "Source/Drain doping",
    "LDD": "LDD doping",
}
CONDITION_UNITS = {
    "L": "nm",
    "T": "nm",
    "B": "cm⁻³",
    "SD": "cm⁻³",
    "LDD": "cm⁻³",
}


def format_case_comparison(topic: Any) -> tuple[str, str, str]:
    if getattr(topic, "reference_conditions", ()):
        return (
            topic.comparison_caption or "전기적 파라미터 (대표 비교)",
            topic.baseline_label,
            topic.comparison_label,
        )
    changed = [
        name
        for name in topic.baseline_conditions
        if topic.baseline_conditions[name] != topic.comparison_conditions[name]
    ]
    if len(changed) != 1:
        return "전기적 파라미터 (Baseline → Comparison)", "Baseline", "Comparison"
    name = changed[0]
    unit = CONDITION_UNITS.get(name, "")
    baseline = f"{topic.baseline_conditions[name]:g}" + (f" {unit}" if unit else "")
    comparison = f"{topic.comparison_conditions[name]:g}" + (f" {unit}" if unit else "")
    label = CONDITION_LABELS.get(name, name)
    return (
        f"전기적 파라미터 ({label}: {baseline} → {comparison})",
        baseline,
        comparison,
    )
