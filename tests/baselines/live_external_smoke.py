"""Optional live Groq smoke for the final Analyzer-guided Curve and Field paths."""

from __future__ import annotations

import json
import sys
import argparse
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai.curve_model.inference import FinalCurvePredictor
from ai.field_map_model.inference import FieldMapPredictor
from backend.explanation.providers import ProviderSettings, create_explanation_provider
from backend.explanation.service import ExplanationService
from backend.explanation.prompts import build_prompt
from backend.explanation.safety import sanitize_payload_for_json, validate_grounded_response, validate_provider_response
from backend.explanation.curve_analyzer import build_curve_payload
from backend.explanation.field_analyzer import build_field_payload
from tests.baselines.generate_phase1_baseline import BASE, _curve_results, _field_output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose", action="store_true", help="Print only validator codes and schema-valid provider text; never prints credentials.")
    args = parser.parse_args()
    settings = replace(ProviderSettings.from_environment("external_llm"), cache_enabled=False, timeout_seconds=60.0)
    provider = create_explanation_provider(settings)
    service = ExplanationService(provider)
    curve_predictor = FinalCurvePredictor(REPO_ROOT / "ai/model_artifacts/curve_model/final/pca_xgboost")
    field_predictor = FieldMapPredictor(REPO_ROOT / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics")
    template = REPO_ROOT / "tcad/data_extraction/base_case/gmsh_mos2d.geo"
    configs = [BASE, BASE | {"L": "1200", "T": "22"}]
    curve_results = _curve_results(curve_predictor, configs)
    outputs = [(f"Curve {index + 1}", _field_output(field_predictor, template, config)) for index, config in enumerate(configs)]
    if args.diagnose:
        diagnostic = {}
        for name, payload in (("curve", build_curve_payload(curve_results, configs)),
                              ("field", build_field_payload(outputs, "Potential", "Auto", "Robust 1-99%"))):
            data, _warnings = sanitize_payload_for_json(payload.to_dict())
            system, user = build_prompt(data)
            response = None
            try:
                response = validate_provider_response(provider.generate(system, user, data))
                validate_grounded_response(response, data)
            except Exception as error:
                diagnostic[name] = {"validator": str(error), "response": response}
            else:
                diagnostic[name] = {"validator": "pass", "response": response}
        print(json.dumps(diagnostic, ensure_ascii=False, indent=2))
        return 0
    curve = service.explain_curves(curve_results, configs)
    field = service.explain_fields(outputs, "Potential", "Auto", "Robust 1-99%")
    result = {
        "curve": {"provider": curve.provider, "model": curve.model, "response": curve.to_dict()},
        "field": {"provider": field.provider, "model": field.model, "response": field.to_dict()},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if curve.provider == field.provider == "external_llm" else 1


if __name__ == "__main__":
    raise SystemExit(main())
