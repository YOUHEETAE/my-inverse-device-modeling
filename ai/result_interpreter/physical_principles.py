from __future__ import annotations

from typing import Any


def expected(quantity: str, observation: str, weight: float = 1.0, **selectors: Any) -> dict[str, Any]:
    return {"quantity": quantity, "expected_observation": observation, "weight": weight, **selectors}


PHYSICAL_PRINCIPLES: dict[tuple[str, str], list[dict[str, Any]]] = {
    ("channel_length", "increased"): [
        {"principle_id": "channel_length_increase_reduces_sce", "target_concept": "short_channel_control",
         "statement_key": "channel_length_increase_may_reduce_short_channel_effect",
         "expected_evidence": [expected("dibl", "decreased"), expected("ioff", "decreased", .8),
                               expected("potential_contour_spacing", "widened", .8, evidence_type="contour_spacing_change"),
                               expected("electric_field_magnitude", "weakened", .8, evidence_type="hotspot_strength_change", region_contains="drain"),
                               expected("electric_field_magnitude", "contracted", .7, evidence_type="high_value_area_change", region_contains="drain"),
                               expected("channel_entry_barrier", "raised", .6)]},
        {"principle_id": "channel_length_increase_raises_channel_resistance", "target_concept": "drive_performance",
         "statement_key": "channel_length_increase_may_raise_channel_resistance",
         "expected_evidence": [expected("ion", "decreased"), expected("gm_max", "decreased", .7), expected("ron", "increased")]},
    ],
    ("channel_length", "decreased"): [
        {"principle_id": "channel_length_decrease_may_increase_sce", "target_concept": "short_channel_control",
         "statement_key": "channel_length_decrease_may_increase_short_channel_effect",
         "expected_evidence": [expected("dibl", "increased"), expected("ioff", "increased", .8)]},
        {"principle_id": "channel_length_decrease_reduces_channel_resistance", "target_concept": "drive_performance",
         "statement_key": "channel_length_decrease_may_reduce_channel_resistance",
         "expected_evidence": [expected("ion", "increased"), expected("gm_max", "increased", .7), expected("ron", "decreased")]},
    ],
    ("oxide_thickness", "decreased"): [
        {"principle_id": "oxide_thickness_decrease_strengthens_gate_control", "target_concept": "gate_control",
         "statement_key": "oxide_thickness_decrease_may_strengthen_gate_control",
         "expected_evidence": [expected("ion", "increased", .8), expected("gm_max", "increased"), expected("ss", "decreased"),
                               expected("electron_density", "increased", .7, region_contains="channel"),
                               expected("electron_density", "widened", .7, evidence_type="distribution_width_change", region_contains="channel")]},
        {"principle_id": "oxide_thickness_decrease_may_raise_oxide_field", "target_concept": "junction_field",
         "statement_key": "oxide_thickness_decrease_may_raise_oxide_field",
         "expected_evidence": [expected("electric_field_magnitude", "strengthened", .8, evidence_type="hotspot_strength_change", region_contains="oxide")]},
    ],
    ("oxide_thickness", "increased"): [
        {"principle_id": "oxide_thickness_increase_weakens_gate_control", "target_concept": "gate_control",
         "statement_key": "oxide_thickness_increase_may_weaken_gate_control",
         "expected_evidence": [expected("ion", "decreased", .8), expected("gm_max", "decreased"), expected("ss", "increased")]},
    ],
    ("bulk_doping", "increased"): [
        {"principle_id": "bulk_doping_change_modifies_depletion", "target_concept": "gate_control",
         "statement_key": "bulk_doping_change_may_modify_depletion", "expected_evidence": [expected("bulk_depletion", "context_dependent")]},
        {"principle_id": "bulk_doping_change_modifies_threshold_behavior", "target_concept": "gate_control",
         "statement_key": "bulk_doping_change_may_modify_threshold_behavior", "expected_evidence": [expected("vth_at_vd_0_05", "context_dependent")]},
    ],
    ("bulk_doping", "decreased"): [
        {"principle_id": "bulk_doping_change_modifies_depletion", "target_concept": "gate_control",
         "statement_key": "bulk_doping_change_may_modify_depletion", "expected_evidence": [expected("bulk_depletion", "context_dependent")]},
        {"principle_id": "bulk_doping_change_modifies_threshold_behavior", "target_concept": "gate_control",
         "statement_key": "bulk_doping_change_may_modify_threshold_behavior", "expected_evidence": [expected("vth_at_vd_0_05", "context_dependent")]},
    ],
    ("source_drain_doping", "increased"): [
        {"principle_id": "source_drain_doping_increase_reduces_series_resistance", "target_concept": "series_resistance",
         "statement_key": "source_drain_doping_increase_may_reduce_series_resistance",
         "expected_evidence": [expected("ion", "increased"), expected("ron", "decreased"), expected("total_current_density_magnitude", "expanded", .7, evidence_type="high_value_area_change")]},
        {"principle_id": "source_drain_doping_increase_may_raise_junction_field", "target_concept": "junction_field",
         "statement_key": "source_drain_doping_increase_may_raise_junction_field",
         "expected_evidence": [expected("electric_field_magnitude", "strengthened", .8, evidence_type="hotspot_strength_change")]},
    ],
    ("source_drain_doping", "decreased"): [
        {"principle_id": "source_drain_doping_decrease_raises_series_resistance", "target_concept": "series_resistance",
         "statement_key": "source_drain_doping_decrease_may_raise_series_resistance",
         "expected_evidence": [expected("ion", "decreased"), expected("ron", "increased")]},
    ],
    ("ldd_doping", "increased"): [
        {"principle_id": "ldd_doping_increase_reduces_extension_resistance", "target_concept": "series_resistance",
         "statement_key": "ldd_doping_increase_may_reduce_extension_resistance",
         "expected_evidence": [expected("ion", "increased"), expected("ron", "decreased")]},
        {"principle_id": "ldd_doping_increase_may_concentrate_drain_field", "target_concept": "drain_field_management",
         "statement_key": "ldd_doping_increase_may_concentrate_drain_field",
         "expected_evidence": [expected("electric_field_magnitude", "strengthened", .9, evidence_type="hotspot_strength_change", region_contains="drain"),
                               expected("electric_field_magnitude", "expanded", .7, evidence_type="high_value_area_change", region_contains="drain")]},
    ],
    ("ldd_doping", "decreased"): [
        {"principle_id": "ldd_doping_decrease_spreads_potential_drop", "target_concept": "drain_field_management",
         "statement_key": "ldd_doping_decrease_may_spread_potential_drop",
         "expected_evidence": [expected("potential_contour_spacing", "widened", .8, region_contains="drain"),
                               expected("electric_field_magnitude", "weakened", .9, evidence_type="hotspot_strength_change", region_contains="drain")]},
        {"principle_id": "ldd_doping_decrease_raises_extension_resistance", "target_concept": "series_resistance",
         "statement_key": "ldd_doping_decrease_may_raise_extension_resistance",
         "expected_evidence": [expected("ion", "decreased"), expected("ron", "increased")]},
    ],
}

TARGET_CONCEPTS = {"short_channel_control", "gate_control", "drive_performance", "series_resistance", "saturation_behavior",
                   "drain_field_management", "channel_inversion", "current_transport", "junction_field", "recombination_activity", "energy_barrier"}

FORBIDDEN_CLAIM_TERMS = ["proved", "demonstrated_causality", "sole_cause", "necessarily_caused", "guaranteed",
                         "증명", "입증", "유일한 원인", "반드시 유발", "완전히 최적", "성능이 절대적으로 우수"]
