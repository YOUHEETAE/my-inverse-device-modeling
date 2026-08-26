import { Sparkles } from "lucide-react";

/**
 * 로컬 실행판에서 AI 응답 자리에 대신 서는 안내.
 *
 * 그냥 두면 이 자리에 서버의 실패 안내가 뜬다 — "AI 기능 미연결 / 서비스
 * 관리자에게 문의해 주세요". 연결할 서버가 없는 로컬 실행판에서는 맞지 않는
 * 말이고, 처음 보는 사람에게는 고장으로 읽힌다. 빠진 것이 무엇이고 무엇이
 * 그대로 도는지, 온전한 것은 어디서 볼 수 있는지를 대신 적는다.
 */
export function StandaloneAiNotice({ compact }: { compact?: boolean }) {
  return (
    <div
      className={
        compact
          ? "flex h-full flex-col items-center justify-center gap-2 rounded-md border border-outline-variant bg-surface-container-lowest p-4 text-center"
          : "flex flex-col items-center gap-2 rounded-md border border-outline-variant bg-surface-container-lowest p-6 text-center"
      }
    >
      <div className="flex h-8 w-8 items-center justify-center rounded-sm border border-outline-variant bg-surface-container-highest">
        <Sparkles className="h-4 w-4 text-on-surface-variant" />
      </div>
      <p className="text-xs font-bold">이 로컬 실행판에는 AI 응답 기능이 없습니다.</p>
      <p className="max-w-md text-[11px] leading-relaxed text-on-surface-variant">
        예측, 조건 비교, Case Study 채점은 인터넷 없이 그대로 동작합니다. AI 설명과
        자유질문만 외부 모델을 부르는 기능이라 빠져 있습니다.
      </p>
      {/* 링크로 걸지 않는다 — 인터넷이 없는 PC에서 눌리면 그것대로 고장으로
          보인다. 주소만 적어두고 판단은 보는 사람에게 맡긴다. */}
      <p className="text-[11px] text-on-surface-variant">
        온전한 기능은 <span className="font-mono font-bold text-on-surface">semiscopeai.com</span> 에서 볼 수 있습니다.
      </p>
    </div>
  );
}
