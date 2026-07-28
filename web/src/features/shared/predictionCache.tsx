import { createContext, useContext, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import type { CurveResponse, DeviceParameters } from "../curves/types";
import type { FieldResponse } from "../fields/types";

// Prediction results are expensive (backend simulation/mesh generation) and
// keyed by the shared device id (see deviceStore.tsx). Lifted to App level
// so switching between Curves and Field Map doesn't throw the cache away and
// re-predict every visible curve/device from scratch on every visit.
export interface CachedCurveResult {
  parameters: DeviceParameters;
  result: CurveResponse;
}

export interface CachedFieldMesh {
  parameters: DeviceParameters;
  mesh: FieldResponse;
}

interface PredictionCacheValue {
  curveResults: Record<number, CachedCurveResult>;
  setCurveResults: Dispatch<SetStateAction<Record<number, CachedCurveResult>>>;
  fieldMeshes: Record<number, CachedFieldMesh>;
  setFieldMeshes: Dispatch<SetStateAction<Record<number, CachedFieldMesh>>>;
}

const PredictionCacheContext = createContext<PredictionCacheValue | null>(null);

export function PredictionCacheProvider({ children }: { children: ReactNode }) {
  const [curveResults, setCurveResults] = useState<Record<number, CachedCurveResult>>({});
  const [fieldMeshes, setFieldMeshes] = useState<Record<number, CachedFieldMesh>>({});

  return (
    <PredictionCacheContext.Provider value={{ curveResults, setCurveResults, fieldMeshes, setFieldMeshes }}>
      {children}
    </PredictionCacheContext.Provider>
  );
}

export function usePredictionCache() {
  const ctx = useContext(PredictionCacheContext);
  if (!ctx) throw new Error("usePredictionCache must be used within a PredictionCacheProvider");
  return ctx;
}
