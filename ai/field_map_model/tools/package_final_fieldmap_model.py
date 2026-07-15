from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "ai/model_artifacts/field_map_model/candidates/element_bulk_physics"
DESTINATION = ROOT / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _export_numpy_model(checkpoint_path: Path, output_path: Path) -> None:
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    arrays = {
        name: tensor.detach().cpu().numpy().astype(np.float32, copy=False)
        for name, tensor in checkpoint["model_state_dict"].items()
    }
    np.savez_compressed(output_path, **arrays)


def main() -> int:
    marker_path = SOURCE / "final_test/FINAL_TEST_COMPLETED.json"
    if not marker_path.exists():
        raise FileNotFoundError("Final test marker is required before packaging")
    if DESTINATION.exists():
        raise FileExistsError(f"Final package already exists: {DESTINATION}")
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    source_models = {domain: SOURCE / domain / "model.pt" for domain in ("node", "element")}
    for domain, model_path in source_models.items():
        expected = marker[f"{domain}_model_sha256"]
        actual = _sha256(model_path)
        if actual != expected:
            raise RuntimeError(f"{domain} model changed after final test: {actual} != {expected}")
    for domain in ("node", "element"):
        target_dir = DESTINATION / domain; target_dir.mkdir(parents=True, exist_ok=True)
        for name in ("model.pt", "feature_scaler.json", "target_transform.json"):
            shutil.copy2(SOURCE / domain / name, target_dir / name)
        _export_numpy_model(SOURCE / domain / "model.pt", target_dir / "model.npz")
    shutil.copy2(ROOT / "ai/field_map_model/configs/selected_preprocessing.json", DESTINATION / "preprocessing_config.json")
    shutil.copy2(SOURCE / "selection/selection_report.md", DESTINATION / "selection_report.md")
    shutil.copy2(SOURCE / "selection/selection_report.json", DESTINATION / "selection_report.json")
    shutil.copy2(SOURCE / "final_test/final_test_report.md", DESTINATION / "final_test_report.md")
    shutil.copy2(SOURCE / "final_test/final_test_report.json", DESTINATION / "final_test_report.json")
    portable_marker = {
        "completed_at_utc": marker["completed_at_utc"],
        "model_dir": "ai/model_artifacts/field_map_model/candidates/element_bulk_physics",
        "node_model_sha256": marker["node_model_sha256"],
        "element_model_sha256": marker["element_model_sha256"],
        "test_cases": marker["test_cases"],
        "report": "ai/model_artifacts/field_map_model/candidates/element_bulk_physics/final_test/final_test_report.md",
    }
    (DESTINATION / "FINAL_TEST_COMPLETED.json").write_text(
        json.dumps(portable_marker, indent=2), encoding="utf-8"
    )
    manifest = {
        "schema_version": 1,
        "name": "coordinate_mlp_physics",
        "bias": {"Vg_V": 3.0, "Vd_V": 3.0},
        "input": "device geometry/doping parameters plus a region-labelled triangle mesh",
        "node_outputs": ["Potential", "Electrons", "Holes", "USRH"],
        "element_outputs": ["ElectricField_x", "ElectricField_y", "ElectronCurrent_x", "ElectronCurrent_y", "HoleCurrent_x", "HoleCurrent_y"],
        "known_local_input": "analytic NetDoping",
        "model_sha256": {domain: _sha256(DESTINATION / domain / "model.pt") for domain in ("node", "element")},
        "runtime_model_sha256": {domain: _sha256(DESTINATION / domain / "model.npz") for domain in ("node", "element")},
        "test_cases": marker["test_cases"],
        "inference_api": "ai.field_map_model.inference.FieldMapPredictor",
    }
    (DESTINATION / "final_model_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    readme = """# Final field-map model\n\nFixed-bias (`Vg=3 V`, `Vd=3 V`) coordinate-MLP surrogate. The node model is the validated baseline; the element model uses bulk/channel-focused sampling and an electric-field direction loss.\n\nThe package contains both training checkpoints, NumPy runtime weights, fitted feature scalers, fitted target transforms, preprocessing metadata, validation selection, and the one-time final-test report. Runtime inference uses `model.npz`; PyTorch is not required by the visualization application.\n\n```python\nfrom pathlib import Path\nfrom ai.field_map_model.inference import FieldMapPredictor, generate_gmsh_mesh\n\nroot = Path('.')\nmesh = generate_gmsh_mesh(1000, 10, root / 'tcad/data_extraction/base_case/gmsh_mos2d.geo')\npredictor = FieldMapPredictor(root / 'ai/model_artifacts/field_map_model/final/coordinate_mlp_physics')\nresult = predictor.predict(mesh, 1000, 10, 1e16, 5e20, 1e18)\n```\n\nThe model is valid for the training design space and the fixed bias only.\n"""
    (DESTINATION / "README.md").write_text(readme, encoding="utf-8")
    print(DESTINATION)
    return 0


if __name__ == "__main__":
    sys.exit(main())
