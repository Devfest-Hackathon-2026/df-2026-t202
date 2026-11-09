'use client';

import { Link2, MapPin, MessageCircle } from 'lucide-react';
import { signInAsGuest, signInWithGoogle } from '@/lib/auth';
import { useT } from '@/lib/i18n';

/** Google's four-colour "G", as their sign-in branding requires on the button. */
function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#4285F4"
        d="M45.12 24.5c0-1.56-.14-3.06-.4-4.5H24v8.51h11.84c-.51 2.75-2.06 5.08-4.39 6.64v5.52h7.11c4.16-3.83 6.56-9.47 6.56-16.17z"
      />
      <path
        fill="#34A853"
        d="M24 46c5.94 0 10.92-1.97 14.56-5.33l-7.11-5.52c-1.97 1.32-4.49 2.1-7.45 2.1-5.73 0-10.58-3.87-12.31-9.07H4.34v5.7C7.96 41.07 15.4 46 24 46z"
      />
      <path
        fill="#FBBC05"
        d="M11.69 28.18C11.25 26.86 11 25.45 11 24s.25-2.86.69-4.18v-5.7H4.34A21.99 21.99 0 0 0 2 24c0 3.55.85 6.91 2.34 9.88l7.35-5.7z"
      />
      <path
        fill="#EA4335"
        d="M24 10.75c3.23 0 6.13 1.11 8.41 3.29l6.31-6.31C34.91 4.18 29.93 2 24 2 15.4 2 7.96 6.93 4.34 14.12l7.35 5.7c1.73-5.2 6.58-9.07 12.31-9.07z"
      />
    </svg>
  );
}

const FEATURES = [
  { key: 'plan', Icon: MessageCircle },
  { key: 'real', Icon: MapPin },
  { key: 'share', Icon: Link2 },
] as const;

/** The signed-out start screen: what the app is, then sign in (PLAN.md 10.1 S7). */
export function SignInCard() {
  const t = useT();

  return (
    <div className="mx-auto flex w-full max-w-[400px] flex-col gap-6 rounded-2xl border border-white/15 bg-stone-900/50 bg-clip-padding p-7 shadow-[0_24px_60px_rgba(4,12,26,0.45)] backdrop-blur-2xl">
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {FEATURES.map(({ key, Icon }) => (
          <li key={key} className="flex items-center gap-3 text-[14px] text-white">
            <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-white/18 text-white">
              <Icon size={16} strokeWidth={1.8} aria-hidden="true" />
            </span>
            {t(`home.feature.${key}`)}
          </li>
        ))}
      </ul>

      <button
        type="button"
        className="text-ink flex min-h-12 items-center justify-center gap-3 rounded-2xl bg-white text-[15px] font-semibold shadow-[0_10px_28px_rgba(4,12,26,0.35)]"
        onClick={() => void signInWithGoogle()}
      >
        <GoogleMark />
        {t('auth.signInGoogle')}
      </button>

      {/* Development only: lets the flow be exercised on localhost without a Google account.
          It is never rendered on a deployed host. */}
      {typeof window !== 'undefined' && window.location.hostname === 'localhost' && (
        <button
          type="button"
          className="min-h-10 rounded-xl border border-white/25 bg-white/10 text-[13px] text-white"
          onClick={() => void signInAsGuest()}
        >
          {t('auth.signInGuest')}
        </button>
      )}
    </div>
  );
}
