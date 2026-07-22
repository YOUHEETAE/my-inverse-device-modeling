import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

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

interface ExplanationPanelProps {
  status: ExplanationStatus;
  content: string;
  provider: "mock" | "external_llm";
  onProviderChange: (provider: "mock" | "external_llm") => void;
  onAnalyze: () => void;
  disabled?: boolean;
  disabledReason?: string;
  promptText: string;
}

export function ExplanationPanel({
  status,
  content,
  provider,
  onProviderChange,
  onAnalyze,
  disabled,
  disabledReason,
  promptText,
}: ExplanationPanelProps) {
  const [promptOpen, setPromptOpen] = useState(false);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">Explanation</span>
        <Select value={provider} onValueChange={(v) => onProviderChange(v as "mock" | "external_llm")}>
          <SelectTrigger size="sm" className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="mock">mock</SelectItem>
            <SelectItem value="external_llm">external_llm</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex gap-2">
        <Button
          size="sm"
          className="flex-1"
          onClick={onAnalyze}
          disabled={disabled || status === "analyzing"}
        >
          Analyze
        </Button>
        <Button
          size="sm"
          variant="secondary"
          className="flex-1"
          onClick={() => navigator.clipboard.writeText(content)}
          disabled={!content}
        >
          Copy
        </Button>
        <Button
          size="sm"
          variant="secondary"
          className="flex-1"
          onClick={() => setPromptOpen(true)}
          disabled={disabled}
        >
          Preview LLM Prompt
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        {disabled && disabledReason ? disabledReason : STATUS_LABEL[status]}
      </p>

      <Textarea readOnly value={content} className="h-48 resize-none overflow-y-auto text-sm" />

      <Dialog open={promptOpen} onOpenChange={setPromptOpen}>
        <DialogContent className="max-w-3xl">
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
