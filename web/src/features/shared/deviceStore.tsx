import { createContext, useContext, useState, type ReactNode } from "react";
import { DEFAULT_PARAMETERS, type DeviceParameters } from "../curves/types";

// The parameter list a curve/device was built from, shared between the Curves
// and Field Map pages (mirrors the desktop app's single curve_configs list
// used by both tabs). Each page keeps its own prediction cache (CurveResponse /
// FieldResponse) keyed by id — those are expensive, page-specific outputs and
// don't belong on the shared entry itself.
export interface SharedDeviceEntry {
  id: number;
  label: string;
  visible: boolean;
  parameters: DeviceParameters;
}

export const MAX_SHARED_DEVICES = 4;

interface DeviceStoreValue {
  devices: SharedDeviceEntry[];
  activeId: number;
  inputValues: DeviceParameters;
  atCapacity: boolean;
  setInputValues: (values: DeviceParameters) => void;
  selectDevice: (id: number) => void;
  addDevice: () => void;
  updateSelected: () => void;
  removeSelected: () => void;
  toggleVisible: (id: number) => void;
}

const DeviceStoreContext = createContext<DeviceStoreValue | null>(null);

let nextId = 2;

export function DeviceStoreProvider({ children }: { children: ReactNode }) {
  const [devices, setDevices] = useState<SharedDeviceEntry[]>([
    { id: 1, label: "Curve 1", visible: true, parameters: DEFAULT_PARAMETERS },
  ]);
  const [activeId, setActiveId] = useState(1);
  const [inputValues, setInputValues] = useState<DeviceParameters>(DEFAULT_PARAMETERS);

  function selectDevice(id: number) {
    setActiveId(id);
    const device = devices.find((d) => d.id === id);
    if (device) setInputValues(device.parameters);
  }

  function addDevice() {
    if (devices.length >= MAX_SHARED_DEVICES) return;
    const id = nextId++;
    setDevices([...devices, { id, label: `Curve ${id}`, visible: true, parameters: inputValues }]);
    setActiveId(id);
  }

  function updateSelected() {
    setDevices(devices.map((d) => (d.id === activeId ? { ...d, parameters: inputValues } : d)));
  }

  function removeSelected() {
    const remaining = devices.filter((d) => !d.visible);
    setDevices(remaining);
    if (remaining.length > 0 && !remaining.some((d) => d.id === activeId)) {
      const next = remaining[remaining.length - 1];
      setActiveId(next.id);
      setInputValues(next.parameters);
    }
  }

  function toggleVisible(id: number) {
    setDevices(devices.map((d) => (d.id === id ? { ...d, visible: !d.visible } : d)));
  }

  return (
    <DeviceStoreContext.Provider
      value={{
        devices,
        activeId,
        inputValues,
        atCapacity: devices.length >= MAX_SHARED_DEVICES,
        setInputValues,
        selectDevice,
        addDevice,
        updateSelected,
        removeSelected,
        toggleVisible,
      }}
    >
      {children}
    </DeviceStoreContext.Provider>
  );
}

export function useDeviceStore() {
  const ctx = useContext(DeviceStoreContext);
  if (!ctx) throw new Error("useDeviceStore must be used within a DeviceStoreProvider");
  return ctx;
}
