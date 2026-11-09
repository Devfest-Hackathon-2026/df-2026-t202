'use client';

import { dayColor } from '@/components/map-canvas';
import { useT } from '@/lib/i18n';
import type { Day } from '@/lib/types';

/**
 * Day switcher. On a phone it sits at the top of the itinerary; on a desktop it floats
 * over the map, top right (the desktop mock).
 */
export function DayTabs({
  days,
  activeDay,
  onDayChange,
  variant,
}: {
  days: Day[];
  activeDay: number | null;
  onDayChange: (day: number | null) => void;
  variant: 'inline' | 'floating';
}) {
  const t = useT();
  if (days.length === 0) return null;

  const wrapper =
    variant === 'floating'
      ? 'frost hidden gap-1.5 rounded-[18px] px-2.5 py-1.5 desk:flex'
      : 'flex flex-none gap-1.5 overflow-x-auto border-b border-line-soft bg-surface/90 backdrop-blur-xl px-4 py-3 desk:hidden';

  const tab =
    'flex min-h-11 flex-none items-center gap-1.5 whitespace-nowrap rounded-full px-3.5 text-[13px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink';
  const off =
    variant === 'inline'
      ? 'border border-line bg-surface text-muted-strong'
      : 'border-line text-muted-strong bg-surface border';
  const on = 'text-on-accent border border-transparent font-semibold';

  return (
    <div className={`${wrapper} overflow-x-auto`} role="tablist" aria-label={t('plan.days')}>
      <button
        type="button"
        role="tab"
        aria-selected={activeDay == null}
        className={`${tab} ${activeDay == null ? on : off}`}
        style={activeDay == null ? { background: 'var(--color-control)' } : undefined}
        onClick={() => onDayChange(null)}
      >
        {t('plan.allDays')}
      </button>
      {days.map((day) => (
        <button
          key={day.day}
          type="button"
          role="tab"
          aria-selected={activeDay === day.day}
          className={`${tab} ${activeDay === day.day ? on : off}`}
          style={activeDay === day.day ? { background: dayColor(day.day) } : undefined}
          onClick={() => onDayChange(day.day)}
        >
          {variant === 'floating' && activeDay !== day.day && (
            <span className="h-2 w-2 rounded-full" style={{ background: dayColor(day.day) }} />
          )}
          {t('plan.day').replace('{n}', String(day.day))}
        </button>
      ))}
    </div>
  );
}
