import { useEffect, useRef, useState } from "react";
import { Check, Pencil, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { renameSession } from "../api";

interface SessionNameProps {
  sessionId: string;
  name: string;
  disabled?: boolean;
  onRenamed: (name: string) => void;
}

/**
 * 학습 기록 이름 (panel.py의 _rename_selected_session).
 *
 * 같은 케이스를 여러 번 풀면 기록이 전부 "새 학습 세션"이라 목록에서
 * 구분할 수 없다. 이름은 저장된 JSON 안의 값만 바꾸는 일이라 Python을
 * 거치지 않고 자바가 바로 처리한다.
 */
export function SessionName({ sessionId, name, disabled, onRenamed }: SessionNameProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(name);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => setDraft(name), [name]);
  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  async function save() {
    const value = draft.trim();
    if (!value || value === name) {
      setEditing(false);
      setDraft(name);
      return;
    }
    setSaving(true);
    try {
      await renameSession(sessionId, value);
      onRenamed(value);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  if (!editing) {
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={() => setEditing(true)}
        title="이름 바꾸기"
        className="group flex min-w-0 items-center gap-1 text-[11px] text-on-surface-variant hover:text-on-surface disabled:cursor-default"
      >
        <span className="truncate">{name}</span>
        <Pencil className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100 motion-reduce:transition-none" />
      </button>
    );
  }

  return (
    <div className="flex items-center gap-1">
      <input
        ref={inputRef}
        value={draft}
        maxLength={80}
        disabled={saving}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") save();
          if (event.key === "Escape") {
            setDraft(name);
            setEditing(false);
          }
        }}
        className="w-40 rounded-sm border border-outline-variant bg-surface-container-lowest px-1.5 py-0.5 text-[11px] outline-none focus:border-primary"
      />
      <Button variant="ghost" size="sm" className="h-6 w-6 p-0" disabled={saving} onClick={save}>
        <Check className="h-3 w-3" />
      </Button>
      <Button
        variant="ghost"
        size="sm"
        className="h-6 w-6 p-0"
        disabled={saving}
        onClick={() => {
          setDraft(name);
          setEditing(false);
        }}
      >
        <X className="h-3 w-3" />
      </Button>
    </div>
  );
}
