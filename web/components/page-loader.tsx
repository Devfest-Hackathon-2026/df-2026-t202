'use client';

import { useT } from '@/lib/i18n';

/** A spinning ring. Inherits the text colour. */
export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <span
      className="spin-ring inline-block flex-none rounded-full border-2 border-current border-t-transparent"
      style={{ width: size, height: size }}
      aria-hidden="true"
    />
  );
}

/**
 * Full-screen loading state over the dusk photo: a small glass pill with a spinner,
 * so a page that is still loading looks like the app, not a blank page with a line of text.
 */
export function PageLoader({ label }: { label?: string }) {
  const t = useT();
  return (
    <main
      className="flex h-[100svh] items-center justify-center bg-[url('/dusk.webp')] bg-cover bg-[position:50%_45%]"
      role="status"
      aria-live="polite"
    >
      <span className="rise flex items-center gap-3 rounded-full border border-white/15 bg-stone-900/50 px-5 py-3 text-[14px] text-white shadow-[0_24px_60px_rgba(4,12,26,0.45)] backdrop-blur-2xl">
        <Spinner />
        {label ?? t('state.loading')}
      </span>
    </main>
  );
}
