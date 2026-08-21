from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path
import subprocess
import sys
import time


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))


def _measure_import() -> float:
    started = time.perf_counter()
    subprocess.run(
        [sys.executable, "-c", "import frontend.app"],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return time.perf_counter() - started


def _interactive_contract() -> tuple[bool, str]:
    from frontend import app

    startup = getattr(app, "_start_interactive_app", None)
    if startup is None:
        return False, "interactive_startup_helper_missing"
    source = inspect.getsource(startup)
    window_position = source.find("_create_tk_window()")
    loading_position = source.find("_load_runtime_models_async(")
    if window_position < 0 or loading_position < 0:
        return False, "window_or_async_loader_missing"
    if window_position > loading_position:
        return False, "runtime_models_start_before_window"
    if "window.mainloop()" not in source:
        return False, "responsive_event_loop_missing"
    return True, "window_created_before_async_model_load"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-import-seconds", type=float, default=5.0)
    parser.add_argument("--samples", type=int, default=1)
    args = parser.parse_args()
    timings = [_measure_import() for _ in range(max(args.samples, 1))]
    contract_ok, contract_detail = _interactive_contract()
    result = {
        "import_seconds": timings,
        "max_import_seconds": args.max_import_seconds,
        "import_pass": max(timings) <= args.max_import_seconds,
        "interactive_contract_pass": contract_ok,
        "interactive_contract_detail": contract_detail,
    }
    passed = result["import_pass"] and contract_ok
    result["status"] = "pass" if passed else "fail"
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
