from __future__ import annotations

import torch
from torch import nn


class ResidualBlock(nn.Module):
    def __init__(self, width: int, dropout: float = 0.0) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(width, width),
            nn.SiLU(),
            nn.Dropout(dropout),
            nn.Linear(width, width),
        )
        self.normalization = nn.LayerNorm(width)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.normalization(values + self.layers(values))


class CoordinateFieldMLP(nn.Module):
    """Shared coordinate trunk with simultaneous field outputs."""

    def __init__(
        self,
        input_size: int,
        output_size: int,
        hidden_size: int = 192,
        residual_blocks: int = 4,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_size = hidden_size
        self.residual_blocks = residual_blocks
        self.dropout = dropout
        self.input_layer = nn.Sequential(nn.Linear(input_size, hidden_size), nn.SiLU())
        self.blocks = nn.Sequential(
            *[ResidualBlock(hidden_size, dropout) for _ in range(residual_blocks)]
        )
        self.output_layer = nn.Linear(hidden_size, output_size)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        return self.output_layer(self.blocks(self.input_layer(values)))

    def architecture(self) -> dict[str, int | float | str]:
        return {
            "name": "coordinate_residual_mlp",
            "input_size": self.input_size,
            "output_size": self.output_size,
            "hidden_size": self.hidden_size,
            "residual_blocks": self.residual_blocks,
            "dropout": self.dropout,
            "activation": "SiLU",
            "normalization": "LayerNorm",
        }
