# SemiScopeAI 로컬 실행판

배포된 웹 서비스(https://semiscopeai.com)를 인터넷도 설치도 없이 한 대의 PC에서
돌리는 빌드입니다. 공모전 제출용 "SW 실행 파일"이 이것입니다.

**화면은 배포판과 같습니다.** 같은 `web/dist`를 그대로 서빙하므로, 심사위원이
보는 것과 사업계획서에 실린 화면이 일치합니다.

## 받는 쪽에서 하는 일

1. 압축을 풉니다.
2. `SemiScopeAI.exe`를 실행합니다.
3. 잠시 뒤 기본 브라우저가 열립니다. 안 열리면 콘솔에 찍힌 주소로 들어갑니다.

설치, 계정, 인터넷 연결이 모두 필요 없습니다. 학습 기록은 실행 파일 옆의
`SemiScopeAI-data/` 폴더에 쌓이고, 폴더를 지우면 처음 상태로 돌아갑니다.

**처음 한 번은 30초쯤 걸립니다.** 글꼴 캐시를 만드느라 그렇고, 두 번째부터는
10초 안에 열립니다.

**"Windows가 PC를 보호했습니다"가 뜨면** *추가 정보* → *실행*을 누르십시오.
코드 서명 인증서가 없는 실행 파일에 Windows가 붙이는 경고입니다.

## 되는 것 / 안 되는 것

| | 로컬 실행판 | 이유 |
|---|---|---|
| I-V Curve 예측·파라미터 추출·조건 비교 | 그대로 | 예측 모델이 번들에 들어감 |
| Field Map 예측·비교·컨투어·에너지 밴드 | 그대로 | 〃 |
| Theory 6장 + PN 접합·MOS Capacitor 시뮬레이터 | 그대로 | 미리 계산된 TCAD 결과를 씀 |
| Case Study 8종 4단계 | 그대로 | 채점은 정답표 대조라 LLM이 필요 없음 |
| Case Study 피드백 · 모범답안 | 그대로 | 케이스 정의와 실제 계산 결과로 조립 |
| AI 설명 · 자유질문 | 없음 (안내 문구) | 아래 참고 |
| 로그인 / 계정별 학습 기록 | 없음 | 아래 참고 |

**AI 설명과 자유질문**은 외부 LLM을 부르는 기능이라 빠져 있습니다. API 키를
실행 파일에 넣으면 압축만 풀어도 꺼낼 수 있어서 넣지 않습니다. 해당 자리에는
무엇이 빠졌는지 알리는 안내가 대신 서고, 온전한 동작은 배포된 서비스에서 볼 수
있습니다.

키를 가진 분이 직접 붙이려면 `web/.env.standalone`의 `VITE_STANDALONE`을 끄고
다시 빌드한 뒤, 실행 전에 `LLM_API_KEY_ENV`가 가리키는 환경변수(기본
`GROQ_API_KEY`)를 설정하면 됩니다.

**로그인**은 구글 OAuth라 인터넷과 실제 client secret이 필요합니다. 로컬판은
사용자가 한 명뿐인 것으로 두고 모든 기능을 열어 둡니다. 같은 이유로 계정별
하루 사용량 제한과 초당 요청 제한도 빠집니다 — 여러 사람이 함께 쓰는 서버의
사정이지 로컬 실행판의 것이 아닙니다.

**Case Study 채점이 LLM 없이 되는 이유**는 원래 그렇게 설계돼 있기 때문입니다.
답안 채점은 케이스 설정의 정답과 대조하는 결정론적 계산이고
(`backend/learning/llm_service.py`의 `evaluate_structured_answer`), 모범 답안은
케이스 정의와 실제 시뮬레이션 결과로 조립합니다(`build_grounded_model_answer`).
LLM은 피드백 문장을 다듬는 역할이라, 없으면 로컬 버전이 대신합니다.

## 구조

```
브라우저  ──▶  SemiScopeAI.exe (로컬 FastAPI, 127.0.0.1)
                 ├── /            web/dist  (배포판과 같은 화면)
                 ├── /auth, /chat, /case-study/sessions
                 │      standalone/shim.py  ← 배포판에서 자바가 하던 자리
                 └── /curves, /fields, /explain, /theory, /case-study/topics
                        backend/app/routers  ← 배포판과 같은 코드
```

배포 구성은 Caddy → java_service → backend → Postgres 네 겹입니다. 여기서는
`backend`만 남기고, 자바가 맡던 **저장과 인증**을 `shim.py`가 파일로 대신합니다.
예측·이론·Case Study 로직은 배포판과 완전히 같은 코드가 돕니다.

Python 라우터를 HTTP로 다시 부르지 않고 함수로 직접 호출합니다 — 같은 프로세스
안이라 자기 자신에게 요청을 보낼 이유가 없습니다.

## 빌드

```powershell
# 1. 화면을 로컬 실행판용으로 빌드한다
cd web
npm run build:standalone
cd ..

# 2. 실행 파일을 만든다
python -m pip install pyinstaller
python -m PyInstaller --noconfirm --clean `
    --distpath dist_standalone --workpath build_standalone `
    standalone/SemiScopeAI.spec
```

`build:standalone`은 `web/.env.standalone`을 읽어 두 가지를 바꾼다. API 주소를
비워 화면이 상대 경로로 요청하게 하고(자기를 내려준 서버 = 실행 파일 안의
FastAPI), `VITE_STANDALONE=1`로 AI 자리를 안내 문구로 바꾼다.

**그냥 `npm run build`를 쓰면 안 된다** — `web/.env`의 `http://localhost:8080`이
구워지고, 받는 사람 PC에는 그 주소에 아무것도 없어서 화면은 뜨는데 데이터만
전부 실패한다.

배포판 빌드에는 이 플래그가 없으므로 `IS_STANDALONE`이 false로 접히고, 안내
문구는 번들에서 통째로 사라진다 — 화면 코드는 한 벌이지만 두 빌드는 서로에게
영향을 주지 않는다.

`dist_standalone/SemiScopeAI/` 폴더가 나옵니다. 이 폴더를 통째로 압축해 제출합니다.

### 빌드에서 주의할 점

- **`--onefile`을 쓰지 않습니다.** 실행할 때마다 수백 MB를 임시 폴더에 풀어야
  해서 첫 화면까지 십 수 초가 걸립니다. 폴더째 압축하는 편이 빠릅니다.
- **xgboost는 `collect_all`로 수집해야 합니다.** 네이티브 `xgboost.dll`을 패키지
  옆에서 직접 찾는 구조라 PyInstaller의 정적 분석에 잡히지 않고, 빠뜨리면 얼린
  뒤 import 단계에서 죽습니다.
- **torch는 제외합니다.** Field Map 추론은 `model.npz`만 읽습니다
  (`ai/field_map_model/inference/runtime.py`). 같이 있는 `model.pt`는 학습
  산출물이라 번들에서 빠지고, 그것만으로 수백 MB가 줄어듭니다.
- **matplotlib은 제외하면 안 됩니다.** GUI 전용처럼 보이지만
  `ai/shared/field_data.py`가 `matplotlib.tri`로 삼각분할을 합니다 — Field Map
  표시 경로의 계산 의존성입니다. 빼면 얼린 뒤 첫 요청에서
  `ModuleNotFoundError`로 죽습니다. 대신 `tkinter`를 빼고 `launcher.py`가
  백엔드를 `Agg`로 못박아 대화형 백엔드가 딸려오지 않게 합니다.
- **gmsh는 손볼 것이 없습니다.** 얼린 상태에서 그대로 mesh를 만듭니다.

## 개발 중 실행

실행 파일을 만들지 않고 바로 띄워볼 수 있습니다.

```powershell
python standalone/launcher.py
```
