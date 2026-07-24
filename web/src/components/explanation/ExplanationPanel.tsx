import { useState } from "react";
import { Copy, Eye, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

export type ExplanationStatus =
  | "ready"
  | "analyzing"
  | "cached"
  | "complete"
  | "failed"
  | "stale";

const STATUS_LABEL: Record<ExplanationStatus, string> = {
  ready: "Ready",
  analyzing: "Analyzing...",
  cached: "Cached",
  complete: "Complete",
  failed: "Failed",
  stale: "Results changed — press Analyze",
};

const PROVIDER_LABEL: Record<"mock" | "external_llm", string> = {
  mock: "Mock Analysis Engine",
  external_llm: "Groq (openai/gpt-oss-120b)",
};

interface ExplanationPanelProps {
  status: ExplanationStatus;
  content: string;
  provider: "mock" | "external_llm" | null;
  onAnalyze: () => void;
  disabled?: boolean;
  disabledReason?: string;
  fetchPromptText: () => Promise<string>
}

export function ExplanationPanel({
  status,
  content,
  provider,
  onAnalyze,
  disabled,
  disabledReason,
  fetchPromptText,
}: ExplanationPanelProps) {
  const [promptOpen, setPromptOpen] = useState(false);
  const [promptText, setPromptText] = useState("");

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-sm border border-primary/30 bg-primary/10">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wide">AI Explanation</h3>
            <p className="text-[11px] text-on-surface-variant">
              Neural inference engine for physical device interpretation.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {provider && (
            <span className="rounded-sm border border-outline-variant bg-surface-container-highest px-2 py-1 font-mono text-[10px] uppercase tracking-wide text-on-surface-variant">
              {PROVIDER_LABEL[provider]}
            </span>
          )}
          <Button
            size="sm"
            onClick={onAnalyze}
            disabled={disabled || status === "analyzing"}
            className="gap-1.5 bg-primary text-xs font-bold text-primary-foreground hover:bg-primary/90"
          >
            <Sparkles className="h-3.5 w-3.5" />
            Analyze
          </Button>
        </div>
      </div>

      <div className="relative min-h-32 rounded-md border border-outline-variant bg-surface-container-lowest p-3">
        <div className="whitespace-pre-wrap text-xs leading-relaxed text-on-surface-variant">
          {content || (disabled && disabledReason) || "Press Analyze to generate an explanation."}
        </div>
        <div className="mt-2 flex items-center gap-1.5 border-t border-outline-variant pt-2">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              status === "analyzing" ? "animate-pulse bg-accent-orange" : "bg-accent-green",
            )}
          />
          <span className="font-mono text-[10px] uppercase tracking-wider text-on-surface-variant">
            {disabled && disabledReason ? disabledReason : STATUS_LABEL[status]}
          </span>
        </div>
      </div>

      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 border-outline-variant text-xs text-on-surface-variant"
          onClick={() => navigator.clipboard.writeText(content)}
          disabled={!content}
        >
          <Copy className="h-3.5 w-3.5" />
          Copy Analysis
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5 border-outline-variant text-xs text-on-surface-variant"
          onClick={async () => {
            setPromptOpen(true);
            setPromptText(await fetchPromptText());
          }}
          disabled={disabled}
        >
          <Eye className="h-3.5 w-3.5" />
          Preview Prompt
        </Button>
      </div>

      <Dialog open={promptOpen} onOpenChange={setPromptOpen}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>LLM Prompt Preview</DialogTitle>
          </DialogHeader>
          <Textarea readOnly value={promptText} className="min-h-96 font-mono text-xs" />
          <Button
            variant="outline"
            onClick={() => navigator.clipboard.writeText(promptText)}
            className="self-end"
          >
            Copy Prompt
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
