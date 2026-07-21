from fastapi import FastAPI

from app import services
from app.routers.parameters import router as parameters_router

app = FastAPI(title="Inverse Device Modeling API")
app.include_router(parameters_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
