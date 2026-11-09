'use client';

import { useState, type CSSProperties, type ReactNode } from 'react';
import { useT } from '@/lib/i18n';
import type { Message } from '@/lib/types';

/**
 * Entrance order for each message. On load (or refresh) the last few messages play back one
 * after another; anything that arrives later rises in straight away.
 */
export function useEnterOrder(messages: Message[]) {
  const [initial] = useState(() => {
    const ids = messages.map((m) => m.id);
    // Only the last 8 replay; older ones would sit off-screen anyway.
    const start = Math.max(0, ids.length - 8);
    return new Map(ids.map((id, i) => [id, Math.max(0, i - start)]));
  });
  return (id: string): CSSProperties => ({ '--i': initial.get(id) ?? 0 }) as CSSProperties;
}

/** True while the AI's reply is on its way: we are posting, or the last word is still ours. */
export function useAwaitingReply(messages: Message[], sending: boolean, failed: boolean) {
  const last = messages[messages.length - 1];
  return !failed && (sending || last?.role === 'user');
}

const AI = {
  photo:
    'max-w-[85%] self-start rounded-[18px_18px_18px_4px] border border-white/15 bg-stone-900/55 px-4 py-2.5 text-[15px] leading-[1.7] whitespace-pre-line text-white backdrop-blur-xl',
  sheet:
    'max-w-[88%] self-start rounded-[18px_18px_18px_4px] bg-fill-soft px-4 py-3 text-[15px] leading-[1.65] whitespace-pre-line text-ink',
};

const ME = {
  photo:
    'text-ink max-w-[85%] self-end rounded-[18px_18px_4px_18px] border border-white/60 bg-white/55 px-3.5 py-2 text-[15px] leading-[1.6] whitespace-pre-line backdrop-blur-xl',
  sheet:
    'bg-control text-on-control max-w-[80%] self-end rounded-[18px_18px_4px_18px] px-4 py-2.5 text-[15px] leading-[1.6] whitespace-pre-line',
};

/**
 * The chat transcript. `photo` is the start screen, over the dusk image (white text);
 * `sheet` is the panel over the map.
 */
export function Messages({
  messages,
  variant,
}: {
  messages: Message[];
  variant: 'photo' | 'sheet';
}) {
  const order = useEnterOrder(messages);

  return (
    <>
      {messages.map((m) => (
        <p
          key={m.id}
          className={`${m.role === 'ai' ? AI[variant] : ME[variant]} rise`}
          style={order(m.id)}
        >
          {m.text}
        </p>
      ))}
    </>
  );
}

/** Three dots in an AI bubble while the reply is being written. */
export function TypingBubble({ variant }: { variant: 'photo' | 'sheet' }) {
  const t = useT();
  return (
    <p
      className={`${AI[variant]} rise flex items-center gap-1 py-3.5`}
      role="status"
      aria-label={t('chat.typing')}
    >
      <span className="typing-dot" />
      <span className="typing-dot" />
      <span className="typing-dot" />
    </p>
  );
}

/**
 * Holds the current question card. A new `key` per card makes it rise in; `leaving` (the answer
 * is being sent) fades it down and folds its height away while the typing dots take over.
 * On first load the card waits for the replayed messages (`delay` steps) before it rises.
 */
export function CardShell({
  leaving,
  delay,
  children,
}: {
  leaving: boolean;
  delay: number;
  children: ReactNode;
}) {
  return (
    <div
      className={`card-shell ${leaving ? 'leaving' : ''}`}
      style={{ '--i': delay } as CSSProperties}
      aria-hidden={leaving || undefined}
    >
      <div>{children}</div>
    </div>
  );
}

/** How many entrance steps the first card waits, so it comes in after the replayed messages. */
export function useFirstCardDelay(cardKey: string, messageCount: number) {
  const [first] = useState(() => ({ key: cardKey, delay: Math.min(messageCount, 8) }));
  return cardKey === first.key ? first.delay : 0;
}
