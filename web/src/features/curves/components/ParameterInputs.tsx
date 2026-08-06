import { useEffect, useRef, useState } from "react";
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
  const [openField, setOpenField] = useState<keyof DeviceParameters | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!openField) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpenField(null);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [openField]);

  return (
    <div ref={containerRef} className="flex flex-wrap gap-2">
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
            value={values[name]}
            onChange={(event) => onChange({ ...values, [name]: event.target.value })}
            className="bg-transparent pr-4 font-mono text-xs text-accent-green outline-none"
          />
          <button
            type="button"
            onClick={() => setOpenField(openField === name ? null : name)}
            className="absolute right-1.5 bottom-1.5 flex h-3.5 w-3.5 items-center justify-center text-on-surface-variant/60 hover:text-on-surface-variant"
          >
            <ChevronDown className="h-3 w-3" />
          </button>
          {openField === name && (
            <ul className="absolute left-0 top-full z-10 mt-1 max-h-40 w-full min-w-24 overflow-y-auto rounded-sm border border-outline-variant bg-surface-container-low shadow-md">
              {PARAMETER_OPTIONS[name].map((option) => (
                <li key={option}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange({ ...values, [name]: option });
                      setOpenField(null);
                    }}
                    className="block w-full px-2 py-1 text-left font-mono text-xs text-accent-green hover:bg-surface-container-high"
                  >
                    {option}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  );
}
