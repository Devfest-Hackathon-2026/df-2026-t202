'use client';

import { useCallback, useRef, useState, type PointerEvent, type ReactNode } from 'react';
import { useT } from '@/lib/i18n';

export type SheetStop = 'peek' | 'half' | 'full';

const ORDER: SheetStop[] = ['peek', 'half', 'full'];
/** Same proportions as the mock: 132 / 470 / 770 of an 844 px screen. */
const RATIO: Record<SheetStop, number> = { peek: 0.156, half: 0.557, full: 0.912 };
const HEIGHT: Record<SheetStop, string> = {
  peek: 'var(--height-sheet-peek)',
  half: 'var(--height-sheet-half)',
  full: 'var(--height-sheet-full)',
};

function nearestStop(height: number, viewport: number): SheetStop {
  let best: SheetStop = 'peek';
  let bestGap = Infinity;
  for (const stop of ORDER) {
    const gap = Math.abs(height - RATIO[stop] * viewport);
    if (gap < bestGap) {
      bestGap = gap;
      best = stop;
    }
  }
  return best;
}

/**
 * The assistant and the itinerary live in one panel (PLAN.md 10.1).
 * Phone: it comes up from the bottom — drag it, or tap the handle to cycle peek -> half -> full.
 * Desktop (>= 900 px): it is a fixed column down the left and the handle is hidden.
 */
export function BottomSheet({
  stop,
  onStopChange,
  children,
}: {
  stop: SheetStop;
  onStopChange: (stop: SheetStop) => void;
  children: ReactNode;
}) {
  const t = useT();
  const [dragHeight, setDragHeight] = useState<number | null>(null);
  const drag = useRef<{ startY: number; startHeight: number; viewport: number } | null>(null);
  // A pointer tap already cycles the sheet; without this the click that follows would cycle it twice.
  const handledByPointer = useRef(false);

  const cycle = useCallback(() => {
    onStopChange(ORDER[(ORDER.indexOf(stop) + 1) % ORDER.length]);
  }, [stop, onStopChange]);

  const onPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    handledByPointer.current = true;
    const viewport = event.currentTarget.ownerDocument.defaultView?.innerHeight ?? 844;
    drag.current = { startY: event.clientY, startHeight: RATIO[stop] * viewport, viewport };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    const state = drag.current;
    if (!state) return;
    const next = state.startHeight - (event.clientY - state.startY);
    setDragHeight(
      Math.min(RATIO.full * state.viewport, Math.max(RATIO.peek * state.viewport, next)),
    );
  };

  const onPointerUp = (event: PointerEvent<HTMLButtonElement>) => {
    const state = drag.current;
    drag.current = null;
    if (state) {
      // A tap (almost no movement) cycles; a drag snaps to the nearest stop.
      // dragHeight stays null on a tap, because no pointermove ever fired.
      if (Math.abs(event.clientY - state.startY) < 6) cycle();
      else if (dragHeight !== null) onStopChange(nearestStop(dragHeight, state.viewport));
    }
    setDragHeight(null);
  };

  return (
    <section
      className={[
        'sheet-in absolute inset-x-0 bottom-0 z-40 flex flex-col overflow-hidden rounded-t-2xl',
        'border border-white/15 bg-stone-900/50 bg-clip-padding shadow-[0_24px_60px_rgba(4,12,26,0.45)] backdrop-blur-2xl',
        dragHeight === null ? 'transition-[height] duration-350 ease-(--ease-sheet)' : '',
        'desk:inset-x-auto desk:top-4 desk:bottom-4 desk:left-4 desk:h-auto! desk:w-[440px] desk:rounded-2xl desk:transition-none',
      ].join(' ')}
      aria-label={t('sheet.label')}
      style={{ height: dragHeight !== null ? `${dragHeight}px` : HEIGHT[stop] }}
    >
      <button
        type="button"
        className="flex h-7 w-full flex-none touch-none items-center justify-center border-0 bg-transparent p-0 desk:hidden"
        aria-label={t(stop === 'full' ? 'sheet.collapse' : 'sheet.expand')}
        onClick={() => {
          // Keyboard (Enter/Space) only: a pointer tap is handled in onPointerUp.
          if (handledByPointer.current) handledByPointer.current = false;
          else cycle();
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      >
        <span className="bg-line h-[5px] w-11 rounded-full" />
      </button>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </section>
  );
}
