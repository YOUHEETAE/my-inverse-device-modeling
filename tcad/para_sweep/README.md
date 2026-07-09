# para_sweep 실행 방법

이 폴더는 노트북과 본체 컴퓨터에서 같은 방식으로 TCAD parameter sweep을 돌리기 위한 작업 폴더입니다.

## 한 번만 준비하기

### 1. Anaconda Prompt 열기

Windows 시작 메뉴에서 `Anaconda Prompt`를 엽니다.

### 2. 프로젝트 폴더로 이동

아래 경로는 본인 컴퓨터의 실제 위치에 맞게 바꿔서 입력합니다.

```bat
cd C:\Users\내이름\devsim_project\inverse-device-modeling\tcad\para_sweep
```

### 3. conda 환경 만들기

처음 한 번만 실행합니다.

```bat
conda env create -f environment.yml
```

이미 `devsim_env`가 있으면 업데이트합니다.

```bat
conda env update -n devsim_env -f environment.yml --prune
```

### 4. Gmsh 경로 설정

보통은 `environment.yml` 안의 conda Gmsh 또는 PATH의 Gmsh를 자동으로 찾습니다.

못 찾는 경우에만 아래 파일을 복사합니다.

```bat
copy configs\local_config.template.json configs\local_config.json
```

그 다음 `configs\local_config.json`을 열어서 `gmsh_exe`를 본체 컴퓨터의 `gmsh.exe` 위치로 바꿉니다.

예시:

```json
{
  "gmsh_exe": "C:/Program Files/Gmsh/gmsh.exe",
  "python_exe": "",
  "devsim_math_libs": [],
  "extra_path": []
}
```

`local_config.json`은 컴퓨터마다 다른 개인 설정이라 Git에 올리지 않습니다.

### 5. 환경 확인

파일 탐색기에서 `run_check_env.bat`를 실행하거나, Anaconda Prompt에서 아래 명령을 실행합니다.

```bat
run_check_env.bat
```

마지막에 `Environment check passed.`가 나오면 준비가 끝난 것입니다.

## 시뮬레이션 실행

파일 탐색기에서 `run_sweep.bat`를 실행하거나, Anaconda Prompt에서 아래 명령을 실행합니다.

```bat
run_sweep.bat
```

기본 실행 순서:

1. `devsim_env` 환경 확인
2. `config/sweep_geometry.csv`로 mesh 생성
3. `config/sweep_doping.csv`로 DEVSIM sweep 실행
4. 결과를 `dataset/`에 저장

작은 테스트만 돌리고 싶으면 `run_sweep.bat` 안의 `sweep_geometry.csv`, `sweep_doping.csv`를 각각 `test_geometry.csv`, `test_doping.csv`로 바꿉니다.

## 직접 명령어로 실행하기

```bat
conda run -n devsim_env python scripts\check_environment.py
conda run -n devsim_env python templates\sweep_generate_meshes.py --config config\sweep_geometry.csv
conda run -n devsim_env python templates\sweep_run.py --geometry-config config\sweep_geometry.csv --doping-config config\sweep_doping.csv
```

## Git에 올리지 않는 파일

다음은 컴퓨터마다 다르거나 결과물이므로 Git에 올리지 않습니다.

- `configs/local_config.json`
- `.venv/`, `venv/`, conda 환경 폴더
- `runs/`
- `dataset/`
- `*.msh`
- `*.log`

## 문제 해결

### `is devsim_env: NO`

현재 Python이 `devsim_env`가 아닙니다. 아래처럼 실행하세요.

```bat
conda run -n devsim_env python scripts\check_environment.py
```

### `import devsim: FAIL`

`inverse-device-modeling/tcad/devsim` 폴더가 프로젝트 안에 있는지 확인하세요. 이 프로젝트는 원본 `tcad/devsim` 폴더를 수정하지 않고, import 경로만 잡아서 사용합니다.

### `gmsh: FAIL`

먼저 conda 환경에 Gmsh가 있는지 확인합니다.

```bat
conda run -n devsim_env gmsh --version
```

그래도 안 되면 `configs/local_config.json`의 `gmsh_exe`에 Windows용 `gmsh.exe` 경로를 적습니다.
