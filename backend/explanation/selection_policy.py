IMPORTANCE_POLICY = {
    "metric_weights": {"ion": 1.0, "ioff": 1.0, "ion_ioff_ratio": .95, "ss": .90, "dibl": .95,
                       "vth_at_vd_0_05": .85, "vth_at_vd_1_5": .80, "gm_max": .80, "ron": .85,
                       "gds": .70, "lambda_clm": .70, "drain_current": .55, "idvg_transition_position": .50},
    "field_feature_weights": {"hotspot_location_shift": 1.0, "hotspot_strength_change": .95, "high_value_area_change": .90,
                              "path_connectivity_change": 1.0, "crowding_change": .95, "barrier_or_band_change": .90,
                              "contour_spacing_change": .85, "distribution_width_change": .80, "regional_level_change": .70,
                              # A robust regional ranking is the primary usable
                              # observation when only one Field map is selected.
                              "regional_level": .65, "global_statistic": .35},
    "magnitude_weights": {"negligible": 0.0, "minor": .35, "moderate": .65, "major": .90, "critical": 1.0, "not_applicable": .70},
    "confidence_weights": {"low": .20, "medium": .70, "high": 1.0},
    "comparison_role_weights": {"primary_baseline_to_variant": 1.0, "variant_to_variant": .65},
    "claim_quality_weights": {"cross_validated_controlled_association": 1.0, "controlled_association": .90,
                              "multi_parameter_association": .70, "descriptive_only": .60},
    "warning_penalties": {"extrapolation": .55, "multiple_parameter_change": .80, "missing_region": 0.0,
                          "invalid_numeric_value": 0.0, "parameter_extraction_failed": 0.0,
                          "weak_visual_evidence": .50, "model_approximation": .75},
    "priority_thresholds": {"essential": .85, "high": .70, "medium": .50, "low": .30},
    "uniqueness_weights": {"unique": 1.0, "related": .85, "partial_duplicate": .55, "duplicate": 0.0},
    "tradeoff_min_magnitude": "minor", "tradeoff_min_confidence": "medium",
    "variant_effect_min_separation": 5.0,
}

IV_GROUPS = {"vth_at_vd_0_05": "threshold_behavior", "vth_at_vd_1_5": "threshold_behavior",
             "ioff": "switching_control", "ion_ioff_ratio": "switching_control", "ss": "switching_control", "dibl": "switching_control",
             "ion": "drive_performance", "gm_max": "drive_performance", "ron": "drive_performance",
             "gds": "saturation_behavior", "lambda_clm": "saturation_behavior", "drain_current": "curve_shape", "idvg_transition_position": "curve_shape"}

FIELD_GROUPS = {"contour_spacing_change": "potential_distribution", "hotspot_strength_change": "field_concentration",
                "hotspot_location_shift": "field_concentration", "high_value_area_change": "field_concentration",
                "path_connectivity_change": "current_transport", "crowding_change": "current_crowding",
                "barrier_or_band_change": "energy_barrier", "regional_level": "carrier_distribution"}

SUMMARY_KEYS = {
    "short_channel_control_vs_drive_performance": ("short_channel_control_improved", "drive_performance_degraded"),
    "drive_current_vs_off_state_leakage": ("drive_performance_improved", "off_state_leakage_degraded"),
    "gate_control_vs_oxide_field": ("gate_control_improved", "oxide_field_concentration_increased"),
    "series_resistance_vs_drain_field": ("series_resistance_improved", "drain_field_concentration_increased"),
    "current_spreading_vs_current_crowding": ("current_spreading_improved", "current_crowding_increased"),
    "drive_performance_vs_saturation_behavior": ("drive_performance_improved", "saturation_behavior_degraded"),
    "field_reduction_vs_extension_resistance": ("drain_field_concentration_decreased", "extension_resistance_degraded"),
    "channel_inversion_vs_field_concentration": ("channel_inversion_strengthened", "field_concentration_increased"),
}
