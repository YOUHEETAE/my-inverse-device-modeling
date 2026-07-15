from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import gmsh
import numpy as np
from scipy.special import erfc


REGION_IDS = {"bulk": 0, "oxide": 1, "gate": 2}
REGION_NAMES = ("bulk", "oxide", "gate")


@dataclass(frozen=True)
class GeneratedMesh:
    node_xy_nm: np.ndarray
    node_region: np.ndarray
    triangles: np.ndarray
    element_centroid_xy_nm: np.ndarray
    element_region: np.ndarray


def _replace_geo_parameter(text: str, name: str, value: float) -> str:
    pattern = re.compile(
        rf"^(\s*{re.escape(name)}\s*=\s*)([^;]+)(;\s*)$", re.MULTILINE
    )
    replacement = rf"\g<1>{value:.15e}\g<3>"
    result, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError(f"Could not replace {name!r} in Gmsh template")
    return result


def generate_gmsh_mesh(
    length_nm: float,
    oxide_thickness_nm: float,
    template_geo: Path,
) -> GeneratedMesh:
    """Generate the original MOS geometry and duplicate interface nodes by region."""
    text = template_geo.read_text(encoding="utf-8")
    text = _replace_geo_parameter(text, "gate_width", length_nm * 1e-7)
    text = _replace_geo_parameter(text, "oxide_thickness", oxide_thickness_nm * 1e-7)
    with tempfile.TemporaryDirectory(prefix="idm_fieldmap_mesh_") as temporary:
        geo_path = Path(temporary) / "fieldmap.geo"
        geo_path.write_text(text, encoding="utf-8")
        gmsh.initialize(["gmsh", "-v", "0"])
        try:
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.open(str(geo_path))
            gmsh.model.mesh.generate(2)
            all_tags, all_coordinates, _ = gmsh.model.mesh.getNodes()
            coordinate_lookup = {
                int(tag): all_coordinates[index * 3 : index * 3 + 2]
                for index, tag in enumerate(all_tags)
            }
            physical_groups = {
                gmsh.model.getPhysicalName(dim, tag).lower(): (dim, tag)
                for dim, tag in gmsh.model.getPhysicalGroups(2)
            }
            missing = set(REGION_NAMES).difference(physical_groups)
            if missing:
                raise ValueError(f"Generated mesh is missing physical regions: {sorted(missing)}")
            node_batches: list[np.ndarray] = []
            node_regions: list[np.ndarray] = []
            triangle_batches: list[np.ndarray] = []
            element_regions: list[np.ndarray] = []
            offset = 0
            for region_name in REGION_NAMES:
                dim, physical_tag = physical_groups[region_name]
                triangle_tags: list[np.ndarray] = []
                for entity in gmsh.model.getEntitiesForPhysicalGroup(dim, physical_tag):
                    element_types, _element_tags, element_node_tags = gmsh.model.mesh.getElements(
                        dim, entity
                    )
                    for element_type, flattened in zip(element_types, element_node_tags):
                        properties = gmsh.model.mesh.getElementProperties(element_type)
                        nodes_per_element = int(properties[3])
                        if nodes_per_element != 3:
                            continue
                        triangle_tags.append(
                            np.asarray(flattened, dtype=np.int64).reshape(-1, 3)
                        )
                if not triangle_tags:
                    raise ValueError(f"No triangles were generated for region {region_name}")
                region_triangles_by_tag = np.concatenate(triangle_tags)
                region_node_tags = np.unique(region_triangles_by_tag)
                local_index = {
                    int(tag): index for index, tag in enumerate(region_node_tags)
                }
                local_triangles = np.asarray(
                    [
                        [local_index[int(tag)] for tag in triangle]
                        for triangle in region_triangles_by_tag
                    ],
                    dtype=np.int32,
                )
                coordinates_nm = np.asarray(
                    [coordinate_lookup[int(tag)] for tag in region_node_tags],
                    dtype=np.float64,
                ) * 1e7
                node_batches.append(coordinates_nm.astype(np.float32))
                node_regions.append(
                    np.full(len(coordinates_nm), REGION_IDS[region_name], dtype=np.uint8)
                )
                triangle_batches.append(local_triangles + offset)
                element_regions.append(
                    np.full(len(local_triangles), REGION_IDS[region_name], dtype=np.uint8)
                )
                offset += len(coordinates_nm)
        finally:
            gmsh.finalize()
    node_xy_nm = np.concatenate(node_batches)
    triangles = np.concatenate(triangle_batches).astype(np.int32)
    centroids = node_xy_nm[triangles].mean(axis=1).astype(np.float32)
    return GeneratedMesh(
        node_xy_nm=node_xy_nm,
        node_region=np.concatenate(node_regions),
        triangles=triangles,
        element_centroid_xy_nm=centroids,
        element_region=np.concatenate(element_regions),
    )


def analytic_net_doping(
    node_xy_nm: np.ndarray,
    node_region: np.ndarray,
    length_nm: float,
    bulk_doping_cm3: float,
    sd_doping_cm3: float,
    ldd_doping_cm3: float,
) -> np.ndarray:
    """Reproduce the exact DEVSIM sweep NetDoping equations at arbitrary nodes."""
    coordinates_cm = np.asarray(node_xy_nm, dtype=np.float64) * 1e-7
    x = coordinates_cm[:, 0]
    y = coordinates_cm[:, 1]
    length_cm = float(length_nm) * 1e-7
    spacer_width = 5.0e-6
    contact_width = 3.0e-5
    device_width = length_cm + 2.0 * spacer_width + 2.0 * contact_width
    x_center = 0.5 * device_width
    x_gate_left = x_center - 0.5 * length_cm
    x_gate_right = x_center + 0.5 * length_cm
    x_spacer_left = x_gate_left - spacer_width
    x_spacer_right = x_gate_right + spacer_width
    x_decay = 2.0e-7
    y_decay = 5.0e-7
    y_diffusion = 5.0e-6
    y_ldd = 2.5e-6
    y_bulk_bottom = 1.0e-4
    body_doping = 1.0e19
    result = np.zeros(len(x), dtype=np.float64)
    bulk_mask = np.asarray(node_region) == REGION_IDS["bulk"]
    xb = x[bulk_mask]
    yb = y[bulk_mask]
    drain = (
        0.25
        * sd_doping_cm3
        * erfc((xb - x_spacer_left) / x_decay)
        * erfc((yb - y_diffusion) / y_decay)
    )
    source = (
        0.25
        * sd_doping_cm3
        * erfc(-(xb - x_spacer_right) / x_decay)
        * erfc((yb - y_diffusion) / y_decay)
    )
    left_ldd = (
        0.25
        * ldd_doping_cm3
        * erfc((xb - x_gate_left) / x_decay)
        * erfc((yb - y_ldd) / y_decay)
    )
    right_ldd = (
        0.25
        * ldd_doping_cm3
        * erfc(-(xb - x_gate_right) / x_decay)
        * erfc((yb - y_ldd) / y_decay)
    )
    body = 0.5 * body_doping * erfc(-(yb - y_bulk_bottom) / y_decay)
    result[bulk_mask] = drain + source + left_ldd + right_ldd + 1.0 - (
        bulk_doping_cm3 + body
    )
    gate_mask = np.asarray(node_region) == REGION_IDS["gate"]
    result[gate_mask] = 1.0e20 - 1.0
    return result.astype(np.float32)
