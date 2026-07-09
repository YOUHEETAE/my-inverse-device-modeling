from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_DLL_DIR_HANDLES = []


def configure_devsim_runtime(caller_file: str) -> Path:
    this_file = Path(caller_file).resolve()
    work_root = this_file.parents[1]
    tcad_root = work_root.parent
    devsim_repo = tcad_root / "devsim"

    if devsim_repo.exists():
        devsim_repo_str = str(devsim_repo)
        if devsim_repo_str not in sys.path:
            sys.path.insert(0, devsim_repo_str)

    if os.name == "nt":
        dll_dirs = []
        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            dll_dirs.append(Path(conda_prefix) / "Library" / "bin")
        dll_dirs.append(Path(sys.prefix) / "Library" / "bin")
        dll_dirs.append(Path(sys.base_prefix) / "Library" / "bin")

        seen = set()
        for dll_dir in dll_dirs:
            dll_dir_str = str(dll_dir)
            key = dll_dir_str.lower()
            if key in seen or not dll_dir.exists():
                continue
            seen.add(key)

            if hasattr(os, "add_dll_directory"):
                _DLL_DIR_HANDLES.append(os.add_dll_directory(dll_dir_str))
            os.environ["PATH"] = f"{dll_dir_str};{os.environ.get('PATH', '')}"

            if "DEVSIM_MATH_LIBS" not in os.environ:
                mkl_candidates = sorted(dll_dir.glob("mkl_rt*.dll"))
                if mkl_candidates:
                    mkl_dll = str(mkl_candidates[0])
                    os.environ["DEVSIM_MATH_LIBS"] = f"{mkl_dll};{mkl_dll};{mkl_dll}"

    return this_file.parent


def mesh_path(example_dir: Path, filename: str) -> Path:
    return example_dir / filename


def read_mesh_format(mesh_path: Path) -> str | None:
    try:
        lines = mesh_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for index, line in enumerate(lines):
        if line.strip() == "$MeshFormat" and index + 1 < len(lines):
            return lines[index + 1].strip().split()[0]
    return None


def read_mesh_counts(mesh_path: Path) -> tuple[int, int] | None:
    try:
        lines = mesh_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    node_count = None
    element_count = None
    for index, line in enumerate(lines):
        text = line.strip()
        if text == "$Nodes" and index + 1 < len(lines):
            try:
                node_count = int(lines[index + 1].strip().split()[0])
            except (TypeError, ValueError, IndexError):
                node_count = None
        elif text == "$Elements" and index + 1 < len(lines):
            try:
                element_count = int(lines[index + 1].strip().split()[0])
            except (TypeError, ValueError, IndexError):
                element_count = None

    if node_count is None or element_count is None:
        return None
    return node_count, element_count


def find_gmsh_executable() -> str | None:
    candidates = []
    for candidate in (os.environ.get("GMSH_EXE"), os.environ.get("GMSH_PATH")):
        if candidate:
            candidates.append(Path(candidate))

    gmsh_home = os.environ.get("GMSH_HOME")
    if gmsh_home:
        candidates.append(Path(gmsh_home) / "gmsh.exe")

    which_result = shutil.which("gmsh")
    if which_result:
        candidates.append(Path(which_result))

    user_home = Path.home()
    search_roots = [
        user_home / "Downloads",
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
        user_home / "AppData" / "Local",
    ]
    for root in search_roots:
        if not root.exists():
            continue
        try:
            matches = list(root.glob("**/gmsh.exe"))
        except OSError:
            continue
        if matches:
            candidates.extend(matches[:5])

    seen = set()
    for candidate in candidates:
        candidate_str = str(candidate)
        key = candidate_str.lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            return candidate_str
    return None


def ensure_msh2(mesh_file: Path) -> None:
    mesh_format = read_mesh_format(mesh_file)
    if mesh_format is None or mesh_format in {"2.1", "2.2"}:
        return

    original_counts = read_mesh_counts(mesh_file)
    gmsh_exe = find_gmsh_executable()
    if not gmsh_exe:
        raise RuntimeError(
            "Gmsh executable was not found. Set GMSH_EXE to gmsh.exe or add Gmsh to PATH."
        )

    temp_mesh_path = None
    with tempfile.NamedTemporaryFile(suffix=".msh", delete=False, dir=str(mesh_file.parent)) as handle:
        temp_mesh_path = Path(handle.name)

    try:
        command = [
            gmsh_exe,
            str(mesh_file),
            "-save",
            "-format",
            "msh2",
            "-o",
            str(temp_mesh_path),
        ]
        completed = subprocess.run(
            command,
            cwd=str(mesh_file.parent),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "Failed to convert mesh to msh2 using Gmsh.\n"
                f"Command: {' '.join(command)}\n"
                f"stdout:\n{completed.stdout}\n"
                f"stderr:\n{completed.stderr}"
            )

        temp_format = read_mesh_format(temp_mesh_path)
        temp_counts = read_mesh_counts(temp_mesh_path)
        if temp_format != "2.2":
            raise RuntimeError(
                f"Gmsh conversion completed, but output mesh format is '{temp_format}', not '2.2'."
            )
        if temp_counts is None or temp_counts[0] <= 0 or temp_counts[1] <= 0:
            raise RuntimeError(
                "Converted mesh is empty after Gmsh export. "
                f"Original counts: {original_counts}, converted counts: {temp_counts}."
            )

        temp_mesh_path.replace(mesh_file)
        print(
            f"Converted {mesh_file.name} from MeshFormat {mesh_format} to 2.2 using {gmsh_exe} "
            f"(nodes={temp_counts[0]}, elements={temp_counts[1]})"
        )
    finally:
        if temp_mesh_path and temp_mesh_path.exists():
            temp_mesh_path.unlink()
