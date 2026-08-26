# -*- mode: python ; coding: utf-8 -*-
"""로컬 실행판 빌드 설정.

빌드:
    cd web && npm run build          # VITE_API_BASE_URL 을 비우고 (같은 출처)
    pyinstaller standalone/SemiScopeAI.spec

산출물은 dist/SemiScopeAI/ 폴더 하나다. --onefile 로 묶지 않는 이유는, 실행할
때마다 500MB를 임시 폴더에 풀어야 해서 첫 화면까지 십 수 초가 걸리기
때문이다. 폴더째 압축해서 전달하는 편이 빠르고, 받는 쪽도 압축만 풀면 된다.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent


def tree(source: str, exclude: tuple[str, ...] = ()) -> list[tuple[str, str]]:
    """디렉터리를 번들 안의 같은 경로로 옮긴다."""
    items = []
    for path in (ROOT / source).rglob("*"):
        if not path.is_file() or path.suffix in exclude:
            continue
        items.append((str(path), str(path.parent.relative_to(ROOT))))
    return items


datas = [
    # 배포판과 똑같은 화면. 이것이 있어야 심사용 실행 파일과 실제 서비스가
    # 같은 것을 보여준다.
    *tree("web/dist"),

    # 예측 모델. .pt 는 학습 산출물이고 추론은 model.npz 만 읽으므로 뺀다
    # (ai/field_map_model/inference/runtime.py) — 그것만으로 수백 MB가 준다.
    *tree("ai/model_artifacts/curve_model/final", exclude=(".pt",)),
    *tree("ai/model_artifacts/field_map_model/final", exclude=(".pt",)),

    # Case Study 8종의 정의와 이론 지식베이스. 채점과 모범 답안이 전부
    # 여기서 나오므로 LLM 없이도 학습이 끝까지 간다.
    *tree("backend/learning/configs"),
    *tree("backend/learning/knowledge"),

    # 구조 생성용 gmsh 템플릿과 전기적 파라미터 추출.
    *tree("tcad/data_extraction/base_case"),

    # Theory 화면이 읽는 미리 계산된 TCAD 결과. 실시간 DEVSIM 실행이
    # 필요 없는 이유가 이것이다.
    *tree("tcad/theory/chapter1_pn_junction/precomputed_data"),
    *tree("tcad/theory/chapter2_long_channel_mosfet/simulations/long_channel_mosfet/precomputed_data"),
    *tree("tcad/theory/chapter2_long_channel_mosfet/simulations/mos_capacitor/precomputed_data"),
]

binaries = []
hiddenimports = [
    # 라우터가 문자열 경로로만 참조하는 것들이 있어 정적 분석에 안 잡힌다.
    "app.routers.parameters",
    "app.routers.curves",
    "app.routers.fields",
    "app.routers.explain",
    "app.routers.theory",
    "app.routers.case_study",
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

# xgboost 는 네이티브 xgboost.dll 을 파이썬 패키지 옆에서 직접 찾는데,
# PyInstaller 의 정적 분석에는 그게 보이지 않는다. 수집하지 않으면 얼린
# 뒤 import 단계에서 "Cannot find XGBoost Library" 로 죽는다.
for package in ("xgboost", "sklearn", "gmsh"):
    extra_datas, extra_binaries, extra_hidden = collect_all(package)
    datas += extra_datas
    binaries += extra_binaries
    hiddenimports += extra_hidden


a = Analysis(
    [str(ROOT / "standalone" / "launcher.py")],
    pathex=[str(ROOT), str(ROOT / "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    # torch 는 학습 산출물(.pt)에만 필요하고 추론은 numpy 로 돈다.
    #
    # matplotlib 은 뺄 수 없다. GUI 로만 쓰인다는 인상과 달리 ai/shared/
    # field_data.py 가 matplotlib.tri 로 삼각분할을 한다 — Field Map 표시
    # 경로의 계산 의존성이다. 대신 tkinter 를 빼서 대화형 백엔드가 딸려
    # 오지 않게 하고, 백엔드는 launcher 에서 Agg 로 못박는다.
    excludes=["torch", "torchvision", "tkinter", "IPython", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SemiScopeAI",
    debug=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SemiScopeAI",
)
