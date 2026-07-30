import { ArrowRight } from "lucide-react";

export function FlowSteps({ steps, className = "" }: { steps: string[]; className?: string }) {
  return (
    <div className={`flex flex-wrap items-center gap-x-2 gap-y-2 ${className}`}>
      {steps.map((step, index) => (
        <span key={step} className="flex items-center gap-2">
          {index > 0 && <ArrowRight className="h-3.5 w-3.5 shrink-0 text-on-surface-variant" />}
          <span className="rounded-sm border border-outline-variant bg-surface-container px-2.5 py-1 font-mono text-[11px] font-medium">
            {step}
          </span>
        </span>
      ))}
    </div>
  );
}
