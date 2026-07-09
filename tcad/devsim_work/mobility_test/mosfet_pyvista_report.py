from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

# Windows runtime bootstrap to reduce DLL resolution issues when launched from arbitrary CWD.
if os.name == "nt":
    _conda_prefix = Path(os.environ.get("CONDA_PREFIX", ""))
    _dll_dirs = [
        _conda_prefix / "Library" / "bin",
        _conda_prefix / "DLLs",
    ]
    _path_entries = []
    for _d in _dll_dirs:
        if _d.exists():
            _path_entries.append(str(_d))
            try:
                os.add_dll_directory(str(_d))
            except (AttributeError, OSError):
                pass
    if _path_entries:
        os.environ["PATH"] = ";".join(_path_entries + [os.environ.get("PATH", "")])

    _mkl = _conda_prefix / "Library" / "bin" / "mkl_rt.2.dll"
    if _mkl.exists() and not os.environ.get("DEVSIM_MATH_LIBS"):
        os.environ["DEVSIM_MATH_LIBS"] = str(_mkl)

import matplotlib.pyplot as plt
import numpy as np
import pyvista as pv


def _safe_eval(expr: str, symbols: dict[str, float]) -> float:
    return float(eval(expr, {"__builtins__": {}}, dict(symbols)))


def _collect_datasets(obj, out):
    if obj is None:
        return
    if hasattr(obj, "n_blocks"):
        for i in range(obj.n_blocks):
            _collect_datasets(obj[i], out)
        return
    if hasattr(obj, "n_points") and obj.n_points > 0:
        out.append(obj)


def _merge_datasets(obj):
    datasets = []
    _collect_datasets(obj, datasets)
    if not datasets:
        raise ValueError("No readable mesh block with scalar arrays was found.")
    if len(datasets) == 1:
        return datasets[0]
    return pv.merge(datasets, merge_points=False)


def _find_dataset_with_array(obj, array_name: str):
    if obj is None:
        return None
    if hasattr(obj, "n_blocks"):
        for i in range(obj.n_blocks):
            found = _find_dataset_with_array(obj[i], array_name)
            if found is not None:
                return found
        return None
    if hasattr(obj, "array_names") and array_name in obj.array_names:
        return obj
    return None


def _leaf_datasets(obj):
    leaves = []

    def _walk(node):
        if node is None:
            return
        if hasattr(node, "n_blocks"):
            for i in range(node.n_blocks):
                _walk(node[i])
            return
        if hasattr(node, "n_points") and node.n_points > 0:
            leaves.append(node)

    _walk(obj)
    return leaves


def _parse_geo_contacts_and_dimensions(geo_path: Path):
    symbols = {}
    points = {}
    lines = {}
    physical_lines = {}

    for raw in geo_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue

        if "=" in line and line.endswith(";"):
            lhs = line.split("=", 1)[0].strip()
            if lhs.replace("_", "").isalnum() and lhs[0].isalpha() and "(" not in lhs:
                expr = line.split("=", 1)[1].rstrip(";").strip()
                try:
                    symbols[lhs] = _safe_eval(expr, symbols)
                except Exception:
                    pass

        if line.startswith("Point(") and "=" in line:
            pid = int(line.split("(", 1)[1].split(")", 1)[0])
            body = line.split("{", 1)[1].split("}", 1)[0]
            items = [x.strip() for x in body.split(",")]
            if len(items) >= 2:
                try:
                    x = _safe_eval(items[0], symbols)
                    y = _safe_eval(items[1], symbols)
                    points[pid] = (x, y)
                except Exception:
                    pass

        if line.startswith("Line(") and "=" in line:
            lid = int(line.split("(", 1)[1].split(")", 1)[0])
            body = line.split("{", 1)[1].split("}", 1)[0]
            ids = [int(x.strip()) for x in body.split(",") if x.strip()]
            if len(ids) == 2:
                lines[lid] = (ids[0], ids[1])

        if line.startswith("Physical Line(") and "=" in line:
            name = line.split("\"", 2)[1]
            body = line.split("{", 1)[1].split("}", 1)[0]
            lids = [int(x.strip()) for x in body.split(",") if x.strip()]
            if lids:
                physical_lines[name] = lids

    contacts = {}
    mapping = {
        "gate_contact": "GATE",
        "source_contact": "SOURCE",
        "drain_contact": "DRAIN",
        "body_contact": "BODY",
    }
    for key, label in mapping.items():
        lids = physical_lines.get(key, [])
        for lid in lids:
            if lid not in lines:
                continue
            p0, p1 = lines[lid]
            if p0 in points and p1 in points:
                contacts[label] = (points[p0], points[p1])
                break

    dims = {
        "Device width": symbols.get("device_width", np.nan) * 1e4,
        "Bulk height": symbols.get("device_thickness", np.nan) * 1e4,
        "Gate width": symbols.get("gate_width", np.nan) * 1e4,
        "Oxide thickness": symbols.get("oxide_thickness", np.nan) * 1e7,
        "Gate thickness": symbols.get("gate_thickness", np.nan) * 1e7,
    }
    return contacts, dims


def _split_material_blocks(dd_obj):
    silicon = []
    oxide = []
    for leaf in _leaf_datasets(dd_obj):
        arrs = set(getattr(leaf, "array_names", []))
        if "Electrons" in arrs or "Holes" in arrs:
            silicon.append(leaf)
        else:
            oxide.append(leaf)
    return silicon, oxide


def _build_total_current_density_mesh(dd_obj):
    meshes = []
    for leaf in _leaf_datasets(dd_obj):
        arrs = set(getattr(leaf, "array_names", []))
        needed = {"ElectronCurrent_x", "ElectronCurrent_y", "HoleCurrent_x", "HoleCurrent_y"}
        if not needed.issubset(arrs):
            continue
        m = leaf.copy(deep=True)
        jx = np.asarray(m["ElectronCurrent_x"]) + np.asarray(m["HoleCurrent_x"])
        jy = np.asarray(m["ElectronCurrent_y"]) + np.asarray(m["HoleCurrent_y"])
        mag = np.hypot(jx, jy)
        mag = np.nan_to_num(mag, nan=1e-30, posinf=1e30, neginf=1e-30)
        mag = np.where(mag <= 0.0, 1e-30, mag)
        m["TotalCurrentDensity"] = mag
        meshes.append(m)
    if not meshes:
        return None
    if len(meshes) == 1:
        return meshes[0]
    return pv.merge(meshes, merge_points=False)


def _build_abs_netdoping_mesh(dd_obj):
    meshes = []
    for leaf in _leaf_datasets(dd_obj):
        arrs = set(getattr(leaf, "array_names", []))
        if "NetDoping" not in arrs:
            continue
        m = leaf.copy(deep=True)
        vals = np.asarray(m["NetDoping"])
        vals = np.abs(np.nan_to_num(vals, nan=0.0, posinf=1e30, neginf=-1e30))
        vals = np.where(vals <= 0.0, 1e-30, vals)
        m["AbsNetDoping"] = vals
        meshes.append(m)

    if not meshes:
        return None
    if len(meshes) == 1:
        return meshes[0]
    return pv.merge(meshes, merge_points=False)


def _robust_positive_clim(mesh, scalar_name: str, low_q: float = 0.02, high_q: float = 0.98):
    if mesh is None or scalar_name not in getattr(mesh, "array_names", []):
        return None
    vals = np.asarray(mesh[scalar_name])
    vals = vals[np.isfinite(vals) & (vals > 0.0)]
    if vals.size == 0:
        return None
    if vals.size < 16:
        lo = float(np.min(vals))
        hi = float(np.max(vals))
    else:
        lo = float(np.quantile(vals, low_q))
        hi = float(np.quantile(vals, high_q))
    if not np.isfinite(lo) or not np.isfinite(hi):
        return None
    if hi <= lo:
        lo = float(np.min(vals))
        hi = float(np.max(vals))
    if hi <= lo:
        hi = lo * 1.01
    return (lo, hi)


def _parse_ivpoints(log_path: Path):
    raw = log_path.read_bytes()
    text = None
    for enc in ("utf-8", "utf-16", "utf-16-le", "cp949"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="replace")

    points = {
        "IDVD_VG1P0": [],
        "IDVG_VD0P05": [],
        "IDVG_VD1P5": [],
    }
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("IVPOINT"):
            continue
        parts = line.split()
        # expected: IVPOINT <TAG> <GateV> <DrainV> <Idrain>
        if len(parts) < 5:
            continue
        tag = parts[1]
        if tag not in points:
            continue
        try:
            gate_v = float(parts[2])
            drain_v = float(parts[3])
            i_total = float(parts[4])
        except ValueError:
            continue
        points[tag].append((gate_v, drain_v, i_total))

    for key in points:
        points[key].sort(key=lambda x: x[1] if key == "IDVD_VG1P0" else x[0])

    return points


def _extract_xy(points, x_mode: str):
    if not points:
        return [], []
    if x_mode == "drain":
        x = [p[1] for p in points]
    else:
        x = [p[0] for p in points]
    y = [p[2] for p in points]
    return x, y


def _plot_curve(ax, x, y, title: str, xlabel: str, log_y: bool, current_unit: str):
    if not x:
        ax.set_title(f"{title} (No data)")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(f"Drain current ({current_unit})")
        ax.grid(True, alpha=0.35)
        return

    ax.plot(x, y, marker="o", linewidth=1.4)
    if log_y:
        if np.all(np.asarray(y) > 0.0):
            ax.set_yscale("log")
            ax.set_title(f"{title} (Log y)")
        else:
            # Preserve sign while still showing logarithmic behavior on y-axis.
            ax.set_yscale("symlog", linthresh=1e-12)
            ax.set_title(f"{title} (Symlog y)")
    else:
        ax.set_title(f"{title} (Linear)")

    ax.set_xlabel(xlabel)
    ax.set_ylabel(f"Drain current ({current_unit})")
    ax.grid(True, which="both", alpha=0.35)


def _curve_defs():
    return [
        ("IDVD_VG1P0", "drain", "Id-Vd @ Vg=1.0V", "Drain bias (V)"),
        ("IDVG_VD0P05", "gate", "Id-Vg @ Vd=0.05V", "Gate bias (V)"),
        ("IDVG_VD1P5", "gate", "Id-Vg @ Vd=1.5V", "Gate bias (V)"),
    ]


def _infer_snapshot_bias(iv):
    # DD field snapshot is written after all sweeps; this is usually last point of IDVG_VD1P5.
    for tag in ("IDVG_VD1P5", "IDVG_VD0P05", "IDVD_VG1P0"):
        pts = iv.get(tag, [])
        if pts:
            gv, dv, _ = pts[-1]
            return gv, dv
    return None


def _save_iv_plot_images(iv, out_dir: Path, current_unit: str):
    images = []
    idx = 0
    for tag, x_mode, title, xlabel in _curve_defs():
        x, y = _extract_xy(iv.get(tag, []), x_mode)
        for log_y in (False, True):
            fig, ax = plt.subplots(figsize=(7.8, 4.5), dpi=140)
            _plot_curve(ax, x, y, title, xlabel, log_y=log_y, current_unit=current_unit)
            fig.tight_layout()
            image_path = out_dir / f"iv_panel_{idx}.png"
            fig.savefig(image_path)
            plt.close(fig)
            label = f"{title} ({'Linear' if not log_y else 'Log y'})"
            images.append((label, image_path))
            idx += 1
    return images


def _set_gate_up_camera(p):
    p.view_xy()
    p.camera.up = (0.0, -1.0, 0.0)


def _show_axes_with_units(p, bounds):
    p.show_bounds(
        bounds=bounds,
        grid="front",
        location="outer",
        ticks="outside",
        fmt="%.6f",
        n_xlabels=6,
        n_ylabels=6,
        show_zaxis=False,
        show_zlabels=False,
        xtitle="x (cm)",
        ytitle="y (cm)",
        font_size=8,
    )


def _add_contacts_from_geo(p, contacts, bounds):
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    z0 = 0.0 if zmin <= 0.0 <= zmax else zmin

    colors = {
        "GATE": "yellow",
        "SOURCE": "lime",
        "DRAIN": "orange",
        "BODY": "cyan",
    }

    label_points = []
    label_names = []
    for name, seg in contacts.items():
        (x0, y0), (x1, y1) = seg
        line = pv.Line((x0, y0, z0), (x1, y1, z0))
        p.add_mesh(line, color=colors.get(name, "white"), line_width=2)
        label_points.append([(x0 + x1) * 0.5, (y0 + y1) * 0.5, z0])
        label_names.append(name)

    if label_points:
        p.add_point_labels(
            np.asarray(label_points),
            label_names,
            font_size=10,
            shape_opacity=0.15,
            show_points=False,
        )


def _add_plot_image_panel(p, row: int, col: int, title: str, image_path: Path):
    p.subplot(row, col)
    texture = pv.read_texture(str(image_path))
    plane = pv.Plane(i_size=2.8, j_size=1.8)
    p.add_mesh(plane, texture=texture, lighting=False, show_edges=False)
    p.add_text(title, font_size=10)
    p.view_xy()
    p.enable_parallel_projection()
    p.reset_camera()
    p.camera.zoom(1.35)


def _build_pyvista_dashboard(
    mesh,
    silicon_blocks,
    oxide_blocks,
    abs_netdoping_mesh,
    tcd_mesh,
    iv_images,
    contacts,
    dims,
    current_unit,
    snapshot_bias,
):
    has_net_doping = abs_netdoping_mesh is not None
    has_tcd = tcd_mesh is not None
    view_bounds = mesh.bounds

    p = pv.Plotter(shape=(3, 3), off_screen=False, window_size=(1800, 980))

    p.subplot(0, 0)
    for blk in silicon_blocks:
        p.add_mesh(blk, color="#4C78A8", opacity=0.85, show_edges=True, line_width=0.6)
    for blk in oxide_blocks:
        p.add_mesh(blk, color="#F2CF5B", opacity=0.95, show_edges=True, line_width=0.6)
    _add_contacts_from_geo(p, contacts, view_bounds)
    p.add_text("Mesh by Material", font_size=11)
    z_depth_cm = max(0.0, view_bounds[5] - view_bounds[4])
    if z_depth_cm > 0.0:
        z_text = f"Depth(z): {z_depth_cm * 1e4:.2f} um"
    else:
        z_text = "Depth(z): N/A (2D)"

    dim_text = (
        f"Width: {dims['Device width']:.2f} um\n"
        f"Bulk Height: {dims['Bulk height']:.2f} um\n"
        f"Gate Width: {dims['Gate width']:.2f} um\n"
        f"Oxide: {dims['Oxide thickness']:.0f} nm\n"
        f"Gate: {dims['Gate thickness']:.0f} nm\n"
        f"{z_text}\n"
        f"I unit: {current_unit}"
    )
    p.add_text(dim_text, position="lower_left", font_size=9)
    p.add_legend(
        labels=[
            ["Silicon", "#4C78A8"],
            ["SiO2", "#F2CF5B"],
            ["Contacts", "white"],
        ],
        bcolor="black",
        size=(0.22, 0.2),
    )
    _show_axes_with_units(p, view_bounds)
    _set_gate_up_camera(p)

    p.subplot(0, 1)
    if has_net_doping:
        net_clim = _robust_positive_clim(abs_netdoping_mesh, "AbsNetDoping", low_q=0.01, high_q=0.995)
        p.add_mesh(
            abs_netdoping_mesh,
            scalars="AbsNetDoping",
            cmap="cividis",
            log_scale=True,
            clim=net_clim,
            n_colors=12,
            scalar_bar_args={
                "title": "|NetDoping| (cm^-3)",
                "vertical": True,
                "position_x": 0.82,
                "position_y": 0.08,
                "height": 0.84,
                "width": 0.06,
            },
        )
        for blk in oxide_blocks:
            p.add_mesh(blk, color="#F2CF5B", opacity=0.45, show_edges=True, line_width=0.6)
        p.add_text("Absolute NetDoping", font_size=11)
    else:
        p.add_text("NetDoping (missing)", font_size=11)
        p.add_mesh(mesh, show_edges=True, color="lightgray", line_width=1)
    _add_contacts_from_geo(p, contacts, view_bounds)
    _show_axes_with_units(p, view_bounds)
    _set_gate_up_camera(p)

    p.subplot(0, 2)
    if has_tcd:
        tcd_clim = _robust_positive_clim(tcd_mesh, "TotalCurrentDensity", low_q=0.02, high_q=0.98)
        p.add_mesh(
            tcd_mesh,
            scalars="TotalCurrentDensity",
            cmap="turbo",
            log_scale=True,
            clim=tcd_clim,
            n_colors=10,
            scalar_bar_args={
                "title": "|Jtotal| (A/cm^2)",
                "vertical": True,
                "position_x": 0.82,
                "position_y": 0.08,
                "height": 0.84,
                "width": 0.06,
            },
        )
        for blk in oxide_blocks:
            p.add_mesh(blk, color="#F2CF5B", opacity=0.45, show_edges=True, line_width=0.6)
        p.add_text("Total Current Density", font_size=11)
        if snapshot_bias is not None:
            gv, dv = snapshot_bias
            p.add_text(f"Snapshot: Vg={gv:.2f} V, Vd={dv:.2f} V", position="lower_right", font_size=9)
    else:
        p.add_text("Total Current Density (missing)", font_size=11)
        p.add_mesh(mesh, show_edges=True, color="lightgray", line_width=1)
    _add_contacts_from_geo(p, contacts, view_bounds)
    _show_axes_with_units(p, view_bounds)
    _set_gate_up_camera(p)

    _add_plot_image_panel(p, 1, 0, iv_images[0][0], iv_images[0][1])
    _add_plot_image_panel(p, 1, 1, iv_images[2][0], iv_images[2][1])
    _add_plot_image_panel(p, 1, 2, iv_images[4][0], iv_images[4][1])
    _add_plot_image_panel(p, 2, 0, iv_images[1][0], iv_images[1][1])
    _add_plot_image_panel(p, 2, 1, iv_images[3][0], iv_images[3][1])
    _add_plot_image_panel(p, 2, 2, iv_images[5][0], iv_images[5][1])

    return p, has_net_doping, has_tcd


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate MOSFET visualization report (mesh, doping, carriers, I-V)."
    )
    parser.add_argument("--mobility-dir", default=".", help="Path to mobility output folder")
    parser.add_argument("--log-file", default="gmsh_mos2d_run_test.log", help="Run log filename under mobility folder")
    parser.add_argument("--no-show", action="store_true", help="Do not open interactive windows")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    mobility_dir = (script_dir / args.mobility_dir).resolve()

    dd_vtm = mobility_dir / "gmsh_mos2d_dd.vtm"
    dd_dat = mobility_dir / "gmsh_mos2d_dd.dat"
    potential_vtm = mobility_dir / "gmsh_mos2d_potentialonly.vtm"
    run_log = mobility_dir / args.log_file

    if not dd_vtm.exists() and not dd_dat.exists():
        raise FileNotFoundError(f"Missing DD result file: {dd_vtm} or {dd_dat}")
    if not run_log.exists():
        raise FileNotFoundError(f"Missing run log: {run_log}")

    if dd_vtm.exists():
        dd_obj = pv.get_reader(str(dd_vtm)).read()
    else:
        dd_obj = pv.get_reader(str(dd_dat)).read()

    dd_mesh = _merge_datasets(dd_obj)
    abs_netdoping_mesh = _build_abs_netdoping_mesh(dd_obj)
    electrons_mesh = _find_dataset_with_array(dd_obj, "Electrons")
    tcd_mesh = _build_total_current_density_mesh(dd_obj)
    silicon_blocks, oxide_blocks = _split_material_blocks(dd_obj)

    geo_path = mobility_dir / "gmsh_mos2d.geo"
    contacts, dims = _parse_geo_contacts_and_dimensions(geo_path)

    if potential_vtm.exists():
        out_mesh = _merge_datasets(pv.get_reader(str(potential_vtm)).read())
    else:
        out_mesh = dd_mesh

    iv = _parse_ivpoints(run_log)
    snapshot_bias = _infer_snapshot_bias(iv)
    z_depth_cm = max(0.0, out_mesh.bounds[5] - out_mesh.bounds[4])
    current_unit = "A" if z_depth_cm > 0.0 else "A/cm"
    if not args.no_show:
        with tempfile.TemporaryDirectory(prefix="mos_iv_panels_") as tmp:
            iv_images = _save_iv_plot_images(iv, Path(tmp), current_unit=current_unit)
            p, has_net_doping, has_tcd = _build_pyvista_dashboard(
                out_mesh,
                silicon_blocks,
                oxide_blocks,
                abs_netdoping_mesh,
                tcd_mesh,
                iv_images,
                contacts,
                dims,
                current_unit,
                snapshot_bias,
            )
            has_electrons = electrons_mesh is not None
            p.show()
    else:
        has_net_doping = abs_netdoping_mesh is not None
        has_electrons = electrons_mesh is not None
        has_tcd = tcd_mesh is not None
        plt.close("all")

    print("Interactive mode:", not args.no_show)
    print("Has NetDoping:", has_net_doping)
    print("Has Electrons:", has_electrons)
    print("Has TotalCurrentDensity:", has_tcd)
    print("Id-Vd points:", len(iv["IDVD_VG1P0"]))
    print("Id-Vg @ Vd=0.05 points:", len(iv["IDVG_VD0P05"]))
    print("Id-Vg @ Vd=1.5 points:", len(iv["IDVG_VD1P5"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
