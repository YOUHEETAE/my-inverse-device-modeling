"""Shared, dependency-free device parameter domain definitions."""

from __future__ import annotations


PARAMETER_OPTIONS = {
    "L": ("100", "120", "150", "170", "200", "250", "300", "400", "500", "700", "1000", "1300", "1600"),
    "T": ("5", "7", "10", "12", "15", "20", "27", "35", "50"),
    "B": ("5e15", "1e16", "5e16"),
    "SD": ("1e19", "5e19", "1e20", "5e20"),
    "LDD": ("1e17", "5e17", "1e18", "5e18"),
}

DEFAULT_PARAMETERS = {"L": "200", "T": "20", "B": "1e16", "SD": "1e20", "LDD": "1e18"}
