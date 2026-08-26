"""로컬 실행판의 FastAPI 앱: API와 화면을 한 포트에서 서빙한다."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.routers.case_study import router as case_study_router
from app.routers.curves import router as curves_router
from app.routers.explain import router as explain_router
from app.routers.fields import router as fields_router
from app.routers.parameters import router as parameters_router
from app.routers.theory import router as theory_router
from standalone import shim


def bundled_root() -> Path:
    """번들된 자원의 뿌리. 얼리면 _MEIPASS 아래로 풀린다."""
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else Path(__file__).resolve().parents[1]


def create_app() -> FastAPI:
    app = FastAPI(title="SemiScopeAI (로컬 실행판)")

    # 순서가 중요하다. Python의 case_study 라우터에도 POST /case-study/sessions
    # 가 있는데(무상태 버전 — 세션을 본문으로 받는다), 화면이 부르는 것은
    # 저장까지 하는 shim 쪽이다. 먼저 등록한 쪽이 이긴다.
    app.include_router(shim.router)

    app.include_router(parameters_router)
    app.include_router(curves_router)
    app.include_router(fields_router)
    app.include_router(explain_router)
    app.include_router(theory_router)
    app.include_router(case_study_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    _serve_frontend(app)
    return app


def _serve_frontend(app: FastAPI) -> None:
    """배포판과 같은 화면(web/dist)을 같은 출처에서 내보낸다.

    CORS 설정이 없는 이유가 이것이다 — 화면과 API가 같은 포트에 있으면
    브라우저가 교차 출처로 보지 않는다.
    """
    dist = bundled_root() / "web" / "dist"
    index = dist / "index.html"

    # API 경로가 전부 등록된 뒤에 붙는다. 여기서 걸리는 것은 화면 자원과
    # react-router의 경로(/fields 같은 것)뿐이다.
    @app.get("/{asset_path:path}")
    def spa(asset_path: str) -> FileResponse:
        if not index.exists():
            raise RuntimeError(
                f"화면 파일이 없습니다: {dist}\n"
                "standalone/build.py로 빌드하거나 web에서 `npm run build`를 먼저 실행하세요."
            )
        candidate = dist / asset_path
        # 실제 파일이면 그대로, 아니면 index.html — 새로고침으로 /fields에
        # 바로 들어와도 화면이 뜨게 하는 SPA 폴백이다.
        if asset_path and candidate.is_file() and dist in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(index)
