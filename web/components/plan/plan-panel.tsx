'use client';

import { Check, Film, Play, Route, Search, type LucideIcon } from 'lucide-react';
import { LanguageNote } from '@/components/language-note';
import { PlacePhoto } from './place-photo';
import { DayTabs } from '@/components/day-tabs';
import { dayColor } from '@/components/map-canvas';
import { useEffect, useRef } from 'react';
import { useT } from '@/lib/i18n';
import type { Cost, Day, Plan, Progress, Stop, Trip } from '@/lib/types';

const BODY =
  'flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] desk:px-[18px]';
const STATE = 'py-2 text-[13px] text-white/70';
const SECTION =
  'flex flex-col gap-2 rounded-[var(--radius-card)] border border-white/15 bg-white/8 p-3 text-white';
const BADGE = 'self-start rounded-full bg-white/15 px-2 py-0.5 text-[11px] text-white/90';
const SKELETON = 'h-14 animate-pulse rounded-xl bg-white/10';

export function mapsUrl(stop: Stop): string {
  if (stop.placeId) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(stop.name)}&query_place_id=${stop.placeId}`;
  }
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(stop.nameLocal || stop.name)}`;
}

function money(currency: string, amount: number) {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatMinutes(minutes: number, t: (key: string) => string): string {
  if (minutes < 60) return t('time.minutes').replace('{m}', String(minutes));
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m === 0
    ? t('time.hours').replace('{h}', String(h))
    : t('time.hoursMinutes').replace('{h}', String(h)).replace('{m}', String(m));
}

const PROGRESS_STEPS: Progress[] = ['spots', 'routes', 'videos'];

const PROGRESS_ICONS: Record<Progress, LucideIcon> = {
  spots: Search,
  routes: Route,
  videos: Film,
  done: Check,
};

/** The pipeline's real stages (trips.progress), ticked off as the server reports them. */
export function PlanProgress({ progress }: { progress: Progress }) {
  const t = useT();
  const current = PROGRESS_STEPS.indexOf(progress);

  return (
    <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
      {PROGRESS_STEPS.map((step, i) => {
        const done = progress === 'done' || (current >= 0 && i < current);
        const active = i === current;
        const Icon = PROGRESS_ICONS[step];
        return (
          <li
            key={step}
            className={[
              'flex items-center gap-3 text-[14px]',
              done ? 'text-white/60' : active ? 'text-white' : 'text-white/35',
            ].join(' ')}
          >
            <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-white/12">
              {done ? (
                <Check size={16} strokeWidth={2.2} aria-hidden="true" />
              ) : (
                <Icon
                  size={16}
                  strokeWidth={1.8}
                  className={active ? 'animate-pulse' : ''}
                  aria-hidden="true"
                />
              )}
            </span>
            {t(`plan.progress.${step}`)}
          </li>
        );
      })}
    </ul>
  );
}

/** S3: the itinerary. The map behind shows the selected day (PLAN.md 10.1). */
export function PlanPanel({
  trip,
  plan,
  loading,
  error,
  activeDay,
  onDayChange,
  onSelectStop,
  onOpenShorts,
  onShare,
}: {
  trip: Trip | null;
  plan: Plan | null;
  loading: boolean;
  error: Error | null;
  activeDay: number | null;
  onDayChange: (day: number | null) => void;
  onSelectStop: (day: number, index: number) => void;
  onOpenShorts: (day: number, index: number) => void;
  onShare?: () => void;
}) {
  const t = useT();
  const dayRefs = useRef<Record<number, HTMLElement | null>>({});

  // Picking a day drives the map; bring that day's part of the itinerary along with it.
  useEffect(() => {
    if (activeDay == null) return;
    dayRefs.current[activeDay]?.scrollIntoView({ block: 'start', behavior: 'smooth' });
  }, [activeDay]);

  if (trip?.status === 'planning') {
    return (
      <div className={BODY}>
        <PlanProgress progress={trip.progress ?? 'spots'} />
        <div className={SKELETON} />
        <div className={SKELETON} />
        <div className={SKELETON} />
      </div>
    );
  }
  if (loading) return <p className={`${BODY} ${STATE}`}>{t('state.loading')}</p>;
  if (error) return <p className={`${BODY} ${STATE}`}>{t('state.error')}</p>;
  if (!plan) return <p className={`${BODY} ${STATE}`}>{t('plan.none')}</p>;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <DayTabs days={plan.days} activeDay={activeDay} onDayChange={onDayChange} variant="inline" />

      <div className={BODY}>
        {trip && <LanguageNote tripLanguage={trip.language} />}

        <div>
          <h2 className="m-0 text-[17px] text-white">{plan.title}</h2>
          {plan.subtitle && <p className="m-0 text-[13px] text-white/70">{plan.subtitle}</p>}
        </div>

        {plan.days.map((day) => (
          <DaySection
            key={day.day}
            day={day}
            activeDay={activeDay}
            onSelectStop={onSelectStop}
            onOpenShorts={onOpenShorts}
            sectionRef={(el) => {
              dayRefs.current[day.day] = el;
            }}
          />
        ))}

        {plan.cost && <CostSection cost={plan.cost} currency={plan.currency} />}

        {plan.checks.length > 0 && (
          <section className={SECTION}>
            <h3 className="text-[13px] font-semibold text-white">
              {t('plan.checks')} <span className={BADGE}>{t('plan.badge.pleaseCheck')}</span>
            </h3>
            <ul className="m-0 list-disc pl-[18px] text-[13px] leading-[1.7] text-white/85">
              {plan.checks.map((check) => (
                <li key={check}>{check}</li>
              ))}
            </ul>
          </section>
        )}

        {onShare && (
          <div className="flex gap-2">
            <button
              type="button"
              className="flex min-h-11 flex-1 items-center justify-center rounded-xl border border-white/20 bg-white/10 text-[13px] text-white no-underline"
              onClick={onShare}
            >
              {t('share.open')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function DaySection({
  day,
  activeDay,
  onSelectStop,
  onOpenShorts,
  sectionRef,
}: {
  day: Day;
  activeDay: number | null;
  onSelectStop: (day: number, index: number) => void;
  onOpenShorts: (day: number, index: number) => void;
  sectionRef: (el: HTMLElement | null) => void;
}) {
  const t = useT();
  const color = dayColor(day.day);
  const moving = day.stops.reduce((total, stop) => total + (stop.leg?.minutes ?? 0), 0);

  const dimmed = activeDay != null && activeDay !== day.day;

  return (
    <section
      ref={sectionRef}
      className={`scroll-mt-2 transition-opacity ${dimmed ? 'opacity-45' : 'opacity-100'}`}
    >
      <header className="flex flex-col gap-0.5">
        <span className="text-[15px] font-semibold text-white">
          {t('plan.day').replace('{n}', String(day.day))}
          {day.date ? ` · ${day.date}` : ''}
          {day.theme ? ` · ${day.theme}` : ''}
        </span>
        <span className="text-xs text-white/65">
          {t('plan.stats')
            .replace('{stops}', String(day.stops.length))
            .replace('{minutes}', formatMinutes(moving, t))}
          {day.stay ? ` · ${day.stay}` : ''}
        </span>
      </header>

      <div className="flex flex-col">
        {day.stops.map((stop, index) => (
          <div key={stop.id}>
            <div className="flex gap-3 py-2.5">
              <span className="w-12 flex-none text-[13px] font-semibold tabular-nums text-white/85">
                {stop.time}
              </span>
              <button
                type="button"
                className="flex min-w-0 flex-1 border-0 bg-transparent p-0 text-left font-inherit text-inherit"
                onClick={() => onSelectStop(day.day, index)}
              >
                <span
                  className="text-on-accent mt-px flex h-[22px] w-[22px] flex-none items-center justify-center rounded-full text-[11px] font-bold"
                  style={{ background: color }}
                >
                  {index + 1}
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-1 text-left">
                  <span className="text-[15px] font-semibold text-white">{stop.name}</span>
                  {stop.note && (
                    <span className="text-xs leading-[1.5] whitespace-pre-line text-white/70">
                      {stop.note}
                    </span>
                  )}
                  {stop.warn && <span className={BADGE}>{stop.warn}</span>}
                </span>
              </button>
              {stop.videoIds.length > 0 ? (
                <button
                  type="button"
                  className="relative flex h-16 w-12 flex-none items-center justify-center overflow-hidden rounded-xl border border-white/20 bg-white/10 text-white"
                  aria-label={t('shorts.play').replace('{name}', stop.name)}
                  onClick={() => onOpenShorts(day.day, index)}
                >
                  {/* The video's own cover, so the row shows what it is before it is opened. */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={`https://i.ytimg.com/vi/${stop.videoIds[0]}/mqdefault.jpg`}
                    alt=""
                    loading="lazy"
                    className="absolute inset-0 h-full w-full object-cover"
                  />
                  <span className="relative flex h-7 w-7 items-center justify-center rounded-full bg-black/55">
                    <Play size={14} fill="currentColor" aria-hidden="true" />
                  </span>
                </button>
              ) : (
                // No Short for this spot: show the place's own photo from Google Maps instead.
                <PlacePhoto
                  placeId={stop.placeId}
                  className="h-16 w-12 flex-none overflow-hidden rounded-xl border border-white/20 bg-white/10"
                />
              )}
            </div>
            {stop.leg && (
              <p className="flex items-center gap-2 py-1 pl-[60px] text-xs text-white/60">
                {t(`leg.${stop.leg.mode}`)} · {formatMinutes(stop.leg.minutes, t)}
                {stop.leg.estimate && <span className={BADGE}>{t('plan.badge.pleaseCheck')}</span>}
              </p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function CostSection({ cost, currency }: { cost: Cost; currency: string }) {
  const t = useT();
  return (
    <section className={SECTION}>
      <h3 className="text-[13px] font-semibold text-white">
        {t(`cost.${cost.basis}`)} <span className={BADGE}>{t('plan.badge.estimate')}</span>
      </h3>
      <p className="text-[15px] font-bold text-white">
        {money(currency, cost.min)} – {money(currency, cost.max)}
      </p>
      {cost.items.map((item) => (
        <p key={item.label} className="flex justify-between gap-3 text-[13px] text-white/80">
          <span>{item.label}</span>
          <span>
            {money(currency, item.min)} – {money(currency, item.max)}
          </span>
        </p>
      ))}
    </section>
  );
}
