'use client';

import { ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useT } from '@/lib/i18n';
import type { Day, Stop } from '@/lib/types';
import { mapsUrl } from './plan-panel';

export type ShortRef = { day: number; index: number };

/** Every stop that has a video, in trip order. */
export function shortsOf(days: Day[]): ShortRef[] {
  return days.flatMap((day) =>
    day.stops.flatMap((stop, index) => (stop.videoIds.length > 0 ? [{ day: day.day, index }] : [])),
  );
}

/**
 * S4: the Short for the stop being looked at. It sits beside the itinerary rather than taking
 * the screen, so the plan stays visible while the video plays. The official YouTube IFrame
 * player only (API terms); it starts on the tap that opened it, never on its own.
 */
export function VideoPanel({
  days,
  shorts,
  position,
  onPosition,
  onClose,
}: {
  days: Day[];
  shorts: ShortRef[];
  position: number;
  onPosition: (position: number) => void;
  onClose: () => void;
}) {
  const t = useT();
  const current = shorts[position];
  const day = days.find((d) => d.day === current?.day);
  const stop: Stop | undefined = day?.stops[current?.index ?? -1];
  const videoId = stop?.videoIds[0];

  if (!stop) return null;

  return (
    <section
      className="border border-white/15 bg-stone-900/50 bg-clip-padding shadow-[0_24px_60px_rgba(4,12,26,0.45)] backdrop-blur-2xl absolute top-[68px] right-3 z-50 flex h-[min(620px,calc(100svh-5.5rem))] w-[min(320px,calc(100vw-1.5rem))] flex-col gap-2 rounded-2xl p-3 desk:top-[76px] desk:right-5 desk:w-[320px]"
      aria-label={t('shorts.title')}
    >
      <header className="flex items-start gap-2 text-white">
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-[14px] font-bold">{stop.name}</span>
          <span className="text-[11px] text-white/65">
            {t('plan.day').replace('{n}', String(current.day))} · {stop.time}
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

      {videoId ? (
        <div className="flex min-h-0 flex-1 justify-center">
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
        </div>
      ) : (
        <a
          className="flex min-h-11 items-center justify-center rounded-xl border border-white/25 bg-white/10 text-[13px] text-white no-underline"
          href={`https://www.youtube.com/results?search_query=${encodeURIComponent(stop.nameLocal || stop.name)}`}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t('shorts.searchOnYouTube')}
        </a>
      )}

      <nav className="flex items-center gap-2">
        <button
          type="button"
          className="flex h-10 w-10 flex-none items-center justify-center rounded-full border border-white/25 bg-white/10 text-white disabled:opacity-35"
          aria-label={t('action.previous')}
          disabled={position === 0}
          onClick={() => onPosition(position - 1)}
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
          disabled={position >= shorts.length - 1}
          onClick={() => onPosition(position + 1)}
        >
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </nav>
    </section>
  );
}
