# Copyright 2013 DEVSIM LLC
#
# SPDX-License-Identifier: Apache-2.0

import os
import sys
from pathlib import Path


_DLL_DIR_HANDLES = []


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

from devsim import set_parameter, solve

from devsim.python_packages.simple_physics import GetContactBiasName, PrintCurrents
import diode_common

# dio1
#
# Make doping a step function
# print dat to text file for viewing in grace
# verify currents analytically
# in dio2 add recombination
#

device = "MyDevice"
region = "MyRegion"

diode_common.Create2DMesh(device, region)

diode_common.SetParameters(device=device, region=region)

diode_common.SetNetDoping(device=device, region=region)

diode_common.InitialSolution(device, region)

# Initial DC solution
solve(type="dc", absolute_error=1.0, relative_error=1e-12, maximum_iterations=30)

diode_common.DriftDiffusionInitialSolution(device, region)
###
### Drift diffusion simulation at equilibrium
###
solve(type="dc", absolute_error=1e10, relative_error=1e-10, maximum_iterations=30)

####
#### Sweep the bias from -2.0 to 2.0 Volts
####
v = -2.0
while v < 2.01:
    set_parameter(device=device, name=GetContactBiasName("top"), value=v)
    solve(type="dc", absolute_error=1e10, relative_error=1e-10, maximum_iterations=30)
    PrintCurrents(device, "top")
    PrintCurrents(device, "bot")
    v += 0.1
