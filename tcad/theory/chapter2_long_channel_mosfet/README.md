# Chapter 2: Long-Channel MOSFET Structure and Operation

MOS capacitor physics is included only as the electrostatic foundation needed
to explain channel formation and threshold voltage.

## Planned theory

- MOS structure and gate control
- Accumulation, depletion, and inversion
- Threshold voltage and inversion-layer formation
- Long-channel MOSFET structure
- Linear and saturation operation
- ID–VG and ID–VD characteristics
- Pinch-off and gradual-channel approximation

## Simulation folders

- `simulations/mos_capacitor`
  - Silicon/oxide capacitor electrostatics reference copied from the DEVSIM
    `cap2.py` test.
  - This is a starting reference, not yet the final semiconductor MOS C–V
    simulation.
- `simulations/long_channel_mosfet`
  - `mos_2d_create.py`: creates the gate/oxide/bulk/source/drain geometry and
    doping models.
  - `mos_2d.py`: solves electrostatics and drift–diffusion equations.

The copied files retain their original Apache-2.0 headers. `runtime_setup.py`
connects the existing `devsim_env` MKL installation before DEVSIM is imported.
