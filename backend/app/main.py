from fastapi import FastAPI

from app import services
from app.routers.parameters import router as parameters_router
from app.routers.curves import router as curves_router
from app.routers.fields import router as fields_router
from app.routers.explain import router as explain_router

app = FastAPI(title="Inverse Device Modeling API")
app.include_router(parameters_router)
app.include_router(curves_router)
app.include_router(fields_router)
app.include_router(explain_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
