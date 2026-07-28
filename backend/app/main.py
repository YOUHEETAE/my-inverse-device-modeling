import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import services
from app.routers.parameters import router as parameters_router
from app.routers.curves import router as curves_router
from app.routers.fields import router as fields_router
from app.routers.explain import router as explain_router

DEFAULT_ORIGINS = "http://localhost:5174,http://127.0.0.1:5174"
allow_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOW_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

app = FastAPI(title="Inverse Device Modeling API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(parameters_router)
app.include_router(curves_router)
app.include_router(fields_router)
app.include_router(explain_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
