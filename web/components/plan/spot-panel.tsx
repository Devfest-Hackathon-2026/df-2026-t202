'use client';

import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useT } from '@/lib/i18n';
import type { Day, Stop } from '@/lib/types';
import { mapsUrl } from './plan-panel';
import { PlacePhoto } from './place-photo';

export type StopRef = { day: number; index: number };

/** Every stop of the trip, in order. */
export function stopsOf(days: Day[]): StopRef[] {
  return days.flatMap((day) => day.stops.map((_, index) => ({ day: day.day, index })));
}

/**
 * S4: what the spot being looked at actually looks like — its Short, or its photo from
 * Google Maps when it has no video. It sits beside the itinerary rather than taking the screen,
 * so the plan stays visible. The official YouTube IFrame player only (API terms); it starts on
 * the tap that opened it, never on its own.
 */
export function SpotPanel({
  days,
  selected,
  onSelect,
  onClose,
}: {
  days: Day[];
  selected: StopRef;
  onSelect: (selected: StopRef) => void;
  onClose: () => void;
}) {
  const t = useT();
  const all = stopsOf(days);
  const position = all.findIndex((s) => s.day === selected.day && s.index === selected.index);
  const day = days.find((d) => d.day === selected.day);
  const stop: Stop | undefined = day?.stops[selected.index];
  const videoId = stop?.videoIds[0];

  if (!stop) return null;

  return (
    <section
      className="absolute inset-x-3 top-[68px] bottom-[calc(var(--height-sheet-peek)+0.75rem)] z-50 flex flex-col gap-2 rounded-2xl border border-white/15 bg-stone-900/50 bg-clip-padding p-3 shadow-[0_24px_60px_rgba(4,12,26,0.45)] backdrop-blur-2xl desk:inset-x-auto desk:top-[76px] desk:bottom-auto desk:right-5 desk:h-[min(620px,calc(100svh-5.5rem))] desk:w-[320px]"
      aria-label={stop.name}
    >
      <header className="flex items-start gap-2 text-white">
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-[14px] font-bold">{stop.name}</span>
          <span className="text-[11px] text-white/65">
            {t('plan.day').replace('{n}', String(selected.day))} · {stop.time}
          </span>
        </span>
        <button
          type="button"
          className="flex h-8 w-8 flex-none items-center justify-center rounded-full border-0 bg-white/15 text-white"
          aria-label={t('action.close')}
          onClick={onClose}
        >
          <X size={15} aria-hidden="true" />
        </button>
      </header>

      <div className="flex min-h-0 flex-1 justify-center">
        {videoId ? (
          <div
            className="relative h-full max-h-full overflow-hidden rounded-xl bg-black"
            style={{ aspectRatio: '9 / 16' }}
          >
            <iframe
              key={videoId}
              className="absolute inset-0 h-full w-full border-0"
              src={`https://www.youtube.com/embed/${videoId}?playsinline=1&rel=0&modestbranding=1&autoplay=1`}
              title={stop.name}
              allow="autoplay; accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
              allowFullScreen
            />
          </div>
        ) : (
          <PlacePhoto
            key={stop.id}
            placeId={stop.placeId}
            className="h-full w-full overflow-hidden rounded-xl bg-white/10"
          />
        )}
      </div>

      {stop.note && <p className="m-0 text-[12px] leading-[1.5] text-white/75">{stop.note}</p>}

      <nav className="flex items-center gap-2">
        <button
          type="button"
          className="flex h-10 w-10 flex-none items-center justify-center rounded-full border border-white/25 bg-white/10 text-white disabled:opacity-35"
          aria-label={t('action.previous')}
          disabled={position <= 0}
          onClick={() => onSelect(all[position - 1])}
        >
          <ChevronLeft size={18} aria-hidden="true" />
        </button>
        <a
          className="flex min-h-10 flex-1 items-center justify-center rounded-xl border border-white/20 bg-white/8 text-[12px] text-white/90 no-underline"
          href={mapsUrl(stop)}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t('action.openInMaps')}
        </a>
        <button
          type="button"
          className="flex h-10 w-10 flex-none items-center justify-center rounded-full border border-white/25 bg-white/10 text-white disabled:opacity-35"
          aria-label={t('action.next')}
          disabled={position < 0 || position >= all.length - 1}
          onClick={() => onSelect(all[position + 1])}
        >
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </nav>
    </section>
  );
}
