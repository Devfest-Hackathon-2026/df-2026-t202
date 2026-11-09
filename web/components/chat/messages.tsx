'use client';

import type { Message } from '@/lib/types';

/**
 * The chat transcript. `photo` is the start screen, over the dusk image (white text);
 * `sheet` is the panel over the map (ink text).
 */
export function Messages({
  messages,
  variant,
}: {
  messages: Message[];
  variant: 'photo' | 'sheet';
}) {
  const ai =
    variant === 'photo'
      ? 'max-w-[85%] self-start rounded-[18px_18px_18px_4px] border border-white/15 bg-stone-900/55 px-4 py-2.5 text-[15px] leading-[1.7] whitespace-pre-line text-white backdrop-blur-xl'
      : 'max-w-[85%] self-start rounded-[18px_18px_18px_4px] bg-white/12 px-3.5 py-2 text-[15px] leading-[1.65] whitespace-pre-line text-white';
  const me =
    variant === 'photo'
      ? 'text-ink max-w-[85%] self-end rounded-[18px_18px_4px_18px] border border-white/60 bg-white/55 px-3.5 py-2 text-[15px] leading-[1.6] whitespace-pre-line backdrop-blur-xl'
      : 'text-ink max-w-[85%] self-end rounded-[18px_18px_4px_18px] bg-white px-3.5 py-2 text-[15px] leading-[1.65] whitespace-pre-line';

  return (
    <>
      {messages.map((m) => (
        <p key={m.id} className={m.role === 'ai' ? ai : me}>
          {m.text}
        </p>
      ))}
    </>
  );
}
