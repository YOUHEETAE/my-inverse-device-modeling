from __future__ import annotations

from typing import Any


# These definitions describe general device-physics paths. A path is promoted
# into an explanation only when the current controlled comparison contains at
# least one matching, eligible observation.
MECHANISM_SPECS: dict[tuple[str, str], tuple[dict[str, Any], ...]] = {
    ("channel_length", "decreased"): (
        {
            "mechanism_key": "channel_resistance_reduction",
            "concept": "drive_performance",
            "process_steps": (
                "shorter_effective_transport_path",
                "lower_channel_resistance",
                "stronger_drive_current",
            ),
            "expectations": {
                "ion": "increased", "gm_max": "increased", "ron": "decreased",
            },
            "priority": 10,
        },
        {
            "mechanism_key": "drain_barrier_coupling_increase",
            "concept": "short_channel_control",
            "process_steps": (
                "larger_relative_drain_electrostatic_coupling",
                "lower_source_side_injection_barrier",
                "threshold_lowering_and_off_state_injection",
            ),
            "expectations": {
                "dibl": "increased",
                "vth_at_vd_0_05": "decreased",
                "vth_at_vd_1_5": "decreased",
                "ioff": "increased",
            },
            "priority": 20,
        },
        {
            "mechanism_key": "subthreshold_control_weakened",
            "concept": "subthreshold_behavior",
            "process_steps": (
                "weaker_relative_gate_control",
                "less_steep_subthreshold_turn_off",
                "larger_off_state_penalty",
            ),
            "expectations": {
                "ss": "increased",
                "ioff": "increased",
                "ion_ioff_ratio": "decreased",
            },
            "priority": 30,
        },
        {
            "mechanism_key": "saturation_control_weakened",
            "concept": "saturation_behavior",
            "process_steps": (
                "stronger_drain_influence_on_short_channel",
                "larger_output_current_slope",
                "weaker_current_saturation",
            ),
            "expectations": {"gds": "increased", "lambda_clm": "increased"},
            "priority": 40,
        },
    ),
    ("channel_length", "increased"): (
        {
            "mechanism_key": "channel_resistance_increase",
            "concept": "drive_performance",
            "process_steps": (
                "longer_effective_transport_path",
                "higher_channel_resistance",
                "weaker_drive_current",
            ),
            "expectations": {
                "ion": "decreased", "gm_max": "decreased", "ron": "increased",
            },
            "priority": 10,
        },
        {
            "mechanism_key": "drain_barrier_coupling_decrease",
            "concept": "short_channel_control",
            "process_steps": (
                "smaller_relative_drain_electrostatic_coupling",
                "better_preserved_source_side_injection_barrier",
                "improved_threshold_and_off_state_control",
            ),
            "expectations": {
                "dibl": "decreased",
                "vth_at_vd_0_05": "increased",
                "vth_at_vd_1_5": "increased",
                "ioff": "decreased",
            },
            "priority": 20,
        },
        {
            "mechanism_key": "subthreshold_control_strengthened",
            "concept": "subthreshold_behavior",
            "process_steps": (
                "stronger_relative_gate_control",
                "steeper_subthreshold_turn_off",
                "smaller_off_state_penalty",
            ),
            "expectations": {
                "ss": "decreased",
                "ioff": "decreased",
                "ion_ioff_ratio": "increased",
            },
            "priority": 30,
        },
        {
            "mechanism_key": "saturation_control_strengthened",
            "concept": "saturation_behavior",
            "process_steps": (
                "weaker_drain_influence_on_channel",
                "smaller_output_current_slope",
                "stronger_current_saturation",
            ),
            "expectations": {"gds": "decreased", "lambda_clm": "decreased"},
            "priority": 40,
        },
    ),
    ("oxide_thickness", "decreased"): (
        {
            "mechanism_key": "gate_coupling_strengthened",
            "concept": "gate_control",
            "process_steps": (
                "larger_gate_capacitance_per_area",
                "stronger_gate_to_channel_coupling",
                "stronger_inversion_and_subthreshold_control",
            ),
            "expectations": {
                "ion": "increased", "gm_max": "increased", "ss": "decreased",
            },
            "priority": 10,
        },
    ),
    ("oxide_thickness", "increased"): (
        {
            "mechanism_key": "gate_coupling_weakened",
            "concept": "gate_control",
            "process_steps": (
                "smaller_gate_capacitance_per_area",
                "weaker_gate_to_channel_coupling",
                "weaker_inversion_and_subthreshold_control",
            ),
            "expectations": {
                "ion": "decreased", "gm_max": "decreased", "ss": "increased",
            },
            "priority": 10,
        },
    ),
    ("source_drain_doping", "increased"): (
        {
            "mechanism_key": "series_resistance_reduction",
            "concept": "series_resistance",
            "process_steps": (
                "higher_terminal_region_conductivity",
                "lower_source_drain_series_resistance",
                "stronger_terminal_current_delivery",
            ),
            "expectations": {"ion": "increased", "ron": "decreased"},
            "priority": 10,
        },
    ),
    ("source_drain_doping", "decreased"): (
        {
            "mechanism_key": "series_resistance_increase",
            "concept": "series_resistance",
            "process_steps": (
                "lower_terminal_region_conductivity",
                "higher_source_drain_series_resistance",
                "weaker_terminal_current_delivery",
            ),
            "expectations": {"ion": "decreased", "ron": "increased"},
            "priority": 10,
        },
    ),
    ("ldd_doping", "increased"): (
        {
            "mechanism_key": "extension_resistance_reduction",
            "concept": "series_resistance",
            "process_steps": (
                "higher_ldd_region_conductivity",
                "lower_extension_resistance",
                "stronger_drive_current",
            ),
            "expectations": {"ion": "increased", "ron": "decreased"},
            "priority": 10,
        },
    ),
    ("ldd_doping", "decreased"): (
        {
            "mechanism_key": "extension_resistance_increase",
            "concept": "series_resistance",
            "process_steps": (
                "lower_ldd_region_conductivity",
                "higher_extension_resistance",
                "weaker_drive_current",
            ),
            "expectations": {"ion": "decreased", "ron": "increased"},
            "priority": 10,
        },
    ),
    ("bulk_doping", "increased"): (
        {
            "mechanism_key": "depletion_threshold_redistribution",
            "concept": "gate_control",
            "process_steps": (
                "modified_depletion_charge",
                "modified_surface_potential_condition",
                "shifted_threshold_behavior",
            ),
            "expectations": {
                "vth_at_vd_0_05": "changed",
                "vth_at_vd_1_5": "changed",
            },
            "priority": 10,
        },
    ),
    ("bulk_doping", "decreased"): (
        {
            "mechanism_key": "depletion_threshold_redistribution",
            "concept": "gate_control",
            "process_steps": (
                "modified_depletion_charge",
                "modified_surface_potential_condition",
                "shifted_threshold_behavior",
            ),
            "expectations": {
                "vth_at_vd_0_05": "changed",
                "vth_at_vd_1_5": "changed",
            },
            "priority": 10,
        },
    ),
}


def _matches(observation: str, expected: str) -> bool:
    return observation in {"increased", "decreased"} if expected == "changed" else observation == expected


def build_iv_mechanism_chains(
    comparisons: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    chains: list[dict[str, Any]] = []
    for comparison in comparisons:
        # A mechanism is used as a direct explanation only for a controlled
        # one-parameter comparison. Multi-parameter cases retain descriptive
        # observations because individual contributions cannot be isolated.
        if (
            comparison.get("changed_parameter_count") != 1
            or comparison.get("effective_claim_level") != "controlled_association"
        ):
            continue
        change = comparison.get("changed_parameters", [])[0]
        specs = MECHANISM_SPECS.get(
            (str(change.get("parameter")), str(change.get("direction"))),
            (),
        )
        available = [
            item
            for item in evidence
            if item.get("comparison_id") == comparison.get("comparison_id")
            and item.get("evidence_type") == "metric_change"
            and item.get("eligible_for_output", False)
            and item.get("confidence") in {"medium", "high"}
            and item.get("magnitude_class") != "negligible"
        ]
        for spec in specs:
            relevant = [
                item
                for item in available
                if item.get("quantity") in spec["expectations"]
            ]
            supporting = [
                item for item in relevant
                if _matches(
                    str(item.get("observation")),
                    str(spec["expectations"][item["quantity"]]),
                )
            ]
            conflicting = [item for item in relevant if item not in supporting]
            if not supporting:
                continue
            alignment = "partial" if conflicting else "consistent"
            high_quality = [
                item for item in supporting
                if item.get("confidence") == "high"
                and item.get("magnitude_class") in {"moderate", "major", "critical"}
            ]
            support_level = (
                "strongly_supported"
                if len(high_quality) >= 2
                else ("supported" if high_quality or len(supporting) >= 2 else "tentative")
            )
            chains.append({
                "mechanism_id": (
                    f"mechanism_{comparison['comparison_id']}_"
                    f"{spec['mechanism_key']}"
                ),
                "comparison_id": comparison["comparison_id"],
                "parameter": change["parameter"],
                "change_direction": change["direction"],
                "mechanism_key": spec["mechanism_key"],
                "target_concept": spec["concept"],
                "process_steps": list(spec["process_steps"]),
                "expected_metric_directions": dict(spec["expectations"]),
                "observed_metric_links": [
                    {
                        "quantity": item["quantity"],
                        "observation": item["observation"],
                        "evidence_id": item["evidence_id"],
                    }
                    for item in supporting
                ],
                "supporting_evidence_ids": [
                    item["evidence_id"] for item in supporting
                ],
                "conflicting_evidence_ids": [
                    item["evidence_id"] for item in conflicting
                ],
                "alignment": alignment,
                "support_level": support_level,
                "claim_level": comparison["effective_claim_level"],
                "priority": int(spec["priority"]),
            })
    return chains
