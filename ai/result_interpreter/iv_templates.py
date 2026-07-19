IV_TEMPLATES = {
    "single.condition": "{curve}의 Id–Vd 및 Id–Vg 예측 결과와 추출된 전기 파라미터를 기준으로 특성을 분석했습니다.",
    "single.switching": "Switching 특성은 {metrics}을 통해 off-state control과 short-channel behavior를 확인할 수 있습니다.",
    "single.drive": "Drive 특성은 {metrics} 값으로 구성되며 전류 구동, Gate 응답 및 전도 저항을 나타냅니다.",
    "single.saturation": "Saturation 특성은 {metrics}로 평가되며 Drain voltage 증가에 따른 전류 변화 정도를 나타냅니다.",
    "condition.same": "{baseline}과 {candidate}의 device parameter 조건은 동일합니다.",
    "condition.single.increased": "{baseline} 대비 {candidate}에서는 {parameter}만 {before}에서 {after}로 증가했습니다.",
    "condition.single.decreased": "{baseline} 대비 {candidate}에서는 {parameter}만 {before}에서 {after}로 감소했습니다.",
    "condition.multi.two": "{baseline} 대비 {candidate}에서는 {first}와 {second}가 함께 변경되었습니다.",
    "condition.multi.many": "{baseline} 대비 {candidate}에서는 {parameters}를 포함한 여러 device parameter가 함께 변경되었습니다.",
    "principle.channel_length_increase_reduces_sce": "일반적으로 Channel length 증가는 short-channel effect와 DIBL을 완화할 수 있습니다.",
    "principle.channel_length_increase_raises_channel_resistance": "한편 Channel length 증가는 Channel resistance를 높여 Drive performance를 낮출 수 있습니다.",
    "principle.channel_length_decrease_may_increase_sce": "일반적으로 Channel length 감소는 short-channel effect를 증가시킬 수 있습니다.",
    "principle.channel_length_decrease_reduces_channel_resistance": "한편 Channel length 감소는 Channel resistance를 낮출 수 있습니다.",
    "principle.oxide_thickness_decrease_strengthens_gate_control": "일반적으로 Tox 감소는 Gate-to-channel coupling과 Gate control을 강화할 수 있습니다.",
    "principle.oxide_thickness_increase_weakens_gate_control": "일반적으로 Tox 증가는 Gate-to-channel coupling을 약화할 수 있습니다.",
    "principle.source_drain_doping_increase_reduces_series_resistance": "일반적으로 Source/Drain doping 증가는 series resistance를 낮출 수 있습니다.",
    "principle.ldd_doping_increase_reduces_extension_resistance": "일반적으로 LDD doping 증가는 extension resistance를 낮출 수 있습니다.",
    "principle.ldd_doping_decrease_spreads_potential_drop": "일반적으로 LDD doping 감소는 Drain 측 Potential drop을 더 넓게 분산시킬 수 있습니다.",
    "comparison.observation": "이 모델 결과에서 {groups}.",
    "comparison.no_difference": "{baseline}과 {candidate}의 주요 I–V 특성은 현재 유의 기준 내에서 유사하게 나타났습니다.",
    "comparison.variant": "보조적으로 {baseline}과 {candidate}을 비교하면 {groups}.",
    "consistency.consistent": "관찰된 변화는 {concept}에 관한 일반적인 물리 경향과 일치합니다.",
    "consistency.partially_consistent": "{concept} 관련 지표가 서로 다른 방향을 보여 일반적인 경향과 부분적으로만 일치합니다.",
    "consistency.inconsistent": "관찰된 변화는 {concept}에 관한 일반적인 기대 방향과 다르게 나타났습니다.",
    "caution.single": "비교 기준이 없으므로 현재 값만으로 절대적인 개선·악화 또는 우수성을 판단하지 않습니다.",
    "caution.model": "이 결과는 학습 모델의 prediction이며 실제 측정 또는 TCAD 검증을 대체하지 않습니다.",
    "caution.multiple": "여러 parameter가 동시에 변경되어 관찰된 결과를 특정 parameter 하나의 영향으로 분리해 단정할 수 없습니다.",
    "caution.extrapolation": "학습 범위를 벗어난 extrapolation 조건이 포함되어 결과는 참고 경향으로 제한해 해석해야 합니다.",
    "caution.invalid": "일부 전기 파라미터를 유효하게 추출하지 못해 해당 항목은 해석에서 제외했습니다.",
    "fallback.description": "선택된 Curve에서 유효한 I–V 분석 결과를 충분히 확보하지 못했습니다.",
    "fallback.caution": "입력 데이터와 전기 파라미터 추출 상태를 확인해 주세요.",
}

PARAMETER_LABELS = {"channel_length": "Channel length", "oxide_thickness": "Oxide thickness(Tox)", "bulk_doping": "Bulk doping",
                    "source_drain_doping": "Source/Drain doping", "ldd_doping": "LDD doping"}
METRIC_LABELS = {"vth_at_vd_0_05": "Vth(Vd=0.05 V)", "vth_at_vd_1_5": "Vth(Vd=1.5 V)", "ion": "Ion", "ioff": "Ioff",
                 "ion_ioff_ratio": "Ion/Ioff", "ss": "SS", "dibl": "DIBL", "gm_max": "gm max", "gds": "gds",
                 "ron": "Ron", "lambda_clm": "lambda(Channel-length modulation)"}
CONCEPT_LABELS = {"short_channel_control": "short-channel control", "gate_control": "Gate control", "drive_performance": "Drive performance",
                  "series_resistance": "series resistance", "saturation_behavior": "Saturation", "drain_field_management": "Drain field management"}

TRADEOFF_TEMPLATES = {
    "short_channel_control_vs_drive_performance": "Short-channel control은 개선 방향을 보이지만 Drive performance는 저하 방향을 보여 Trade-off가 나타났습니다.",
    "drive_current_vs_off_state_leakage": "Drive current는 증가했지만 off-state leakage도 증가하는 방향의 Trade-off가 나타났습니다.",
    "gate_control_vs_oxide_field": "Gate control은 강화 방향을 보이지만 Oxide electric field도 강화되는 Trade-off가 나타났습니다.",
    "series_resistance_vs_drain_field": "Series resistance는 개선 방향을 보이지만 Drain-side electric field concentration은 강화되는 Trade-off가 나타났습니다.",
    "current_spreading_vs_current_crowding": "Current path는 넓어지는 방향을 보이지만 current crowding은 강화되는 Trade-off가 나타났습니다.",
    "drive_performance_vs_saturation_behavior": "Drive performance는 개선 방향을 보이지만 saturation behavior는 저하 방향을 보여 Trade-off가 나타났습니다.",
    "field_reduction_vs_extension_resistance": "Drain-side field는 완화되지만 extension resistance는 증가하는 방향의 Trade-off가 나타났습니다.",
    "channel_inversion_vs_field_concentration": "Channel inversion은 강화되지만 local electric-field concentration도 강화되는 Trade-off가 나타났습니다.",
}

IV_TEMPLATES.update({
    "multi_principle.oxide_thickness_increase_weakens_gate_control": "반면 Tox 증가는 Gate-to-channel coupling과 Gate control을 약화해 Ion과 gm을 낮추고 SS를 높이는 방향을 가집니다.",
    "multi_principle.channel_length_increase_reduces_sce": "일반적으로 Channel length 증가는 DIBL과 Ioff를 낮추는 방향을 가집니다.",
    "multi_principle.channel_length_increase_raises_channel_resistance": "동시에 긴 Channel은 Ion과 gm을 낮추고 Ron을 높이는 방향을 가집니다.",
    "multi_principle.oxide_thickness_decrease_strengthens_gate_control": "반면 Tox 감소는 Gate control을 강화해 Ion과 gm을 높이고 SS를 낮추는 방향을 가집니다.",
    "multi_principle.source_drain_doping_increase_reduces_series_resistance": "Source/Drain doping 증가는 series resistance를 낮춰 Ion을 높이고 Ron을 낮추는 방향을 가집니다.",
    "multi_principle.ldd_doping_increase_reduces_extension_resistance": "LDD doping 증가는 extension resistance를 낮춰 Drive current를 높이는 방향을 가집니다.",
    "multi_principle.bulk_doping_change_modifies_depletion": "Bulk doping 증가는 depletion과 threshold 특성을 함께 변화시키는 방향을 가집니다.",
})
