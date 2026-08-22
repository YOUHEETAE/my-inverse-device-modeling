from __future__ import annotations

from .analysis_schemas import ElectricalChange, LearningAnalysisContext
from .schemas import TopicConfig


METRIC_LABELS = {
    "ion": "Ion",
    "ioff": "Ioff",
    "ion_ioff_ratio": "Ion/Ioff",
    "ratio": "Ion/Ioff",
    "vth": "Vth",
    "vth_low": "Vth (낮은 Vd)",
    "vth_high": "Vth (높은 Vd)",
    "ss": "SS",
    "dibl": "DIBL",
    "gm": "gm",
    "gm_max": "gm max",
    "gds": "gds",
    "lambda_clm": "λ (CLM)",
    "ron": "Ron",
}
PARAMETER_LABELS = {
    "L": "채널 길이",
    "T": "Gate oxide 두께",
    "B": "Body doping",
    "SD": "Source/Drain doping",
    "LDD": "LDD doping",
}
PARAMETER_UNITS = {"L": "nm", "T": "nm", "B": "cm⁻³", "SD": "cm⁻³", "LDD": "cm⁻³"}
FIELD_LABELS = {
    "potential": "전위",
    "potential_magnitude": "전위 크기",
    "potential_contour_spacing": "전위 등고선 간격",
    "electric_field": "전계",
    "electric_field_magnitude": "전계 크기",
    "electric_field_hotspot": "전계 hotspot",
    "electron_density": "전자 농도",
    "hole_density": "정공 농도",
    "electron_current": "전자 전류",
    "hole_current": "정공 전류",
}
REGION_LABELS = {
    "channel_near_surface": "채널 표면 부근",
    "drain_near_surface": "Drain 표면 부근",
    "source_near_surface": "Source 표면 부근",
    "source_side_ldd_near_surface": "Source-side LDD 표면 부근",
    "drain_side_ldd_near_surface": "Drain-side LDD 표면 부근",
    "oxide": "Gate oxide",
    "gate_oxide": "Gate oxide",
    "gate": "Gate 및 oxide 인접 영역",
    "global": "전체 영역",
}
OBSERVATION_LABELS = {
    "increase": "증가",
    "increased": "증가",
    "decrease": "감소",
    "decreased": "감소",
    "strengthened": "강화",
    "weakened": "약화",
    "expanded": "확대",
    "contracted": "축소",
    "shifted_left": "왼쪽 이동",
    "shifted_right": "오른쪽 이동",
    "stable": "큰 변화 없음",
}


def _format_number(value: float | None) -> str:
    if value is None:
        return "-"
    magnitude = abs(value)
    if magnitude and (magnitude >= 1e5 or magnitude < 1e-3):
        return f"{value:.3e}"
    return f"{value:.5g}"


def _change_line(
    topic_id: str,
    name: str,
    change: ElectricalChange,
) -> str:
    label = METRIC_LABELS.get(name, name)
    unit = f" {change.unit}" if change.unit else ""
    direction = {
        "increase": "증가",
        "decrease": "감소",
        "stable": "큰 변화 없음",
    }.get(change.direction, "변화")
    return (
        f"- {label}: {_format_number(change.before)}{unit} → "
        f"{_format_number(change.after)}{unit} ({direction}). "
        f"{_metric_mechanism(topic_id, name, change.direction)}"
    )


def _metric_mechanism(topic_id: str, name: str, direction: str) -> str:
    if topic_id == "oxide_gate_control":
        if name == "ion":
            return (
                "얇은 oxide의 큰 Cox는 같은 Gate bias에서 inversion charge에 더 "
                "강하게 결합하므로 구동 전류가 증가할 수 있다."
            )
        if name == "ioff":
            return (
                "Ioff는 지정된 off bias에서 추출한 Drain 전류다. SS 감소는 "
                "subthreshold Curve를 더 가파르게 하지만 Vth 감소는 Curve의 전도 "
                "시작 위치를 낮은 Vg 쪽으로 옮긴다. 이번 결과에서는 Vth 이동의 "
                "영향이 더 커 같은 off bias가 전도 영역에 상대적으로 가까워졌고 "
                "Ioff가 증가했다. 이 값은 전체 Drain 전류이므로 oxide tunneling "
                "성분과 동일한 지표는 아니다."
            )
        if name in {"ion_ioff_ratio", "ratio"}:
            return (
                "Gate control 개선으로 Ion이 증가하더라도 현재처럼 Ioff가 함께 "
                "증가하면 비율의 최종 방향은 두 전류의 상대 변화량으로 결정된다."
            )
        if name.startswith("vth") or name == "vth":
            return (
                "Cox 증가로 Gate 전압과 표면 전위의 결합이 달라지면 정해진 전류 "
                "기준에서 추출되는 Vth도 이동할 수 있다. 추출법과 Drain bias를 "
                "고정한 비교인지 확인해야 한다."
            )
        if name == "dibl":
            return (
                "채널 길이를 고정한 Case이므로 DIBL은 중심 목표가 아니라 보조 "
                "점검값이다. 두 Drain bias의 Vth 차이가 어떻게 변했는지 확인하되 "
                "oxide 전계 hotspot과 동일시하지 않는다."
            )
        if name == "ss":
            return (
                "Cox가 커지면 Gate 전압 변화가 채널 표면 전위에 더 잘 전달되어 "
                "subthreshold 전류를 한 decade 바꾸는 데 필요한 전압이 줄 수 있다. "
                "따라서 SS 감소는 강한 Gate control과 일치한다."
            )
        if name in {"gm", "gm_max"}:
            return (
                "큰 Cox와 강한 Gate-to-channel coupling은 Gate 전압 변화에 따른 "
                "inversion charge 변화를 키울 수 있으므로 dId/dVg인 gm이 증가한다."
            )
        if name == "ron":
            return (
                "같은 on bias에서 inversion charge가 증가하면 채널 전도도가 커져 "
                "유효 on-resistance가 감소할 수 있다."
            )
    if topic_id == "sce_channel_length":
        if name == "ion":
            return (
                "채널 길이 감소로 Source–Drain 사이의 유효 전도 경로가 짧아지고 "
                "채널 저항 성분이 줄어 같은 on bias에서 구동 전류가 증가할 수 있다."
            )
        if name == "ioff":
            return (
                "짧은 채널에서는 Drain 전위가 Source-side 주입 장벽에 더 강하게 "
                "결합한다. Gate가 꺼진 조건에서도 장벽이 낮아져 carrier 주입이 "
                "쉬워지므로 Ioff가 증가하는 방향과 연결된다."
            )
        if name in {"ion_ioff_ratio", "ratio"}:
            return (
                "Ion 증가보다 Ioff 증가가 상대적으로 크면 on/off 분리 능력이 "
                "나빠져 Ion/Ioff가 감소한다. 따라서 구동 전류 증가만으로 성능 "
                "개선을 판단할 수 없다."
            )
        if name.startswith("vth") or name == "vth":
            return (
                "Drain과 Source의 전위가 채널 장벽 제어에 참여하면 동일한 전류 "
                "기준에 도달하는 데 필요한 Gate 전압이 줄어 추출 Vth가 낮아질 "
                "수 있다. 특히 높은 Vd에서 이 효과가 더 크게 나타날 수 있다."
            )
        if name == "dibl":
            return (
                "채널이 짧아질수록 Drain bias 변화가 Source-side 장벽까지 전달되기 "
                "쉬워진다. 이에 따라 높은 Vd에서 Vth가 더 크게 낮아지고 두 Vd의 "
                "Vth 차이로 계산되는 DIBL이 증가한다."
            )
        if name == "ss":
            return (
                "Drain과 Source의 electrostatic coupling이 커지면 Gate가 "
                "subthreshold 장벽을 단독으로 제어하는 능력이 약해진다. 전류를 "
                "한 decade 바꾸는 데 더 큰 Gate 전압이 필요해져 SS가 증가한다."
            )
        if name in {"gm", "gm_max"}:
            return (
                "짧아진 전도 경로와 달라진 channel charge가 dId/dVg에 함께 "
                "반영된다. gm 변화는 같은 Gate-bias 구간에서 비교해야 하며 "
                "SCE 개선 지표로 단독 해석하지 않는다."
            )
        if name == "ron":
            return (
                "채널 길이 감소로 채널 저항 성분이 줄어 on-state의 유효 Ron이 "
                "감소할 수 있다. 접촉·확장 영역의 직렬저항은 고정된 조건이다."
            )
    if topic_id == "body_doping_design_window":
        if name == "ion":
            return (
                "Body doping 증가로 Vth가 높아지면 같은 on-state Gate bias의 "
                "overdrive가 줄어 inversion charge와 Ion이 감소할 수 있다. 이번 "
                "결과의 Ion 감소는 누설 억제와 함께 지불한 구동 성능의 비용이다."
            )
        if name == "ioff":
            return (
                "높아진 Vth는 Id–Vg Curve의 전도 시작 위치를 높은 Vg 쪽으로 "
                "옮긴다. 같은 off bias가 turn-on 지점에서 더 멀어져 이번 결과의 "
                "Ioff는 감소했다. SS는 별도의 기울기 지표이므로 Ioff 방향을 Vth와 "
                "SS 중 하나만으로 일반화하지 않는다."
            )
        if name in {"ion_ioff_ratio", "ratio"}:
            return (
                "Ion과 Ioff가 모두 감소했지만 Ioff의 상대 감소폭이 더 커 이번 "
                "결과의 Ion/Ioff 비는 증가했다. 큰 비율은 on/off 분리에 유리하지만 "
                "절대 Ion 감소를 없던 일로 만들지는 않는다."
            )
        if name.startswith("vth") or name == "vth":
            return (
                "높아진 Body doping은 공핍영역의 이온화 전하와 표면 전위 조건을 "
                "바꾸어 inversion channel 형성에 필요한 Gate bias를 높일 수 있다. "
                "동일한 추출법과 Drain bias에서 두 Vth가 증가한 방향과 일치한다."
            )
        if name == "dibl":
            return (
                "높은 Body doping에서 공핍 폭과 Drain-to-channel 정전기적 결합이 "
                "달라질 수 있다. 이번 결과의 DIBL 감소는 Drain bias에 따른 Vth "
                "간격이 줄었음을 뜻하지만 Body doping의 유일한 설계 목표는 아니다."
            )
        if name == "ss":
            return (
                "SS는 Curve의 subthreshold 기울기이고 Vth는 가로 위치이다. 이번 "
                "결과에서는 Vth와 달리 SS가 증가했으므로, 낮아진 Ioff를 SS 개선으로 "
                "설명하지 않고 높은 Vth에 따른 Curve 이동과 구분한다."
            )
        if name in {"gm", "gm_max"}:
            return (
                "같은 Gate-bias 범위에서 overdrive와 inversion charge 응답이 줄면 "
                "dId/dVg의 최대값인 gm도 감소할 수 있다. Vth 이동과 함께 bias "
                "구간을 맞춰 비교해야 한다."
            )
        if name == "ron":
            return (
                "고정 on bias에서 줄어든 inversion charge와 Ion은 유효 Ron 증가와 "
                "연결된다. 이 값에는 채널과 고정된 접촉·확장 영역의 영향이 함께 "
                "포함된다."
            )
    if topic_id == "source_drain_on_state_conduction":
        if name == "ion":
            return (
                "Source/Drain과 인접 접근영역의 전도 조건이 달라지면 단자에서 "
                "Channel로 이어지는 전류 경로의 유효 저항 성분도 변한다. 현재 "
                "비교에서는 같은 on bias의 Ion이 증가했다."
            )
        if name == "ron":
            return (
                "낮은 Vd의 on-state Id–Vd 기울기가 커지면서 추출된 유효 Ron은 "
                "감소했다. 이 Ron은 접촉저항만이 아니라 Channel과 Source/Drain "
                "접근영역을 포함하므로 한 저항 성분의 변화로 단정하지 않는다."
            )
        if name == "dibl":
            return (
                "Source/Drain 접합과 인접 공핍·전위 분포가 달라지면 Drain bias가 "
                "Channel 장벽에 전달되는 정도도 변할 수 있다. 이번 결과에서는 두 "
                "Drain bias의 Vth 간격이 커져 DIBL이 증가했다."
            )
        if name == "gds":
            return (
                "gds는 Drain 전압 변화에 대한 포화영역 Drain 전류의 민감도이다. "
                "이번 결과의 gds 증가는 포화영역 출력 저항이 감소하는 방향이며, "
                "Ion 증가와는 다른 평가 축이다."
            )
        if name in {"gm", "gm_max"}:
            return (
                "Source 쪽 직렬 저항과 전류 전달 조건이 달라지면 Gate 전압 변화가 "
                "Drain 전류로 나타나는 gm도 변할 수 있다. 동일한 bias 구간에서 "
                "비교하며 이동도 증가로 직접 치환하지 않는다."
            )
        if name == "ioff":
            return (
                "Ioff는 고정 off bias의 전체 Drain 전류이다. Source/Drain 접합과 "
                "장벽 분포의 영향을 받을 수 있지만 이번 학습에서는 검증된 DIBL과 "
                "Drain-side Field를 중심으로 전기적 제어 변화를 판단한다."
            )
    if topic_id == "ldd_field_resistance_tradeoff":
        if name == "ion":
            return (
                "높아진 LDD doping은 Channel과 고농도 Drain 사이 access 경로의 "
                "전도 조건을 바꾸고 유효 저항 성분을 줄일 수 있다. 현재 비교에서는 "
                "같은 on bias의 Ion이 증가했다."
            )
        if name == "ron":
            return (
                "낮은 Vd의 on-state Id–Vd 기울기가 커지면서 유효 Ron은 감소했다. "
                "이 값에는 LDD뿐 아니라 전체 Channel과 Source/Drain 경로가 포함되므로 "
                "LDD 영역 저항 하나의 정량 변화로 축소하지 않는다."
            )
        if name in {"gm", "gm_max"}:
            return (
                "access resistance가 줄면 같은 Gate 전압 변화가 Drain 전류 응답으로 "
                "나타나는 정도가 커질 수 있다. 이번 결과의 gm 증가는 구동 응답 "
                "강화와 일치하지만 Field 완화를 뜻하지는 않는다."
            )
        if name == "gds":
            return (
                "gds 증가는 포화영역에서 Drain 전압 변화에 대한 전류 민감도가 "
                "커지고 출력 저항은 감소하는 방향이다. Ion 증가와 같은 종류의 "
                "구동 이득으로 합치지 않는다."
            )
        if name == "lambda_clm":
            return (
                "λ 증가는 포화영역 전류가 Drain 전압에 더 민감해지는 방향이며 "
                "gds 증가와 함께 출력 특성의 비용을 보조적으로 보여준다."
            )
        if name.startswith("vth") or name == "vth":
            return (
                "LDD doping 변화는 Drain 접합 인접 전위와 두 Drain bias에서의 "
                "추출 조건에 영향을 줄 수 있다. 현재 Vth 이동은 동일한 추출법과 "
                "bias에서 확인하되 LDD의 중심 성능 지표로 단독 평가하지 않는다."
            )
    if topic_id == "channel_oxide_electrostatic_compensation":
        if name == "ss":
            return (
                "짧은 Channel에서 Oxide가 얇아지면 Gate-to-channel 결합이 강화되어 "
                "subthreshold barrier를 더 가파르게 제어하므로 SS가 감소했다."
            )
        if name == "dibl":
            return (
                "강해진 Gate coupling은 Drain bias가 Channel barrier에 미치는 상대적 "
                "영향을 줄여 현재 Short 조건의 DIBL을 낮췄다."
            )
        if name == "ioff":
            return (
                "SS는 개선됐지만 Vth 이동과 고정 off-bias 위치의 영향이 함께 반영되어 "
                "현재 Short 조건의 Ioff는 증가했다. SS 개선만으로 Ioff 감소를 보장하지 않는다."
            )
        if name == "ion":
            return (
                "얇은 Oxide의 강한 Gate coupling과 증가한 inversion charge가 현재 "
                "on bias의 Ion 증가에 기여했다. 이 증가는 electrostatic recovery의 "
                "완료 여부와는 별도의 구동 지표이다."
            )
        if name in {"gm", "gm_max"}:
            return (
                "Gate 전압 변화가 Channel charge와 Drain 전류에 더 강하게 전달되어 "
                "gm이 증가했다."
            )
        if name.startswith("vth") or name == "vth":
            return (
                "Oxide 두께에 따른 Gate coupling 변화는 동일한 전류 기준으로 추출한 "
                "Vth의 위치도 바꾼다. Vth 이동과 SS 변화를 분리해 읽는다."
            )
    if topic_id == "source_drain_ldd_junction_engineering":
        if name == "ion":
            return (
                "High SD에서 LDD를 높이면 단자–Channel과 access 경로의 전도 조건이 "
                "함께 강화되어 현재 on bias의 Ion이 증가했다."
            )
        if name == "ron":
            return (
                "낮은 Vd on-state 기울기가 커져 전체 전류 경로의 유효 Ron이 "
                "감소했다. 개별 SD·LDD 영역 저항의 단순 합으로 분해하지 않는다."
            )
        if name in {"ioff", "dibl", "gds"}:
            return (
                "접합과 Drain-side 전위 분포가 바뀌면서 off-state 누설 또는 Drain "
                "bias 민감도도 변했다. 구동 이득과 별도의 설계 비용으로 평가한다."
            )
    if topic_id == "integrated_device_design":
        if name == "ion":
            return (
                "Control보다 짧은 Channel을 사용한 Balanced는 구동 전류 하한을 "
                "넘도록 Ion이 증가했다."
            )
        if name == "ioff":
            return (
                "짧은 Channel에서 Ioff는 증가했지만 현재 목표 상한 0.001 mA/µm "
                "이내에 남았다."
            )
        if name == "dibl":
            return (
                "Channel 단축으로 Drain coupling이 커져 DIBL은 증가했지만 현재 "
                "목표 상한 30 mV/V는 만족했다."
            )
        if name == "ss":
            return (
                "얇은 Oxide와 높은 Body doping 조건에서 SS는 목표 상한 80 mV/dec "
                "이내에 유지됐다."
            )
        if name == "ron":
            return (
                "짧은 전도 경로와 높은 구동 전류 조건으로 유효 Ron이 감소했다."
            )
    if name == "ion":
        return (
            "Ion은 정해진 on-state bias의 구동 전류이므로 채널 전하, 이동 경로와 "
            "유효 채널 저항이 함께 반영된다."
        )
    if name == "ioff":
        return (
            "Ioff는 정해진 off-state bias의 누설 전류이다. Source-side 장벽이 "
            "낮아지거나 Gate의 subthreshold 제어가 약해지면 증가할 수 있다."
        )
    if name in {"ion_ioff_ratio", "ratio"}:
        return (
            "이 비는 구동 전류와 누설 전류를 함께 보는 지표이며, Ion이 늘더라도 "
            "Ioff가 더 빠르게 증가하면 감소할 수 있다."
        )
    if name.startswith("vth") or name == "vth":
        return (
            "Vth는 채택한 추출법과 Drain bias에 의존한다. 감소는 동일한 전류 기준에 "
            "도달하는 데 필요한 Gate 전압이 낮아졌음을 뜻한다."
        )
    if name == "dibl":
        return (
            "DIBL은 두 Drain bias에서 추출한 Vth 차이로 Source-side 장벽에 대한 "
            "Drain 전위의 결합 정도를 나타내며, 값이 클수록 장벽 제어가 불리하다."
        )
    if name == "ss":
        return (
            "SS는 subthreshold 전류를 한 decade 바꾸는 데 필요한 Gate 전압이다. "
            "값이 작을수록 Gate가 off-state 전류를 더 가파르게 제어한다."
        )
    if name in {"gm", "gm_max"}:
        return (
            "gm은 dId/dVg이므로 Gate 전압 변화가 채널 전류로 전달되는 민감도를 "
            "나타낸다. 비교 시 같은 bias 구간의 최대값 또는 지정 추출값을 봐야 한다."
        )
    if name == "ron":
        return (
            "Ron은 on-state의 유효 저항으로 채널 길이, inversion charge와 직렬저항의 "
            "영향을 함께 받으며, 값이 작을수록 같은 전압에서 전류가 잘 흐른다."
        )
    return (
        f"이 지표의 {direction} 방향은 동일한 추출 조건에서 비교하고 다른 지표 및 "
        "공간 분포와 함께 해석해야 한다."
    )


def _case_mechanism(topic_id: str) -> str:
    if topic_id == "sce_channel_length":
        return (
            "채널 길이가 짧아지면 Source와 Drain 사이의 유효 이동 거리가 줄어 "
            "on-state 채널 저항이 낮아질 수 있으므로 Ion 증가와 Ron 감소 방향이 "
            "나타날 수 있다. 동시에 Drain 전위와 공핍영역이 채널 내부, 특히 "
            "Source-side 주입 장벽에 더 강하게 결합한다. 이 electrostatic "
            "coupling은 Gate가 단독으로 장벽을 지배하는 정도를 약화시켜 Vth 감소, "
            "DIBL 증가, Ioff 증가 및 SS 악화로 이어질 수 있다. 따라서 짧은 채널의 "
            "핵심은 단순한 전류 증가가 아니라 구동 성능 개선과 off-state/SCE "
            "악화를 동시에 판단하는 것이다."
        )
    if topic_id == "oxide_gate_control":
        return (
            "Gate oxide가 얇아지면 oxide capacitance가 커져 같은 Gate 전압 변화가 "
            "채널 표면 전위와 inversion charge에 더 강하게 전달된다. 이 때문에 "
            "gm 증가와 SS 감소처럼 Gate control이 개선되는 방향이 기대된다. "
            "그러나 같은 전압차가 더 얇은 절연막에 걸리면 oxide 및 계면 부근의 "
            "전계 분포도 달라질 수 있고, 현재 결과에서는 Ioff 변화도 함께 확인해야 "
            "한다. 강한 Gate control과 oxide 신뢰성은 같은 판단이 아니며 Field "
            "Map의 hotspot만으로 breakdown을 확정해서는 안 된다."
        )
    if topic_id == "body_doping_design_window":
        return (
            "Body doping을 높이면 채널 아래 공핍영역의 이온화 전하와 전위 분포가 "
            "달라져 inversion channel을 형성하는 데 필요한 Gate bias가 변한다. "
            "현재 비교에서는 Vth가 높아져 Id–Vg Curve가 높은 Vg 방향으로 이동했고, "
            "그 결과 고정 off bias의 Ioff는 크게 감소했지만 고정 on bias의 "
            "overdrive와 Ion도 감소했다. 따라서 이 Case의 핵심은 높은 Vth나 낮은 "
            "Ioff를 단독으로 좋은 변화라 부르는 것이 아니라 누설 예산, 공급 전압과 "
            "필요 구동 전류가 허용하는 Vth–Ioff 설계 범위를 판단하는 것이다."
        )
    if topic_id == "source_drain_on_state_conduction":
        return (
            "Source/Drain doping은 단자에서 Channel로 이어지는 접근영역의 전도 "
            "조건과 Source/Drain 접합 주변의 공핍·전위 분포에 함께 영향을 준다. "
            "현재 비교에서는 Ion 증가와 유효 Ron 감소로 on-state conduction "
            "이득이 나타났다. 동시에 DIBL과 gds가 증가하고 Drain-side 인접 "
            "Potential·Electric Field도 증가했으므로 Drain bias에 대한 장벽 및 "
            "포화영역 전류 민감도는 별도의 비용으로 평가해야 한다. 핵심은 높은 "
            "Source/Drain doping을 일방적인 개선으로 보는 것이 아니라 구동 전류, "
            "유효 저항과 Drain-side 전기적 제어를 함께 판단하는 것이다."
        )
    if topic_id == "ldd_field_resistance_tradeoff":
        return (
            "LDD는 Channel과 고농도 Drain 사이에서 Drain 전위 변화와 국부 전계가 "
            "전달되는 구간을 조절한다. 낮은 LDD doping은 Drain-side 전계를 완화할 "
            "수 있지만 access 영역의 전도성을 낮춰 유효 Ron을 키우고 Ion을 줄일 "
            "수 있다. 현재 비교에서는 높은 LDD에서 Ion·gm 증가와 Ron 감소가 "
            "나타난 대신 gds와 Drain 인접 Potential·Electric Field도 증가했다. "
            "따라서 LDD의 핵심은 전계 완화와 access resistance 사이의 trade-off이며, "
            "Field 감소만으로 신뢰성 향상을 확정하거나 Ron을 LDD 저항 하나로 "
            "해석해서는 안 된다."
        )
    if topic_id == "channel_oxide_electrostatic_compensation":
        return (
            "Channel Length 감소는 Drain의 정전기적 영향이 Source-side 장벽까지 더 "
            "강하게 전달되게 하여 SS와 DIBL을 악화시킨다. Oxide를 얇게 하면 "
            "Gate-to-channel coupling이 강화되어 이 영향을 일부 상쇄할 수 있다. "
            "현재 2×2 비교에서는 같은 T 20→10 nm 변화가 Long Channel보다 Short "
            "Channel의 SS와 DIBL을 더 크게 낮췄다. 그러나 Short·Thin의 DIBL은 "
            "Long·Thin보다 여전히 높고 Ioff도 증가했으므로 이는 부분적 보상이지 "
            "Channel Length 효과의 제거 또는 전체 특성의 완전한 회복은 아니다."
        )
    if topic_id == "source_drain_ldd_junction_engineering":
        return (
            "SD와 LDD는 terminal–Channel 전류 전달과 Drain-side 전위 분포를 함께 "
            "바꾼다. 현재 2×2 결과에서 LDD 증가는 두 SD 수준 모두 Ion을 높이고 "
            "유효 Ron을 낮췄으며, Ion 증가율은 High SD에서 더 컸다. HighSD·HighLDD는 "
            "최대 Ion과 최소 Ron을 만들었지만 Ioff와 DIBL도 가장 컸다. 따라서 "
            "각 SD 수준의 LowLDD→HighLDD 대응 차이로 효과를 분리하고 최대 구동과 "
            "Drain 제어 목표 사이의 접합 trade-off를 판단해야 한다."
        )
    if topic_id == "integrated_device_design":
        return (
            "통합 설계는 한 파라미터의 방향을 맞히는 문제가 아니라 여러 제약을 "
            "동시에 적용해 feasible candidate를 찾는 과정이다. 현재 목표는 Ion≥10 "
            "mA/µm, Ioff≤0.001 mA/µm, DIBL≤30 mV/V, SS≤80 mV/dec이다. Drive는 "
            "Ioff·DIBL, Leakage는 Ion·SS, Control은 Ion 기준을 실패했고 Balanced만 "
            "네 기준을 모두 만족했다. Balanced는 보편적 최적점이 아니라 현재 목표 "
            "집합의 유일한 통과 후보이며 Field Map으로 남은 공간적 비용을 추가로 "
            "검토해야 한다."
        )
    return (
        "변경한 소자 파라미터가 electrostatic control, 채널 전하와 저항에 미치는 "
        "일반적 영향과 현재 시뮬레이션에서 실제로 관찰된 방향을 구분해 해석해야 한다."
    )


def _available_change(
    context: LearningAnalysisContext,
    *names: str,
) -> tuple[str, ElectricalChange] | None:
    for name in names:
        change = context.electrical_changes.get(name)
        if change and change.available:
            return name, change
    return None


def _curve_evidence_lines(
    topic_id: str,
    context: LearningAnalysisContext,
) -> str:
    lines: list[str] = []
    ss_item = _available_change(context, "ss")
    if ss_item:
        change = ss_item[1]
        if change.direction == "increase":
            lines.append(
                "- SS: log(Id)–Vg의 subthreshold 구간에서 "
                "d(log10 Id)/dVg가 완만해지고, 전류를 1 decade 바꾸는 데 필요한 "
                "Gate 전압 폭이 커지는 형태가 추출된 SS 증가와 대응한다."
            )
        elif change.direction == "decrease":
            lines.append(
                "- SS: log(Id)–Vg의 subthreshold 구간에서 "
                "d(log10 Id)/dVg가 가팔라지고, 전류를 1 decade 바꾸는 데 필요한 "
                "Gate 전압 폭이 작아지는 형태가 추출된 SS 감소와 대응한다."
            )
    gm_item = _available_change(context, "gm_max", "gm")
    if gm_item:
        change = gm_item[1]
        direction = "커지는" if change.direction == "increase" else "작아지는"
        lines.append(
            f"- {METRIC_LABELS.get(gm_item[0], gm_item[0])}: 선형 Id–Vg의 turn-on "
            f"구간에서 dId/dVg의 최대 기울기가 {direction}지 확인하면 추출된 "
            f"gm의 {OBSERVATION_LABELS.get(change.direction, change.direction)}와 대응시킬 수 있다."
        )
    for name in ("vth_low", "vth_high", "vth"):
        item = _available_change(context, name)
        if not item:
            continue
        change = item[1]
        shift = "더 낮은 Vg 쪽으로 이동" if change.direction == "decrease" else "더 높은 Vg 쪽으로 이동"
        lines.append(
            f"- {METRIC_LABELS.get(name, name)}: 동일한 추출 전류 기준과 Drain bias에서 "
            f"Curve의 교차점이 {shift}하는지가 추출값과 일치하는지 확인한다."
        )
    dibl_item = _available_change(context, "dibl")
    if dibl_item:
        change = dibl_item[1]
        relation = (
            "높은 Vd Curve의 문턱 이동이 더 커지고 두 Vd에서의 Vth 간격이 벌어지는"
            if change.direction == "increase"
            else "두 Vd에서의 Vth 간격이 줄어드는"
        )
        lines.append(
            f"- DIBL: 낮은 Vd와 높은 Vd의 log(Id)–Vg를 겹쳐 보았을 때 {relation} "
            f"형태가 DIBL {OBSERVATION_LABELS.get(change.direction, change.direction)}와 대응한다."
        )
    gds_item = _available_change(context, "gds")
    if gds_item:
        change = gds_item[1]
        slope = "커지는" if change.direction == "increase" else "작아지는"
        lines.append(
            "- gds: 포화영역 Id–Vd에서 Drain 전압 변화에 대한 전류 기울기가 "
            f"{slope} 형태가 gds "
            f"{OBSERVATION_LABELS.get(change.direction, change.direction)}와 대응한다."
        )
    for name, bias_label in (("ioff", "정의된 off bias"), ("ion", "정의된 on bias")):
        item = _available_change(context, name)
        if item:
            change = item[1]
            lines.append(
                f"- {METRIC_LABELS[name]}: {bias_label}에서 두 Curve의 Drain 전류를 직접 "
                f"비교하면 표의 {METRIC_LABELS[name]} "
                f"{OBSERVATION_LABELS.get(change.direction, change.direction)}를 확인할 수 있다."
            )
    ratio_item = _available_change(context, "ion_ioff_ratio", "ratio")
    if ratio_item:
        change = ratio_item[1]
        lines.append(
            "- Ion/Ioff: Curve의 한 지점에서 직접 읽는 값이 아니라 동일한 정의의 "
            f"Ion과 Ioff를 함께 계산한 결과이며, 현재 표에서는 "
            f"{OBSERVATION_LABELS.get(change.direction, change.direction)}했다."
        )
    ron_item = _available_change(context, "ron")
    if ron_item:
        change = ron_item[1]
        slope = "커지는" if change.direction == "decrease" else "작아지는"
        lines.append(
            f"- Ron: on-state의 낮은 Vd Id–Vd 기울기(전도도)가 {slope} 형태가 "
            f"Ron {OBSERVATION_LABELS.get(change.direction, change.direction)}와 대응한다."
        )
    if lines:
        return "\n".join(lines)
    return (
        "- 현재 추출된 전기적 파라미터가 부족해 특정 Curve 변화와 연결할 수 없다. "
        "동일한 축·bias 조건의 원본 Curve를 먼저 확인해야 한다."
    )


def _meaningful_field_observations(
    context: LearningAnalysisContext,
) -> tuple:
    return tuple(
        item
        for item in context.field_observations
        if item.observation in OBSERVATION_LABELS
    )[:6]


def _field_evidence_lines(
    topic_id: str,
    context: LearningAnalysisContext,
) -> str:
    observations = _meaningful_field_observations(context)
    if not observations:
        return (
            "- 현재 구조화된 Field 관찰에는 방향이 검증된 항목이 없다. 따라서 이번 "
            "Case의 물리 원인을 Field Map에서 확인했다고 단정하지 않는다."
        )
    lines: list[str] = []
    direct_oxide_regions = {"oxide", "gate_oxide", "gate"}
    for item in observations:
        quantity = FIELD_LABELS.get(item.quantity, item.quantity.replace("_", " "))
        region_key = str(item.region or "")
        region = REGION_LABELS.get(region_key, (region_key or "관찰 영역").replace("_", " "))
        observation = OBSERVATION_LABELS[item.observation]
        statement = f"- {region}의 {quantity}: {observation}."
        if topic_id == "sce_channel_length":
            if region_key in {
                "channel_near_surface", "drain_near_surface",
                "source_near_surface", "source_side_ldd_near_surface",
            } and item.quantity.startswith(("potential", "electric_field")):
                statement += (
                    " 이는 채널 장벽과 Drain 전위의 공간적 결합을 판단할 현재 Case의 "
                    "단서이며, DIBL·Vth·Ioff의 실제 방향과 교차 확인해야 한다."
                )
        elif topic_id == "oxide_gate_control":
            if region_key in direct_oxide_regions:
                statement += (
                    " Gate–oxide–channel 결합과 oxide 인접 전계 분포를 판단할 직접적인 "
                    "공간 단서이다."
                )
            elif region_key == "drain_near_surface":
                if item.quantity.startswith("electric_field"):
                    statement += (
                        " 이는 Drain 쪽 정전기적 영향의 공간 변화이며, DIBL 방향과 "
                        "함께 보면 Drain-side channel 제어가 어떻게 달라졌는지 "
                        "설명하는 근거가 된다. Oxide의 국부 전계 부담은 같은 bias와 "
                        "color scale에서 Gate–oxide 경계 분포를 이어서 비교한다."
                    )
                else:
                    statement += (
                        " 이는 Drain 주변 전위 재분포를 보여주며 Vth·DIBL 변화와 "
                        "연결해 channel barrier 제어를 해석할 수 있다. Oxide 내부 "
                        "전계 크기는 Gate–oxide 경계의 Electric Field에서 구분한다."
                    )
            else:
                statement += (
                    " 이 위치의 변화는 해당 영역의 전위·전계 재분포를 설명한다. "
                    "Gate control은 gm·SS·DIBL과 교차 확인하고 Oxide 부담은 "
                    "Gate–oxide 경계의 분포로 나누어 해석한다."
                )
        elif topic_id == "body_doping_design_window":
            if region_key == "channel_near_surface" and item.quantity.startswith(
                ("potential", "electric_field")
            ):
                statement += (
                    " 이는 Body 전하와 공핍 정전기가 Channel 표면 조건을 바꾼 "
                    "공간 근거이다. Vth 증가와 고정 bias의 Ion·Ioff 감소 방향에 "
                    "연결하되 Field 크기를 전류 크기로 직접 치환하지 않는다."
                )
            else:
                statement += (
                    " Body doping에 따른 소자 내부 정전기 재분포의 일부이며, 같은 "
                    "bias와 color scale에서 Channel 표면 부근 분포 및 Vth·Ion·Ioff와 "
                    "함께 확인한다."
                )
        elif topic_id == "source_drain_on_state_conduction":
            if region_key in {"drain_near_surface", "drain_side_ldd_near_surface"}:
                statement += (
                    " 이는 Source/Drain 접합과 Drain-side 인접 영역의 정전기 "
                    "재분포를 보여준다. 현재 DIBL 증가와 함께 보면 Drain bias의 "
                    "Channel 장벽 영향이 커진 방향을 설명하는 공간 근거가 된다."
                )
            else:
                statement += (
                    " Source/Drain doping 변화에 따른 공간 분포의 일부이며, 같은 "
                    "bias와 color scale에서 Drain-side 인접 영역과 DIBL 방향을 "
                    "우선 교차 확인한다."
                )
        elif topic_id == "ldd_field_resistance_tradeoff":
            if region_key in {"drain_near_surface", "drain_side_ldd_near_surface"}:
                statement += (
                    " 이는 LDD doping에 따른 Drain-side 전위·전계 재분포의 직접적인 "
                    "공간 근거이다. 높은 LDD에서 증가한 Field와 낮은 LDD에서의 "
                    "Ion 감소·Ron 증가를 함께 보면 전계 완화와 access resistance의 "
                    "trade-off를 확인할 수 있다."
                )
            else:
                statement += (
                    " LDD 변화에 따른 소자 내부 재분포의 일부이며, 같은 bias와 "
                    "color scale에서 Drain 인접 영역을 우선 비교한다."
                )
        elif topic_id == "channel_oxide_electrostatic_compensation":
            if region_key in {
                "channel_near_surface",
                "drain_near_surface",
                "source_near_surface",
            }:
                statement += (
                    " 이는 Short 조건에서 Oxide 두께 감소가 Channel–Drain 방향의 "
                    "정전기 분포를 바꾼 공간 근거이다. Long의 Thick→Thin 변화와 "
                    "Short의 Thick→Thin 변화를 같은 bias와 color scale에서 대응 "
                    "비교해야 보상 효과의 Channel-Length 의존성을 분리할 수 있다."
                )
            else:
                statement += (
                    " 네 조건의 global 최대값보다 대응 조건 사이의 공간 변화 위치와 "
                    "방향을 SS·DIBL 결과와 교차 확인한다."
                )
        elif topic_id == "source_drain_ldd_junction_engineering":
            statement += (
                " 각 SD 수준의 LowLDD→HighLDD Drain 인접 변화를 대응 비교하고 "
                "Ion·Ron·DIBL 방향과 함께 읽어 접합 전도와 Drain 제어를 연결한다."
            )
        elif topic_id == "integrated_device_design":
            if region_key in {"drain_near_surface", "drain_side_ldd_near_surface"}:
                statement += (
                    " Balanced는 Control보다 짧은 Channel로 DIBL과 Drain-side Field가 "
                    "증가한 공간적 비용이 남아 있다. 전기적 사양 통과 후의 설계 "
                    "여유로 기록하되 신뢰성 수명으로 직접 환산하지 않는다."
                )
        lines.append(statement)
    return "\n".join(lines)


def _integrated_interpretation(
    topic_id: str,
    context: LearningAnalysisContext,
) -> str:
    directions = {
        name: change.direction
        for name, change in context.electrical_changes.items()
        if change.available
    }
    if topic_id == "sce_channel_length":
        return (
            "채널 길이 감소는 한편으로 전도 경로와 채널 저항 성분을 줄여 Ion·Ron 같은 "
            "구동 특성을 바꾸고, 다른 한편으로 Drain/Source의 정전기적 결합 비중을 "
            "높여 Gate의 장벽 제어를 약화시킨다. 이번 표에서 확인된 방향은 "
            f"Ion {OBSERVATION_LABELS.get(directions.get('ion', ''), '미확인')}, "
            f"Ioff {OBSERVATION_LABELS.get(directions.get('ioff', ''), '미확인')}, "
            f"DIBL {OBSERVATION_LABELS.get(directions.get('dibl', ''), '미확인')}, "
            f"SS {OBSERVATION_LABELS.get(directions.get('ss', ''), '미확인')}이다. "
            "Curve에서는 이 결과를 on/off 전류, 문턱 이동, subthreshold 기울기로 "
            "확인하고, Field에서는 그 원인이 될 채널·Source-side 장벽 방향의 전위와 "
            "전계 결합 단서를 확인한다."
        )
    if topic_id == "oxide_gate_control":
        gm_direction = directions.get("gm_max", directions.get("gm", ""))
        vth_direction = directions.get("vth_high", directions.get("vth", ""))
        return (
            "Oxide 두께 감소는 Cox를 키워 Gate 전압 변화가 채널 표면 전위와 inversion "
            "charge에 더 강하게 전달되도록 한다. 이번 표에서 확인된 방향은 "
            f"gm {OBSERVATION_LABELS.get(gm_direction, '미확인')}, "
            f"SS {OBSERVATION_LABELS.get(directions.get('ss', ''), '미확인')}, "
            f"Vth {OBSERVATION_LABELS.get(vth_direction, '미확인')}, "
            f"Ioff {OBSERVATION_LABELS.get(directions.get('ioff', ''), '미확인')}이다. "
            "gm과 SS는 Gate 응답의 크기와 subthreshold 기울기를 보여주고, Vth는 "
            "Curve의 가로 위치를 정한다. 이번에는 SS가 개선됐어도 Vth가 낮아진 "
            "영향이 더 커 고정 off bias의 Ioff가 증가했다. Drain 인접 Field와 "
            "DIBL은 Drain-side 제어를, Gate/oxide/channel 인접 Field는 Oxide의 "
            "국부 전계 부담을 각각 설명한다."
        )
    if topic_id == "body_doping_design_window":
        vth_direction = directions.get("vth_low", directions.get("vth", ""))
        return (
            "Body doping 증가는 공핍 전하와 Channel 표면의 정전기적 조건을 바꾸어 "
            "inversion에 필요한 Gate bias를 이동시킨다. 이번 표에서 확인된 방향은 "
            f"Vth {OBSERVATION_LABELS.get(vth_direction, '미확인')}, "
            f"Ion {OBSERVATION_LABELS.get(directions.get('ion', ''), '미확인')}, "
            f"Ioff {OBSERVATION_LABELS.get(directions.get('ioff', ''), '미확인')}, "
            f"SS {OBSERVATION_LABELS.get(directions.get('ss', ''), '미확인')}이다. "
            "Curve에서는 Vth의 가로 이동과 고정 on/off bias 전류를 구분해 확인하고, "
            "Field에서는 Channel 표면 부근 Potential·Electric Field 재분포가 같은 "
            "물리적 흐름을 뒷받침하는지 확인한다. 누설 감소와 구동 전류 감소가 "
            "동시에 있으므로 최종 판단은 목표 전력과 성능에 종속된다."
        )
    if topic_id == "source_drain_on_state_conduction":
        return (
            "Source/Drain doping 증가는 단자–Channel 전류 경로와 Drain 접합 인접 "
            "정전기를 함께 바꾼다. 이번 표에서 확인된 방향은 "
            f"Ion {OBSERVATION_LABELS.get(directions.get('ion', ''), '미확인')}, "
            f"Ron {OBSERVATION_LABELS.get(directions.get('ron', ''), '미확인')}, "
            f"DIBL {OBSERVATION_LABELS.get(directions.get('dibl', ''), '미확인')}, "
            f"gds {OBSERVATION_LABELS.get(directions.get('gds', ''), '미확인')}이다. "
            "I–V Curve에서는 정의된 on bias의 Ion과 낮은 Vd 기울기의 Ron으로 "
            "conduction 이득을 확인하고, 두 Drain bias의 Vth 간격과 포화영역 "
            "Id–Vd 기울기로 DIBL·gds 비용을 구분한다. Field에서는 Drain-side "
            "Potential·Electric Field 재분포가 DIBL 방향을 뒷받침하는지 확인한다."
        )
    if topic_id == "ldd_field_resistance_tradeoff":
        gm_direction = directions.get("gm_max", directions.get("gm", ""))
        return (
            "LDD doping은 access 경로의 전도성과 Drain-side 전계 분포를 동시에 "
            "바꾼다. 이번 표에서 확인된 방향은 "
            f"Ion {OBSERVATION_LABELS.get(directions.get('ion', ''), '미확인')}, "
            f"Ron {OBSERVATION_LABELS.get(directions.get('ron', ''), '미확인')}, "
            f"gm {OBSERVATION_LABELS.get(gm_direction, '미확인')}, "
            f"gds {OBSERVATION_LABELS.get(directions.get('gds', ''), '미확인')}이다. "
            "I–V에서는 Ion·Ron으로 access conduction, gm으로 Gate 입력 응답, "
            "gds로 포화영역 출력 민감도를 나누어 확인한다. Field에서는 높은 LDD의 "
            "Drain 인접 Potential·Electric Field 증가를 확인하고, 반대 조건인 낮은 "
            "LDD의 전계 완화와 Ion 감소·Ron 증가를 하나의 trade-off로 연결한다."
        )
    if topic_id == "channel_oxide_electrostatic_compensation":
        return (
            "네 조건을 대응 비교하면 T 20→10 nm에서 SS 감소 폭은 Long Channel의 "
            "약 8.05 mV/dec보다 Short Channel의 약 17.65 mV/dec에서 더 컸고, DIBL "
            "감소 폭도 약 11.21 mV/V보다 약 54.94 mV/V로 더 컸다. 이는 얇은 "
            "Oxide의 Gate-control 효과가 Channel Length에 따라 다르게 나타난 "
            "상호작용이다. Short·Thin은 Short·Thick보다 SS와 DIBL이 개선됐지만 "
            "Long·Thin보다 DIBL이 높고 고정 off-bias의 Ioff도 증가했다. 따라서 "
            "Curve에서는 부분적 보상과 잔여 SCE를 구분하고, Field에서는 Long과 "
            "Short 각각의 Thick→Thin 공간 변화를 대응시켜 확인한다."
        )
    if topic_id == "source_drain_ldd_junction_engineering":
        return (
            "LDD 증가의 Ion 상승률은 Low SD에서 약 5.14%, High SD에서 약 6.68%였고 "
            "두 조건 모두 유효 Ron은 감소했다. HighSD·HighLDD가 최대 구동 조건이지만 "
            "Ioff와 DIBL도 가장 크므로 구동 이득과 Drain 제어 비용을 함께 평가한다. "
            "Curve에서는 각 SD 수준의 LDD 대응 차이를, Field에서는 같은 pair의 Drain "
            "인접 분포를 교차 확인한다."
        )
    if topic_id == "integrated_device_design":
        return (
            "후보별 결과는 Drive: Ion 19.226, Ioff 0.08003, DIBL 70.03, SS 76.80; "
            "Leakage: Ion 1.8549, Ioff 1.564×10⁻⁸, DIBL 14.86, SS 92.63; "
            "Control: Ion 4.8972, Ioff 3.158×10⁻⁵, DIBL 6.12, SS 76.88; "
            "Balanced: Ion 12.982, Ioff 0.0006135, DIBL 22.67, SS 76.30이다. "
            "모든 제약을 동시에 적용하면 Balanced만 통과한다. Control→Balanced의 "
            "Channel 단축은 Ion 하한을 넘기는 대신 DIBL과 Drain-side Field를 키웠으므로 "
            "Field Map에서 남은 electrostatic margin을 확인한다."
        )
    return (
        "파라미터 표의 정량 변화, Curve의 형태, Field의 공간 분포를 같은 bias 조건에서 "
        "교차 확인해야 원인과 결과를 연결할 수 있다."
    )


def _tradeoff_and_limits(topic_id: str) -> str:
    if topic_id == "sce_channel_length":
        return (
            "구동 전류 증가나 Ron 감소는 성능 이점이지만, Ioff·DIBL·SS가 악화되면 "
            "off-state 전력과 Gate 제어 측면의 손실이 생긴다. 따라서 Ion 하나만으로 "
            "개선이라 판단하지 않는다. 수치는 현재 추출 bias와 방법에 종속되며, Field "
            "Map은 메커니즘의 공간적 단서이지 전기적 파라미터 변화량 자체는 아니다."
        )
    if topic_id == "oxide_gate_control":
        return (
            "gm 증가는 Gate 응답의 이점이고 SS 감소는 더 가파른 subthreshold 전이를 "
            "뜻한다. 그러나 Ioff는 고정된 Vg에서 읽기 때문에 Curve의 기울기뿐 아니라 "
            "Vth가 정한 가로 위치에도 좌우된다. 이번 Case에서는 낮아진 Vth의 영향이 "
            "SS 개선보다 커 Ioff가 증가했으므로 Gate control과 off-state 누설을 서로 "
            "다른 평가 축으로 봐야 한다. Field는 Drain-side 제어와 Gate–oxide 국부 "
            "부담을 위치별로 나누어 읽으며, 구체적인 breakdown이나 tunneling은 해당 "
            "물리 모델과 재료 기준이 있을 때 판단한다."
        )
    if topic_id == "body_doping_design_window":
        return (
            "높은 Vth와 낮은 Ioff는 off-state 누설 억제에 유리하지만, 같은 공급 "
            "전압에서 overdrive와 Ion이 줄어들 수 있다. 이번 결과에서는 Ioff의 "
            "상대 감소가 더 커 Ion/Ioff 비가 증가했지만 절대 Ion도 감소했다. 따라서 "
            "목표 누설, 요구 구동 전류와 허용 Vth 범위를 함께 정해야 한다. SS는 "
            "Curve의 기울기이고 Vth는 가로 위치이므로 서로 다른 방향도 모순이 "
            "아니다. 수치는 현재 구조·bias·추출법과 학습된 모델에 종속되며 Field "
            "Map은 공핍 전하 자체의 정량값이 아니라 정전기 재분포를 확인하는 공간 "
            "근거로 사용한다."
        )
    if topic_id == "source_drain_on_state_conduction":
        return (
            "Ion 증가와 유효 Ron 감소는 on-state 구동에 유리하지만, DIBL 증가는 "
            "Drain bias에 대한 Channel 장벽 민감도 증가를 뜻하고 gds 증가는 "
            "포화영역 출력 저항 감소 방향이다. 따라서 낮은 저항과 큰 구동 전류가 "
            "중요한 설계인지, 작은 DIBL과 높은 출력 저항이 중요한 설계인지에 따라 "
            "조건의 적합성이 달라진다. Ron은 순수 contact resistance가 아니며 Ion "
            "증가만으로 이동도 증가를 확정하지 않는다. Field Map은 Drain 접합 인접 "
            "정전기의 공간 근거이므로 Electric Field 크기를 전류 증가량으로 직접 "
            "환산하거나 hotspot만으로 breakdown을 판단하지 않는다."
        )
    if topic_id == "ldd_field_resistance_tradeoff":
        return (
            "낮은 LDD doping은 Drain 인접 전계를 완화하는 데 유리하지만 access "
            "resistance 증가로 Ion이 줄 수 있다. 높은 LDD doping은 Ion·gm 증가와 "
            "Ron 감소의 구동 이점을 만들지만, 현재 결과처럼 gds와 Drain-side Field가 "
            "증가하면 출력 저항과 전계 부담 측면의 비용이 생긴다. 목표 신뢰성, "
            "허용 Field, 구동 전류와 출력 저항을 함께 정해야 적절한 LDD 조건을 "
            "선택할 수 있다. Field Map은 공간 분포의 근거이며 breakdown·hot-carrier "
            "수명을 직접 예측하지 않고, 유효 Ron은 LDD 영역 저항만의 값이 아니다."
        )
    if topic_id == "channel_oxide_electrostatic_compensation":
        return (
            "얇은 Oxide는 짧은 Channel에서 SS와 DIBL을 완화했지만 Channel Length의 "
            "영향을 제거하지는 않았다. Short·Thin의 DIBL은 Long·Thin보다 높고 "
            "Ioff도 증가했으므로 Gate 제어 개선, 잔여 Drain coupling과 누설을 "
            "서로 다른 평가 축으로 봐야 한다. 상호작용은 Long·Thick→Long·Thin과 "
            "Short·Thick→Short·Thin의 대응 차이로 판단한다. 대각선 두 조건의 "
            "차이는 L과 T를 동시에 섞고, global Field 최대값은 공간적 장벽 제어를 "
            "대신하지 못한다. 수치는 현재 모델·bias·추출법의 결과이다."
        )
    if topic_id == "source_drain_ldd_junction_engineering":
        return (
            "최대 Ion과 최소 Ron은 구동 중심 목표에는 유리하지만 Ioff·DIBL 제한이 "
            "엄격한 목표에서는 HighSD·HighLDD가 최적이 아닐 수 있다. 따라서 최대 "
            "구동 조건을 보편적 최적 조건으로 보지 않는다. 유효 Ron을 "
            "개별 영역 저항의 단순 합으로 분해하지 않고, 대각선 두 조건의 차이로 "
            "SD와 LDD 효과를 각각 확정하지 않는다. Field hotspot도 전체 접합 성능 "
            "순위나 신뢰성 수명을 직접 제공하지 않는다."
        )
    if topic_id == "integrated_device_design":
        return (
            "한 지표의 큰 여유는 다른 제약의 실패를 상쇄하지 않는다. Balanced는 "
            "현재 네 전기적 기준을 통과했지만 목표값이 달라지면 선택도 달라질 수 "
            "있다. Field Map은 전기적 사양 검사를 대체하지 않으며, 사양 통과가 "
            "breakdown·hot-carrier 신뢰성을 자동으로 입증하지도 않는다. 현재 결과는 "
            "학습 모델, bias와 추출 정의에 종속된 후보 선별 결과이다."
        )
    return (
        "현재 시뮬레이션에서 직접 확인한 결과와 일반 이론을 구분하고, 추출법과 bias "
        "조건 및 모델 한계를 함께 밝혀야 한다."
    )


def build_grounded_model_answer(
    topic: TopicConfig,
    context: LearningAnalysisContext,
) -> str:
    experiment = context.experiment
    changed = str(experiment.get("changed_parameter", ""))
    before = experiment.get("before")
    after = experiment.get("after")
    unit = PARAMETER_UNITS.get(changed, "")
    parameter = PARAMETER_LABELS.get(changed, changed or "실험 파라미터")
    condition = (
        "이번 Case는 L=700/300 nm와 T=20/10 nm의 네 조건을 사용한다. "
        "Long과 Short에서 각각 Thick→Thin 변화를 구한 뒤 두 변화의 차이를 "
        "비교하며, 전기적 파라미터 표는 Short 조건의 T 20→10 nm 결과를 표시한다."
        if topic.topic_id == "channel_oxide_electrostatic_compensation"
        else (
            "이번 Case는 SD=10¹⁹/10²⁰ cm⁻³와 LDD=5×10¹⁷/5×10¹⁸ cm⁻³의 "
            "2×2 접합 조건을 비교한다. 전기적 파라미터 표는 High SD의 "
            "LowLDD→HighLDD pair를 표시한다."
            if topic.topic_id == "source_drain_ldd_junction_engineering"
            else (
                "이번 Case는 Drive·Leakage·Control·Balanced 네 후보를 목표 사양으로 "
                "선별한다. 전기적 파라미터 표는 Control→Balanced 비교를 표시하고 "
                "전체 후보 값은 통합 해석에서 함께 대조한다."
                if topic.topic_id == "integrated_device_design"
                else (
                    f"이번 Case는 {parameter}만 {_format_number(before)} {unit}에서 "
                    f"{_format_number(after)} {unit}로 변경하고 나머지 조건을 고정한 비교이다."
                )
            )
        )
    )
    metric_lines = [
        _change_line(topic.topic_id, name, change)
        for name, change in context.electrical_changes.items()
        if change.available
    ]
    metrics = "\n".join(metric_lines) or (
        "- 유효하게 추출된 전기적 파라미터가 부족하므로 Curve 자체의 방향만 확인한다."
    )
    return (
        f"[현재 Case의 핵심 메커니즘]\n{condition} {_case_mechanism(topic.topic_id)}\n\n"
        f"[전기적 파라미터별 변화와 원인]\n{metrics}\n\n"
        f"[현재 Case의 I–V 근거]\n{_curve_evidence_lines(topic.topic_id, context)}\n\n"
        f"[현재 Case의 Field Map 근거]\n{_field_evidence_lines(topic.topic_id, context)}\n\n"
        f"[Curve–파라미터–Field 통합 해석]\n"
        f"{_integrated_interpretation(topic.topic_id, context)}\n\n"
        f"[Trade-off와 해석 한계]\n{_tradeoff_and_limits(topic.topic_id)}\n\n"
        "[일반 해석 원칙]\n"
        "Curve는 전기적 응답의 형태, 파라미터 표는 동일한 정의로 추출한 정량 결과, "
        "Field Map은 원인과 연결할 공간 분포를 보여준다. Curve는 동일한 축과 bias에서, "
        "Field는 동일한 display와 color scale에서 비교한다. 현재 Case에서 검증되지 "
        "않은 가상 조건이나 자유질문의 추가 실험은 이 모범 답안에 포함하지 않는다."
    )
