from tools.deployment_readiness import _git_hygiene, _required_paths


def test_required_runtime_files_are_git_upload_candidates() -> None:
    check = _required_paths()
    assert check.passed, check.detail


def test_git_upload_candidates_contain_no_secret_material() -> None:
    check = _git_hygiene()
    assert check.passed, check.detail

