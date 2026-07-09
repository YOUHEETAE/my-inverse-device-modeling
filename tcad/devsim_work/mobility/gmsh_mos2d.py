# Copyright 2013 DEVSIM LLC
#
# SPDX-License-Identifier: Apache-2.0

from runtime_setup import configure_devsim_runtime, mesh_path


_EXAMPLE_DIR = configure_devsim_runtime(__file__)

from devsim.python_packages.simple_physics import (
    GetContactBiasName,
    SetOxideParameters,
    SetSiliconParameters,
    CreateSiliconPotentialOnly,
    CreateSiliconPotentialOnlyContact,
    CreateSiliconDriftDiffusion,
    CreateSiliconDriftDiffusionAtContact,
    CreateOxidePotentialOnly,
    CreateSiliconOxideInterface,
)
from devsim.python_packages.ramp import rampbias, printAllCurrents
from devsim import (
    element_from_edge_model,
    get_contact_current,
    get_contact_list,
    get_parameter,
    get_region_list,
    node_model,
    set_node_values,
    set_parameter,
    solve,
    write_devices,
)
from devsim.python_packages.model_create import CreateSolution


import gmsh_mos2d_create  # noqa


def _noop(_device):
    return None


def _make_iv_callback(tag):
    def _callback(dev):
        gate_v = get_parameter(device=dev, name=GetContactBiasName("gate"))
        drain_v = get_parameter(device=dev, name=GetContactBiasName("drain"))
        drain_e = get_contact_current(
            device=dev, contact="drain", equation="ElectronContinuityEquation"
        )
        drain_h = get_contact_current(
            device=dev, contact="drain", equation="HoleContinuityEquation"
        )
        drain_i = drain_e + drain_h
        print(
            "IVPOINT\t{0}\t{1:.8e}\t{2:.8e}\t{3:.8e}".format(
                tag, gate_v, drain_v, drain_i
            )
        )

    return _callback


def _log_ivpoint(tag, dev):
    _make_iv_callback(tag)(dev)

device = "mos2d"
silicon_regions = ("gate", "bulk")
oxide_regions = ("oxide",)
regions = ("gate", "bulk", "oxide")
interfaces = ("bulk_oxide", "gate_oxide")

for i in regions:
    CreateSolution(device, i, "Potential")

for i in silicon_regions:
    SetSiliconParameters(device, i, 300)
    CreateSiliconPotentialOnly(device, i)

for i in oxide_regions:
    SetOxideParameters(device, i, 300)
    CreateOxidePotentialOnly(device, i, "log_damp")

### Set up contacts
contacts = get_contact_list(device=device)
for i in contacts:
    tmp = get_region_list(device=device, contact=i)
    r = tmp[0]
    print("%s %s" % (r, i))
    CreateSiliconPotentialOnlyContact(device, r, i)
    set_parameter(device=device, name=GetContactBiasName(i), value=0.0)

for i in interfaces:
    CreateSiliconOxideInterface(device, i)

solve(type="dc", absolute_error=1.0e-13, relative_error=1e-12, maximum_iterations=30)
solve(type="dc", absolute_error=1.0e-13, relative_error=1e-12, maximum_iterations=30)

write_devices(file=str(mesh_path(_EXAMPLE_DIR, "gmsh_mos2d_potentialonly")), type="vtk")

for i in silicon_regions:
    CreateSolution(device, i, "Electrons")
    CreateSolution(device, i, "Holes")
    set_node_values(
        device=device, region=i, name="Electrons", init_from="IntrinsicElectrons"
    )
    set_node_values(device=device, region=i, name="Holes", init_from="IntrinsicHoles")
    CreateSiliconDriftDiffusion(device, i, "mu_n", "mu_p")

for c in contacts:
    tmp = get_region_list(device=device, contact=c)
    r = tmp[0]
    CreateSiliconDriftDiffusionAtContact(device, r, c)

solve(type="dc", absolute_error=1.0e30, relative_error=1e-5, maximum_iterations=30)

for r in silicon_regions:
    node_model(
        device=device, region=r, name="logElectrons", equation="log(Electrons)/log(10)"
    )


for r in silicon_regions:
    element_from_edge_model(edge_model="ElectricField", device=device, region=r)
    element_from_edge_model(edge_model="ElectronCurrent", device=device, region=r)
    element_from_edge_model(edge_model="HoleCurrent", device=device, region=r)

print("=== SWEEP_START IDVD_VG1P0 ===")
rampbias(device, "gate", 1.0, 0.1, 0.001, 100, 1e-10, 1e30, _noop)
rampbias(device, "drain", 0.0, 0.1, 0.001, 100, 1e-10, 1e30, _noop)
_log_ivpoint("IDVD_VG1P0", device)
rampbias(
    device,
    "drain",
    5.0,
    0.1,
    0.001,
    100,
    1e-10,
    1e30,
    _make_iv_callback("IDVD_VG1P0"),
)

print("=== SWEEP_START IDVG_VD0P05 ===")
rampbias(device, "drain", 0.05, 0.05, 0.001, 100, 1e-10, 1e30, _noop)
rampbias(device, "gate", -0.5, 0.1, 0.001, 100, 1e-10, 1e30, _noop)
_log_ivpoint("IDVG_VD0P05", device)
rampbias(
    device,
    "gate",
    1.5,
    0.05,
    0.001,
    100,
    1e-10,
    1e30,
    _make_iv_callback("IDVG_VD0P05"),
)

print("=== SWEEP_START IDVG_VD1P5 ===")
rampbias(device, "drain", 1.5, 0.1, 0.001, 100, 1e-10, 1e30, _noop)
rampbias(device, "gate", -0.5, 0.1, 0.001, 100, 1e-10, 1e30, _noop)
_log_ivpoint("IDVG_VD1P5", device)
rampbias(
    device,
    "gate",
    1.5,
    0.05,
    0.001,
    100,
    1e-10,
    1e30,
    _make_iv_callback("IDVG_VD1P5"),
)

printAllCurrents(device)

write_devices(file=str(mesh_path(_EXAMPLE_DIR, "gmsh_mos2d_dd")), type="vtk")
write_devices(file=str(mesh_path(_EXAMPLE_DIR, "gmsh_mos2d_dd.dat")), type="tecplot")
