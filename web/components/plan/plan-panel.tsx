'use client';

import {
  Car,
  Check,
  CircleAlert,
  Film,
  Footprints,
  Plane,
  Play,
  Route,
  Search,
  Share,
  Ship,
  TrainFront,
  type LucideIcon,
} from 'lucide-react';
import { LanguageNote } from '@/components/language-note';
import { DayTabs } from '@/components/day-tabs';
import { dayColor } from '@/components/map-canvas';
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { useLanguage, useT } from '@/lib/i18n';
import type { Cost, Day, Leg, LegMode, Plan, Progress, Stop, Trip } from '@/lib/types';

const BODY =
  'flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto overscroll-contain bg-transparent px-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))] desk:px-5';
const STATE = 'py-6 text-[15px] text-muted-strong';
const SECTION =
  'flex flex-col gap-3 rounded-xl border border-line-soft bg-fill-soft/50 p-4 text-ink';
const EYEBROW =
  'm-0 flex flex-wrap items-center justify-between gap-2 text-[15px] font-semibold text-ink';
const BADGE = 'self-start rounded-md bg-fill px-2 py-1 text-xs font-medium text-muted-strong';
const WARN =
  'self-start rounded-md bg-warning-surface px-2 py-1 text-xs font-semibold text-warning-ink';
const SKELETON = 'h-14 animate-pulse rounded-xl bg-fill';

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
    currencyDisplay: 'narrowSymbol', // "¥", not "JP¥"
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

/** "Public transport · Kamome Shinkansen · about 1 h 30 min": how you travel (always, so a line name never hides
 *  whether you walk or ride, D9), what to ride when known, then the time; "about" when estimated. */
export function legText(leg: Leg, t: (key: string) => string): string {
  const time = formatMinutes(leg.minutes, t);
  const parts = [
    t(`leg.${leg.mode}`),
    leg.line,
    leg.estimate ? t('time.about').replace('{t}', time) : time,
  ];
  return parts.filter(Boolean).join(' · ');
}

const PROGRESS_STEPS: Progress[] = ['spots', 'routes', 'videos'];

const PROGRESS_ICONS: Record<Progress, LucideIcon> = {
  spots: Search,
  routes: Route,
  videos: Film,
  done: Check,
};

const PROGRESS_HINTS: Record<Progress, string> = {
  spots: 'plan.progressHint.spots',
  routes: 'plan.progressHint.routes',
  videos: 'plan.progressHint.videos',
  done: 'plan.progress.done',
};

// Typical seconds per stage, from the API's plan_done logs (the Gemini draft dominates "spots").
const STEP_SECONDS: Record<Progress, number> = { spots: 35, routes: 8, videos: 3, done: 0.6 };

/**
 * The pipeline's real stages (trips.progress), ticked off as the server reports them.
 * The current one spins, finished ones turn green. The bar eases towards 90% of the current stage over its typical
 * time, so a long Gemini draft still shows movement, but it never passes a stage the server hasn't reached.
 */
export function PlanProgress({ progress }: { progress: Progress }) {
  const t = useT();
  const current = progress === 'done' ? PROGRESS_STEPS.length : PROGRESS_STEPS.indexOf(progress);
  const step = Math.max(current, 0);
  const shown = Math.min(step + 1, PROGRESS_STEPS.length);
  const target = progress === 'done' ? 1 : (step + 0.9) / PROGRESS_STEPS.length;
  // Start from the stage's beginning on mount, then animate to the target on the next frame.
  const [started, setStarted] = useState(false);
  useEffect(() => {
    const id = requestAnimationFrame(() => setStarted(true));
    return () => cancelAnimationFrame(id);
  }, []);
  const fraction = started ? target : step / PROGRESS_STEPS.length;

  return (
    <div className="flex flex-col gap-3" role="status" aria-live="polite">
      <div className="flex items-center justify-between text-[12px] text-white/70">
        <span>
          {t('plan.building')}
          {progress !== 'done' && <span className="text-white/45"> · {t('plan.eta')}</span>}
        </span>
        <span className="tabular-nums">
          {t('plan.progressCount')
            .replace('{n}', String(shown))
            .replace('{total}', String(PROGRESS_STEPS.length))}
        </span>
      </div>
      <div className="h-[3px] overflow-hidden rounded-full bg-white/12">
        <div
          className="h-full origin-left rounded-full bg-white transition-transform motion-reduce:transition-none"
          style={{
            transform: `scaleX(${fraction})`,
            transitionDuration: `${started ? STEP_SECONDS[progress] : 0}s`,
            transitionTimingFunction: 'cubic-bezier(0.2, 0.6, 0.35, 1)', // gentle: keeps moving all stage long
          }}
        />
      </div>
      <ul className="m-0 flex list-none flex-col p-0">
        {PROGRESS_STEPS.map((step, i) => {
          const done = progress === 'done' || (current >= 0 && i < current);
          const active = i === current;
          const Icon = PROGRESS_ICONS[step];
          return (
            <li
              key={step}
              className={[
                'relative flex items-center gap-3 py-1.5 text-[14px] transition-colors duration-300',
                done ? 'text-white/70' : active ? 'text-white' : 'text-white/35',
              ].join(' ')}
            >
              {/* The connector to the next step turns green once this one is done. */}
              {i < PROGRESS_STEPS.length - 1 && (
                <span
                  className={`absolute top-[38px] left-[15px] h-3 w-0.5 rounded-full transition-colors duration-300 ${done ? 'bg-ok' : 'bg-white/15'}`}
                  aria-hidden="true"
                />
              )}
              <span
                className={`relative flex h-8 w-8 flex-none items-center justify-center rounded-full transition-colors duration-300 ${done ? 'bg-ok text-white' : 'bg-white/12'}`}
              >
                {done ? (
                  <Check
                    key="done"
                    size={16}
                    strokeWidth={2.4}
                    className="pop"
                    aria-hidden="true"
                  />
                ) : (
                  <Icon size={16} strokeWidth={1.8} aria-hidden="true" />
                )}
                {active && (
                  <span
                    className="spin-ring absolute -inset-[3px] rounded-full border-2 border-transparent border-t-white"
                    aria-hidden="true"
                  />
                )}
              </span>
              <span className="flex flex-col">
                {t(`plan.progress.${step}`)}
                {!done && (
                  <span className="text-[11.5px] text-white/55">{t(PROGRESS_HINTS[step])}</span>
                )}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
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
  selected,
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
  /** The stop the map is showing; its row gets a soft highlight. */
  selected?: { day: number; index: number } | null;
}) {
  const t = useT();
  const dayRefs = useRef<Record<number, HTMLElement | null>>({});

  // Picking a day drives the map; bring that day's part of the itinerary along with it.
  useEffect(() => {
    if (activeDay == null) return;
    dayRefs.current[activeDay]?.scrollIntoView({
      block: 'start',
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant'
        : 'smooth',
    });
  }, [activeDay]);

  if (trip?.status === 'planning') {
    return (
      <div className={BODY}>
        <div className="mt-5 rounded-xl bg-control p-4">
          <PlanProgress progress={trip.progress ?? 'spots'} />
        </div>
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
    <div className="flex min-h-0 flex-1 flex-col bg-transparent text-ink">
      <DayTabs days={plan.days} activeDay={activeDay} onDayChange={onDayChange} variant="inline" />

      <div className={BODY}>
        {trip && <LanguageNote tripLanguage={trip.language} tone="light" />}

        {plan.subtitle && (
          <p className="m-0 pt-5 text-[14px] leading-relaxed text-muted-strong">{plan.subtitle}</p>
        )}

        {plan.days.map((day, i) => (
          <DaySection
            key={day.day}
            order={i}
            day={day}
            selectedIndex={selected?.day === day.day ? selected.index : null}
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
            <h3 className={EYEBROW}>
              {t('plan.checks')}
              <span className={WARN}>{t('plan.badge.pleaseCheck')}</span>
            </h3>
            <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
              {plan.checks.map((check) => (
                <li
                  key={check}
                  className="flex gap-2.5 text-[14px] leading-[1.5] text-muted-strong"
                >
                  <CircleAlert
                    size={16}
                    strokeWidth={2}
                    className="mt-0.5 flex-none text-muted"
                    aria-hidden="true"
                  />
                  <span>{check}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {onShare && (
          <div className="flex flex-col items-center gap-2 pt-1">
            <button
              type="button"
              className="bg-accent text-on-accent flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border-0 text-[15px] font-semibold transition-[filter] hover:brightness-110 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink"
              onClick={onShare}
            >
              <Share size={17} strokeWidth={2.2} aria-hidden="true" />
              {t('share.open')}
            </button>
            <p className="m-0 text-center text-[12px] text-muted">{t('share.hint')}</p>
          </div>
        )}
      </div>
    </div>
  );
}

const LEG_ICONS: Record<LegMode, LucideIcon> = {
  DRIVE: Car,
  TRANSIT: TrainFront,
  WALK: Footprints,
  FLIGHT: Plane,
  FERRY: Ship,
};

/** "2027-03-10" -> "Wed, Mar 10" in the UI language (parsed as a local date, not UTC). */
function dayDate(iso: string, lang: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat(lang, { weekday: 'short', month: 'short', day: 'numeric' }).format(
    new Date(y, m - 1, d),
  );
}

function DaySection({
  day,
  order,
  selectedIndex,
  onSelectStop,
  onOpenShorts,
  sectionRef,
}: {
  day: Day;
  order: number;
  selectedIndex: number | null;
  onSelectStop: (day: number, index: number) => void;
  onOpenShorts: (day: number, index: number) => void;
  sectionRef: (el: HTMLElement | null) => void;
}) {
  const t = useT();
  const lang = useLanguage();
  const color = dayColor(day.day);

  return (
    <section
      ref={sectionRef}
      className={`scroll-mt-0 ${order > 0 ? 'border-t border-line-soft' : ''}`}
      style={{ '--itinerary-day': color } as CSSProperties}
    >
      <header className="sticky top-0 z-10 -mx-4 flex flex-col gap-2 border-b border-line-soft bg-surface/80 px-4 py-4 backdrop-blur-xl desk:-mx-5 desk:px-5">
        <span className="flex items-center gap-2 text-[13px] font-semibold">
          <span className="h-2 w-2 rounded-full" style={{ background: color }} aria-hidden="true" />
          <span className="text-ink">{t('plan.day').replace('{n}', String(day.day))}</span>
          {day.date && (
            <span className="font-semibold tracking-normal text-muted-strong normal-case">
              · {dayDate(day.date, lang)}
            </span>
          )}
        </span>
        {day.theme && (
          <h3 className="m-0 text-[18px] leading-snug font-semibold text-ink">{day.theme}</h3>
        )}
      </header>

      <div className="mt-3 flex flex-col">
        {day.stops.map((stop, index) => {
          const LegIcon = stop.leg ? LEG_ICONS[stop.leg.mode] : null;
          const last = index === day.stops.length - 1;
          return (
            <div key={stop.id} className="relative">
              {/* A quiet connector keeps stop order visible without competing with the text. */}
              {!last && (
                <span
                  className="absolute top-10 -bottom-5 left-[13px] w-px bg-line"
                  aria-hidden="true"
                />
              )}
              <div className="flex gap-2 py-2">
                <span
                  className="text-on-accent relative mt-3 flex h-7 w-7 flex-none items-center justify-center rounded-full text-xs font-semibold"
                  style={{ background: color }}
                >
                  {index + 1}
                </span>
                {/* Only the selected stop gets a day-colored highlight. */}
                <div
                  className={`flex min-w-0 flex-1 gap-3 rounded-xl p-3 transition-colors duration-200 ${
                    selectedIndex === index
                      ? 'bg-[color-mix(in_srgb,var(--itinerary-day)_9%,var(--color-surface))] ring-1 ring-inset ring-[color-mix(in_srgb,var(--itinerary-day)_25%,var(--color-surface))]'
                      : 'hover:bg-fill-soft'
                  }`}
                >
                  <button
                    type="button"
                    className="flex min-w-0 flex-1 flex-col gap-1 border-0 bg-transparent p-0 text-left font-inherit text-inherit min-h-11 rounded-md focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink"
                    aria-current={selectedIndex === index ? 'true' : undefined}
                    onClick={() => onSelectStop(day.day, index)}
                  >
                    <span className="text-[13px] font-semibold text-muted-strong tabular-nums">
                      {stop.time}
                    </span>
                    <span className="text-[17px] leading-snug font-semibold text-ink">
                      {stop.name}
                    </span>
                    {stop.nameLocal && stop.nameLocal !== stop.name && (
                      <span className="text-[13px] leading-snug text-muted">{stop.nameLocal}</span>
                    )}
                    {stop.note && (
                      <span className="mt-1 text-[15px] leading-[1.6] whitespace-pre-line text-muted-strong">
                        {stop.note}
                      </span>
                    )}
                    {stop.warn && <span className={`${WARN} mt-1.5`}>{stop.warn}</span>}
                  </button>
                  {/* A thumbnail only when there is a Short to play: no empty boxes. */}
                  {stop.videoIds.length > 0 ? (
                    <button
                      type="button"
                      className="relative flex h-16 w-12 flex-none items-center justify-center overflow-hidden rounded-lg bg-fill text-on-accent focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink"
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
                  ) : null}
                </div>
              </div>
              {stop.leg && LegIcon && (
                <p className="my-1 mr-3 ml-12 flex flex-wrap items-center gap-2 rounded-lg bg-fill-soft px-3 py-2.5 text-[13px] leading-relaxed">
                  <span className="inline-flex items-start gap-2 text-muted-strong">
                    <LegIcon size={15} className="mt-0.5 shrink-0" aria-hidden="true" />
                    {legText(stop.leg, t)}
                  </span>
                  {stop.leg.estimate && <span className={WARN}>{t('plan.badge.pleaseCheck')}</span>}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

/** "¥14K" / "1.4万円": short enough to sit next to a bar. */
function compactMoney(currency: string, amount: number, lang: string) {
  return new Intl.NumberFormat(lang, {
    style: 'currency',
    currency,
    notation: 'compact',
    currencyDisplay: 'narrowSymbol',
    maximumFractionDigits: 1,
  }).format(amount);
}

// Neutral shades distinguish costs without assigning them the route colors.
const COST_COLORS = [95, 68, 46, 30, 20, 14].map(
  (opacity) => `color-mix(in srgb, var(--color-ink) ${opacity}%, transparent)`,
);

/**
 * The total first and biggest, then where the money goes: one bar split by each item's share
 * (the middle of its range), and a row per item with the matching color dot, range and share.
 */
function CostSection({ cost, currency }: { cost: Cost; currency: string }) {
  const t = useT();
  const lang = useLanguage();
  const mids = cost.items.map((item) => (item.min + item.max) / 2);
  const sum = Math.max(
    1,
    mids.reduce((a, b) => a + b, 0),
  );
  const share = (i: number) => Math.round((mids[i] / sum) * 100);
  const color = (i: number) => COST_COLORS[i % COST_COLORS.length];

  return (
    <section className={SECTION}>
      <h3 className={EYEBROW}>
        {t(`cost.${cost.basis}`)} <span className={BADGE}>{t('plan.badge.estimate')}</span>
      </h3>
      <p className="m-0 text-[26px] leading-tight font-extrabold tracking-tight text-ink tabular-nums">
        {money(currency, cost.min)} – {money(currency, cost.max)}
      </p>

      {cost.items.length > 0 && (
        <>
          {/* Each segment shows its share of the estimated cost. */}
          <div className="mt-1 flex h-2.5 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
            {cost.items.map((item, i) => (
              <span
                key={item.label}
                className="h-full first:rounded-l-full last:rounded-r-full"
                style={
                  {
                    width: `${(mids[i] / sum) * 100}%`,
                    background: color(i),
                    '--i': i,
                  } as CSSProperties
                }
              />
            ))}
          </div>

          <ul className="m-0 flex list-none flex-col p-0">
            {cost.items.map((item, i) => (
              <li
                key={item.label}
                className="flex items-start gap-3 border-t border-line-soft py-2.5 first:border-t-0 first:pt-0.5"
              >
                <span
                  className="mt-1.5 h-2.5 w-2.5 flex-none rounded-full"
                  style={{ background: color(i) }}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1 text-[14px] leading-snug text-muted-strong">
                  {item.label}
                </span>
                <span className="flex flex-none flex-col items-end">
                  <span className="text-[14px] font-semibold text-ink tabular-nums">
                    {compactMoney(currency, item.min, lang)} –{' '}
                    {compactMoney(currency, item.max, lang)}
                  </span>
                  <span className="text-[12px] text-muted tabular-nums">{share(i)}%</span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
