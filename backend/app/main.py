import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app import services
from app.limiter import limiter
from app.routers.parameters import router as parameters_router
from app.routers.curves import router as curves_router
from app.routers.fields import router as fields_router
from app.routers.explain import router as explain_router
from app.routers.theory import router as theory_router
from app.routers.case_study import router as case_study_router

DEFAULT_ORIGINS = "http://localhost:5174,http://127.0.0.1:5174"
allow_origins = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOW_ORIGINS", DEFAULT_ORIGINS).split(",")
    if origin.strip()
]

app = FastAPI(title="Inverse Device Modeling API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
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
app.include_router(theory_router)
app.include_router(case_study_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
