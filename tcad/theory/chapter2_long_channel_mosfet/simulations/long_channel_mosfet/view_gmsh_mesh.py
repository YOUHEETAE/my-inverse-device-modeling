from __future__ import annotations

from pathlib import Path

import gmsh


mesh_file = Path(__file__).resolve().parent / "long_channel_mos2d.msh"

gmsh.initialize()
try:
    gmsh.open(str(mesh_file))
    gmsh.fltk.run()
finally:
    gmsh.finalize()
