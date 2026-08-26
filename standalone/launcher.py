"""실행 파일의 진입점: 로컬 서버를 띄우고 브라우저를 연다."""
from __future__ import annotations

import multiprocessing
import os
import socket
import sys
import threading
import webbrowser

# matplotlib 을 import 하기 전에 못박는다. Field Map 표시가 matplotlib.tri 로
# 삼각분할을 하는데(ai/shared/field_data.py), 백엔드를 정해주지 않으면
# 창을 띄우는 백엔드를 찾다가 얼린 실행 파일에서 실패할 수 있다. 그림을
# 그리는 것이 아니라 계산에만 쓰므로 Agg 로 충분하다.
os.environ.setdefault("MPLBACKEND", "Agg")

# 저장소가 두 가지 임포트 방식을 함께 쓴다. FastAPI 앱은 `app.routers...`로
# (도커의 uvicorn이 --app-dir backend 로 띄운다), 학습·설명 모듈은
# `backend.learning...`으로 부른다. 그래서 저장소 뿌리와 backend/ 가 모두
# 경로에 있어야 한다. 얼리면 PyInstaller가 둘 다 _MEIPASS 아래에 풀어놓고
# 그 경로는 이미 sys.path에 있다.
if not getattr(sys, "frozen", False):
    from pathlib import Path

    _root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(_root))
    sys.path.insert(1, str(_root / "backend"))

import uvicorn  # noqa: E402

from standalone import local_store  # noqa: E402
from standalone.app import create_app  # noqa: E402

# 개인 PC에서 쓰는 포트라 흔히 비어 있는 값을 고정으로 쓴다. 이미 물려
# 있으면 아래에서 다음 빈 포트를 찾는다.
PREFERRED_PORT = 8765


def free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("쓸 수 있는 포트를 찾지 못했습니다.")


def main() -> int:
    # 얼린 윈도우 실행 파일에서 자식 프로세스가 생기면 앱이 통째로 다시
    # 시작된다. uvicorn은 여기서 워커를 쓰지 않지만, 의존 라이브러리가
    # 프로세스를 띄울 때를 대비해 켜 둔다.
    multiprocessing.freeze_support()

    port = free_port(PREFERRED_PORT)
    url = f"http://127.0.0.1:{port}/"

    print("SemiScopeAI 로컬 실행판")
    print(f"  주소      : {url}")
    print(f"  저장 위치 : {local_store.data_dir()}")
    print("  창을 닫으면 종료됩니다. 학습 기록은 위 폴더에 남습니다.")

    # 서버가 받을 준비가 되기 전에 열면 빈 화면이 뜬다. 1초 뒤에 연다.
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    # 0.0.0.0이 아니라 127.0.0.1에 묶는다. 같은 네트워크의 다른 PC에서
    # 접근할 이유가 없고, 방화벽 경고도 뜨지 않는다.
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
