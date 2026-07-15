import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.field_map_model.evaluation.audit_validation import main

if __name__ == "__main__":
    main()
