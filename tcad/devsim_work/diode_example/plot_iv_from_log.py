from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt


def _to_float(token: str):
    try:
        return float(token)
    except ValueError:
        return None


def _read_log_text(log_path: Path) -> str:
    raw = log_path.read_bytes()

    # PowerShell Tee-Object commonly writes UTF-16 LE with BOM on Windows.
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp949", errors="replace")


def parse_currents(log_path: Path) -> Dict[str, List[Tuple[float, float]]]:
    """Parse top/bot current lines from diode_2d log output."""
    data: Dict[str, List[Tuple[float, float]]] = {"top": [], "bot": []}

    text = _read_log_text(log_path)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 3:
            continue

        contact = parts[0].lower()
        if contact not in data:
            continue

        values = [_to_float(p) for p in parts[1:]]
        values = [v for v in values if v is not None]
        if len(values) < 2:
            continue

        voltage = values[0]
        # DevSim PrintCurrents prints several current columns; the last one is total current.
        current_total = values[-1]
        data[contact].append((voltage, current_total))

    return data


def deduplicate_and_sort(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    by_voltage: Dict[float, float] = {}
    for voltage, current in points:
        by_voltage[voltage] = current
    return sorted(by_voltage.items(), key=lambda x: x[0])


def build_plot(points: List[Tuple[float, float]], contact: str, out_path: Path | None, show_plot: bool) -> None:
    if not points:
        raise ValueError(f"No points were parsed for contact '{contact}'.")

    x = [p[0] for p in points]
    y = [p[1] for p in points]

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), dpi=120)

    axes[0].plot(x, y, marker="o", linewidth=1.6)
    axes[0].set_title(f"I-V Curve ({contact})")
    axes[0].set_xlabel("Voltage (V)")
    axes[0].set_ylabel("Current (A)")
    axes[0].grid(True, alpha=0.35)

    y_abs = [abs(v) for v in y]
    y_abs = [v if v > 0 else 1e-30 for v in y_abs]
    axes[1].semilogy(x, y_abs, marker="o", linewidth=1.6)
    axes[1].set_title(f"|I|-V (Semilogy, {contact})")
    axes[1].set_xlabel("Voltage (V)")
    axes[1].set_ylabel("|Current| (A)")
    axes[1].grid(True, which="both", alpha=0.35)

    fig.tight_layout()
    if out_path is not None:
        fig.savefig(out_path)

    if show_plot:
        plt.show()

    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract currents from diode_2d_run.log and draw an I-V curve."
    )
    parser.add_argument(
        "--log",
        default="diode_2d_run.log",
        help="Path to simulation log file (default: diode_2d_run.log)",
    )
    parser.add_argument(
        "--contact",
        default="top",
        choices=["top", "bot"],
        help="Contact current to plot (top or bot)",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Optional output image path. If omitted, no image file is written.",
    )
    parser.add_argument(
        "--no-show",
        action="store_true",
        help="Do not open a plot window.",
    )

    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        raise FileNotFoundError(f"Log file not found: {log_path}")

    parsed = parse_currents(log_path)
    points = deduplicate_and_sort(parsed[args.contact])
    out_path = Path(args.out) if args.out else None
    build_plot(points, args.contact, out_path, show_plot=not args.no_show)

    print(f"Parsed {len(points)} I-V points for contact '{args.contact}'.")
    for voltage, current in points:
        print(f"V={voltage:.6g} V, I={current:.6e} A")
    if out_path is not None:
        print(f"Saved plot: {out_path}")
    else:
        print("No image file requested (plot window only).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
