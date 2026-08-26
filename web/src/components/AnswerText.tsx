import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

/**
 * AI가 만든 답변 본문.
 *
 * 답변은 마크다운으로 온다 — 굵게, 목록, 그리고 지표를 나란히 놓을 때는 표.
 * 그동안 순수 텍스트로 그려서 별표와 `|---|---|`가 화면에 그대로 보였다.
 *
 * HTML은 일부러 해석하지 않는다(rehype-raw를 쓰지 않는다). 모델이 만든 글을
 * 그리는 자리라 태그가 살아나면 안 된다 — react-markdown은 기본이 이스케이프다.
 *
 * 표는 자기 상자 안에서만 가로로 넘친다. 말풍선이 좁아서 그대로 두면 대화
 * 전체가 옆으로 밀린다.
 */
export function AnswerText({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("space-y-2 [&>*:first-child]:mt-0 [&>*:last-child]:mb-0", className)}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="leading-relaxed">{children}</p>,
          strong: ({ children }) => <strong className="font-bold text-on-surface">{children}</strong>,
          ul: ({ children }) => <ul className="ml-4 list-disc space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="ml-4 list-decimal space-y-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          // 답변 안의 제목은 본문보다 살짝 굵은 정도면 된다. 크게 키우면
          // 말풍선 안에서 문서처럼 보인다.
          h1: ({ children }) => <p className="font-bold text-on-surface">{children}</p>,
          h2: ({ children }) => <p className="font-bold text-on-surface">{children}</p>,
          h3: ({ children }) => <p className="font-bold text-on-surface">{children}</p>,
          h4: ({ children }) => <p className="font-bold text-on-surface">{children}</p>,
          code: ({ children }) => (
            <code className="rounded-sm bg-surface-container-highest px-1 py-0.5 font-mono text-[0.9em]">
              {children}
            </code>
          ),
          a: ({ children }) => <span>{children}</span>,
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left tabular-nums">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="text-on-surface-variant">{children}</thead>,
          th: ({ children }) => (
            <th className="border-b border-outline-variant px-1.5 py-1 font-medium">{children}</th>
          ),
          td: ({ children }) => (
            <td className="border-b border-outline-variant/50 px-1.5 py-1 align-top">{children}</td>
          ),
        }}
      >
        {children}
      </Markdown>
    </div>
  );
}
