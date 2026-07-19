from ai.result_interpreter.payload_builders import build_payload
from ai.result_interpreter.service import ExplanationService
from ai.result_interpreter.staged_explanation import (
    STAGE_EVIDENCE, STAGE_EXTRACTED, build_staged_payload,
)


def _item(label="Curve 1"):
    return {"label": label, "device_parameters": {"L": 200, "T": 20, "B": 1e16, "SD": 1e20, "LDD": 1e18},
            "electrical_parameters": {"ion_ma_per_um": {"value": 1.2, "unit": "mA/um"}}}


def test_extracted_only_keeps_parameters_but_removes_evidence_judgments():
    full = build_payload(kind="iv_curve", context={}, items=[_item()], legacy_comparisons=[], warnings=[]).to_dict()
    staged = build_staged_payload(full, STAGE_EXTRACTED)
    assert staged["processing_stage"] == STAGE_EXTRACTED
    assert staged["extracted_parameters"][0]["quantity"] == "ion"
    assert staged["extracted_parameters"][0]["extracted_values"]["value"] == 1.2
    assert "evidence" not in staged and "conclusions" not in staged
    assert "importance_score" not in str(staged) and "selected_for_explanation" not in str(staged)


def test_evidence_assisted_keeps_classification_but_removes_selection_and_conclusions():
    full = build_payload(kind="iv_curve", context={}, items=[_item()], legacy_comparisons=[], warnings=[]).to_dict()
    staged = build_staged_payload(full, STAGE_EVIDENCE)
    evidence = staged["evidence"][0]
    assert evidence["observation"] == "measured_value" and evidence["confidence"] == "high"
    assert "importance_score" not in evidence and "selected_for_explanation" not in evidence
    assert "conclusions" not in staged


class StagedProvider:
    name = "external_llm"
    model = "test-model"

    def generate(self, system_prompt, user_prompt, payload):
        assert payload["processing_stage"] in {STAGE_EXTRACTED, STAGE_EVIDENCE}
        return {"descriptions": ["단계별 해석"], "comparisons": [], "tradeoffs": [], "cautions": []}


def test_staged_service_marks_processing_level():
    full = build_payload(kind="iv_curve", context={}, items=[_item()], legacy_comparisons=[], warnings=[]).to_dict()
    data = build_staged_payload(full, STAGE_EVIDENCE)
    result = ExplanationService(StagedProvider())._explain_staged(data, STAGE_EVIDENCE)
    assert result.provider == "external_llm" and STAGE_EVIDENCE in result.model
    assert any(STAGE_EVIDENCE in caution for caution in result.cautions)
