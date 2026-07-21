from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CURVE_DIR = ROOT / "ai/model_artifacts/curve_model/final/pca_xgboost"
FIELD_DIR = ROOT / "ai/model_artifacts/field_map_model/final/coordinate_mlp_physics"
GITHUB_FILE_LIMIT = 100 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(paths: list[Path]) -> None:
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing runtime files:\n" + "\n".join(missing))


def main() -> int:
    curve_manifest_path = CURVE_DIR / "final_model_manifest.json"
    field_manifest_path = FIELD_DIR / "final_model_manifest.json"
    _require(
        [
            ROOT / "frontend/app.py",
            ROOT / "frontend/visualization/explanation_panel.py",
            ROOT / "backend/explanation/service.py",
            ROOT / "ai/shared/field_data.py",
            ROOT / "ai/requirements.txt",
            ROOT / "environment.yml",
            ROOT / "ai/curve_model/inference/predictor.py",
            ROOT / "ai/field_map_model/inference/predictor.py",
            ROOT / "ai/field_map_model/inference/runtime.py",
            ROOT / "tcad/data_extraction/base_case/gmsh_mos2d.geo",
            curve_manifest_path,
            field_manifest_path,
            FIELD_DIR / "node/feature_scaler.json",
            FIELD_DIR / "node/model.npz",
            FIELD_DIR / "node/target_transform.json",
            FIELD_DIR / "element/feature_scaler.json",
            FIELD_DIR / "element/model.npz",
            FIELD_DIR / "element/target_transform.json",
            FIELD_DIR / "preprocessing_config.json",
        ]
    )
    curve_manifest = json.loads(curve_manifest_path.read_text(encoding="utf-8"))
    field_manifest = json.loads(field_manifest_path.read_text(encoding="utf-8"))
    _require([CURVE_DIR / relative for relative in curve_manifest["required_inference_files"]])
    expected = {
        CURVE_DIR / relative: digest
        for relative, digest in curve_manifest["model_hashes_sha256"].items()
    }
    expected.update(
        {
            FIELD_DIR / "node/model.pt": field_manifest["model_sha256"]["node"],
            FIELD_DIR / "element/model.pt": field_manifest["model_sha256"]["element"],
            FIELD_DIR / "node/model.npz": field_manifest["runtime_model_sha256"]["node"],
            FIELD_DIR / "element/model.npz": field_manifest["runtime_model_sha256"]["element"],
        }
    )
    _require(list(expected))
    for path, expected_hash in expected.items():
        actual = _sha256(path)
        if actual != expected_hash:
            raise ValueError(f"Hash mismatch: {path.relative_to(ROOT)}")
        if path.stat().st_size >= GITHUB_FILE_LIMIT:
            raise ValueError(f"GitHub 100 MiB limit exceeded: {path.relative_to(ROOT)}")
        print(f"OK  {path.relative_to(ROOT)}  ({path.stat().st_size / 1024**2:.2f} MiB)")
    print("Runtime package is complete and all model hashes match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
