# LDD comparison at L = 300 nm

This experiment reuses the validated `tcad/data_extraction/base_case` DEVSIM
model and changes only the requested device parameters:

| Parameter | Value |
|---|---:|
| Gate length | 300 nm |
| Oxide thickness | 20 nm |
| Bulk doping | 1e16 cm^-3 |
| Source/drain doping | 1e20 cm^-3 |
| LDD doping, case 1 | 0 cm^-3 |
| LDD doping, case 2 | 1e18 cm^-3 |

The geometry mesh is shared by both cases. The runner copies the base scripts
into `generated/runs/<case>/`, patches the six parameters above, runs DEVSIM,
and writes comparable I-V CSV files and the Vg=3 V, Vd=3 V field dump under
`generated/dataset/`.

## Run

From this directory:

```powershell
python run_comparison.py
python app.py
```

Use `python run_comparison.py --force` to rerun existing results. The GUI also
has **Run / rerun DEVSIM** and **Reload results** buttons.

On Windows, `app.py` automatically relaunches itself through `conda run` when
the environment's `python.exe` was invoked by absolute path without activation.
This ensures that Tcl/Tk and its DLL search paths are initialized correctly.

The runtime and Gmsh paths are resolved through the existing
`tcad/data_extraction/configs/local_config.json` configuration. If the Gmsh
executable cannot start because of a Windows DLL conflict, the runner
automatically falls back to the Python `gmsh` package in `devsim_env`.

Requirements:

- DEVSIM and Gmsh must be available through the active environment or the
  existing local configuration.
- The Python used to launch `app.py` must include Tcl/Tk support.

Check the shared TCAD environment first if needed:

```powershell
python ..\..\..\..\data_extraction\scripts\check_environment.py
```
