from __future__ import annotations

from dataclasses import dataclass

import matplotlib.tri as mtri
import numpy as np

from ai.field_map_model.inference import FieldMapPrediction, GeneratedMesh


FIELD_DISPLAYS = (
    "Mesh",
    "Abs net doping",
    "Net doping",
    "Potential",
    "Electric field",
    "Electron density",
    "Hole density",
    "Electron current density",
    "Hole current density",
    "Total current density",
    "SRH recombination",
    "Energy band (1D)",
)
SCALE_MODES = ("Auto", "Linear", "Log magnitude", "SymLog")
RANGE_MODES = ("Robust 1-99%", "Full range")


@dataclass(frozen=True)
class GeneratedFieldMap:
    mesh: GeneratedMesh
    prediction: FieldMapPrediction
    length_nm: float
    tox_nm: float
    bulk_doping: float
    sd_doping: float
    ldd_doping: float


@dataclass(frozen=True)
class ScalarDisplay:
    values: np.ndarray
    domain: str
    title: str
    label: str
    default_scale: str
    cmap: str


def scalar_display(output: GeneratedFieldMap, display: str) -> ScalarDisplay:
    node = output.prediction.node_fields
    element = output.prediction.element_fields
    if display == "Abs net doping":
        return ScalarDisplay(np.abs(output.prediction.net_doping), "node", display, "|NetDoping| (cm$^{-3}$)", "Log magnitude", "plasma")
    if display == "Net doping":
        return ScalarDisplay(output.prediction.net_doping, "node", display, "NetDoping (cm$^{-3}$)", "SymLog", "RdBu_r")
    if display == "Potential":
        return ScalarDisplay(node["Potential"], "node", display, "Potential (V)", "Linear", "coolwarm")
    if display == "Electric field":
        values = np.hypot(element["ElectricField_x"], element["ElectricField_y"])
        return ScalarDisplay(values, "element", "|Electric field|", "Electric field (V/cm)", "Log magnitude", "inferno")
    if display == "Electron density":
        return ScalarDisplay(node["Electrons"], "node", display, "Electrons (cm$^{-3}$)", "Log magnitude", "Blues")
    if display == "Hole density":
        return ScalarDisplay(node["Holes"], "node", display, "Holes (cm$^{-3}$)", "Log magnitude", "Reds")
    if display == "Electron current density":
        values = np.hypot(element["ElectronCurrent_x"], element["ElectronCurrent_y"])
        return ScalarDisplay(values, "element", "|Electron current density|", "|Jn| (A/cm$^2$)", "Log magnitude", "inferno")
    if display == "Hole current density":
        values = np.hypot(element["HoleCurrent_x"], element["HoleCurrent_y"])
        return ScalarDisplay(values, "element", "|Hole current density|", "|Jp| (A/cm$^2$)", "Log magnitude", "magma")
    if display == "Total current density":
        values = np.hypot(element["ElectronCurrent_x"] + element["HoleCurrent_x"], element["ElectronCurrent_y"] + element["HoleCurrent_y"])
        return ScalarDisplay(values, "element", "|Total current density|", "|Jn + Jp| (A/cm$^2$)", "Log magnitude", "inferno")
    if display == "SRH recombination":
        return ScalarDisplay(node["USRH"], "node", display, "USRH (cm$^{-3}$ s$^{-1}$)", "SymLog", "PiYG")
    raise ValueError(f"Unknown scalar display: {display}")


def finite_limits(values: np.ndarray, range_mode: str, absolute: bool = False) -> tuple[float, float]:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if absolute:
        finite = np.abs(finite)
    if not len(finite):
        return 0.0, 1.0
    low, high = np.percentile(finite, (1.0, 99.0)) if range_mode == "Robust 1-99%" else (np.min(finite), np.max(finite))
    if high <= low:
        high = low + max(abs(low) * 0.01, 1e-12)
    return float(low), float(high)


def geometry_markers(output: GeneratedFieldMap) -> dict[str, float]:
    x, y = output.mesh.node_xy_nm[:, 0], output.mesh.node_xy_nm[:, 1]
    bulk, gate = output.mesh.node_region == 0, output.mesh.node_region == 2
    surface, body = float(np.min(y[bulk])), float(np.max(y[bulk]))
    gate_left, gate_right = float(np.min(x[gate])), float(np.max(x[gate]))
    spacer_width, contact_gap = 50.0, 50.0
    return {
        "bulk_left": float(np.min(x[bulk])), "bulk_right": float(np.max(x[bulk])),
        "surface": surface, "body": body,
        "gate_left": gate_left, "gate_right": gate_right,
        "gate_top": float(np.min(y[gate])), "oxide_top": -output.tox_nm,
        "spacer_left": gate_left - spacer_width, "spacer_right": gate_right + spacer_width,
        "source_contact_right": gate_left - spacer_width - contact_gap,
        "drain_contact_left": gate_right + spacer_width + contact_gap,
        "diffusion": min(surface + 50.0, body),
    }


def region_interpolator(output: GeneratedFieldMap, region: int):
    triangles = output.mesh.triangles[output.mesh.element_region == region]
    triangulation = mtri.Triangulation(output.mesh.node_xy_nm[:, 0], output.mesh.node_xy_nm[:, 1], triangles)
    return mtri.LinearTriInterpolator(triangulation, output.prediction.node_fields["Potential"])
