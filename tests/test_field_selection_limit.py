from frontend.app import IntegratedModelApp, MAX_FIELD_SELECTIONS


class _Variable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def test_third_field_curve_is_rejected_without_changing_selection() -> None:
    status = _Variable("")
    app = object.__new__(IntegratedModelApp)
    app.field_selected_indices = {0, 1}
    app.field_curve_vars = {2: _Variable(True)}
    app.status = status

    app._field_curve_toggled(2)

    assert MAX_FIELD_SELECTIONS == 2
    assert app.field_selected_indices == {0, 1}
    assert app.field_curve_vars[2].get() is False
    assert "최대 2개" in status.get()
