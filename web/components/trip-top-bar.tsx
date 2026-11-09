'use client';

import { Share2 } from 'lucide-react';
import { useT } from '@/lib/i18n';

/**
 * Frosted bar over the map: the trip's name, and the share button (PLAN.md 10.1 S5).
 * Phone only — on a desktop the name moves into the panel header (SheetHeader).
 */
export function TripTopBar({
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
    <div className="absolute top-3 right-16 left-3 z-30 flex items-center gap-2 desk:hidden">
      <div className="frost flex h-12 min-w-0 flex-1 items-center gap-2.5 rounded-3xl px-4">
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-sm font-bold">{name}</span>
          <span className="text-muted truncate text-[11px]">{sub}</span>
        </span>
      </div>
      {onShare && (
        <button
          type="button"
          className="frost flex h-12 w-12 flex-none items-center justify-center rounded-full p-0"
          aria-label={t('share.open')}
          onClick={onShare}
        >
          <Share2 size={18} strokeWidth={2} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
