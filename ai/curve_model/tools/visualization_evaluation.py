from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from ai.curve_model.evaluation.visualization_app import main


if __name__ == "__main__":
    main()
