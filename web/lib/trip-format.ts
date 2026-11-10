import type { Trip } from './types';

/**
 * A trip's dates for lists: "Mar 10 – 13", or "3 nights" when only the length is known,
 * or null when nothing is decided yet. `t` is the i18n function.
 */
export function tripDates(trip: Trip, lang: string, t: (key: string) => string): string | null {
  const { dates, nights } = trip.slots;
  if (dates) {
    const start = new Date(`${dates.start}T00:00:00`);
    const end = new Date(`${dates.end}T00:00:00`);
    if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime())) {
      return new Intl.DateTimeFormat(lang, { month: 'short', day: 'numeric' }).formatRange(
        start,
        end,
      );
    }
  }
  if (nights != null) {
    return nights === 0
      ? t('card.dates.dayTrip')
      : t('card.dates.nights').replace('{n}', String(nights));
  }
  return null;
}

/** The place a trip goes to, or the "untitled" text. */
export function tripPlace(trip: Trip, t: (key: string) => string): string {
  return trip.slots.dest?.label || t('trip.untitled');
}
