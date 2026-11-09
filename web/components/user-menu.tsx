'use client';

import type { User } from 'firebase/auth';
import { Check, CircleUserRound, House, LogOut } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import { signOutUser } from '@/lib/auth';
import { setLanguage, useLanguage, useT } from '@/lib/i18n';
import type { Language } from '@/lib/language';
import type { Trip } from '@/lib/types';

/** Account menu: the trips list and sign out, behind the avatar next to the language switch. */
const LANGUAGES: Language[] = ['en', 'ja'];

export function UserMenu({ user, trips }: { user: User; trips: Trip[] }) {
  const t = useT();
  const language = useLanguage();
  const [open, setOpen] = useState(false);
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

  return (
    <div className="relative" ref={root}>
      <button
        type="button"
        className="frost text-ink flex h-11 w-11 items-center justify-center rounded-full p-0"
        aria-label={t('auth.account')}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <CircleUserRound size={22} strokeWidth={1.8} aria-hidden="true" />
      </button>

      {open && (
        <div
          role="menu"
          aria-label={t('auth.account')}
          className="frost absolute top-13 right-0 z-50 flex max-h-[70svh] w-64 flex-col overflow-y-auto rounded-2xl p-1.5"
        >
          <p className="text-ink m-0 truncate px-2.5 py-2 text-[13px] font-semibold">
            {user.displayName || user.email || t('auth.account')}
          </p>

          <span className="bg-line/60 mx-2.5 h-px" />

          <Link
            role="menuitem"
            href="/"
            className="text-ink hover:bg-ink/6 mt-1 flex min-h-11 items-center gap-2.5 rounded-xl px-2.5 text-[13px] no-underline"
            onClick={() => setOpen(false)}
          >
            <House size={16} strokeWidth={1.8} aria-hidden="true" />
            {t('home.start')}
          </Link>

          <span className="bg-line/60 mx-2.5 my-1 h-px" />

          <p className="text-muted m-0 px-2.5 pt-1 pb-1 text-[11px] font-medium">
            {t('home.title')}
          </p>
          {trips.length === 0 ? (
            <p className="text-muted m-0 px-2.5 pb-2 text-xs">{t('home.empty')}</p>
          ) : (
            <ul className="m-0 flex list-none flex-col p-0">
              {trips.map((trip) => (
                <li key={trip.id}>
                  <Link
                    role="menuitem"
                    href={`/trips/${trip.id}`}
                    className="text-ink hover:bg-ink/6 flex min-h-11 flex-col justify-center rounded-xl px-2.5 py-1.5 no-underline"
                    onClick={() => setOpen(false)}
                  >
                    <span className="truncate text-[13px] font-medium">
                      {trip.slots.dest?.label || t('trip.untitled')}
                    </span>
                    <span className="text-muted text-[11px]">{t(`status.${trip.status}`)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}

          <span className="bg-line/60 mx-2.5 my-1 h-px" />

          <p className="text-muted m-0 px-2.5 pt-1 pb-1 text-[11px] font-medium">
            {t('auth.language')}
          </p>
          <p className="text-muted m-0 px-2.5 pb-1 text-[11px] leading-snug">
            {t('auth.languageNote')}
          </p>
          {LANGUAGES.map((lang) => (
            <button
              key={lang}
              type="button"
              role="menuitemradio"
              aria-checked={lang === language}
              className="text-ink hover:bg-ink/6 flex min-h-11 items-center gap-2.5 rounded-xl border-0 bg-transparent px-2.5 text-left text-[13px]"
              onClick={() => lang !== language && setLanguage(lang)}
            >
              <span className="flex h-4 w-4 flex-none items-center justify-center">
                {lang === language && <Check size={14} strokeWidth={2.4} aria-hidden="true" />}
              </span>
              {t(`language.${lang}`)}
            </button>
          ))}

          <span className="bg-line/60 mx-2.5 my-1 h-px" />

          <button
            type="button"
            role="menuitem"
            className="text-ink hover:bg-ink/6 flex min-h-11 items-center gap-2.5 rounded-xl border-0 bg-transparent px-2.5 text-left text-[13px]"
            onClick={() => void signOutUser()}
          >
            <LogOut size={16} strokeWidth={1.8} aria-hidden="true" />
            {t('auth.signOut')}
          </button>
        </div>
      )}
    </div>
  );
}
