import { useState } from "react";

import { Button, Textarea } from "@/shared/ui";

/** Enter sends, Shift+Enter is a new line. The hint button climbs the hint ladder one rung for the open lesson/problem. */
export function Composer({ disabled, sending, showHint, onSend, onHint }: {
  disabled: boolean;
  sending: boolean;
  showHint: boolean;
  onSend: (content: string) => void;
  onHint: () => void;
}) {
  const [text, setText] = useState("");
  const submit = () => {
    const content = text.trim();
    if (!content || disabled || sending) return;
    onSend(content);
    setText("");
  };

  return (
    <div className="border-t border-slate-200 bg-white p-3">
      <Textarea
        aria-label="Message the tutor"
        rows={2}
        maxLength={4000}
        value={text}
        disabled={disabled}
        placeholder={disabled ? "The tutor isn't available right now." : "Ask about the course…"}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
      />
      <div className="mt-2 flex justify-end gap-2">
        {showHint && (
          <Button variant="secondary" disabled={disabled || sending} onClick={onHint}>
            Give me a hint
          </Button>
        )}
        <Button icon="arrowUp" loading={sending} disabled={disabled || !text.trim()} onClick={submit}>
          Send
        </Button>
      </div>
    </div>
  );
}
