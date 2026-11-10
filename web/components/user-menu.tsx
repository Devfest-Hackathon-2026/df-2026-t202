'use client';

import type { User } from 'firebase/auth';
import {
  Check,
  ChevronLeft,
  ChevronRight,
  CircleUserRound,
  LogOut,
  Plus,
  Settings,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { linkGuestWithGoogle, signInWithGoogle, signOutUser } from '@/lib/auth';
import { CURRENCIES, setCurrency, useCurrency, type Currency } from '@/lib/currency';
import { setLanguage, useLanguage, useT } from '@/lib/i18n';
import type { Language } from '@/lib/language';
import { tripDates, tripPlace } from '@/lib/trip-format';
import type { Trip } from '@/lib/types';

const LANGUAGES: Language[] = ['en', 'ja'];
const RECENT = 3; // trips shown in the menu; the rest are on /trips

const ROW =
  'text-ink hover:bg-ink/6 flex min-h-11 w-full items-center gap-2.5 rounded-xl border-0 bg-transparent px-2.5 text-left text-[13px] no-underline';
const SECTION = 'text-muted m-0 px-2.5 pt-1 pb-1 text-[11px] font-medium';
const DIVIDER = 'bg-line/60 mx-2.5 my-1 block h-px';

/**
 * Account menu behind the avatar: who is signed in, new trip, the most recent trips with a link to
 * all of them, settings (language, currency) and sign out. Guests are asked to keep their trips by
 * signing in with Google.
 */
export function UserMenu({ user, trips }: { user: User; trips: Trip[] }) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<'main' | 'settings'>('main');
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const close = () => setOpen(false);

  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        className="frost text-ink flex h-11 w-11 items-center justify-center overflow-hidden rounded-full p-0"
        aria-label={t('auth.account')}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          setView('main');
          setOpen(!open);
        }}
      >
        <Avatar user={user} size={44} />
      </button>

      {open && (
        <div
          role="menu"
          aria-label={t('auth.account')}
          className="border-ink/10 absolute top-13 right-0 z-50 flex max-h-[75svh] w-72 flex-col overflow-y-auto overscroll-contain rounded-2xl border bg-surface/95 p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.18)] backdrop-blur-xl"
        >
          {view === 'main' ? (
            <MainView
              user={user}
              trips={trips}
              onClose={close}
              onSettings={() => setView('settings')}
            />
          ) : (
            <SettingsView onBack={() => setView('main')} />
          )}
        </div>
      )}
    </div>
  );
}

function MainView({
  user,
  trips,
  onClose,
  onSettings,
}: {
  user: User;
  trips: Trip[];
  onClose: () => void;
  onSettings: () => void;
}) {
  const t = useT();
  const language = useLanguage();
  const currency = useCurrency();
  const recent = trips.slice(0, RECENT);

  return (
    <>
      <div className="flex items-center gap-3 px-2.5 py-2">
        <span className="flex h-10 w-10 flex-none items-center justify-center overflow-hidden rounded-full bg-fill">
          <Avatar user={user} size={40} />
        </span>
        <span className="flex min-w-0 flex-col">
          <span className="text-ink truncate text-[14px] font-semibold">
            {user.isAnonymous ? t('menu.guest') : user.displayName || t('auth.account')}
          </span>
          {user.isAnonymous ? (
            <span className="text-muted text-[11px]">{t('menu.guestSub')}</span>
          ) : (
            user.email && <span className="text-muted truncate text-[11px]">{user.email}</span>
          )}
        </span>
      </div>

      {user.isAnonymous && <GuestNudge />}

      <span className={DIVIDER} />

      <Link role="menuitem" href="/" className={ROW} onClick={onClose}>
        <Plus size={16} strokeWidth={1.8} aria-hidden="true" />
        {t('home.newTrip')}
      </Link>

      <span className={DIVIDER} />

      <p className={SECTION}>{t('menu.recent')}</p>
      {recent.length === 0 ? (
        <p className="text-muted m-0 px-2.5 pb-2 text-xs">{t('home.empty')}</p>
      ) : (
        <ul className="m-0 flex list-none flex-col p-0">
          {recent.map((trip) => {
            const dates = tripDates(trip, language, t);
            return (
              <li key={trip.id}>
                <Link
                  role="menuitem"
                  href={`/trips/${trip.id}`}
                  className="text-ink hover:bg-ink/6 flex min-h-11 items-center gap-2.5 rounded-xl px-2.5 py-1.5 no-underline"
                  onClick={onClose}
                >
                  <StatusDot status={trip.status} />
                  <span className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate text-[13px] font-medium">{tripPlace(trip, t)}</span>
                    <span className="text-muted truncate text-[11px]">
                      {[dates, t(`status.${trip.status}`)].filter(Boolean).join(' · ')}
                    </span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {trips.length > 0 && (
        <Link role="menuitem" href="/trips" className={`${ROW} font-medium`} onClick={onClose}>
          <span className="flex-1">{t('menu.seeAll').replace('{n}', String(trips.length))}</span>
          <ChevronRight size={16} strokeWidth={1.8} aria-hidden="true" />
        </Link>
      )}

      <span className={DIVIDER} />

      <button type="button" role="menuitem" className={ROW} onClick={onSettings}>
        <Settings size={16} strokeWidth={1.8} aria-hidden="true" />
        <span className="flex-1">{t('menu.settings')}</span>
        <span className="text-muted text-[11px]">
          {language.toUpperCase()} · {currency}
        </span>
        <ChevronRight size={16} strokeWidth={1.8} aria-hidden="true" />
      </button>
      <button type="button" role="menuitem" className={ROW} onClick={() => void signOutUser()}>
        <LogOut size={16} strokeWidth={1.8} aria-hidden="true" />
        {t('auth.signOut')}
      </button>
    </>
  );
}

function SettingsView({ onBack }: { onBack: () => void }) {
  const t = useT();
  const language = useLanguage();
  const currency = useCurrency();
  const currencyName = (code: string) =>
    new Intl.DisplayNames(language, { type: 'currency' }).of(code) ?? code;

  return (
    <>
      <button type="button" className={`${ROW} font-semibold`} onClick={onBack}>
        <ChevronLeft size={16} strokeWidth={1.8} aria-hidden="true" />
        {t('menu.settings')}
      </button>

      <span className={DIVIDER} />

      <p className={SECTION}>{t('auth.language')}</p>
      <p className="text-muted m-0 px-2.5 pb-1 text-[11px] leading-snug">
        {t('auth.languageNote')}
      </p>
      {LANGUAGES.map((lang) => (
        <button
          key={lang}
          type="button"
          role="menuitemradio"
          aria-checked={lang === language}
          className={ROW}
          onClick={() => lang !== language && setLanguage(lang)}
        >
          <span className="flex h-4 w-4 flex-none items-center justify-center">
            {lang === language && <Check size={14} strokeWidth={2.4} aria-hidden="true" />}
          </span>
          {t(`language.${lang}`)}
        </button>
      ))}

      <span className={DIVIDER} />

      {/* Currency for budgets and costs on new trips (a trip keeps the one it started with). */}
      <label className="flex flex-col gap-1 px-2.5 pt-1 pb-2">
        <span className="text-muted text-[11px] font-medium">{t('auth.currency')}</span>
        <span className="text-muted text-[11px] leading-snug">{t('auth.currencyNote')}</span>
        <select
          className="text-ink border-ink/15 min-h-11 rounded-xl border bg-white/70 px-2.5 text-[13px]"
          value={currency}
          onChange={(e) => setCurrency(e.target.value as Currency)}
        >
          {CURRENCIES.map((code) => (
            <option key={code} value={code}>
              {code} · {currencyName(code)}
            </option>
          ))}
        </select>
      </label>
    </>
  );
}

/** Guests: keep the trips by turning the guest into a Google account (same uid). */
export function GuestNudge({
  className = 'mx-1.5 my-1',
  dark = false,
}: {
  className?: string;
  dark?: boolean; // on the dusk photo (dark glass, white text)
}) {
  const t = useT();
  const [state, setState] = useState<'idle' | 'busy' | 'exists' | 'failed'>('idle');

  async function link() {
    setState('busy');
    try {
      setState((await linkGuestWithGoogle()) === 'linked' ? 'idle' : 'exists');
    } catch (e) {
      // Closing the popup is not an error worth showing.
      const code = (e as { code?: string }).code;
      setState(
        code === 'auth/popup-closed-by-user' || code === 'auth/cancelled-popup-request'
          ? 'idle'
          : 'failed',
      );
    }
  }

  return (
    <div
      className={`${className} flex flex-col gap-2 rounded-xl p-2.5 ${
        dark ? 'border border-white/15 bg-stone-900/50 backdrop-blur-2xl' : 'bg-ink/5'
      }`}
    >
      <p className={`m-0 text-[12px] leading-snug ${dark ? 'text-white' : 'text-ink'}`}>
        {state === 'exists' ? t('menu.accountExists') : t('menu.guestNudge')}
      </p>
      {state === 'failed' && <p className="text-accent m-0 text-[12px]">{t('menu.linkFailed')}</p>}
      <button
        type="button"
        className={`min-h-10 rounded-lg border-0 px-3 text-[13px] font-semibold disabled:opacity-60 ${
          dark ? 'text-ink bg-white' : 'bg-ink text-surface'
        }`}
        disabled={state === 'busy'}
        onClick={() => void (state === 'exists' ? signInWithGoogle() : link())}
      >
        {state === 'exists' ? t('menu.signInExisting') : t('menu.signInGoogle')}
      </button>
    </div>
  );
}

function Avatar({ user, size }: { user: User; size: number }) {
  if (user.photoURL) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={user.photoURL}
        alt=""
        width={size}
        height={size}
        referrerPolicy="no-referrer"
        className="h-full w-full object-cover"
      />
    );
  }
  const initial = !user.isAnonymous && user.displayName ? user.displayName.trim()[0] : '';
  return initial ? (
    <span className="text-ink text-[15px] font-semibold uppercase">{initial}</span>
  ) : (
    <CircleUserRound size={Math.round(size / 2)} strokeWidth={1.8} aria-hidden="true" />
  );
}

/** Status as a small dot: ready is solid, in progress is outlined, error uses the accent. */
function StatusDot({ status }: { status: Trip['status'] }) {
  const style =
    status === 'ready'
      ? 'bg-ink'
      : status === 'error'
        ? 'bg-accent'
        : 'border-ink/40 border bg-transparent';
  return <span className={`h-2 w-2 flex-none rounded-full ${style}`} aria-hidden="true" />;
}
