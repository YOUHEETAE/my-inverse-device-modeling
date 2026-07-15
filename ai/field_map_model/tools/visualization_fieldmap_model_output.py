from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ai.field_map_model.inference.visualization_model_app import main


if __name__ == "__main__":
    raise SystemExit(main())
