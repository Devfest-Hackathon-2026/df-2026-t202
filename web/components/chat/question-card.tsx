'use client';

import {
  Bus,
  Car,
  ChevronLeft,
  ChevronRight,
  Minus,
  Plane,
  Plus,
  Ship,
  Sparkles,
  TrainFront,
  type LucideIcon,
} from 'lucide-react';
import { useState } from 'react';
import { useLanguage, useT } from '@/lib/i18n';
import type { Slots, StepKey, TransportMode, UiCard } from '@/lib/types';

const CARD =
  'mt-1 flex flex-col gap-3 rounded-2xl border border-white/60 bg-white/55 p-4 shadow-[0_12px_40px_rgba(8,24,48,0.22)] backdrop-blur-2xl';
const HINT = 'text-muted-strong text-center text-[12px]';
const PILL_OFF = 'text-ink border-ink/15 min-h-10 rounded-full border bg-white/70 px-4 text-[13px]';
const PILL_ON =
  'bg-ink text-on-accent min-h-10 rounded-full border border-transparent px-4 text-[13px] font-semibold';
const INPUT =
  'text-ink placeholder:text-muted border-ink/15 min-h-11 min-w-0 flex-1 rounded-xl border bg-white/70 px-3 font-inherit';
const ACTIONS = 'flex items-center justify-end gap-2';
const PRIMARY =
  'bg-accent text-on-accent disabled:bg-line disabled:text-muted min-h-11 rounded-xl border-0 px-5 text-sm font-semibold';
const GHOST =
  'text-muted-strong border-ink/15 min-h-11 rounded-xl border bg-white/70 px-3.5 text-sm';
const ROUND =
  'text-ink disabled:text-ink/25 border-ink/15 flex h-11 w-11 flex-none items-center justify-center rounded-full border bg-white/70';

export type AnswerFn = (step: StepKey, value: unknown) => void;

/** Re-opens the previous card. `mr-auto` keeps it on the left of the action row. */
function BackButton({ onBack, disabled }: { onBack: () => void; disabled: boolean }) {
  const t = useT();
  return (
    <button
      type="button"
      className="text-muted-strong border-ink/15 mr-auto flex min-h-11 items-center gap-1.5 rounded-xl border bg-white/70 px-3 text-sm"
      disabled={disabled}
      onClick={onBack}
    >
      <ChevronLeft size={15} aria-hidden="true" />
      {t('card.back')}
    </button>
  );
}

/** The card shown with the AI's question. The server decides which one (PLAN.md 8.1). */
export function QuestionCard({
  card,
  slots,
  disabled,
  onAnswer,
  onGenerate,
  onBack,
  onPlanMusts,
  plannedMusts,
  onEdit,
}: {
  card: UiCard;
  slots: Slots;
  disabled: boolean;
  onAnswer: AnswerFn;
  onGenerate: () => void;
  onBack?: () => void;
  onPlanMusts?: (labels: string[]) => void;
  plannedMusts?: string[];
  onEdit?: (step: StepKey) => void;
}) {
  const props = { card, slots, disabled, onAnswer, onBack };
  switch (card.type) {
    case 'dest':
      return <DestCard {...props} onPlanMusts={onPlanMusts} />;
    case 'dates':
      return <DatesCard {...props} />;
    case 'people':
      return <PeopleCard {...props} />;
    case 'budget':
      return <BudgetCard {...props} />;
    case 'transport':
      return <TransportCard {...props} />;
    case 'prefs':
      return <ListCard {...props} step="prefs" />;
    case 'musts':
      return <ListCard {...props} step="musts" seed={plannedMusts} />;
    case 'ready':
      return (
        <ReadyCard
          slots={slots}
          disabled={disabled}
          onGenerate={onGenerate}
          onBack={onBack}
          onEdit={onEdit}
        />
      );
    default:
      return null;
  }
}

type CardProps = {
  card: UiCard;
  slots: Slots;
  disabled: boolean;
  onAnswer: AnswerFn;
  onBack?: () => void;
};

function SkipButton({
  step,
  disabled,
  onAnswer,
}: {
  step: StepKey;
  disabled: boolean;
  onAnswer: AnswerFn;
}) {
  const t = useT();
  return (
    <button
      type="button"
      className={GHOST}
      disabled={disabled}
      onClick={() => onAnswer(step, 'skip')}
    >
      {t('card.skip')}
    </button>
  );
}

/* ---------------------------------------------------------------- destination */

/** Suggestions for the demo region. Anywhere else is reached by typing, or by the map picker. */
const SUGGESTIONS = [
  'kyushu',
  'fukuoka',
  'nagasaki',
  'kumamoto',
  'oita',
  'miyazaki',
  'kagoshima',
  'saga',
];

/** These suggestions are all in Japan; the country is what picks the trip's currency. */
const SUGGESTION_COUNTRY = 'JP';

/**
 * A suggestion that covers several places. Picking one opens the places inside it, so the
 * traveller can say which ones to include. `dest` holds one place (models.py PlaceRef), so the
 * chosen ones are carried to the "must-see" card instead of being squeezed into the destination.
 */
const BROAD: Record<string, string[]> = {
  kyushu: ['fukuoka', 'nagasaki', 'kumamoto', 'oita', 'miyazaki', 'kagoshima', 'saga'],
};

function DestCard({
  disabled,
  onAnswer,
  onBack,
  onPlanMusts,
}: CardProps & { onPlanMusts?: (labels: string[]) => void }) {
  const t = useT();
  const [label, setLabel] = useState('');
  const [broad, setBroad] = useState<string | null>(null);
  const [inside, setInside] = useState<string[]>([]);
  const answer = () => label.trim() && onAnswer('dest', { label: label.trim() });

  if (broad) {
    const toggle = (key: string) =>
      setInside(inside.includes(key) ? inside.filter((k) => k !== key) : [...inside, key]);

    return (
      <div className={CARD}>
        <p className={HINT}>
          {t('card.dest.insideHint').replace('{area}', t(`dest.${broad}.name`))}
        </p>
        <div className="grid grid-cols-2 gap-2">
          {BROAD[broad].map((key) => (
            <button
              key={key}
              type="button"
              aria-pressed={inside.includes(key)}
              className={[
                'flex min-h-[64px] flex-col justify-center gap-0.5 rounded-xl border px-3 py-2 text-left transition-colors',
                inside.includes(key)
                  ? 'bg-ink text-on-accent border-transparent'
                  : 'border-ink/15 bg-white/70',
              ].join(' ')}
              disabled={disabled}
              onClick={() => toggle(key)}
            >
              <span className="text-[15px] font-bold">{t(`dest.${key}.name`)}</span>
              <span
                className={
                  inside.includes(key) ? 'text-[11px] opacity-80' : 'text-muted text-[11px]'
                }
              >
                {t(`dest.${key}.sub`)}
              </span>
            </button>
          ))}
        </div>
        <div className={ACTIONS}>
          <button
            type="button"
            className="text-muted-strong border-ink/15 mr-auto flex min-h-11 items-center gap-1.5 rounded-xl border bg-white/70 px-3 text-sm"
            disabled={disabled}
            onClick={() => setBroad(null)}
          >
            <ChevronLeft size={15} aria-hidden="true" />
            {t('card.back')}
          </button>
          <button
            type="button"
            className={PRIMARY}
            disabled={disabled}
            onClick={() => {
              onPlanMusts?.(inside.map((key) => t(`dest.${key}.name`)));
              onAnswer('dest', {
                label: t(`dest.${broad}.name`),
                countryCode: SUGGESTION_COUNTRY,
              });
            }}
          >
            {t('card.ok')}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={CARD}>
      <div className="flex gap-2">
        <input
          className={INPUT}
          value={label}
          placeholder={t('card.dest.placeholder')}
          aria-label={t('card.dest.label')}
          disabled={disabled}
          onChange={(e) => setLabel(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              answer();
            }
          }}
        />
        <button
          type="button"
          className={PRIMARY}
          disabled={disabled || !label.trim()}
          onClick={answer}
        >
          {t('card.ok')}
        </button>
      </div>
      <p className={HINT}>{t('card.dest.hint')}</p>
      <div className="grid grid-cols-2 gap-2">
        {SUGGESTIONS.map((key) => (
          <button
            key={key}
            type="button"
            className="hover:border-ink border-ink/15 flex min-h-[64px] flex-col justify-center gap-0.5 rounded-xl border bg-white/70 px-3 py-2 text-left transition-colors"
            disabled={disabled}
            onClick={() =>
              BROAD[key]
                ? setBroad(key)
                : onAnswer('dest', {
                    label: t(`dest.${key}.name`),
                    countryCode: SUGGESTION_COUNTRY,
                  })
            }
          >
            <span className="text-ink text-[15px] font-bold">{t(`dest.${key}.name`)}</span>
            <span className="text-muted text-[11px]">{t(`dest.${key}.sub`)}</span>
          </button>
        ))}
      </div>
      {onBack && (
        <div className={ACTIONS}>
          <BackButton onBack={onBack} disabled={disabled} />
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------- dates */

const DAY_MS = 86_400_000;

/** "YYYY-MM-DD" in the traveller's own time zone. toISOString() would shift the day in JST. */
function isoDate(time: number): string {
  const d = new Date(time);
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${month}-${day}`;
}

function startOfDay(time: number) {
  const d = new Date(time);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/** The Saturday/Sunday pair of a given week offset, for the quick chips. */
function weekend(weeksAhead: number): [number, number] {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const saturday = new Date(today);
  saturday.setDate(today.getDate() + ((6 - today.getDay() + 7) % 7) + weeksAhead * 7);
  return [saturday.getTime(), saturday.getTime() + DAY_MS];
}

function DatesCard({ disabled, onAnswer, onBack }: CardProps) {
  const t = useT();
  const lang = useLanguage();
  const [monthOffset, setMonthOffset] = useState(0);
  const [start, setStart] = useState<number | null>(null);
  const [end, setEnd] = useState<number | null>(null);

  const today = startOfDay(Date.now());
  const base = new Date();
  const month = new Date(base.getFullYear(), base.getMonth() + monthOffset, 1);
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const leading = month.getDay();

  const weekdays = Array.from({ length: 7 }, (_, i) =>
    new Intl.DateTimeFormat(lang, { weekday: 'narrow' }).format(new Date(2024, 8, 1 + i)),
  );
  const dayLabel = (time: number) =>
    new Intl.DateTimeFormat(lang, { month: 'numeric', day: 'numeric', weekday: 'short' }).format(
      new Date(time),
    );

  const nights = start && end ? Math.round((end - start) / DAY_MS) : null;

  function pick(time: number) {
    if (!start || (start && end) || time < start) {
      setStart(time);
      setEnd(null);
    } else {
      setEnd(time);
    }
  }

  const quick: [string, number][] = [
    ['thisWeekend', 0],
    ['nextWeekend', 1],
    ['nextMonthWeekend', 4],
  ];

  return (
    <div className={CARD}>
      <div className="flex flex-wrap gap-2">
        {quick.map(([key, weeks]) => {
          const [from, to] = weekend(weeks);
          const on = start === from && end === to;
          return (
            <button
              key={key}
              type="button"
              className={on ? PILL_ON : PILL_OFF}
              disabled={disabled}
              onClick={() => {
                setStart(from);
                setEnd(to);
                const target = new Date(from);
                setMonthOffset(
                  (target.getFullYear() - base.getFullYear()) * 12 +
                    target.getMonth() -
                    base.getMonth(),
                );
              }}
            >
              {t(`card.dates.${key}`)}
            </button>
          );
        })}
      </div>

      <div className="flex items-center justify-between">
        <button
          type="button"
          className={ROUND}
          aria-label={t('card.dates.prevMonth')}
          disabled={disabled || monthOffset <= 0}
          onClick={() => setMonthOffset(monthOffset - 1)}
        >
          <ChevronLeft size={18} aria-hidden="true" />
        </button>
        <span className="text-[15px] font-bold">
          {new Intl.DateTimeFormat(lang, { year: 'numeric', month: 'long' }).format(month)}
        </span>
        <button
          type="button"
          className={ROUND}
          aria-label={t('card.dates.nextMonth')}
          disabled={disabled}
          onClick={() => setMonthOffset(monthOffset + 1)}
        >
          <ChevronRight size={18} aria-hidden="true" />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-y-1 text-center">
        {weekdays.map((w, i) => (
          <span key={i} className="text-muted text-[11px]">
            {w}
          </span>
        ))}
        {Array.from({ length: leading }, (_, i) => (
          <span key={`pad-${i}`} />
        ))}
        {Array.from({ length: daysInMonth }, (_, i) => {
          const time = new Date(month.getFullYear(), month.getMonth(), i + 1).getTime();
          const past = time < today;
          const isEdge = time === start || time === end;
          const inRange = Boolean(start && end && time > start && time < end);
          return (
            <span
              key={time}
              className={[
                'flex h-9 items-center justify-center',
                inRange ? 'bg-ink/8' : '',
                time === start && end ? 'rounded-l-full' : '',
                time === end ? 'rounded-r-full' : '',
              ].join(' ')}
            >
              <button
                type="button"
                className={[
                  'h-8 w-8 rounded-full border-0 text-sm',
                  isEdge ? 'bg-ink text-on-accent font-semibold' : '',
                  !isEdge && past ? 'text-line line-through' : '',
                  !isEdge && !past ? 'text-ink bg-transparent' : '',
                ].join(' ')}
                disabled={disabled || past}
                onClick={() => pick(time)}
              >
                {i + 1}
              </button>
            </span>
          );
        })}
      </div>

      <div className="border-line-soft flex items-center justify-between border-t pt-2.5">
        <span className="text-[14px] font-semibold">
          {start
            ? `${dayLabel(start)}${end ? ` – ${dayLabel(end)}` : ''}`
            : t('card.dates.pickStart')}
        </span>
        <span className="text-muted text-[12px]">
          {nights != null
            ? nights === 0
              ? t('card.dates.dayTrip')
              : t('card.dates.nights').replace('{n}', String(nights))
            : start
              ? t('card.dates.pickEnd')
              : ''}
        </span>
      </div>

      <div className={ACTIONS}>
        {onBack && <BackButton onBack={onBack} disabled={disabled} />}
        <SkipButton step="dates" disabled={disabled} onAnswer={onAnswer} />
        <button
          type="button"
          className={PRIMARY}
          disabled={disabled || !start || !end}
          onClick={() => onAnswer('dates', { start: isoDate(start!), end: isoDate(end!) })}
        >
          {t('card.ok')}
        </button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- people */

function PeopleCard({ slots, disabled, onAnswer, onBack }: CardProps) {
  const t = useT();
  const [people, setPeople] = useState(slots.people ?? { adult: 2, child: 0, infant: 0 });
  const total = people.adult + people.child + people.infant;
  const set = (key: 'adult' | 'child' | 'infant', delta: number) =>
    setPeople({ ...people, [key]: people[key] + delta });

  return (
    <div className={CARD}>
      <div className="flex flex-col items-center gap-1 py-1">
        <div className="flex items-center gap-6">
          <button
            type="button"
            className={`${ROUND} h-12 w-12`}
            aria-label={t('card.people.decrease').replace('{what}', t('card.people.adult'))}
            disabled={disabled || people.adult <= 1}
            onClick={() => set('adult', -1)}
          >
            <Minus size={18} aria-hidden="true" />
          </button>
          <span className="min-w-12 text-center text-[40px] leading-none font-bold tabular-nums">
            {people.adult}
          </span>
          <button
            type="button"
            className={`${ROUND} h-12 w-12`}
            aria-label={t('card.people.increase').replace('{what}', t('card.people.adult'))}
            disabled={disabled || total >= 50}
            onClick={() => set('adult', 1)}
          >
            <Plus size={18} aria-hidden="true" />
          </button>
        </div>
        <span className="text-muted text-[12px]">
          {t('card.people.adult')}（{t('card.people.adultSub')}）
        </span>
      </div>

      {(['child', 'infant'] as const).map((key) => (
        <div
          key={key}
          className="border-fill-soft flex items-center justify-between gap-3 border-t pt-3"
        >
          <span className="text-[14px] font-semibold">
            {t(`card.people.${key}`)}{' '}
            <span className="text-muted text-[11px] font-normal">{t(`card.people.${key}Sub`)}</span>
          </span>
          <span className="flex items-center gap-3">
            <button
              type="button"
              className={`${ROUND} h-9 w-9`}
              aria-label={t('card.people.decrease').replace('{what}', t(`card.people.${key}`))}
              disabled={disabled || people[key] <= 0}
              onClick={() => set(key, -1)}
            >
              <Minus size={15} aria-hidden="true" />
            </button>
            <span className="min-w-5 text-center text-[15px] tabular-nums">{people[key]}</span>
            <button
              type="button"
              className={`${ROUND} h-9 w-9`}
              aria-label={t('card.people.increase').replace('{what}', t(`card.people.${key}`))}
              disabled={disabled || total >= 50}
              onClick={() => set(key, 1)}
            >
              <Plus size={15} aria-hidden="true" />
            </button>
          </span>
        </div>
      ))}

      <div className={ACTIONS}>
        {onBack && <BackButton onBack={onBack} disabled={disabled} />}
        <SkipButton step="people" disabled={disabled} onAnswer={onAnswer} />
        <button
          type="button"
          className={PRIMARY}
          disabled={disabled}
          onClick={() => onAnswer('people', people)}
        >
          {t('card.ok')}
        </button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- budget */

function BudgetCard({ card, slots, disabled, onAnswer, onBack }: CardProps) {
  const t = useT();
  const lang = useLanguage();
  const chips = card.options.map(Number).filter(Number.isFinite);
  // The server falls back to USD when the destination's country is unknown
  // (flow.currency_for), and its chip amounts are in that currency. Match it.
  const currency = slots.budget?.currency ?? 'USD';
  const [basis, setBasis] = useState<'person' | 'total'>(slots.budget?.basis ?? 'person');
  const [amount, setAmount] = useState(slots.budget?.amount ?? chips[1] ?? 0);
  const max = (chips[chips.length - 1] ?? 1000) * 2;
  const step = Math.max(1, Math.round(max / 100));
  const money = (value: number) =>
    new Intl.NumberFormat(lang, { style: 'currency', currency, maximumFractionDigits: 0 }).format(
      value,
    );

  return (
    <div className={CARD}>
      <div
        className="bg-ink/8 grid grid-cols-2 gap-0.5 rounded-xl p-[3px]"
        role="group"
        aria-label={t('card.budget.basis')}
      >
        {(['person', 'total'] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={basis === value}
            className={
              basis === value
                ? 'text-ink min-h-[38px] rounded-lg border-0 bg-white text-[13px] font-semibold shadow-[0_1px_3px_rgba(0,0,0,0.12)]'
                : 'text-muted min-h-[38px] rounded-lg border-0 bg-transparent text-[13px]'
            }
            disabled={disabled}
            onClick={() => setBasis(value)}
          >
            {t(`card.budget.${value}`)}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-center gap-5 py-1">
        <button
          type="button"
          className={`${ROUND} h-12 w-12`}
          aria-label={t('card.budget.less')}
          disabled={disabled || amount <= 0}
          onClick={() => setAmount(Math.max(0, amount - step))}
        >
          <Minus size={18} aria-hidden="true" />
        </button>
        <span className="text-[30px] leading-none font-bold tabular-nums">{money(amount)}</span>
        <button
          type="button"
          className={`${ROUND} h-12 w-12`}
          aria-label={t('card.budget.more')}
          disabled={disabled || amount >= max}
          onClick={() => setAmount(Math.min(max, amount + step))}
        >
          <Plus size={18} aria-hidden="true" />
        </button>
      </div>

      <input
        type="range"
        className="accent-ink w-full"
        min={0}
        max={max}
        step={step}
        value={amount}
        aria-label={t('card.budget.label')}
        disabled={disabled}
        onChange={(e) => setAmount(Number(e.target.value))}
      />
      <div className="text-muted flex justify-between text-[11px]">
        <span>{money(0)}</span>
        <span>{money(max)}+</span>
      </div>

      <div className={ACTIONS}>
        {onBack && <BackButton onBack={onBack} disabled={disabled} />}
        <SkipButton step="budget" disabled={disabled} onAnswer={onAnswer} />
        <button
          type="button"
          className={PRIMARY}
          disabled={disabled}
          onClick={() => onAnswer('budget', { basis, amount, currency })}
        >
          {t('card.ok')}
        </button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- transport */

const TRANSPORT_ICONS: Record<TransportMode, LucideIcon> = {
  shinkansen: TrainFront,
  train: TrainFront,
  plane: Plane,
  car: Car,
  bus: Bus,
  ferry: Ship,
  any: Sparkles,
};

function TransportCard({ card, slots, disabled, onAnswer, onBack }: CardProps) {
  const t = useT();
  const [picked, setPicked] = useState<TransportMode[]>(slots.transport ?? []);
  const [origin, setOrigin] = useState(slots.origin?.label ?? '');

  const toggle = (mode: TransportMode) => {
    if (mode === 'any') return setPicked(picked.includes('any') ? [] : ['any']);
    const without = picked.filter((m) => m !== 'any');
    setPicked(without.includes(mode) ? without.filter((m) => m !== mode) : [...without, mode]);
  };

  return (
    <div className={CARD}>
      <div className="grid grid-cols-3 gap-2">
        {(card.options as TransportMode[]).map((mode) => {
          const Icon = TRANSPORT_ICONS[mode] ?? Sparkles;
          const on = picked.includes(mode);
          return (
            <button
              key={mode}
              type="button"
              aria-pressed={on}
              className={[
                'flex min-h-[76px] flex-col items-center justify-center gap-1.5 rounded-xl border text-[12px] transition-colors',
                on
                  ? 'bg-ink text-on-accent border-transparent font-semibold'
                  : 'border-ink/15 bg-white/70 text-ink',
              ].join(' ')}
              disabled={disabled}
              onClick={() => toggle(mode)}
            >
              <Icon size={20} strokeWidth={1.8} aria-hidden="true" />
              {t(`transport.${mode}`)}
            </button>
          );
        })}
      </div>

      <input
        className={INPUT}
        value={origin}
        placeholder={t('card.transport.origin')}
        aria-label={t('card.transport.origin')}
        disabled={disabled}
        onChange={(e) => setOrigin(e.target.value)}
      />

      <div className={ACTIONS}>
        {onBack && <BackButton onBack={onBack} disabled={disabled} />}
        <SkipButton step="transport" disabled={disabled} onAnswer={onAnswer} />
        <button
          type="button"
          className={PRIMARY}
          disabled={disabled || picked.length === 0}
          onClick={() =>
            onAnswer('transport', {
              transport: picked,
              origin: origin.trim() ? { label: origin.trim() } : null,
            })
          }
        >
          {t('card.ok')}
        </button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- prefs / musts */

function ListCard({
  card,
  slots,
  disabled,
  onAnswer,
  onBack,
  step,
  seed,
}: CardProps & { step: 'prefs' | 'musts'; seed?: string[] }) {
  const t = useT();
  // Places chosen on the destination card arrive here, because `dest` only holds one place.
  const [picked, setPicked] = useState<string[]>(() => {
    const existing = slots[step] ?? [];
    return [...new Set([...existing, ...(seed ?? [])])];
  });
  const [own, setOwn] = useState('');

  const toggle = (value: string) =>
    setPicked(picked.includes(value) ? picked.filter((v) => v !== value) : [...picked, value]);

  const addOwn = () => {
    const value = own.trim();
    if (!value || picked.includes(value)) return;
    setPicked([...picked, value]);
    setOwn('');
  };

  const chips = card.options.length > 0 ? card.options : picked;

  return (
    <div className={CARD}>
      {chips.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {chips.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={picked.includes(value)}
              className={picked.includes(value) ? PILL_ON : PILL_OFF}
              disabled={disabled}
              onClick={() => toggle(value)}
            >
              {step === 'prefs' && card.options.length > 0 ? t(`pref.${value}`) : value}
            </button>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <input
          className={INPUT}
          value={own}
          placeholder={t(`card.${step}.placeholder`)}
          aria-label={t(`card.${step}.label`)}
          disabled={disabled}
          onChange={(e) => setOwn(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addOwn();
            }
          }}
        />
        <button type="button" className={GHOST} disabled={disabled || !own.trim()} onClick={addOwn}>
          {t('card.add')}
        </button>
      </div>
      <div className={ACTIONS}>
        {onBack && <BackButton onBack={onBack} disabled={disabled} />}
        <SkipButton step={step} disabled={disabled} onAnswer={onAnswer} />
        <button
          type="button"
          className={PRIMARY}
          disabled={disabled}
          onClick={() => onAnswer(step, picked)}
        >
          {t('card.ok')}
        </button>
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- summary */

const SUMMARY_STEPS: StepKey[] = [
  'dest',
  'dates',
  'people',
  'budget',
  'transport',
  'prefs',
  'musts',
];

function ReadyCard({
  slots,
  disabled,
  onGenerate,
  onBack,
  onEdit,
}: {
  slots: Slots;
  disabled: boolean;
  onGenerate: () => void;
  onBack?: () => void;
  onEdit?: (step: StepKey) => void;
}) {
  const t = useT();
  const lang = useLanguage();

  function value(step: StepKey): string {
    switch (step) {
      case 'dest':
        return slots.dest?.label ?? '';
      case 'dates':
        if (slots.dates) return `${slots.dates.start} – ${slots.dates.end}`;
        return slots.nights != null
          ? t('card.dates.nights').replace('{n}', String(slots.nights))
          : '';
      case 'people': {
        if (!slots.people) return '';
        const total = slots.people.adult + slots.people.child + slots.people.infant;
        return String(total);
      }
      case 'budget':
        if (!slots.budget?.amount) return '';
        return new Intl.NumberFormat(lang, {
          style: 'currency',
          currency: slots.budget.currency,
          maximumFractionDigits: 0,
        }).format(slots.budget.amount);
      case 'transport':
        return slots.transport.map((mode) => t(`transport.${mode}`)).join(' / ');
      case 'prefs':
        return slots.prefs.map((pref) => t(`pref.${pref}`)).join(' / ');
      case 'musts':
        return slots.musts.join(' / ');
    }
  }

  return (
    <div className={CARD}>
      <div className="flex flex-col">
        {SUMMARY_STEPS.map((step) => (
          <div
            key={step}
            className="border-fill-soft flex items-center gap-3 border-b py-2.5 last:border-b-0"
          >
            <span className="text-muted w-20 flex-none text-[12px]">{t(`slot.${step}`)}</span>
            <span className="text-ink flex-1 text-[14px] font-semibold">
              {value(step) || (
                <span className="text-muted font-normal">{t('chat.notDecided')}</span>
              )}
            </span>
            {/* Re-opens that step's card. The server accepts the new answer (flow.can_answer). */}
            {onEdit && (
              <button
                type="button"
                className="text-muted-strong flex-none border-0 bg-transparent text-[12px] underline"
                disabled={disabled}
                onClick={() => onEdit(step)}
              >
                {t('card.change')}
              </button>
            )}
          </div>
        ))}
      </div>
      <div className={ACTIONS}>
        {onBack && <BackButton onBack={onBack} disabled={disabled} />}
        <button type="button" className={PRIMARY} disabled={disabled} onClick={onGenerate}>
          {t('card.generate')}
        </button>
      </div>
    </div>
  );
}
