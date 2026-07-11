# My Inverse Device Modeling

This repository contains the code and configuration for generating TCAD/DEVSIM simulation data that can later be used to train inverse device modeling models.

## Repository Layout

```text
tcad/
  data_extraction/   Active DEVSIM data-generation workflow
  devsim/            DEVSIM source submodule/reference
ai/                  Future model training/inference code
backend/             Future web/API backend
frontend/            Future web frontend
docs/                Project notes and documentation
```

The active TCAD workflow is `tcad/data_extraction`.

## Data Policy

Generated simulation outputs are intentionally not tracked by Git. They are written locally under:

```text
tcad/data_extraction/runs/
tcad/data_extraction/dataset/
```

Keep large datasets, trained model artifacts, and temporary run logs outside Git, or move them separately by USB/cloud/data storage when needed.

## Current TCAD Flow

1. Edit sweep CSV files under `tcad/data_extraction/config/`.
2. Generate meshes with `tools/sweep_generate_meshes.py`.
3. Run DEVSIM sweeps with `tools/sweep_run.py`.
4. Use CSV and Tecplot `.dat` outputs under `dataset/` for later preprocessing/training.

See `tcad/data_extraction/README.md` for the detailed workflow.