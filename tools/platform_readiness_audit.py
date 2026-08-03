from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from backend.learning import run_platform_readiness_audit


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit the complete multi-Case learning platform.",
    )
    parser.add_argument(
        "--skip-models",
        action="store_true",
        help="Run only fast catalog, curriculum, session, and portfolio checks.",
    )
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _arguments()
    report = run_platform_readiness_audit(
        REPOSITORY_ROOT,
        with_models=not args.skip_models,
    )
    rendered = json.dumps(
        report.to_dict(),
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    )
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
