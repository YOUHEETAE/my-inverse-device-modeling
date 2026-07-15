from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ai.field_map_model.inference.mesh_inputs import GeneratedMesh, analytic_net_doping
from ai.field_map_model.inference.runtime import DomainPredictor, coordinate_features


@dataclass(frozen=True)
class FieldMapPrediction:
    net_doping: np.ndarray
    node_fields: dict[str, np.ndarray]
    element_fields: dict[str, np.ndarray]


class FieldMapPredictor:
    """Predict fixed-bias fields on any compatible region-labelled triangle mesh."""

    def __init__(self, model_dir: Path) -> None:
        self.predictors = {
            domain: DomainPredictor(Path(model_dir) / domain)
            for domain in ("node", "element")
        }

    def predict(
        self,
        mesh: GeneratedMesh,
        length_nm: float,
        oxide_thickness_nm: float,
        bulk_doping_cm3: float,
        sd_doping_cm3: float,
        ldd_doping_cm3: float,
    ) -> FieldMapPrediction:
        device_features = np.asarray(
            [length_nm, oxide_thickness_nm, np.log10(bulk_doping_cm3),
             np.log10(sd_doping_cm3), np.log10(ldd_doping_cm3)],
            dtype=np.float32,
        )
        doping = analytic_net_doping(
            mesh.node_xy_nm, mesh.node_region, length_nm, bulk_doping_cm3,
            sd_doping_cm3, ldd_doping_cm3,
        )
        node_features = coordinate_features(
            device_features, mesh.node_xy_nm, mesh.node_region, doping,
            mesh.node_xy_nm,
        )
        element_doping = doping[mesh.triangles].mean(axis=1)
        element_features = coordinate_features(
            device_features, mesh.element_centroid_xy_nm, mesh.element_region,
            element_doping, mesh.node_xy_nm,
        )
        node_values = self.predictors["node"].predict(node_features)
        element_values = self.predictors["element"].predict(element_features)
        return FieldMapPrediction(
            net_doping=doping,
            node_fields=dict(zip(self.predictors["node"].field_names, node_values.T)),
            element_fields=dict(zip(self.predictors["element"].field_names, element_values.T)),
        )
