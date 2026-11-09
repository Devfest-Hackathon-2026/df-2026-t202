'use client';

import {
  BedDouble,
  Car,
  Check,
  CircleAlert,
  Film,
  Footprints,
  MapPin,
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
  'flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto overscroll-contain px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] desk:px-[18px]';
const STATE = 'py-2 text-[13px] text-white/70';
const SECTION =
  'flex flex-col gap-3 rounded-[var(--radius-card)] border border-white/12 bg-black/20 p-4 text-white';
// Section headers: small, spaced capitals, so the content (not the title) carries the weight.
const EYEBROW =
  'm-0 flex items-center justify-between gap-2 text-[11px] font-semibold tracking-[0.08em] text-white/60 uppercase';
const BADGE =
  'self-start rounded-full bg-white/15 px-2 py-0.5 text-[11px] font-medium tracking-normal text-white/90 normal-case';
// Amber, so "check this" stands out from the plain grey badges.
const WARN =
  'bg-warn/20 text-warn rounded-full px-2.5 py-0.5 text-[11px] font-semibold tracking-normal normal-case';
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
 *  whether you walk or ride, D82), what to ride when known, then the time; "about" when estimated. */
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
          <h2 className="m-0 text-[21px] leading-tight font-bold tracking-tight text-white">
            {plan.title}
          </h2>
          {plan.subtitle && (
            <p className="m-0 mt-1 text-[13.5px] leading-snug text-white/65">{plan.subtitle}</p>
          )}
        </div>

        {plan.days.map((day, i) => (
          <DaySection
            key={day.day}
            order={i}
            day={day}
            activeDay={activeDay}
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
                <li key={check} className="flex gap-2.5 text-[14px] leading-[1.5] text-white/90">
                  <CircleAlert
                    size={16}
                    strokeWidth={2}
                    className="mt-0.5 flex-none text-white/45"
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
              className="bg-accent text-on-accent flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl border-0 text-[15px] font-semibold shadow-[0_8px_24px_rgba(217,68,59,0.35)] transition-[filter] hover:brightness-110"
              onClick={onShare}
            >
              <Share size={17} strokeWidth={2.2} aria-hidden="true" />
              {t('share.open')}
            </button>
            <p className="m-0 text-center text-[12px] text-white/50">{t('share.hint')}</p>
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

const FACT = 'inline-flex items-center gap-1.5';

function DaySection({
  day,
  order,
  activeDay,
  selectedIndex,
  onSelectStop,
  onOpenShorts,
  sectionRef,
}: {
  day: Day;
  order: number;
  activeDay: number | null;
  selectedIndex: number | null;
  onSelectStop: (day: number, index: number) => void;
  onOpenShorts: (day: number, index: number) => void;
  sectionRef: (el: HTMLElement | null) => void;
}) {
  const t = useT();
  const lang = useLanguage();
  const color = dayColor(day.day);
  const moving = day.stops.reduce((total, stop) => total + (stop.leg?.minutes ?? 0), 0);

  const dimmed = activeDay != null && activeDay !== day.day;

  return (
    <section
      ref={sectionRef}
      className={`rise scroll-mt-2 transition-opacity duration-300 ${order > 0 ? 'border-t border-white/10 pt-5' : ''} ${dimmed ? 'opacity-45' : 'opacity-100'}`}
      style={{ '--i': order } as CSSProperties}
    >
      <header className="flex flex-col gap-1">
        <span className="flex items-center gap-1.5 text-[11px] font-bold tracking-[0.06em] uppercase">
          <span className="h-2 w-2 rounded-full" style={{ background: color }} aria-hidden="true" />
          <span className="text-white">{t('plan.day').replace('{n}', String(day.day))}</span>
          {day.date && (
            <span className="font-semibold tracking-normal text-white/60 normal-case">
              · {dayDate(day.date, lang)}
            </span>
          )}
        </span>
        {day.theme && (
          <h3 className="m-0 text-[17px] leading-snug font-bold text-white">{day.theme}</h3>
        )}
        <span className="mt-0.5 flex flex-wrap gap-x-3.5 gap-y-1 text-[12.5px] text-white/60">
          <span className={FACT}>
            <MapPin size={13} className="opacity-75" aria-hidden="true" />
            {t('plan.stopsCount').replace('{n}', String(day.stops.length))}
          </span>
          {moving > 0 && (
            <span className={FACT}>
              <Route size={13} className="opacity-75" aria-hidden="true" />
              {formatMinutes(moving, t)}
            </span>
          )}
          {day.stay && (
            <span className={FACT}>
              <BedDouble size={13} className="opacity-75" aria-hidden="true" />
              {day.stay}
            </span>
          )}
        </span>
      </header>

      <div className="stagger mt-2 flex flex-col">
        {day.stops.map((stop, index) => {
          const LegIcon = stop.leg ? LEG_ICONS[stop.leg.mode] : null;
          const last = index === day.stops.length - 1;
          return (
            <div key={stop.id} className="relative">
              {/* The day's line, from this stop's circle down to the next one. */}
              {!last && (
                <span
                  className="absolute top-[30px] -bottom-[10px] left-[70px] w-0.5 rounded-full opacity-60"
                  style={{ background: color }}
                  aria-hidden="true"
                />
              )}
              <div
                className={`flex gap-3 rounded-xl py-2.5 transition-colors duration-200 ${selectedIndex === index ? 'bg-white/10' : ''}`}
              >
                <span className="w-12 flex-none pt-0.5 text-right text-[13px] font-semibold text-white/85 tabular-nums">
                  {stop.time}
                </span>
                <button
                  type="button"
                  className="flex min-w-0 flex-1 gap-3 border-0 bg-transparent p-0 text-left font-inherit text-inherit"
                  aria-current={selectedIndex === index ? 'true' : undefined}
                  onClick={() => onSelectStop(day.day, index)}
                >
                  <span
                    className="text-on-accent relative mt-px flex h-[22px] w-[22px] flex-none items-center justify-center rounded-full text-[11px] font-bold"
                    style={{ background: color }}
                  >
                    {index + 1}
                  </span>
                  <span className="flex min-w-0 flex-1 flex-col gap-0.5 text-left">
                    <span className="text-[15px] leading-snug font-semibold text-white">
                      {stop.name}
                    </span>
                    {stop.nameLocal && stop.nameLocal !== stop.name && (
                      <span className="text-[11.5px] text-white/50">{stop.nameLocal}</span>
                    )}
                    {stop.note && (
                      <span className="mt-0.5 text-xs leading-[1.5] whitespace-pre-line text-white/70">
                        {stop.note}
                      </span>
                    )}
                    {stop.warn && <span className={`${BADGE} mt-1`}>{stop.warn}</span>}
                  </span>
                </button>
                {/* A thumbnail only when there is a Short to play: no empty boxes. */}
                {stop.videoIds.length > 0 ? (
                  <button
                    type="button"
                    className="relative mr-1 flex h-16 w-12 flex-none items-center justify-center overflow-hidden rounded-xl border border-white/20 bg-white/10 text-white"
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
              {stop.leg && LegIcon && (
                <p className="m-0 flex flex-wrap items-center gap-2 py-1 pl-[94px] text-xs text-white/70">
                  <span className="inline-flex items-center gap-1.5 text-white/55">
                    <LegIcon size={13} aria-hidden="true" />
                    {legText(stop.leg, t)}
                  </span>
                  {stop.leg.estimate && (
                    <span className={BADGE}>{t('plan.badge.pleaseCheck')}</span>
                  )}
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

// Shades of white, biggest share brightest: calm, and it reads on any background behind the glass.
const COST_COLORS = [0.95, 0.68, 0.46, 0.3, 0.2, 0.14].map((a) => `rgba(255,255,255,${a})`);

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
    <section className={`${SECTION} rise`}>
      <h3 className={EYEBROW}>
        {t(`cost.${cost.basis}`)} <span className={BADGE}>{t('plan.badge.estimate')}</span>
      </h3>
      <p className="m-0 text-[26px] leading-tight font-extrabold tracking-tight text-white tabular-nums">
        {money(currency, cost.min)} – {money(currency, cost.max)}
      </p>

      {cost.items.length > 0 && (
        <>
          {/* Where the money goes: the parts grow in from the left, one after another. */}
          <div className="mt-1 flex h-2.5 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
            {cost.items.map((item, i) => (
              <span
                key={item.label}
                className="grow-x h-full first:rounded-l-full last:rounded-r-full"
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
                className="flex items-start gap-3 border-t border-white/8 py-2.5 first:border-t-0 first:pt-0.5"
              >
                <span
                  className="mt-1.5 h-2.5 w-2.5 flex-none rounded-full"
                  style={{ background: color(i) }}
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1 text-[14px] leading-snug text-white/90">
                  {item.label}
                </span>
                <span className="flex flex-none flex-col items-end">
                  <span className="text-[14px] font-semibold text-white tabular-nums">
                    {compactMoney(currency, item.min, lang)} –{' '}
                    {compactMoney(currency, item.max, lang)}
                  </span>
                  <span className="text-[12px] text-white/55 tabular-nums">{share(i)}%</span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
