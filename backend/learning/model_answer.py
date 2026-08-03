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
                "이번 증가는 지정된 off bias에서 추출된 Drain 전류의 관찰 결과다. "
                "얇은 oxide가 Ioff를 반드시 늘린다는 뜻은 아니며, Vth 위치와 "
                "subthreshold Curve가 해당 bias에서 어떻게 이동했는지 함께 봐야 한다. "
                "이 값은 oxide tunneling 전류와 동일한 지표도 아니다."
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
            else:
                statement += (
                    " 다만 oxide 또는 Gate 인접 영역의 관찰이 아니므로, oxide 두께가 "
                    "Gate control이나 신뢰성에 미친 직접 근거로 사용하지 않는다."
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
        return (
            "Oxide 두께 감소는 Cox를 키워 Gate 전압 변화가 채널 표면 전위와 inversion "
            "charge에 더 강하게 전달되도록 한다. 이번 표에서 확인된 방향은 "
            f"gm {OBSERVATION_LABELS.get(gm_direction, '미확인')}, "
            f"SS {OBSERVATION_LABELS.get(directions.get('ss', ''), '미확인')}, "
            f"Ioff {OBSERVATION_LABELS.get(directions.get('ioff', ''), '미확인')}이다. "
            "Curve의 dId/dVg와 log(Id)–Vg 기울기는 Gate control의 전기적 결과이고, "
            "Gate/oxide/channel 인접 Field 분포는 이를 뒷받침할 공간 단서이다. "
            "Drain 부근 Field 변화만으로 oxide 결합 개선이나 breakdown을 확정할 수 없다."
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
            "gm 증가와 SS 감소는 Gate control의 이점이지만 Ioff, oxide 전계와 신뢰성은 "
            "별도로 평가해야 한다. 현재 Field hotspot은 추가 점검의 단서일 뿐 "
            "breakdown을 확정하지 않으며, 터널링 모델이 없다면 이 Ioff를 oxide "
            "tunneling 전류라고 해석해서도 안 된다."
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
        f"이번 Case는 {parameter}만 {_format_number(before)} {unit}에서 "
        f"{_format_number(after)} {unit}로 변경하고 나머지 조건을 고정한 비교이다."
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
