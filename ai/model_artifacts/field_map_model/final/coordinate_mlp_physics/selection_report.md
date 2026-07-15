# Field-map element validation selection

All 386 validation devices were evaluated as full maps. Final test was not loaded.

| Field | Baseline | Bulk-focused | Bulk + physics | Physics vs baseline |
|---|---:|---:|---:|---:|
| ElectricField_x | 0.651389 | 0.437035 | 0.439065 | 32.60% |
| ElectricField_y | 0.348235 | 0.264777 | 0.273125 | 21.57% |
| ElectronCurrent_x | 0.154326 | 0.132678 | 0.141722 | 8.17% |
| ElectronCurrent_y | 1.01117 | 0.682837 | 0.68452 | 32.30% |
| HoleCurrent_x | 0.594806 | 0.526779 | 0.529193 | 11.03% |
| HoleCurrent_y | 0.650954 | 0.41618 | 0.418929 | 35.64% |

## Physics selection

- E-direction cosine: baseline 0.750503, bulk-focused 0.716672, bulk+physics 0.873995
- Gradient/field RMS ratio: baseline 0.0965644, bulk-focused 3.81103, bulk+physics 3.80489
- Raw TCAD gradient/field RMS ratio: 4.7604

Selected: `element_bulk_physics`. It retains improvements in every element field and restores much stronger electric-field direction consistency.
