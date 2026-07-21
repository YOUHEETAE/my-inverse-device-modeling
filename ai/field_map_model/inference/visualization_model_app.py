"""Backward-compatible imports for the field-map visualization application."""

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from frontend.visualization.field_rendering import *  # noqa: F403
from frontend.visualization.field_app import main


if __name__ == "__main__":
    raise SystemExit(main())
