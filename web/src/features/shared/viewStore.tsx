import { createContext, useContext, useState, type ReactNode } from "react";
import type { FieldDisplay, RangeMode, ScaleMode } from "../fields/types";

// Per-page display/view preferences (not device parameters — those live in
// deviceStore.tsx). Lifted to App level so navigating Curves <-> Field Map
// doesn't reset the view a user was looking at back to its default.
interface ViewStoreValue {
  fieldDisplay: FieldDisplay;
  setFieldDisplay: (value: FieldDisplay) => void;
  fieldScaleMode: ScaleMode;
  setFieldScaleMode: (value: ScaleMode) => void;
  fieldRangeMode: RangeMode;
  setFieldRangeMode: (value: RangeMode) => void;
  curveCombined: boolean;
  setCurveCombined: (value: boolean) => void;
  curveLogScale: boolean;
  setCurveLogScale: (value: boolean) => void;
}

const ViewStoreContext = createContext<ViewStoreValue | null>(null);

export function ViewStoreProvider({ children }: { children: ReactNode }) {
  const [fieldDisplay, setFieldDisplay] = useState<FieldDisplay>("Mesh");
  const [fieldScaleMode, setFieldScaleMode] = useState<ScaleMode>("Auto");
  const [fieldRangeMode, setFieldRangeMode] = useState<RangeMode>("Robust 1-99%");
  const [curveCombined, setCurveCombined] = useState(true);
  const [curveLogScale, setCurveLogScale] = useState(false);

  return (
    <ViewStoreContext.Provider
      value={{
        fieldDisplay,
        setFieldDisplay,
        fieldScaleMode,
        setFieldScaleMode,
        fieldRangeMode,
        setFieldRangeMode,
        curveCombined,
        setCurveCombined,
        curveLogScale,
        setCurveLogScale,
      }}
    >
      {children}
    </ViewStoreContext.Provider>
  );
}

export function useViewStore() {
  const ctx = useContext(ViewStoreContext);
  if (!ctx) throw new Error("useViewStore must be used within a ViewStoreProvider");
  return ctx;
}
