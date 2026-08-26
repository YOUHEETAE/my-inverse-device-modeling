import sys
from pathlib import Path

from dotenv import load_dotenv

def _repo_root() -> Path:
    # 얼린 실행 파일(standalone/)에서는 소스 트리가 없다. PyInstaller가 자원을
    # 풀어놓은 곳이 뿌리이고, 그 아래 ai/ 와 tcad/ 가 같은 상대 경로로 들어
    # 있다. parents[2]를 그대로 쓰면 한 칸 넘친다 — 소스에서는 이 파일이
    # backend/app/ 아래지만 얼리면 app/ 이 뿌리 바로 밑으로 올라오기 때문이다.
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return Path(__file__).resolve().parents[2]


REPO_ROOT = _repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")
