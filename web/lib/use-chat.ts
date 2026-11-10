'use client';

import { useState } from 'react';
import { errorKey, post } from './api';
import type { MessageIn } from './types';

/** Posting to the chat and starting the plan. Shared by the photo screen and the map sheet. */
export function useChatActions(tripId: string | undefined) {
  const [sending, setSending] = useState(false);
  // The i18n key of the last error ("error.too_fast", "state.sendFailed"), or null.
  const [failed, setFailed] = useState<string | null>(null);

  async function call(path: string, body?: unknown) {
    if (!tripId) return;
    setSending(true);
    setFailed(null);
    try {
      await post(path, body);
    } catch (e) {
      setFailed(errorKey(e));
    } finally {
      setSending(false);
    }
  }

  return {
    sending,
    failed,
    send: (body: MessageIn) => call(`/trips/${tripId}/messages`, body),
    generate: () => call(`/trips/${tripId}/plan`),
  };
}
