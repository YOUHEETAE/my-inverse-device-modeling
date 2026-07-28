# Long-Channel MOSFET Simulation

This chapter uses a Gmsh-generated 0.5 µm gate NMOS as its educational
long-channel baseline. DEVSIM calculates the gate, oxide, and bulk fields plus
the transfer and output characteristics.

Run from this directory:

```powershell
conda activate devsim_env
python generate_dataset.py
python app.py
```

`generate_dataset.py` performs the DEVSIM calculation once and saves a
compressed result. `app.py` only reads that saved result; it does not run
DEVSIM.

The GUI displays:

- net doping, potential, electron density, and hole density field maps;
- ID–VG at VD = 0.05 V;
- ID–VD families at VG = 0, 0.5, 1.0, 1.5, and 2.0 V;
- saved field maps for selected VG and VD conditions.

The field map occupies the upper panel. ID–VG and ID–VD are shown together in
the two lower panels. Changing VG/VD—or clicking a lower graph—moves the
operating-point marker and loads the nearest saved field snapshot.

To inspect the exact Gmsh mesh:

```powershell
python view_gmsh_mesh.py
```

The mesh source is `long_channel_mos2d.geo`, and the generated Gmsh 2.2 file is
`long_channel_mos2d.msh`.
