from __future__ import annotations

import json
import shutil

import h5py
import numpy as np

from ai.field_map_model.data.tecplot import ELEMENT_FIELD_NAMES
from ai.field_map_model.training.optimize_element_mlp import _args, _collect
from ai.field_map_model.training.train_coordinate_mlp import _device, _set_seed, _train_domain


def main() -> None:
    args = _args()
    default_candidate = args.output_dir.name == "element_bulk_focused"
    if default_candidate:
        args.output_dir = args.output_dir.parent / "element_bulk_physics"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    _set_seed(args.seed); device = _device(args.device)
    print(f"Training physics-direction element candidate on {device}", flush=True)
    with h5py.File(args.dataset, "r") as archive:
        train, train_directions = _collect(archive, 0, args.seed)
        validation, validation_directions = _collect(archive, 1, args.seed)
    weights = np.asarray([1.15, 1.10, 0.90, 1.55, 0.85, 0.95], dtype=np.float32)
    physics_weight = 0.03
    report = _train_domain(
        "element", ELEMENT_FIELD_NAMES, train, validation, args, device,
        args.output_dir, weights, train_directions, validation_directions,
        physics_weight,
    )
    destination_node = args.output_dir / "node"
    if destination_node.exists(): shutil.rmtree(destination_node)
    shutil.copytree(args.baseline_dir / "node", destination_node)
    summary = {
        "name": "element_bulk_physics", "test_cases_loaded": 0,
        "physics_direction_weight": physics_weight,
        "physics_target": "cosine alignment of predicted E with triangle -grad(raw Potential)",
        "field_loss_weights": dict(zip(ELEMENT_FIELD_NAMES, weights.tolist())),
        "element_report": report,
        "node_model": "copied unchanged from coordinate_mlp baseline",
    }
    (args.output_dir / "candidate_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(args.output_dir / "candidate_report.json")


if __name__ == "__main__":
    main()
