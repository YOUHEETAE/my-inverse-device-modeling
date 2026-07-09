@echo off
setlocal
cd /d "%~dp0"

echo [1/3] Checking devsim_env...
conda run -n devsim_env python scripts\check_environment.py
if errorlevel 1 (
  echo.
  echo Environment check failed. Fix the message above, then run this file again.
  pause
  exit /b 1
)

echo.
echo [2/3] Generating Gmsh meshes...
conda run -n devsim_env python templates\sweep_generate_meshes.py --config config\sweep_geometry.csv
if errorlevel 1 (
  echo.
  echo Mesh generation failed.
  pause
  exit /b 1
)

echo.
echo [3/3] Running DEVSIM sweep...
conda run -n devsim_env python templates\sweep_run.py --geometry-config config\sweep_geometry.csv --doping-config config\sweep_doping.csv
if errorlevel 1 (
  echo.
  echo Sweep failed.
  pause
  exit /b 1
)

echo.
echo Sweep finished. Results are under dataset\.
pause
