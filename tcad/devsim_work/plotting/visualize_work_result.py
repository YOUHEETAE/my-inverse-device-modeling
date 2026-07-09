from __future__ import annotations

import argparse
from pathlib import Path


def _select_dataset(mesh):
    if hasattr(mesh, "array_names"):
        return mesh

    if hasattr(mesh, "n_blocks"):
        for index in range(mesh.n_blocks):
            block = mesh[index]
            if block is not None and hasattr(block, "array_names"):
                return block

    raise ValueError("Could not find a readable dataset block with scalar arrays.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Visualize a DEVSIM tecplot/vtk result from devsim_work."
    )
    parser.add_argument(
        "--input",
        default="../diode_example/gmsh_diode2d.dat",
        help="Path to the DEVSIM output file relative to this script (default: ../diode_example/gmsh_diode2d.dat)",
    )
    parser.add_argument(
        "--scalar",
        default="Electrons",
        help="Scalar field to color by (default: Electrons)",
    )
    parser.add_argument(
        "--camera",
        default="xy",
        help="Camera position name, e.g. xy, xz, yz, or isometric (default: xy)",
    )
    parser.add_argument(
        "--screenshot",
        default="",
        help="Optional screenshot output path. If omitted, no image file is written.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open an interactive window; useful for validation or screenshot-only runs.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    input_path = (script_dir / args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input result file not found: {input_path}")

    import pyvista as pv

    reader = pv.get_reader(str(input_path))
    mesh = _select_dataset(reader.read())
    if args.scalar not in mesh.array_names:
        raise ValueError(
            f"Scalar '{args.scalar}' not found. Available arrays: {', '.join(mesh.array_names)}"
        )

    screenshot_path = None
    if args.screenshot:
        screenshot_path = str((script_dir / args.screenshot).resolve())

    plotter = pv.Plotter(off_screen=args.no_show or bool(screenshot_path))
    plotter.add_mesh(mesh, scalars=args.scalar, log_scale=True, cmap="RdBu")
    plotter.show_grid()
    plotter.camera_position = args.camera

    if screenshot_path:
        plotter.show(screenshot=screenshot_path, auto_close=False)
        print(f"Saved screenshot: {screenshot_path}")
    elif args.no_show:
        plotter.show(auto_close=False)
    else:
        plotter.show()

    print(f"Loaded result: {input_path}")
    print(f"Available arrays: {', '.join(mesh.array_names)}")
    print(f"Active scalar: {args.scalar}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
