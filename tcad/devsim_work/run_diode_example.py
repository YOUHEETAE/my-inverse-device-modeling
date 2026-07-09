import csv
import os
import shutil
import sys
from pathlib import Path

work_root = Path(r"C:\Users\T590\devsim_project\inverse-device-modeling\tcad\devsim_work")
results_dir = work_root / "results"
results_dir.mkdir(parents=True, exist_ok=True)
summary_path = results_dir / "diode_example_summary.txt"
summary_path.write_text("", encoding="utf-8")

# Make DevSim importable from the cloned repository
repo_root = Path(r"C:\Users\T590\devsim_project\inverse-device-modeling\tcad\devsim")
sys.path.insert(0, str(repo_root))

# Ensure the math runtime is available for this session
mkl_dir = r"C:\Users\T590\AppData\Local\Programs\Python\Python312\Library\bin"
os.environ['DEVSIM_MATH_LIBS'] = (
    f"{mkl_dir}\\mkl_rt.3.dll;"
    f"{mkl_dir}\\mkl_rt.3.dll;"
    f"{mkl_dir}\\mkl_rt.3.dll"
)
os.environ['PATH'] = f"{mkl_dir};{os.environ.get('PATH', '')}"
import devsim

print("DevSim imported successfully")
print("Using repository from:", repo_root)

# Run the copied diode example from the work folder
example_dir = work_root / "diode_example"
if not example_dir.exists():
    raise FileNotFoundError(f"Example directory not found: {example_dir}")

sys.path.insert(0, str(example_dir))
os.chdir(example_dir)

# Execute the diode example script
example_script = example_dir / "diode_1d.py"
if not example_script.exists():
    raise FileNotFoundError(f"Example script not found: {example_script}")

print(f"Running example: {example_script}")

# Capture the script output to a simple text file for later inspection.
import contextlib
from io import StringIO

buffer = StringIO()
with contextlib.redirect_stdout(buffer):
    exec(compile(example_script.read_text(encoding="utf-8"), str(example_script), "exec"), {"__name__": "__main__"})

output_text = buffer.getvalue()
lines = output_text.splitlines()
useful_lines = []
for line in lines:
    if line.strip().startswith("top") or line.strip().startswith("bot") or line.strip().startswith("number of equations") or line.strip().startswith("Iteration") or line.strip().startswith("Warning"):
        useful_lines.append(line)
summary_text = "\n".join(useful_lines) + "\n"
summary_path.write_text(summary_text, encoding="utf-8")

# Copy visualization assets needed by ParaView/Gmsh workflows into results.
visualization_extensions = {".dat", ".lay", ".msh"}
copied_assets = []
for asset_path in example_dir.iterdir():
    if asset_path.is_file() and asset_path.suffix.lower() in visualization_extensions:
        destination_path = results_dir / asset_path.name
        shutil.copy2(asset_path, destination_path)
        copied_assets.append(asset_path.name)

if copied_assets:
    summary_path.write_text(summary_text + "\nCopied visualization assets: " + ", ".join(copied_assets) + "\n", encoding="utf-8")
    print(f"Copied visualization assets to: {results_dir}")
else:
    print("No visualization assets were found to copy")

voltage_values = []
top_values = []
bot_values = []
for line in useful_lines:
    parts = line.split()
    if len(parts) >= 4 and parts[0] in {"top", "bot"}:
        try:
            voltage = float(parts[1])
            current = float(parts[2])
            if parts[0] == "top":
                voltage_values.append(voltage)
                top_values.append(current)
            else:
                bot_values.append(current)
        except ValueError:
            continue

csv_path = results_dir / "diode_current_values.csv"
if voltage_values:
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["voltage", "top_current", "bot_current"])
        for voltage, top_current, bot_current in zip(voltage_values, top_values, bot_values):
            writer.writerow([voltage, top_current, bot_current])
    print(f"Saved numeric results to: {csv_path}")
else:
    print("No voltage/current points found for CSV output")

print(f"Saved simulation output to: {summary_path}")
