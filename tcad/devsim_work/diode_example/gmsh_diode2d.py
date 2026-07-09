# Copyright 2013 DEVSIM LLC
#
# SPDX-License-Identifier: Apache-2.0

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


_DLL_DIR_HANDLES = []
_EXAMPLE_DIR = Path(__file__).resolve().parent


def _configure_devsim_runtime() -> None:
    this_file = Path(__file__).resolve()
    tcad_root = this_file.parents[2]
    devsim_repo = tcad_root / "devsim"

    # Make local devsim package importable when running from devsim_work.
    if devsim_repo.exists():
        devsim_repo_str = str(devsim_repo)
        if devsim_repo_str not in sys.path:
            sys.path.insert(0, devsim_repo_str)

    if os.name != "nt":
        return

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


_configure_devsim_runtime()


def _read_mesh_format(mesh_path: Path) -> str | None:
    try:
        lines = mesh_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    for index, line in enumerate(lines):
        if line.strip() == "$MeshFormat" and index + 1 < len(lines):
            return lines[index + 1].strip().split()[0]
    return None


def _read_mesh_counts(mesh_path: Path) -> tuple[int, int] | None:
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


def _find_gmsh_executable() -> str | None:
    candidates = []

    env_candidates = [
        os.environ.get("GMSH_EXE"),
        os.environ.get("GMSH_PATH"),
    ]
    for candidate in env_candidates:
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


def _ensure_msh2(mesh_path: Path) -> None:
    mesh_format = _read_mesh_format(mesh_path)
    if mesh_format is None or mesh_format == "2.2":
        return

    mesh_counts = _read_mesh_counts(mesh_path)

    gmsh_exe = _find_gmsh_executable()
    if not gmsh_exe:
        raise RuntimeError(
            "Gmsh executable was not found. Set GMSH_EXE to gmsh.exe or add Gmsh to PATH."
        )

    with tempfile.NamedTemporaryFile(suffix=".msh", delete=False, dir=str(mesh_path.parent)) as handle:
        temp_mesh_path = Path(handle.name)

    try:
        command = [
            gmsh_exe,
            str(mesh_path),
            "-save",
            "-format",
            "msh2",
            "-o",
            str(temp_mesh_path),
        ]
        completed = subprocess.run(
            command,
            cwd=str(mesh_path.parent),
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

        temp_format = _read_mesh_format(temp_mesh_path)
        if temp_format != "2.2":
            raise RuntimeError(
                f"Gmsh conversion completed, but output mesh format is '{temp_format}', not '2.2'."
            )

        temp_counts = _read_mesh_counts(temp_mesh_path)
        if temp_counts is None:
            raise RuntimeError("Converted mesh could not be validated for node/element counts.")
        if temp_counts[0] <= 0 or temp_counts[1] <= 0:
            raise RuntimeError(
                "Converted mesh is empty after Gmsh export. "
                f"Original counts: {mesh_counts}, converted counts: {temp_counts}."
            )

        temp_mesh_path.replace(mesh_path)
        print(
            f"Converted {mesh_path.name} from MeshFormat {mesh_format} to 2.2 using {gmsh_exe} "
            f"(nodes={temp_counts[0]}, elements={temp_counts[1]})"
        )
    finally:
        if temp_mesh_path.exists():
            temp_mesh_path.unlink()


_ensure_msh2(_EXAMPLE_DIR / "gmsh_diode2d.msh")

from devsim import node_model, set_parameter, solve, write_devices

from devsim.python_packages.simple_physics import GetContactBiasName, PrintCurrents
import diode_common

device = "diode2d"
region = "Bulk"

diode_common.Create2DGmshMesh(device, region)

# this is is the devsim format
write_devices(file="gmsh_diode2d_out.msh")

diode_common.SetParameters(device=device, region=region)

####
#### NetDoping
####
node_model(
    device=device, region=region, name="Acceptors", equation="1.0e18*step(0.5e-5-y);"
)
node_model(
    device=device, region=region, name="Donors", equation="1.0e18*step(y-0.5e-5);"
)
node_model(device=device, region=region, name="NetDoping", equation="Donors-Acceptors;")

diode_common.InitialSolution(device, region)


####
#### Initial DC solution
####
solve(type="dc", absolute_error=1.0, relative_error=1e-12, maximum_iterations=30)

###
### Drift diffusion simulation at equilibrium
###
diode_common.DriftDiffusionInitialSolution(device, region)

solve(type="dc", absolute_error=1e10, relative_error=1e-10, maximum_iterations=50)

v = 0.0
while v < 0.51:
    set_parameter(device=device, name=GetContactBiasName("top"), value=v)
    solve(type="dc", absolute_error=1e10, relative_error=1e-10, maximum_iterations=30)
    PrintCurrents(device, "top")
    PrintCurrents(device, "bot")
    v += 0.1

write_devices(file="gmsh_diode2d.dat", type="tecplot")
write_devices(file="gmsh_diode2d_dd.msh", type="devsim")
