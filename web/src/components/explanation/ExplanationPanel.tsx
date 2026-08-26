import { useState, type ReactNode } from "react";
import { Copy, Eye, LogIn, Sparkles } from "lucide-react";
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

// 서버가 내려주는 오류·실패 문장이 전부 한국어라(자바의
// ResponseStatusException, Python의 public_presentation.py) 상태 표시만
// 영어로 두면 같은 상자 안에서 두 언어가 부딪힌다. 버튼 이름은 짧은
// 라벨이라 영어로 남긴다.
const STATUS_LABEL: Record<ExplanationStatus, string> = {
  ready: "대기 중",
  analyzing: "분석 중…",
  cached: "저장된 결과",
  complete: "완료",
  failed: "실패",
  stale: "결과가 바뀌었습니다 — Analyze를 다시 누르세요",
};

// 모델명을 적어 두지 않는다. 서버가 응답에 실제로 쓴 모델을 담아 보내므로
// 그걸 그대로 보여준다 — 여기에 박아두면 모델을 바꿀 때마다 화면이
// 거짓말을 하게 되고, 바뀐 줄 모르고 지나가기 쉽다.
//
// 경계 문서(docs/user_information_boundary.md)의 5번은 설명 "본문 끝에"
// provider/model을 덧붙이지 말라는 규칙이라 이 배지와는 다른 얘기다.
const PROVIDER_LABEL: Record<"mock" | "external_llm", string> = {
  mock: "Mock Analysis Engine",
  external_llm: "External LLM",
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
  /** 서버가 실제로 사용한 모델. 없으면 제공자 이름만 보여준다. */
  model?: string | null;
  onAnalyze: () => void;
  disabled?: boolean;
  disabledReason?: string;
  /**
   * 실패한 이유. 서버가 내려준 문장을 그대로 받는다 — "Failed"만 보여주면
   * 하루 한도를 다 썼는지, 조건이 잘못됐는지, 모델이 잠깐 죽었는지를
   * 구분할 수 없다.
   */
  error?: string | null;
  fetchPromptText: () => Promise<string>
  /**
   * 분석도 로그인을 요구한다 — 한 번 누를 때마다 외부 LLM 비용이 나가고,
   * 비로그인은 계정 단위로 하루 한도를 걸 수단이 없다(서버의
   * DailyQuotaInterceptor). 조건을 바꿔 예측하고 비교하는 것은 그대로
   * 열려 있다.
   */
  authenticated: boolean;
  onLogin: () => void;
  /**
   * 자유질문 탭의 내용. 분석과 한 카드에 두되 탭으로 가르는 이유는, 두
   * 경로의 보장이 서로 다르기 때문이다 — 분석에는 캐시와 fallback이 있지만
   * 자유질문은 fallback이 금지되어 있다. 나란히 쌓으면 카드가 계속
   * 길어지기도 한다.
   */
  chat?: ReactNode;
}

export function ExplanationPanel({
  status,
  sections,
  provider,
  model,
  onAnalyze,
  disabled,
  disabledReason,
  error,
  fetchPromptText,
  authenticated,
  onLogin,
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
          {/* 제목은 영어, 설명은 한국어 — Case Study 화면과 같은 규칙이다. */}
          <p className="text-[11px] text-on-surface-variant">
            예측 결과에서 뽑은 수치를 근거로 변화의 원인과 trade-off를 설명합니다.
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
                {provider === "external_llm" && model ? model : PROVIDER_LABEL[provider]}
              </span>
            )}
            {authenticated ? (
              <Button
                size="sm"
                onClick={onAnalyze}
                disabled={disabled || status === "analyzing"}
                className="gap-1.5 bg-primary text-xs font-bold text-primary-foreground hover:bg-primary/90"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Analyze
              </Button>
            ) : (
              // 눌러봐야 401이 돌아오는 버튼을 그대로 두지 않는다 — 무엇이
              // 필요한지 버튼 자체가 말하게 한다 (자유질문 탭과 같은 방식).
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5 border-outline-variant text-xs text-on-surface-variant"
                onClick={onLogin}
              >
                <LogIn className="h-3.5 w-3.5" />
                Sign in to analyze
              </Button>
            )}
          </div>

          <div className="relative min-h-32 rounded-md border border-outline-variant bg-surface-container-lowest p-3">
            {sections.length > 0 ? (
              <div className="space-y-3">
                {sections.map((section) => (
                  <div key={section.title}>
                    <h4 className="mb-1 text-[11px] font-bold">{section.title}</h4>
                    {/* 자동 설명은 서버가 제목과 줄 단위로 이미 쪼개 준다.
                        마크다운이 섞여 오지 않아 그대로 그린다 — 자유질문
                        답변만 AnswerText로 그린다. */}
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
                {(disabled && disabledReason) ||
                  (authenticated
                    ? "Analyze를 누르면 이 결과에 대한 설명을 생성합니다."
                    : "로그인하면 이 결과에 대한 AI 설명을 생성할 수 있습니다. 예측과 비교는 로그인 없이 그대로 사용할 수 있고, 아래 Preview Prompt로 어떤 근거가 모델에 전달되는지 먼저 확인할 수 있습니다.")}
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
              {/* 한국어에는 uppercase가 듣지 않고 자간만 벌어져 읽기 나쁘다.
                  등폭 글꼴도 한글에서는 폴백이 걸린다. */}
              <span className="text-[10px] text-on-surface-variant">
                {disabled && disabledReason ? disabledReason : STATUS_LABEL[status]}
              </span>
            </div>
          </div>

          {/* 지난 분석 결과가 위에 남아 있을 수 있으므로 상자 밖에 따로
              적는다 — 실패했다는 사실이 옛 결과에 묻히면 안 된다. */}
          {status === "failed" && error && (
            <p className="text-[11px] leading-relaxed text-destructive">{error}</p>
          )}

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
