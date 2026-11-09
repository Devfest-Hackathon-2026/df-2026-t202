'use client';

import { Share2 } from 'lucide-react';
import { useT } from '@/lib/i18n';

/** The trip name inside the panel. Desktop only (the desktop mock); the phone uses TripTopBar. */
export function SheetHeader({
  name,
  sub,
  onShare,
}: {
  name: string;
  sub: string;
  onShare?: () => void;
}) {
  const t = useT();

  return (
    <header className="hidden flex-none items-center gap-3 bg-transparent px-5 pt-5 pb-4 desk:flex">
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-[18px] leading-snug font-semibold tracking-tight text-ink">
          {name}
        </span>
        <span className="mt-1 text-[13px] text-muted">{sub}</span>
      </span>
      {onShare && (
        <button
          type="button"
          className="bg-surface text-ink inline-flex min-h-11 flex-none items-center gap-2 rounded-lg border border-line px-3 text-[13px] font-semibold transition-colors hover:bg-fill-soft focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          onClick={onShare}
        >
          <Share2 size={15} aria-hidden="true" />
          {t('share.open')}
        </button>
      )}
    </header>
  );
}
