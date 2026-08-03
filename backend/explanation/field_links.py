from __future__ import annotations

from typing import Any


FIELD_LINK_VERSION = "1.0"
MAX_FIELD_LINKS = 4

# These are verification routes, not electrical conclusions.  A Field Map can
# motivate which I-V quantities to inspect, but cannot establish their change.
LINK_RULES: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "potential_gradient": (
        "전위 강하가 집중되는 위치와 범위는 Gate와 Drain의 정전기적 제어가 "
        "어느 영역에 강하게 작용하는지 보여줍니다.",
        ("vth", "dibl", "ioff"),
        ("potential", "electric_field", "short_channel_effect"),
    ),
    "regional_potential": (
        "채널과 접합 부근의 전위 준위 변화는 캐리어가 넘어야 하는 장벽의 "
        "공간적 변화를 시사합니다.",
        ("vth", "dibl", "ioff"),
        ("potential", "source_barrier", "threshold_voltage"),
    ),
    "field_concentration": (
        "국부 전계 집중은 Drain 전위의 침투나 접합 스트레스가 커질 가능성을 "
        "보여주지만, 그 전기적 결과는 별도 곡선으로 확인해야 합니다.",
        ("dibl", "vth", "ioff", "gds"),
        ("electric_field", "short_channel_effect", "dibl"),
    ),
    "field_crowding": (
        "전계가 좁은 영역에 몰리면 국부 정전기적 영향과 신뢰성 위험 가능성이 "
        "커질 수 있습니다.",
        ("dibl", "ioff", "gds"),
        ("electric_field", "short_channel_effect"),
    ),
    "high_field_extent": (
        "높은 전계 영역의 범위 변화는 Drain-side 영향이 퍼지는 공간적 범위를 "
        "나타냅니다.",
        ("dibl", "vth", "ioff"),
        ("electric_field", "short_channel_effect"),
    ),
    "channel_carrier_population": (
        "채널 표면의 전자 분포는 inversion 형성과 전도 경로의 상태를 "
        "시사하지만 단자 전류와 같지는 않습니다.",
        ("ion", "gm_max", "ron", "vth"),
        ("on_current", "transconductance", "on_resistance"),
    ),
    "inversion_layer": (
        "inversion layer의 공간적 폭은 Gate가 형성한 전도 채널의 범위를 "
        "보여줍니다.",
        ("ion", "gm_max", "ron", "vth"),
        ("on_current", "transconductance", "threshold_voltage"),
    ),
    "carrier_path": (
        "Source에서 Drain으로 이어지는 캐리어 분포는 전도 경로의 연속성을 "
        "시사합니다.",
        ("ion", "ron", "gm_max"),
        ("on_current", "on_resistance"),
    ),
    "depletion_region": (
        "공핍 영역의 공간적 범위는 Gate 및 접합이 채널 전하를 제어하는 "
        "방식과 연결됩니다.",
        ("vth", "ss", "ioff"),
        ("depletion_region", "threshold_voltage", "subthreshold_swing"),
    ),
    "regional_hole_population": (
        "정공 분포 변화는 bulk와 접합 부근의 공핍 상태 변화를 시사합니다.",
        ("vth", "ss", "ioff"),
        ("depletion_region", "threshold_voltage"),
    ),
    "current_path": (
        "국부 current density 경로는 전류가 흐르는 위치를 보여주지만 단자에서 "
        "적분된 Drain current와 동일하지 않습니다.",
        ("ion", "ron", "gds"),
        ("on_current", "on_resistance", "output_conductance"),
    ),
    "current_crowding": (
        "국부 current crowding은 전류 경로의 병목이나 집중 가능성을 보여줍니다.",
        ("ion", "ron", "gds"),
        ("on_current", "on_resistance", "output_conductance"),
    ),
    "current_path_extent": (
        "고전류 밀도 영역의 범위는 전도 경로가 공간적으로 퍼지는 정도를 "
        "보여줍니다.",
        ("ion", "ron"),
        ("on_current", "on_resistance"),
    ),
    "srh_activity_magnitude": (
        "SRH activity의 크기 변화는 재결합·생성 활동이 집중된 위치를 "
        "보여주며 부호와 단자 영향은 별도로 확인해야 합니다.",
        ("ioff",),
        ("off_current",),
    ),
    "srh_activity_extent": (
        "SRH activity 영역의 범위는 재결합·생성 활동이 퍼진 공간을 "
        "보여줍니다.",
        ("ioff",),
        ("off_current",),
    ),
    "channel_entry_barrier": (
        "Source-to-Channel 장벽 변화는 캐리어 주입 난이도의 공간적 변화를 "
        "직접적으로 보여줍니다.",
        ("vth", "ioff", "dibl"),
        ("source_barrier", "threshold_voltage", "dibl"),
    ),
    "vertical_band_bending": (
        "Gate 아래 surface-to-bulk band bending은 Gate가 표면 전위를 "
        "형성하고 채널 전하를 제어하는 공간적 변화를 보여줍니다.",
        ("vth", "ss", "gm_max"),
        ("surface_potential", "threshold_voltage", "gate_control"),
    ),
    "channel_band_slope": (
        "채널 방향 Energy band 기울기는 Source-side에서 Drain-side로 "
        "이어지는 전위 강하와 채널 내 전계 분포를 보여줍니다.",
        ("dibl", "gds", "ion"),
        ("potential_gradient", "electric_field", "channel_length_modulation"),
    ),
}


def build_cross_domain_links(
    conclusions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    used: set[tuple[str | None, str]] = set()
    for conclusion in conclusions:
        concept = str(conclusion.get("concept", ""))
        rule = LINK_RULES.get(concept)
        key = (conclusion.get("comparison_id"), concept)
        if rule is None or key in used:
            continue
        meaning, metrics, theory = rule
        links.append({
            "link_id": f"fdl_{len(links) + 1}",
            "link_version": FIELD_LINK_VERSION,
            "field_display": conclusion.get("field_display"),
            "source_concept": concept,
            "source_assessment": conclusion.get("assessment"),
            "region": conclusion.get("region"),
            "physical_interpretation": meaning,
            "iv_metrics_to_check": list(metrics),
            "theory_concepts": list(theory),
            "evidence_ids": list(conclusion.get("evidence_ids", [])),
            "comparison_id": conclusion.get("comparison_id"),
            "link_status": "requires_iv_verification",
            "claim_limit": "field_observation_not_electrical_result",
        })
        used.add(key)
        if len(links) >= MAX_FIELD_LINKS:
            break
    return links


def validate_cross_domain_links(
    links: list[dict[str, Any]],
    payload: Any,
) -> None:
    evidence_ids = {item["evidence_id"] for item in payload.evidence}
    if len(links) > MAX_FIELD_LINKS:
        raise ValueError("Too many Field-to-I-V links.")
    for item in links:
        if item.get("source_concept") not in LINK_RULES:
            raise ValueError("Unknown Field-to-I-V concept.")
        if not set(item.get("evidence_ids", [])).issubset(evidence_ids):
            raise ValueError("Field-to-I-V link references unknown Evidence.")
        if item.get("link_status") != "requires_iv_verification":
            raise ValueError("Field-to-I-V link cannot claim verification.")
        if item.get("claim_limit") != "field_observation_not_electrical_result":
            raise ValueError("Field-to-I-V claim limit is missing.")
