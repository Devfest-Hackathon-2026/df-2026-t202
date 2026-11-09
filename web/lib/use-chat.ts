'use client';

import { useState } from 'react';
import { post } from './api';
import type { MessageIn } from './types';

/** Posting to the chat and starting the plan. Shared by the photo screen and the map sheet. */
export function useChatActions(tripId: string | undefined) {
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState(false);

  async function call(path: string, body?: unknown) {
    if (!tripId) return;
    setSending(true);
    setFailed(false);
    try {
      await post(path, body);
    } catch {
      setFailed(true);
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
