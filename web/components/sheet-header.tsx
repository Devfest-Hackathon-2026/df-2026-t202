'use client';

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
    <header className="hidden flex-none items-center gap-3 px-[18px] pt-[18px] pb-3.5 desk:flex">
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate text-[17px] font-bold text-white">{name}</span>
        <span className="truncate text-xs text-white/65">{sub}</span>
      </span>
      {onShare && (
        <button
          type="button"
          className="bg-accent text-on-accent h-10 flex-none rounded-[20px] border-0 px-4 text-sm font-bold"
          onClick={onShare}
        >
          {t('share.open')}
        </button>
      )}
    </header>
  );
}
