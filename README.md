# Inverse Device Modeling

MOSFET device parameters로 I-V Curve와 Field Map을 예측하고, Python Analyzer와
Mock renderer가 근거 기반 해설을 생성하는 데스크톱 애플리케이션입니다. Groq LLM은
선택 사항이며 Mock 해설의 의미를 바꾸지 않는 범위에서 문장만 다듬습니다.

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

The app starts with the local `mock` explanation provider. Therefore Curve,
Field Map, extracted parameters, and deterministic explanations work without an
API key or network connection.

## Optional Groq LLM

Copy the variable names from `.env.example`, but set the real key in the Conda
environment or operating-system environment. Do not commit a `.env` file or API
key. If the key is absent, keep `mock` selected in the GUI.

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
