from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DomainPolicy:
    """Full prepared design domain used by every active curve model."""

    name: str = "full"

    def supported(self, features: np.ndarray) -> np.ndarray:
        values = np.asarray(features)
        if values.ndim != 2 or values.shape[1] < 5:
            raise ValueError("Expected device features shaped (N, >=5)")
        return np.ones(len(values), dtype=bool)

    def require_supported(self, features: np.ndarray) -> None:
        self.supported(features)

    def state_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "name": "full",
            "supported": "all prepared device conditions",
            "excluded_rules_any_match": [],
            "warning": "",
        }


def make_domain_policy(name: str = "full") -> DomainPolicy:
    if name != "full":
        raise ValueError(
            f"Restricted domain policy {name!r} is retired; active models use 'full'"
        )
    return DomainPolicy()
