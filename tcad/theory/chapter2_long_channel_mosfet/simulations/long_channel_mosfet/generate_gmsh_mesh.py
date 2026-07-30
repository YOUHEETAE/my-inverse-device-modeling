from __future__ import annotations

from pathlib import Path

import gmsh


ROOT = Path(__file__).resolve().parent
GEO_FILE = ROOT / "long_channel_mos2d.geo"
MESH_FILE = ROOT / "long_channel_mos2d.msh"


def main() -> None:
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.open(str(GEO_FILE))
        gmsh.model.mesh.generate(2)
        gmsh.write(str(MESH_FILE))
    finally:
        gmsh.finalize()
    print(MESH_FILE)


if __name__ == "__main__":
    main()
