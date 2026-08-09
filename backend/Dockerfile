# Build context is the repo root (see docker-compose.yml) because this image
# needs sibling directories outside backend/ — ai/ (inference stack + model
# artifacts) and tcad/data_extraction (gmsh template + parameter extraction).
FROM python:3.11-slim

# gmsh (headless meshing, ai/field_map_model/inference/mesh_inputs.py) needs
# these X11/OpenGL runtime libs even though nothing here ever opens a window.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglu1-mesa \
        libgl1 \
        libxrender1 \
        libxcursor1 \
        libxinerama1 \
        libxft2 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ai/requirements.txt ai/requirements.txt
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Runtime path mirrors ai/DEPLOYMENT.md's documented "Git-tracked runtime"
# list (also enforced by ai/tools/check_runtime_package.py), swapping the
# Tkinter frontend/ for backend/ (the FastAPI equivalent). tcad/devsim is
# intentionally excluded: it's a submodule used only offline for TCAD data
# generation and is never imported by the serving path.
COPY ai/shared ai/shared
COPY ai/curve_model ai/curve_model
COPY ai/field_map_model ai/field_map_model
COPY ai/model_artifacts/curve_model/final ai/model_artifacts/curve_model/final
COPY ai/model_artifacts/field_map_model/final ai/model_artifacts/field_map_model/final
COPY tcad/data_extraction/base_case tcad/data_extraction/base_case
COPY tcad/data_extraction/parameter_extraction_core.py tcad/data_extraction/parameter_extraction_core.py
# Precomputed Theory chapter data (backend/app/routers/theory.py reads these
# directly — no live DEVSIM/gmsh run needed to serve them).
COPY tcad/theory/chapter1_pn_junction/precomputed_data tcad/theory/chapter1_pn_junction/precomputed_data
COPY tcad/theory/chapter2_long_channel_mosfet/simulations/long_channel_mosfet/precomputed_data tcad/theory/chapter2_long_channel_mosfet/simulations/long_channel_mosfet/precomputed_data
COPY tcad/theory/chapter2_long_channel_mosfet/simulations/mos_capacitor/precomputed_data tcad/theory/chapter2_long_channel_mosfet/simulations/mos_capacitor/precomputed_data
COPY backend backend

# Secrets (GROQ_API_KEY, etc.) are injected at `docker run`/compose time via
# env_file or -e — never baked into the image. backend/app/__init__.py's
# load_dotenv() call is a no-op if no .env file is present, which is fine
# here since real env vars are already set before Python starts.

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
