from __future__ import annotations

import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PERSONAL_PATH_PATTERN = re.compile(
    r"(?:[A-Za-z]:\\Users\\[^\\\s]+|/Users/[^/\s]+|/home/[^/\s]+)"
)
SECRET_FILENAME_PATTERN = re.compile(
    r"(^|/)(?:\.env(?:\..+)?|.*(?:secret|credential|api[_-]?key).*)$",
    re.IGNORECASE,
)
SECRET_CONTENT_PATTERNS = (
    re.compile(r"\bgsk_[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(
        r"(?m)^\s*(?:GROQ_API_KEY|OPENAI_API_KEY|API_KEY|PASSWORD|SECRET|"
        r"ACCESS_TOKEN|AUTH_TOKEN)"
        r"\s*=\s*(?!replace_|your-|example|dummy|test|<)[^\s#]{12,}\s*$"
    ),
)
TEXT_SCAN_SUFFIXES = {
    "",
    ".cfg",
    ".env",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str
    required: bool = True


def _run_git(*arguments: str) -> subprocess.CompletedProcess[str]:
    executable = shutil.which("git")
    if executable is None and os.name == "nt":
        roots = [
            os.getenv("ProgramFiles"),
            os.getenv("ProgramFiles(x86)"),
            os.getenv("LOCALAPPDATA"),
        ]
        candidates = [
            Path(root) / "Git" / "cmd" / "git.exe"
            for root in roots[:2]
            if root
        ]
        if roots[2]:
            candidates.append(
                Path(roots[2]) / "Programs" / "Git" / "cmd" / "git.exe"
            )
        executable = next(
            (str(path) for path in candidates if path.is_file()),
            None,
        )
    if executable is None:
        return subprocess.CompletedProcess(
            args=["git", *arguments],
            returncode=127,
            stdout="",
            stderr="git executable not found",
        )
    return subprocess.run(
        [executable, *arguments],
        cwd=REPOSITORY_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _git_upload_candidates() -> tuple[set[str], str | None]:
    result = _run_git("ls-files", "--cached", "--others", "--exclude-standard")
    if result.returncode != 0:
        return set(), "git candidate enumeration failed"
    return {
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip()
    }, None


def _required_paths() -> Check:
    paths = [
        "deployment/runtime_manifest.json",
        "environment.yml",
        "frontend/app.py",
        "backend/public_presentation.py",
        "docs/deployment_handoff.md",
        "docs/security_privacy_handoff.md",
        "ai/tools/check_runtime_package.py",
    ]
    candidates, git_error = _git_upload_candidates()
    if git_error:
        return Check("required_runtime_files", False, git_error)
    missing = [path for path in paths if not (REPOSITORY_ROOT / path).is_file()]
    excluded = [path for path in paths if path not in candidates]
    problems: list[str] = []
    if missing:
        problems.append(f"missing: {missing}")
    if excluded:
        problems.append(f"not included by git add -A: {excluded}")
    return Check(
        "required_runtime_files",
        not problems,
        "all required files are present and upload candidates"
        if not problems
        else "; ".join(problems),
    )


def _python_version() -> Check:
    passed = sys.version_info[:2] == (3, 11)
    return Check(
        "python_version",
        passed,
        f"running Python {sys.version_info.major}.{sys.version_info.minor}; expected 3.11",
    )


def _runtime_imports() -> Check:
    names = ["tkinter", "numpy", "scipy", "matplotlib", "sklearn", "xgboost"]
    failures: list[str] = []
    for name in names:
        try:
            importlib.import_module(name)
        except Exception as error:  # pragma: no cover - environment dependent
            failures.append(f"{name}: {type(error).__name__}")
    return Check(
        "runtime_imports",
        not failures,
        "all runtime imports available" if not failures else "; ".join(failures),
    )


def _git_hygiene() -> Check:
    candidates, git_error = _git_upload_candidates()
    if git_error:
        return Check("git_hygiene", False, git_error)
    unsafe = [
        path
        for path in candidates
        if SECRET_FILENAME_PATTERN.search(path) and path != ".env.example"
    ]
    secret_contents: list[str] = []
    for relative_path in sorted(candidates):
        path = REPOSITORY_ROOT / relative_path
        if (
            not path.is_file()
            or path.suffix.lower() not in TEXT_SCAN_SUFFIXES
            or path.stat().st_size > 2 * 1024 * 1024
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        if any(pattern.search(text) for pattern in SECRET_CONTENT_PATTERNS):
            secret_contents.append(relative_path)
    problems: list[str] = []
    if unsafe:
        problems.append(f"unsafe candidate filenames: {unsafe}")
    if secret_contents:
        problems.append(f"possible secret contents: {secret_contents}")
    return Check(
        "git_hygiene",
        not problems,
        "no secret filenames or high-confidence secret values in upload candidates"
        if not problems
        else "; ".join(problems),
    )


def _ignored_private_state() -> Check:
    paths = [
        "runtime/learning_sessions/example.json",
        "runtime/platform_readiness_release.json",
        ".omx/state.json",
        ".env",
    ]
    failures: list[str] = []
    for path in paths:
        result = _run_git("check-ignore", "-q", path)
        if result.returncode != 0:
            failures.append(path)
    return Check(
        "private_state_ignored",
        not failures,
        "private state patterns are ignored"
        if not failures
        else f"not ignored: {failures}",
    )


def _public_document_paths() -> Check:
    files = [
        REPOSITORY_ROOT / "README.md",
        REPOSITORY_ROOT / "frontend" / "README.md",
        REPOSITORY_ROOT / "docs" / "deployment_handoff.md",
        REPOSITORY_ROOT / "docs" / "groq_llm_setup.md",
        REPOSITORY_ROOT / "docs" / "security_privacy_handoff.md",
    ]
    findings: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if PERSONAL_PATH_PATTERN.search(text):
            findings.append(path.relative_to(REPOSITORY_ROOT).as_posix())
    return Check(
        "portable_public_documentation",
        not findings,
        "no developer-specific absolute paths"
        if not findings
        else f"personal paths in: {findings}",
    )


def _runtime_writable() -> Check:
    runtime = REPOSITORY_ROOT / "runtime"
    try:
        runtime.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix="readiness-",
            suffix=".tmp",
            dir=runtime,
            delete=True,
        ) as handle:
            handle.write("readiness")
            handle.flush()
    except OSError as error:  # pragma: no cover - environment dependent
        return Check("runtime_writable", False, type(error).__name__)
    return Check("runtime_writable", True, "runtime directory is writable")


def _provider_configuration() -> Check:
    variable_name = os.getenv("LLM_API_KEY_ENV", "GROQ_API_KEY")
    configured = bool(os.getenv(variable_name, "").strip())
    return Check(
        "provider_key_configured",
        configured,
        f"{variable_name} is configured"
        if configured
        else f"{variable_name} is not configured; AI calls will be unavailable",
        required=False,
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    factories: list[Callable[[], Check]] = [
        _required_paths,
        _python_version,
        _runtime_imports,
        _git_hygiene,
        _ignored_private_state,
        _public_document_paths,
        _runtime_writable,
        _provider_configuration,
    ]
    checks = [factory() for factory in factories]
    ready = all(check.passed for check in checks if check.required)
    report = {
        "schema_version": 1,
        "ready": ready,
        "application_kind": "desktop_tk",
        "checks": [asdict(check) for check in checks],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
