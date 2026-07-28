from __future__ import annotations

import contextlib
import io

import numpy as np

from result_types import LongChannelResult, MOSFETSnapshot, RegionSnapshot
from runtime_setup import configure_devsim_runtime

configure_devsim_runtime()

from devsim import (  # noqa: E402
    get_contact_current,
    get_contact_list,
    get_node_model_values,
    get_region_list,
    node_model,
    set_node_values,
    set_parameter,
    solve,
)
from devsim.python_packages.model_create import CreateSolution  # noqa: E402
from devsim.python_packages.simple_physics import (  # noqa: E402
    CreateOxidePotentialOnly,
    CreateSiliconDriftDiffusion,
    CreateSiliconDriftDiffusionAtContact,
    CreateSiliconOxideInterface,
    CreateSiliconPotentialOnly,
    CreateSiliconPotentialOnlyContact,
    GetContactBiasName,
    SetOxideParameters,
    SetSiliconParameters,
    ece_name,
    hce_name,
)


DEVICE = "mos2d"
BULK = "bulk"
SNAPSHOT_VOLTAGES = (0.0, 0.5, 1.0, 1.5, 2.0)
IDVD_GATE_VOLTAGES = (0.0, 0.5, 1.0, 1.5, 2.0)
IDVD_DRAIN_VOLTAGES = tuple(np.linspace(0.0, 2.0, 21))
IDVD_SNAPSHOT_DRAIN_VOLTAGES = (0.0, 0.5, 1.0, 1.5, 2.0)


def _total_current(contact: str) -> float:
    electron = get_contact_current(
        device=DEVICE,
        contact=contact,
        equation=ece_name,
    )
    hole = get_contact_current(
        device=DEVICE,
        contact=contact,
        equation=hce_name,
    )
    return float(electron + hole)


def _ramp(contact: str, start: float, stop: float, step: float = 0.05) -> None:
    count = max(1, int(np.ceil(abs(stop - start) / step)))
    for voltage in np.linspace(start, stop, count + 1)[1:]:
        set_parameter(
            device=DEVICE,
            name=GetContactBiasName(contact),
            value=float(voltage),
        )
        solve(
            type="dc",
            absolute_error=1e30,
            relative_error=1e-8,
            maximum_iterations=60,
        )


def _snapshot(gate_voltage: float, drain_voltage: float) -> MOSFETSnapshot:
    regions: dict[str, RegionSnapshot] = {}
    for region in ("gate", "oxide", "bulk"):
        x = np.asarray(
            get_node_model_values(device=DEVICE, region=region, name="x")
        )
        y = np.asarray(
            get_node_model_values(device=DEVICE, region=region, name="y")
        )
        potential = np.asarray(
            get_node_model_values(device=DEVICE, region=region, name="Potential")
        )
        if region == "oxide":
            regions[region] = RegionSnapshot(
                x_um=x * 1e4,
                y_um=y * 1e4,
                potential=potential,
            )
            continue
        regions[region] = RegionSnapshot(
            x_um=x * 1e4,
            y_um=y * 1e4,
            potential=potential,
            net_doping=np.asarray(
                get_node_model_values(
                    device=DEVICE, region=region, name="NetDoping"
                )
            ),
            electrons=np.asarray(
                get_node_model_values(
                    device=DEVICE, region=region, name="Electrons"
                )
            ),
            holes=np.asarray(
                get_node_model_values(device=DEVICE, region=region, name="Holes")
            ),
        )
    return MOSFETSnapshot(
        gate_voltage=gate_voltage,
        drain_voltage=drain_voltage,
        regions=regions,
    )


def run_long_channel_mosfet() -> LongChannelResult:
    """Build the copied DEVSIM MOS structure and calculate ID–VG."""
    with contextlib.redirect_stdout(io.StringIO()):
        # Importing this module creates the mesh, regions, contacts, and doping.
        import gmsh_mos2d_create  # noqa: F401

        silicon_regions = ("gate", "bulk")
        oxide_regions = ("oxide",)
        regions = ("gate", "bulk", "oxide")
        interfaces = ("bulk_oxide", "gate_oxide")

        for region in regions:
            CreateSolution(DEVICE, region, "Potential")
        for region in silicon_regions:
            SetSiliconParameters(DEVICE, region, 300)
            CreateSiliconPotentialOnly(DEVICE, region)
        for region in oxide_regions:
            SetOxideParameters(DEVICE, region, 300)
            CreateOxidePotentialOnly(DEVICE, region, "log_damp")

        contacts = get_contact_list(device=DEVICE)
        for contact in contacts:
            region = get_region_list(device=DEVICE, contact=contact)[0]
            CreateSiliconPotentialOnlyContact(DEVICE, region, contact)
            set_parameter(
                device=DEVICE,
                name=GetContactBiasName(contact),
                value=0.0,
            )
        for interface in interfaces:
            CreateSiliconOxideInterface(DEVICE, interface)

        solve(
            type="dc",
            absolute_error=1e-13,
            relative_error=1e-11,
            maximum_iterations=50,
        )

        for region in silicon_regions:
            CreateSolution(DEVICE, region, "Electrons")
            CreateSolution(DEVICE, region, "Holes")
            set_node_values(
                device=DEVICE,
                region=region,
                name="Electrons",
                init_from="IntrinsicElectrons",
            )
            set_node_values(
                device=DEVICE,
                region=region,
                name="Holes",
                init_from="IntrinsicHoles",
            )
            CreateSiliconDriftDiffusion(DEVICE, region, "mu_n", "mu_p")
        for contact in contacts:
            region = get_region_list(device=DEVICE, contact=contact)[0]
            CreateSiliconDriftDiffusionAtContact(DEVICE, region, contact)

        solve(
            type="dc",
            absolute_error=1e30,
            relative_error=1e-8,
            maximum_iterations=60,
        )
        drain_voltage = 0.05
        _ramp("drain", 0.0, drain_voltage)

        gate_voltages = np.linspace(0.0, 2.0, 21)
        currents: list[float] = []
        snapshots: dict[float, MOSFETSnapshot] = {}
        for gate_voltage in gate_voltages:
            set_parameter(
                device=DEVICE,
                name=GetContactBiasName("gate"),
                value=float(gate_voltage),
            )
            solve(
                type="dc",
                absolute_error=1e30,
                relative_error=1e-8,
                maximum_iterations=60,
            )
            currents.append(_total_current("drain"))
            for requested in SNAPSHOT_VOLTAGES:
                if np.isclose(gate_voltage, requested):
                    snapshots[requested] = _snapshot(requested, drain_voltage)

        node_model(
            device=DEVICE,
            region=BULK,
            name="logElectrons",
            equation="log(Electrons)/log(10)",
        )

        # Calculate output characteristics after returning the drain to 0 V.
        # Ramping between bias points improves nonlinear-solver stability.
        _ramp("drain", drain_voltage, 0.0)
        current_gate_voltage = float(gate_voltages[-1])
        output_currents: list[list[float]] = []
        output_snapshots: dict[tuple[float, float], MOSFETSnapshot] = {}
        for gate_voltage in IDVD_GATE_VOLTAGES:
            _ramp("gate", current_gate_voltage, gate_voltage)
            current_gate_voltage = gate_voltage
            family: list[float] = []
            previous_drain_voltage = 0.0
            for output_drain_voltage in IDVD_DRAIN_VOLTAGES:
                if output_drain_voltage > previous_drain_voltage:
                    _ramp(
                        "drain",
                        previous_drain_voltage,
                        output_drain_voltage,
                    )
                previous_drain_voltage = output_drain_voltage
                family.append(_total_current("drain"))
                for requested in IDVD_SNAPSHOT_DRAIN_VOLTAGES:
                    if np.isclose(output_drain_voltage, requested):
                        output_snapshots[(gate_voltage, requested)] = _snapshot(
                            gate_voltage,
                            requested,
                        )
            output_currents.append(family)
            _ramp("drain", float(IDVD_DRAIN_VOLTAGES[-1]), 0.0)

    return LongChannelResult(
        gate_voltages=gate_voltages,
        drain_currents=np.asarray(currents),
        drain_voltage=drain_voltage,
        snapshots=snapshots,
        idvd_gate_voltages=np.asarray(IDVD_GATE_VOLTAGES),
        idvd_drain_voltages=np.asarray(IDVD_DRAIN_VOLTAGES),
        idvd_currents=np.asarray(output_currents),
        idvd_snapshots=output_snapshots,
    )
