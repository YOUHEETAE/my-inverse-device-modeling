from __future__ import annotations

import argparse
from pathlib import Path

import gmsh


def generate_mesh(geo_path: Path, msh_path: Path) -> None:
    gmsh.initialize(["gmsh", "-v", "2"])
    try:
        gmsh.open(str(geo_path.resolve()))
        gmsh.model.mesh.generate(2)
        gmsh.option.setNumber("Mesh.MshFileVersion", 2.2)
        gmsh.write(str(msh_path.resolve()))
    finally:
        gmsh.finalize()

    if not msh_path.exists() or msh_path.stat().st_size == 0:
        raise RuntimeError(f"Python Gmsh did not create a usable mesh: {msh_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an msh2 mesh with the Python Gmsh API")
    parser.add_argument("geo_path", type=Path)
    parser.add_argument("msh_path", type=Path)
    args = parser.parse_args()
    generate_mesh(args.geo_path, args.msh_path)


if __name__ == "__main__":
    main()
