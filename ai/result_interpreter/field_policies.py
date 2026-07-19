from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldExplanationPolicy:
    display: str
    evidence_priority: tuple[str, ...]
    region_priority: tuple[str, ...]
    allowed_implications: frozenset[str]
    category: str

    def evidence_score(self, evidence_type: str) -> float:
        try: return 1.0 - self.evidence_priority.index(evidence_type) * .04
        except ValueError: return .5

    def region_score(self, region: str | None) -> float:
        try: return .03 - self.region_priority.index(region) * .003
        except ValueError: return 0.0


COMMON_IMPLICATIONS = frozenset({"potential_gradient_strengthened", "potential_gradient_weakened", "inversion_layer_expanded",
                                 "inversion_layer_contracted", "channel_carrier_population_increased", "channel_carrier_population_decreased",
                                 "current_path_more_continuous", "current_path_less_continuous", "current_crowding_strengthened",
                                 "current_crowding_weakened", "field_crowding_strengthened", "field_crowding_weakened",
                                 "depletion_region_expanded", "depletion_region_contracted", "channel_entry_more_restricted", "channel_entry_less_restricted"})

FIELD_POLICY_REGISTRY = {
    "potential": FieldExplanationPolicy("potential", ("contour_spacing_change", "regional_level_change", "high_value_area_change", "distribution_width_change", "hotspot_location_shift", "regional_level"),
        ("channel_near_surface", "drain_side_ldd_near_surface", "drain_near_surface", "source_side_ldd_near_surface"), COMMON_IMPLICATIONS & {"potential_gradient_strengthened", "potential_gradient_weakened"}, "potential"),
    "electric_field": FieldExplanationPolicy("electric_field", ("hotspot_strength_change", "hotspot_location_shift", "high_value_area_change", "crowding_change", "distribution_width_change", "regional_level_change", "regional_level"),
        ("drain_side_ldd_near_surface", "drain_near_surface", "source_side_ldd_near_surface", "channel_near_surface", "oxide"), COMMON_IMPLICATIONS & {"field_crowding_strengthened", "field_crowding_weakened", "potential_gradient_strengthened", "potential_gradient_weakened"}, "electric_field"),
    "electron_density": FieldExplanationPolicy("electron_density", ("path_connectivity_change", "distribution_width_change", "regional_level_change", "high_value_area_change", "hotspot_location_shift", "regional_level"),
        ("channel_near_surface", "source_side_ldd_near_surface", "drain_side_ldd_near_surface", "source_near_surface", "drain_near_surface"), COMMON_IMPLICATIONS & {"inversion_layer_expanded", "inversion_layer_contracted", "channel_carrier_population_increased", "channel_carrier_population_decreased"}, "electron_density"),
    "hole_density": FieldExplanationPolicy("hole_density", ("distribution_width_change", "regional_level_change", "high_value_area_change", "hotspot_location_shift", "regional_level"),
        ("channel_near_surface", "deep_bulk", "source_near_surface", "drain_near_surface"), COMMON_IMPLICATIONS & {"depletion_region_expanded", "depletion_region_contracted"}, "hole_density"),
    "electron_current_density": FieldExplanationPolicy("electron_current_density", ("path_connectivity_change", "crowding_change", "high_value_area_change", "distribution_width_change", "hotspot_strength_change", "hotspot_location_shift", "regional_level_change"),
        ("channel_near_surface", "source_side_ldd_near_surface", "drain_side_ldd_near_surface", "drain_near_surface", "global"), COMMON_IMPLICATIONS & {"current_path_more_continuous", "current_path_less_continuous", "current_crowding_strengthened", "current_crowding_weakened"}, "current_density"),
    "hole_current_density": FieldExplanationPolicy("hole_current_density", ("regional_level_change", "hotspot_strength_change", "hotspot_location_shift", "high_value_area_change", "path_connectivity_change", "crowding_change"),
        ("drain_near_surface", "source_near_surface", "deep_bulk", "drain_side_ldd_near_surface", "global"), COMMON_IMPLICATIONS & {"current_path_more_continuous", "current_path_less_continuous"}, "hole_current_density"),
    "total_current_density": FieldExplanationPolicy("total_current_density", ("path_connectivity_change", "crowding_change", "high_value_area_change", "distribution_width_change", "hotspot_strength_change", "hotspot_location_shift", "regional_level_change"),
        ("channel_near_surface", "source_side_ldd_near_surface", "drain_side_ldd_near_surface", "drain_near_surface", "global"), COMMON_IMPLICATIONS & {"current_path_more_continuous", "current_path_less_continuous", "current_crowding_strengthened", "current_crowding_weakened"}, "current_density"),
    "srh_recombination": FieldExplanationPolicy("srh_recombination", ("hotspot_strength_change", "high_value_area_change", "hotspot_location_shift", "distribution_width_change", "regional_level_change", "regional_level"),
        ("drain_near_surface", "drain_side_ldd_near_surface", "source_near_surface", "source_side_ldd_near_surface", "channel_near_surface"), frozenset(), "srh"),
    "energy_band": FieldExplanationPolicy("energy_band", ("barrier_or_band_change", "hotspot_location_shift", "regional_level_change", "regional_level"),
        ("channel_near_surface", "oxide", "gate", "deep_bulk"), COMMON_IMPLICATIONS & {"channel_entry_more_restricted", "channel_entry_less_restricted", "potential_gradient_strengthened", "potential_gradient_weakened"}, "energy_band"),
}
