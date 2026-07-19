# Visualization package

The visualization code is grouped here by responsibility. Keep model
inference and result interpretation outside this package so plotting and GUI
changes do not alter numerical results.

| File | Responsibility | Edit this file when... |
| --- | --- | --- |
| `integrated_app.py` | Integrated Tk application, tabs, curve selection, and generation workflow | the overall GUI layout or interaction flow changes |
| `curve_rendering.py` | I-V figure creation and curve styling | an I-V plot, axis, legend, or subplot changes |
| `field_data.py` | Field display names, generated-field container, scalar selection, geometry/statistical helpers | a field quantity or shared field definition changes |
| `field_rendering.py` | Mesh, scalar field, comparison, and energy-band plotting | a field-map figure or color scale changes |
| `field_app.py` | Standalone field-map GUI and command-line entry point | the field-only application changes |
| `explanation_panel.py` | Analyze buttons, explanation history, status, and copy UI | explanation-panel behavior changes |
| `guide_panel.py` | Theory/Guide tab widget construction | guide navigation or layout changes |
| `guide_content.py` | Theory/Guide text content | device theory or user-guide wording changes |

The interpretation pipeline remains in `ai/result_interpreter/`. It receives
generated numeric arrays and derived metrics; it does not read pixels from the
rendered figures.

## Compatibility entry points

Existing commands and IDE launch configurations remain valid:

- `ai/integrated_visualization_app.py` forwards to `integrated_app.py`.
- `ai/field_map_model/inference/visualization_model_app.py` forwards to
  `field_app.py` and re-exports field rendering functions.

New code should import directly from `ai.visualization` modules instead of the
compatibility entry points.
