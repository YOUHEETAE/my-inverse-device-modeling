from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np


NODE_FIELD_NAMES = (
    "NetDoping",
    "Potential",
    "Electrons",
    "Holes",
    "USRH",
)
ELEMENT_FIELD_NAMES = (
    "ElectricField_x",
    "ElectricField_y",
    "ElectronCurrent_x",
    "ElectronCurrent_y",
    "HoleCurrent_x",
    "HoleCurrent_y",
)
SELECTED_VARIABLES = {"x", "y", *NODE_FIELD_NAMES, *ELEMENT_FIELD_NAMES}

_ZONE_PATTERN = re.compile(
    r'ZONE[^\n]*T\s*=\s*"([^"]+)"[^\n]*NODES\s*=\s*(\d+)[^\n]*ELEMENTS\s*=\s*(\d+)[^\n]*',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TecplotZone:
    name: str
    coordinates_cm: np.ndarray
    triangles: np.ndarray
    node_fields: np.ndarray
    element_fields: np.ndarray


@dataclass(frozen=True)
class ParsedFieldCase:
    path: Path
    variables: tuple[str, ...]
    zones: tuple[TecplotZone, ...]


def _parse_varlocation(zone_line: str) -> set[int]:
    match = re.search(
        r"VARLOCATION\s*=\s*\(\s*\[([^\]]+)\]\s*=\s*CELLCENTERED",
        zone_line,
        re.IGNORECASE,
    )
    if not match:
        return set()
    indices: set[int] = set()
    for part in match.group(1).split(","):
        token = part.strip()
        if "-" in token:
            start, end = (int(value.strip()) for value in token.split("-", 1))
            indices.update(range(start - 1, end))
        else:
            indices.add(int(token) - 1)
    return indices


def _variables(text: str) -> tuple[str, ...]:
    match = re.search(
        r"VARIABLES\s*=\s*(.*?)(?:\n\s*ZONE|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        raise ValueError("Tecplot VARIABLES header was not found")
    names = tuple(re.findall(r'"([^"]+)"', match.group(1)))
    if not names:
        raise ValueError("Tecplot VARIABLES header is empty")
    return names


def parse_tecplot_field_case(path: Path) -> ParsedFieldCase:
    text = path.read_text(encoding="utf-8", errors="replace")
    variables = _variables(text)
    variable_indices = {name: index for index, name in enumerate(variables)}
    missing = SELECTED_VARIABLES.difference(variable_indices)
    if missing:
        raise ValueError(f"Required Tecplot variables are missing: {sorted(missing)}")

    zone_matches = list(_ZONE_PATTERN.finditer(text))
    if not zone_matches:
        raise ValueError("No Tecplot FETRIANGLE zones were found")

    zones: list[TecplotZone] = []
    for zone_index, match in enumerate(zone_matches):
        name = match.group(1)
        node_count = int(match.group(2))
        element_count = int(match.group(3))
        zone_end = zone_matches[zone_index + 1].start() if zone_index + 1 < len(zone_matches) else len(text)
        tokens = text[match.end() : zone_end].split()
        cell_centered = _parse_varlocation(match.group(0))

        selected: dict[str, np.ndarray] = {}
        cursor = 0
        for index, variable in enumerate(variables):
            count = element_count if index in cell_centered else node_count
            end = cursor + count
            if end > len(tokens):
                raise ValueError(f"Zone {name}: data block ended while reading {variable}")
            if variable in SELECTED_VARIABLES:
                selected[variable] = np.asarray(tokens[cursor:end], dtype=np.float32)
            cursor = end

        connectivity_end = cursor + element_count * 3
        if connectivity_end > len(tokens):
            raise ValueError(f"Zone {name}: triangle connectivity is incomplete")
        triangles = (
            np.asarray(tokens[cursor:connectivity_end], dtype=np.int64).reshape(element_count, 3)
            - 1
        ).astype(np.int32)
        if triangles.size and (triangles.min() < 0 or triangles.max() >= node_count):
            raise ValueError(f"Zone {name}: triangle connectivity references an invalid node")

        for field in NODE_FIELD_NAMES:
            if variable_indices[field] in cell_centered:
                raise ValueError(f"Zone {name}: node field {field} is marked CELLCENTERED")
        for field in ELEMENT_FIELD_NAMES:
            if variable_indices[field] not in cell_centered:
                raise ValueError(f"Zone {name}: element field {field} is not marked CELLCENTERED")

        coordinates = np.column_stack((selected["x"], selected["y"])).astype(np.float32)
        node_fields = np.column_stack([selected[name] for name in NODE_FIELD_NAMES]).astype(np.float32)
        element_fields = np.column_stack(
            [selected[name] for name in ELEMENT_FIELD_NAMES]
        ).astype(np.float32)
        zones.append(
            TecplotZone(
                name=name,
                coordinates_cm=coordinates,
                triangles=triangles,
                node_fields=node_fields,
                element_fields=element_fields,
            )
        )

    return ParsedFieldCase(path=path, variables=variables, zones=tuple(zones))
