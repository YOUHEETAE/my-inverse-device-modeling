import { useState, type ReactNode } from "react";
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
import type { ExplanationSection } from "./explanationSections";

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

// 데스크톱 앱의 탭 이름을 그대로 쓴다
// (frontend/visualization/explanation_panel.py의 ttk.Notebook).
const TABS = [
  { id: "automatic", label: "자동 설명" },
  { id: "chat", label: "AI 질문" },
] as const;

type TabId = (typeof TABS)[number]["id"];

interface ExplanationPanelProps {
  status: ExplanationStatus;
  /**
   * 제목이 붙은 섹션들. 서버가 네 갈래로 나눠 보내므로 그대로 나눠 보여준다 —
   * 이어 붙이면 어디까지가 관찰이고 어디부터가 비교인지 알 수 없다.
   */
  sections: ExplanationSection[];
  provider: "mock" | "external_llm" | null;
  onAnalyze: () => void;
  disabled?: boolean;
  disabledReason?: string;
  fetchPromptText: () => Promise<string>
  /**
   * 자유질문 탭의 내용. 분석과 한 카드에 두되 탭으로 가르는 이유는, 두
   * 경로의 보장이 서로 다르기 때문이다 — 분석은 비로그인도 되고 캐시와
   * fallback이 있지만, 자유질문은 로그인이 필요하고 fallback이 금지되어
   * 있다. 나란히 쌓으면 카드가 계속 길어지기도 한다.
   */
  chat?: ReactNode;
}

export function ExplanationPanel({
  status,
  sections,
  provider,
  onAnalyze,
  disabled,
  disabledReason,
  fetchPromptText,
  chat,
}: ExplanationPanelProps) {
  const [promptOpen, setPromptOpen] = useState(false);
  const [promptText, setPromptText] = useState("");
  const [tab, setTab] = useState<TabId>("automatic");

  return (
    <div className="flex flex-col gap-3">
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

      <div role="tablist" aria-label="AI Explanation" className="flex gap-1 border-b border-outline-variant">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            role="tab"
            type="button"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={cn(
              "-mb-px border-b-2 px-3 py-1.5 text-xs font-bold transition-colors motion-reduce:transition-none",
              tab === id
                ? "border-primary text-primary"
                : "border-transparent text-on-surface-variant hover:text-on-surface",
            )}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "automatic" ? (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center justify-end gap-2">
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

          <div className="relative min-h-32 rounded-md border border-outline-variant bg-surface-container-lowest p-3">
            {sections.length > 0 ? (
              <div className="space-y-3">
                {sections.map((section) => (
                  <div key={section.title}>
                    <h4 className="mb-1 text-[11px] font-bold">{section.title}</h4>
                    {section.paragraph ? (
                      <p className="whitespace-pre-wrap text-xs leading-relaxed text-on-surface-variant">
                        {section.lines.join(" ")}
                      </p>
                    ) : (
                      <ul className="space-y-1">
                        {section.lines.map((line) => (
                          <li key={line} className="text-xs leading-relaxed text-on-surface-variant">
                            · {line}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs leading-relaxed text-on-surface-variant">
                {(disabled && disabledReason) || "Press Analyze to generate an explanation."}
              </div>
            )}
            <div className="mt-2 flex items-center gap-1.5 border-t border-outline-variant pt-2">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  status === "analyzing"
                    ? "animate-pulse bg-accent-orange"
                    : status === "failed"
                      ? "bg-destructive"
                      : "bg-accent-green",
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
              onClick={() => navigator.clipboard.writeText(plainText(sections))}
              disabled={sections.length === 0}
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
        </div>
      ) : (
        chat
      )}

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

// 복사할 때는 제목까지 함께 담는다 — 붙여넣은 쪽에서도 어느 갈래의
// 설명인지 남아야 한다.
function plainText(sections: ExplanationSection[]): string {
  return sections
    .map((section) => {
      const body = section.lines.join(section.paragraph ? " " : "\n");
      return `${section.title}\n${body}`;
    })
    .join("\n\n");
}
