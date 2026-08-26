import { createContext, useContext, useState, type ReactNode } from "react";
import {
  DEFAULT_PARAMETERS,
  findParameterProblem,
  type DeviceParameters,
  type ParameterProblem,
} from "../curves/types";

// The parameter list a curve/device was built from, shared between the Curves
// and Field Map pages (mirrors the desktop app's single curve_configs list
// used by both tabs). Each page keeps its own prediction cache (CurveResponse /
// FieldResponse) keyed by id — those are expensive, page-specific outputs and
// don't belong on the shared entry itself.
//
// No `label` field here on purpose: `id` is a permanently-incrementing,
// never-reused counter (needed for stable React keys and cache keys), but the
// desktop app's "Curve N" numbering is purely positional (index-based, see
// frontend/app.py). Baking the id into the label would leave gaps after a
// delete (e.g. 1, 3, 4) instead of renumbering — so callers should derive the
// display label from each entry's current index in `devices`.
export interface SharedDeviceEntry {
  id: number;
  visible: boolean;
  parameters: DeviceParameters;
}

export const MAX_SHARED_DEVICES = 4;

interface DeviceStoreValue {
  devices: SharedDeviceEntry[];
  activeId: number;
  inputValues: DeviceParameters;
  /**
   * 입력값이 잘못돼 Add/Update를 되돌려보낸 이유. 누르기 전에는 아무 말도
   * 하지 않는다 — 타이핑하는 중간 상태마다 빨간 글씨가 뜨면 잘못한 줄
   * 알게 된다. 값을 고치면 사라진다.
   */
  inputProblem: ParameterProblem | null;
  atCapacity: boolean;
  setInputValues: (values: DeviceParameters) => void;
  selectDevice: (id: number) => void;
  addDevice: () => void;
  updateSelected: () => void;
  removeSelected: () => void;
  toggleVisible: (id: number) => void;
  /**
   * 소자 구성을 통째로 바꾼다. 과거 대화를 열었을 때 그 대화가 얼려둔 소자
   * 조건을 작업대에 되살리기 위한 것 — 말풍선 속 숫자와 화면 그래프가
   * 어긋난 채로 이어서 질문하게 두면 사용자가 어느 쪽을 보고 있는지 알 수
   * 없다. 기존 구성을 덮어쓰므로 호출부가 먼저 확인을 받는다.
   */
  replaceDevices: (parameters: DeviceParameters[]) => void;
}

const DeviceStoreContext = createContext<DeviceStoreValue | null>(null);

let nextId = 2;

export function DeviceStoreProvider({ children }: { children: ReactNode }) {
  const [devices, setDevices] = useState<SharedDeviceEntry[]>([
    { id: 1, visible: true, parameters: DEFAULT_PARAMETERS },
  ]);
  const [activeId, setActiveId] = useState(1);
  const [inputValues, setInputValues] = useState<DeviceParameters>(DEFAULT_PARAMETERS);
  const [inputProblem, setInputProblem] = useState<ParameterProblem | null>(null);

  // 값이 바뀌면 지난 경고는 지운다. 고치는 동안에도 남아 있으면 방금 고친
  // 것이 통했는지 알 수 없다.
  function changeInputValues(values: DeviceParameters) {
    setInputValues(values);
    setInputProblem(null);
  }

  function selectDevice(id: number) {
    setActiveId(id);
    const device = devices.find((d) => d.id === id);
    if (device) changeInputValues(device.parameters);
  }

  function addDevice() {
    if (devices.length >= MAX_SHARED_DEVICES) return;
    const problem = findParameterProblem(inputValues);
    if (problem) {
      setInputProblem(problem);
      return;
    }
    const id = nextId++;
    setDevices([...devices, { id, visible: true, parameters: inputValues }]);
    setActiveId(id);
  }

  function updateSelected() {
    // Add와 같은 문을 지킨다 — 여기로 들어오면 곧장 예측 요청이 나가므로,
    // 잘못된 값이 통과하면 화면에 남아 있던 멀쩡한 곡선까지 오류로 바뀐다.
    const problem = findParameterProblem(inputValues);
    if (problem) {
      setInputProblem(problem);
      return;
    }
    setDevices(devices.map((d) => (d.id === activeId ? { ...d, parameters: inputValues } : d)));
  }

  function removeSelected() {
    const remaining = devices.filter((d) => !d.visible);
    setDevices(remaining);
    if (remaining.length > 0 && !remaining.some((d) => d.id === activeId)) {
      const next = remaining[remaining.length - 1];
      setActiveId(next.id);
      changeInputValues(next.parameters);
    }
  }

  function replaceDevices(parameters: DeviceParameters[]) {
    const restored = parameters
      .slice(0, MAX_SHARED_DEVICES)
      .map((p) => ({ id: nextId++, visible: true, parameters: p }));
    if (restored.length === 0) return;
    setDevices(restored);
    setActiveId(restored[0].id);
    changeInputValues(restored[0].parameters);
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
        inputProblem,
        setInputValues: changeInputValues,
        selectDevice,
        addDevice,
        updateSelected,
        removeSelected,
        toggleVisible,
        replaceDevices,
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
