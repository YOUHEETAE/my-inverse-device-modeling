from __future__ import annotations

import os
import sys
from pathlib import Path


_DLL_HANDLES = []


def configure_devsim_runtime() -> None:
    """Configure the existing local DEVSIM math libraries on Windows."""
    if os.name != "nt":
        return

    conda_bin = Path(sys.prefix) / "Library" / "bin"
    if conda_bin.exists():
        if hasattr(os, "add_dll_directory"):
            _DLL_HANDLES.append(os.add_dll_directory(str(conda_bin)))
        mkl_candidates = sorted(conda_bin.glob("mkl_rt*.dll"))
        if mkl_candidates:
            mkl = str(mkl_candidates[0])
            os.environ.setdefault("DEVSIM_MATH_LIBS", f"{mkl};{mkl};{mkl}")
            return

    math_dir = Path.home() / "devsim_mathlibs"
    libraries = (
        math_dir / "libopenblas.dll",
        math_dir / "liblapack.dll",
        math_dir / "libblas.dll",
    )
    missing = [path for path in libraries if not path.exists()]
    if missing:
        names = ", ".join(str(path) for path in missing)
        raise RuntimeError(f"DEVSIM math libraries not found: {names}")

    if hasattr(os, "add_dll_directory"):
        _DLL_HANDLES.append(os.add_dll_directory(str(math_dir)))
    os.environ.setdefault("DEVSIM_MATH_LIBS", ";".join(map(str, libraries)))
