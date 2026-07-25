import { ChevronDown } from "lucide-react";
import { DEFAULT_PARAMETERS, PARAMETER_OPTIONS, type DeviceParameters } from "../types";

const PARAMETER_LABELS: Record<keyof DeviceParameters, string> = {
  L: "L (nm)",
  T: "T (nm)",
  B: "B (cm⁻³)",
  SD: "SD (cm⁻³)",
  LDD: "LDD (cm⁻³)",
};

interface ParameterInputsProps {
  values: DeviceParameters;
  onChange: (values: DeviceParameters) => void;
}

export function ParameterInputs({ values, onChange }: ParameterInputsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {(Object.keys(DEFAULT_PARAMETERS) as (keyof DeviceParameters)[]).map((name) => (
        <div
          key={name}
          className="relative flex min-w-24 flex-1 flex-col gap-0.5 rounded-sm border border-outline-variant bg-surface-container-low px-2 py-1 transition-colors focus-within:border-primary/50"
        >
          <label
            htmlFor={`param-${name}`}
            className="text-[9px] uppercase tracking-wide text-on-surface-variant"
          >
            {PARAMETER_LABELS[name]}
          </label>
          <input
            id={`param-${name}`}
            list={`param-${name}-options`}
            value={values[name]}
            onChange={(event) => onChange({ ...values, [name]: event.target.value })}
            className="bg-transparent pr-4 font-mono text-xs text-accent-green outline-none"
          />
          <ChevronDown className="pointer-events-none absolute right-2 bottom-1.5 h-3 w-3 text-on-surface-variant/60" />
          <datalist id={`param-${name}-options`}>
            {PARAMETER_OPTIONS[name].map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
        </div>
      ))}
    </div>
  );
}
