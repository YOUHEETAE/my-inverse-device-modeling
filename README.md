# Inverse Device Modeling

MOSFET device parameters로 I-V Curve와 Field Map을 예측하고, Python Analyzer와
Mock renderer가 검증 가능한 분석 초안을 만들고 Groq LLM이 그 의미를 보존하며
학습용 자연어로 다듬는 데스크톱 애플리케이션입니다.

## Repository layout

```text
ai/                      Model inference, shared data, tools, final model packages
backend/explanation/     Payload, Analyzer, Mock renderer, provider, validation
frontend/app.py          Integrated desktop application entry point
frontend/visualization/  Tk and Matplotlib UI components
tcad/                    DEVSIM source and simulation/data-extraction workflow
tests/                   Unit, integration, regression, and Golden tests
docs/                    Architecture and setup documentation
```

## Fresh clone setup (Conda)

Git LFS is required because the two finalized Curve model files are stored with
LFS. After cloning, run these commands from the repository root:

```powershell
git lfs install
git lfs pull
conda env create -f environment.yml
conda activate inverse-device-modeling
python ai/tools/check_runtime_package.py
python frontend/app.py --smoke-test
python frontend/app.py
```

Curve와 Field Map 예측 및 전기적 파라미터 추출은 API key 없이 동작합니다.
I-V·Field 자동 설명과 AI 질문, Case Study 자유 질문은 전용 Groq LLM을
기본 경로로 사용합니다.

## Groq LLM

Copy the variable names from `.env.example`, but set the real key in the Conda
environment or operating-system environment. Do not commit a `.env` file or API
key. 키가 없거나 요청이 실패하면 설명 영역에 연결 또는 실제 provider 오류가
표시되며, 사용자에게 Mock 답변을 LLM 답변처럼 대체해 보여주지 않습니다.

## Runtime and data policy

The finalized Curve and Field Map model packages are versioned so a fresh clone
can execute the application. Generated datasets, training trials, TCAD runs,
plots, local environments, caches, and secrets remain local through `.gitignore`.

Generated TCAD output is written under:

```text
tcad/data_extraction/runs/
tcad/data_extraction/dataset/
```

See `ai/DEPLOYMENT.md` and `tcad/data_extraction/README.md` for details.

## Release handoff

Before handing a source revision to a deployment owner, run:

```powershell
python tools/deployment_readiness.py
```

The complete qualification sequence and the boundary between this desktop
application and deployment infrastructure are documented in
`docs/deployment_handoff.md`. Learner-visible information, private session
state, provider credentials, and remote-deployment responsibilities are defined
in `docs/security_privacy_handoff.md`.
