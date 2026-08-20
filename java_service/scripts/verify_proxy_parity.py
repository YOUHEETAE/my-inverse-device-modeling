"""Verifies that every endpoint java_service proxies returns exactly the
same status code and JSON body as calling the Python backend directly.

This is the real regression test for the Java migration: Python's actual
response is the source of truth, so nothing here is mocked. A mocked Python
response would only prove "Java relays whatever I told it to relay" — it
would never have caught the real bugs found while building this migration
(an HTTP/1.1-vs-h2c corruption bug, a Jackson snake_case edge case). Those
only showed up against a real, running uvicorn process.

Deliberately NOT under tests/ (that suite is the teammate's dependency-free
Python domain-logic tests, discovered by bare `pytest`) — this one needs
Java 21 + Maven on PATH and starts two real server processes, which would
slow down and add a hard Java dependency to a suite that has neither today.

Usage:
    python java_service/scripts/verify_proxy_parity.py

Requires:
    - Java 21 + Maven on PATH
    - backend/requirements.txt already installed in the active Python env
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
JAVA_SERVICE_DIR = REPO_ROOT / "java_service"

PY_PORT = 8128
JAVA_PORT = 8183
PY_BASE = f"http://127.0.0.1:{PY_PORT}"
JAVA_BASE = f"http://127.0.0.1:{JAVA_PORT}"

READY_TIMEOUT_SECONDS = 60
DEVICE = {"L": "200", "T": "20", "B": "1e16", "SD": "1e20", "LDD": "1e18"}


def _terminate_tree(proc: subprocess.Popen) -> None:
    # On Windows the Java process is launched with shell=True (needed for
    # mvn's .cmd wrapper) — proc.pid is then cmd.exe's PID, not mvn's or the
    # JVM's, so proc.terminate()/kill() only kills the empty shell and
    # leaves the actual Maven + Java processes running and still holding
    # the port. `taskkill /T` kills the whole process tree rooted at that
    # PID instead.
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def _call(base: str, method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    # java_service's own RateLimitInterceptor caps every client at 2
    # requests/second (see internal/RateLimiterService.java) — this script
    # calls both services sequentially fast enough to trip that on its own,
    # which would look like a mismatch but is really just this script
    # outrunning the very limiter it's supposed to be testing around.
    time.sleep(0.6)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body_text)
        except json.JSONDecodeError:
            return e.code, body_text


def _wait_until_ready(base: str, path: str = "/health") -> None:
    deadline = time.monotonic() + READY_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(base + path, timeout=2)
            return
        except (urllib.error.URLError, ConnectionError) as e:
            last_error = e
            time.sleep(0.5)
    raise TimeoutError(f"{base} never became ready ({last_error})")


class Failure(Exception):
    pass


def _assert_matches(name: str, method: str, path: str, body: dict | None = None, ignore_keys: tuple = ()) -> None:
    py_status, py_body = _call(PY_BASE, method, path, body)
    java_status, java_body = _call(JAVA_BASE, method, path, body)

    def strip(obj):
        if isinstance(obj, dict):
            return {k: strip(v) for k, v in obj.items() if k not in ignore_keys}
        if isinstance(obj, list):
            return [strip(v) for v in obj]
        return obj

    if py_status != java_status or strip(py_body) != strip(java_body):
        raise Failure(
            f"{name}: status py={py_status} java={java_status}\n"
            f"  py  : {json.dumps(py_body)[:300]}\n"
            f"  java: {json.dumps(java_body)[:300]}"
        )
    print(f"[OK] {name}")


def run_all_checks() -> None:
    _assert_matches("parameters", "GET", "/parameters")
    _assert_matches("curves/predict", "POST", "/curves/predict", DEVICE)
    _assert_matches("fields/predict", "POST", "/fields/predict", DEVICE)
    _assert_matches(
        "fields/display",
        "POST",
        "/fields/display",
        {**DEVICE, "display": "Potential", "scale_mode": "Auto", "range_mode": "Robust 1-99%"},
    )
    _assert_matches(
        "fields/display/compare",
        "POST",
        "/fields/display/compare",
        {
            "devices": [
                {"label": "Curve 1", **DEVICE},
                {"label": "Curve 2", "L": "500", "T": "15", "B": "1e16", "SD": "1e20", "LDD": "1e18"},
            ],
            "display": "Potential",
            "scale_mode": "Auto",
            "range_mode": "Robust 1-99%",
        },
    )
    _assert_matches("theory/pn-junction/options", "GET", "/theory/pn-junction/options")
    _assert_matches(
        "theory/pn-junction/result", "POST", "/theory/pn-junction/result", {"acceptors": 1e16, "donors": 1e16, "bias": 0}
    )
    _assert_matches("theory/long-channel-mosfet/options", "GET", "/theory/long-channel-mosfet/options")
    _assert_matches(
        "theory/long-channel-mosfet/result",
        "POST",
        "/theory/long-channel-mosfet/result",
        {"gate_voltage": 1.5, "drain_voltage": 1.5},
    )
    _assert_matches("theory/mos-capacitor/options", "GET", "/theory/mos-capacitor/options")
    _assert_matches(
        "theory/mos-capacitor/result",
        "POST",
        "/theory/mos-capacitor/result",
        {"acceptor_doping": 1e17, "oxide_thickness_nm": 10, "gate_voltage": 1},
    )
    _assert_matches(
        "theory/mos-capacitor/result (404 case)",
        "POST",
        "/theory/mos-capacitor/result",
        {"acceptor_doping": 999, "oxide_thickness_nm": 999, "gate_voltage": 999},
    )
    _assert_matches(
        "explain/curves/prompt", "POST", "/explain/curves/prompt", {"curves": [{"label": "Curve 1", **DEVICE}]}
    )
    _assert_matches(
        "explain/fields/prompt",
        "POST",
        "/explain/fields/prompt",
        {"fields": [{"label": "Curve 1", **DEVICE}], "display": "Potential", "scale_mode": "Auto", "range_mode": "Robust 1-99%"},
    )

    _, topics = _call(PY_BASE, "GET", "/case-study/topics")
    _assert_matches("case-study/topics", "GET", "/case-study/topics")
    if topics:
        topic_id = topics[0]["topic_id"]
        _assert_matches(f"case-study/topics/{topic_id}", "GET", f"/case-study/topics/{topic_id}")
        _, detail = _call(PY_BASE, "GET", f"/case-study/topics/{topic_id}")
        grade_body = {
            "prediction_answers": [
                {"question_id": q["question_id"], "selected": [], "reason": ""} for q in detail["prediction_questions"]
            ],
            "observation_answers": [
                {"question_id": q["question_id"], "selected": [], "reason": ""} for q in detail["observation_questions"]
            ],
        }
        _assert_matches(f"case-study/topics/{topic_id}/grade", "POST", f"/case-study/topics/{topic_id}/grade", grade_body)
    else:
        print("[SKIP] no case-study topics found")

    # Bean Validation control: Java should reject an incomplete body itself,
    # without ever calling Python.
    java_status, _ = _call(JAVA_BASE, "POST", "/curves/predict", {"L": "200"})
    if java_status != 400:
        raise Failure(f"curves/predict missing fields: expected java_status=400, got {java_status}")
    print("[OK] curves/predict missing fields -> 400")


def main() -> int:
    py_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(PY_PORT)],
        cwd=BACKEND_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    java_proc: subprocess.Popen | None = None
    try:
        _wait_until_ready(PY_BASE)

        java_proc = subprocess.Popen(
            [
                "mvn",
                "-q",
                "spring-boot:run",
                f"-Dspring-boot.run.arguments=--server.port={JAVA_PORT} "
                f"--python.service.base-url={PY_BASE}",
            ],
            cwd=JAVA_SERVICE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=(sys.platform == "win32"),
        )
        _wait_until_ready(JAVA_BASE)

        run_all_checks()
        print("\nAll endpoints match.")
        return 0
    except Failure as e:
        print(f"\nMISMATCH: {e}")
        return 1
    finally:
        for proc in (java_proc, py_proc):
            if proc is None:
                continue
            _terminate_tree(proc)


if __name__ == "__main__":
    raise SystemExit(main())
