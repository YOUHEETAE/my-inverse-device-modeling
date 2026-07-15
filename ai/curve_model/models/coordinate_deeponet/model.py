from __future__ import annotations

import torch
from torch import nn


def _network(input_size: int, width: int, output_size: int, depth: int) -> nn.Sequential:
    layers: list[nn.Module] = [nn.Linear(input_size, width), nn.SiLU()]
    for _ in range(depth - 1):
        layers.extend((nn.Linear(width, width), nn.SiLU()))
    layers.append(nn.Linear(width, output_size))
    return nn.Sequential(*layers)


class CoordinateDeepONet(nn.Module):
    """Predict current at arbitrary sweep coordinates from device/bias features."""

    def __init__(
        self,
        feature_size: int = 6,
        latent_size: int = 128,
        width: int = 256,
        depth: int = 3,
    ) -> None:
        super().__init__()
        self.branch = _network(feature_size, width, latent_size, depth)
        self.trunk = _network(1, width, latent_size, depth)
        self.bias = nn.Parameter(torch.zeros(()))

    def forward(
        self, features: torch.Tensor, coordinates: torch.Tensor
    ) -> torch.Tensor:
        if coordinates.ndim == 1:
            coordinates = coordinates[:, None]
        branch_values = self.branch(features)
        trunk_values = self.trunk(coordinates)
        return torch.einsum("bi,gi->bg", branch_values, trunk_values) + self.bias
