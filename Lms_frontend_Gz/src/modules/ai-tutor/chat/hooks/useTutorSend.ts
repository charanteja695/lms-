import { useCallback, useState } from "react";

import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { env } from "@/core/config/env";
import { useNotify } from "@/core/hooks/useNotify";
import { chatApi, useSendTutorMessageMutation } from "@/modules/ai-tutor/chat/api/chatApi";
import { readNdjson } from "@/modules/ai-tutor/chat/hooks/readNdjson";
import type { MessageContext } from "@/modules/ai-tutor/chat/types";

/**
 * Sends a message with `stream: true` so the answer appears as it is written. If the streamed request
 * can't be made or answers with an HTTP error (an expired token, the tutor switched off in a test, ...),
 * it falls back to the plain request with the SAME Idempotency-Key: that path refreshes the token and
 * shows the server's error, and the key guarantees the message is never saved twice.
 */
export function useTutorSend(conversationId: string) {
  const dispatch = useAppDispatch();
  const notify = useNotify();
  const token = useAppSelector((state) => state.auth.accessToken);
  const [sendPlain] = useSendTutorMessageMutation();
  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [streamed, setStreamed] = useState("");

  const send = useCallback(
    async (content: string, context: MessageContext) => {
      const idempotencyKey = crypto.randomUUID();
      setPendingUser(context.hint_request ? "Give me a hint" : content);
      setStreamed("");
      let streamedOk = false;
      try {
        const response = await fetch(`${env.apiBaseUrl}/conversations/${conversationId}/messages`, {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/x-ndjson",
            "Idempotency-Key": idempotencyKey,
            "X-Session-Transport": "cookie",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({ content, context, stream: true }),
        });
        if (response.ok && response.body) {
          streamedOk = true;
          await readNdjson(response.body, (event) => {
            if (event.type === "delta") setStreamed((text) => text + String(event.text ?? ""));
            if (event.type === "error") notify.error("The tutor couldn't finish", String(event.message ?? "Try again."));
          });
        }
      } catch {
        streamedOk = false;
      }
      if (!streamedOk) {
        try {
          await sendPlain({ conversationId, content, context, idempotencyKey }).unwrap();
        } catch (error) {
          notify.apiError(error, "Message not sent");
        }
      }
      const refreshed = dispatch(chatApi.endpoints.getConversation.initiate(conversationId, { forceRefetch: true }));
      await refreshed;
      refreshed.unsubscribe();
      dispatch(chatApi.util.invalidateTags(["TutorConversationList"]));
      setPendingUser(null);
      setStreamed("");
    },
    [conversationId, token, sendPlain, dispatch, notify],
  );

  return { send, sending: pendingUser !== null, pendingUser, streamed };
}
