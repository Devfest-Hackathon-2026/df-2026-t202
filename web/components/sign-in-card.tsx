'use client';

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

const FEATURES = ['plan', 'real', 'share'] as const;

/** The signed-out start screen: what Tripi does, sign in, and three reasons to trust the plan (PLAN.md 10.1 S7). */
export function SignInCard() {
  const t = useT();

  return (
    <div className="flex w-full flex-col gap-10 text-white [text-shadow:0_1px_20px_rgba(4,12,26,0.35)]">
      <section className="flex max-w-[560px] flex-col gap-5">
        <h1 className="m-0 text-[34px] leading-[1.15] font-semibold tracking-[-0.02em] whitespace-pre-line [word-break:auto-phrase] sm:text-[46px]">
          {t('home.hero.title')}
        </h1>
        <p className="m-0 max-w-[480px] text-[16px] leading-relaxed text-white/85 [word-break:auto-phrase] sm:text-[17px]">
          {t('home.hero.subtitle')}
        </p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pt-1">
          <button
            type="button"
            className="text-ink flex min-h-12 items-center gap-3 rounded-full bg-white px-6 text-[15px] font-semibold [text-shadow:none] shadow-[0_8px_24px_rgba(4,12,26,0.3)] transition-transform active:scale-[0.98]"
            onClick={() => void signInWithGoogle()}
          >
            <GoogleMark />
            {t('auth.signInGoogle')}
          </button>
        </div>

        {/* Development only: lets the flow be exercised on localhost without a Google account.
            It is never rendered on a deployed host. */}
        {typeof window !== 'undefined' && window.location.hostname === 'localhost' && (
          <button
            type="button"
            className="self-start text-[13px] text-white/80 underline underline-offset-4"
            onClick={() => void signInAsGuest()}
          >
            {t('auth.signInGuest')}
          </button>
        )}
      </section>

      <ul className="m-0 grid list-none grid-cols-1 gap-4 border-t border-white/35 p-0 pt-5 sm:grid-cols-3 sm:gap-6">
        {FEATURES.map((key) => (
          <li key={key} className="flex flex-col gap-1">
            <span className="text-[14px] font-semibold">{t(`home.feature.${key}.title`)}</span>
            <span className="text-[13px] leading-snug text-white/85 [word-break:auto-phrase]">
              {t(`home.feature.${key}.desc`)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
