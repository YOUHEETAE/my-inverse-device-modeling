"""Regenerate the phase-1 explanation baseline from the real model artifacts."""

from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ai.curve_model.inference import FinalCurvePredictor, device_features
from ai.field_map_model.inference import FieldMapPredictor, generate_gmsh_mesh
from backend.explanation.curve_analyzer import build_curve_payload
from backend.explanation.field_analyzer import build_field_payload
from backend.explanation.providers.mock import MockExplanationProvider
from backend.explanation.safety import validate_provider_response
from ai.shared.field_data import GeneratedFieldMap


BASE = {"L": "200", "T": "20", "B": "1e16", "SD": "1e20", "LDD": "1e18"}
CASES = {
    "curve_single_default": [BASE],
    "curve_l1200_t22_reinforcing": [BASE, BASE | {"L": "1200", "T": "22"}],
    "curve_l1200_t17_competing": [BASE, BASE | {"L": "1200", "T": "17"}],
    "curve_three_dopings_doubled": [BASE, BASE | {"B": "2e16", "SD": "2e20", "LDD": "2e18"}],
    "curve_three_variants": [BASE, BASE | {"L": "1200", "T": "22"}, BASE | {"L": "1200", "T": "17"}],
}


def _curve_results(predictor: FinalCurvePredictor, configs: list[dict[str, str]]):
    return [
        (f"Curve {index + 1}", predictor.predict("idvd", device_features(config)), predictor.predict("idvg", device_features(config)))
        for index, config in enumerate(configs)
    ]


def _snapshot(payload) -> dict:
    data = payload.to_dict()
    response = validate_provider_response(MockExplanationProvider().generate("", "", data))
    return {"payload": data, "mock_response": response}


def _field_output(predictor: FieldMapPredictor, template: Path, config: dict[str, str]) -> GeneratedFieldMap:
    length, tox = float(config["L"]), float(config["T"])
    mesh = generate_gmsh_mesh(length, tox, template)
    prediction = predictor.predict(mesh, length, tox, float(config["B"]), float(config["SD"]), float(config["LDD"]))
    return GeneratedFieldMap(mesh, prediction, length, tox, float(config["B"]), float(config["SD"]), float(config["LDD"]))


def generate() -> dict:
    curve_model_dir = REPO_ROOT / "ai/model_artifacts/curve_model/final/pca_xgboost"
    field_model_dir = REPO_ROOT / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics"
    template = REPO_ROOT / "tcad/data_extraction/base_case/gmsh_mos2d.geo"
    curve_predictor = FinalCurvePredictor(curve_model_dir)
    field_predictor = FieldMapPredictor(field_model_dir)
    snapshots = {}
    for case_name, configs in CASES.items():
        snapshots[case_name] = {"configs": configs, **_snapshot(build_curve_payload(_curve_results(curve_predictor, configs), configs))}
    field_configs = [BASE, BASE | {"L": "1200", "T": "22"}]
    field_outputs = [(f"Curve {index + 1}", _field_output(field_predictor, template, config)) for index, config in enumerate(field_configs)]
    for display in ("Potential", "Electric field"):
        name = "field_" + display.lower().replace(" ", "_") + "_l1200_t22"
        snapshots[name] = {
            "configs": field_configs,
            "display": display,
            **_snapshot(build_field_payload(field_outputs, display, "Auto", "Robust 1-99%")),
        }
    return {
        "baseline_version": "phase1-v1",
        "purpose": "Frozen pre-improvement Payload v3 and deterministic Mock output for final eight-phase comparison.",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "mock_model": MockExplanationProvider.model,
        "cases": snapshots,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("phase1_explanation_baseline.json"))
    args = parser.parse_args()
    result = generate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"baseline={args.output.resolve()}")
    print(f"cases={len(result['cases'])}")
    for name, case in result["cases"].items():
        response = case["mock_response"]
        print(name, case["payload"]["analysis_type"], {key: len(response[key]) for key in response})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
