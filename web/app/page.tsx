'use client';

// S7 Start: the prompt over the dusk photo, then the trip (PLAN.md 10.1).
import { ArrowUp, Landmark, Mountain, Sparkles, UtensilsCrossed } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState, type CSSProperties } from 'react';
import { LanguageSwitch } from '@/components/language-switch';
import { Spinner } from '@/components/page-loader';
import { SignInCard } from '@/components/sign-in-card';
import { UserMenu } from '@/components/user-menu';
import { post } from '@/lib/api';
import { getCurrency } from '@/lib/currency';
import { handOffFirstMessage } from '@/lib/first-message';
import { useAuthUser } from '@/lib/auth';
import { useLanguage, useT } from '@/lib/i18n';
import { useMyTrips } from '@/lib/trip';

/** Ready-made trips in three countries, plus "Surprise me". Each sends a full sentence, so one tap
 *  fills several questions at once (place, length, style). */
const SUGGESTION_KEYS = ['a', 'b', 'c', 'd'] as const;

const SUGGESTION_ICONS = { a: Mountain, b: UtensilsCrossed, c: Landmark, d: Sparkles } as const;

// Same glass as the sign-in card: both sit on the dusk photo and hold white text.
const PROMPT =
  'flex flex-col gap-3 rounded-2xl border border-white/15 bg-stone-900/50 bg-clip-padding p-5 shadow-[0_24px_60px_rgba(4,12,26,0.45)] backdrop-blur-2xl';
/* The text sits straight on the glass, as in the reference: no inner box, large white type. */
const INPUT =
  'w-full resize-none border-0 bg-transparent p-0 text-[19px] leading-snug text-white outline-none placeholder:text-white/75 [text-shadow:0_1px_6px_rgba(8,24,48,0.45)]';
const CHIP =
  'text-ink flex min-h-9 flex-none items-center gap-1.5 rounded-full border border-white/60 bg-white/85 px-3.5 text-[13px] font-medium whitespace-nowrap backdrop-blur-md';
const STATE = 'm-0 text-[13px] text-white [text-shadow:0_1px_6px_rgba(8,24,48,0.45)]';

export default function HomePage() {
  const t = useT();
  const language = useLanguage();
  const router = useRouter();
  const { user, loading } = useAuthUser();
  const { trips, loading: tripsLoading } = useMyTrips(user?.uid);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);

  /**
   * Create the trip and open it straight away. The first sentence is handed to the trip page,
   * which shows it with typing dots while the AI answers (that takes a few seconds).
   */
  async function start(first?: string) {
    setBusy(true);
    setFailed(false);
    try {
      const trip = await post<{ tripId: string }>('/trips', { language, currency: getCurrency() });
      const message = (first ?? text).trim();
      if (message) handOffFirstMessage(trip.tripId, message);
      router.push(`/trips/${trip.tripId}`);
    } catch {
      setFailed(true);
      setBusy(false);
    }
  }

  return (
    <main className="relative flex h-[100svh] flex-col overflow-hidden bg-[url('/dusk.webp')] bg-cover bg-[position:50%_45%]">
      <div className="flex items-center justify-end gap-2 px-4 py-3">
        {user ? <UserMenu user={user} trips={trips} /> : <LanguageSwitch />}
      </div>

      <div className="mx-auto flex w-full max-w-[760px] min-h-0 flex-1 flex-col justify-center gap-3 p-4">
        {loading ? (
          <p className={`${STATE} flex items-center justify-center gap-2`} role="status">
            <Spinner size={16} />
            {t('state.loading')}
          </p>
        ) : user ? (
          <>
            <form
              className={`${PROMPT} rise`}
              onSubmit={(e) => {
                e.preventDefault();
                if (!busy) void start();
              }}
            >
              <h1 className="sr-only">{t('home.prompt')}</h1>
              <textarea
                className={INPUT}
                rows={2}
                value={text}
                placeholder={t('home.prompt')}
                aria-label={t('home.prompt')}
                disabled={busy}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  // Enter sends; Shift+Enter is a new line.
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (!busy) void start();
                  }
                }}
              />
              <div className="flex items-end justify-end gap-2">
                <button
                  type="submit"
                  className="enabled:hover:bg-accent enabled:hover:border-accent flex h-12 w-12 flex-none items-center justify-center rounded-2xl border border-white/25 bg-white/15 text-white transition-colors disabled:text-white/40"
                  aria-label={t('home.newTrip')}
                  disabled={busy || !text.trim()}
                  aria-busy={busy}
                >
                  {busy ? (
                    <Spinner size={20} />
                  ) : (
                    <ArrowUp size={20} strokeWidth={2.4} aria-hidden="true" />
                  )}
                </button>
              </div>
            </form>

            {/* The chips follow the prompt in, one after another. */}
            <div
              className="noscroll stagger flex gap-2 overflow-x-auto"
              style={{ '--i': 2 } as CSSProperties}
            >
              {SUGGESTION_KEYS.map((key) => (
                <button
                  key={key}
                  type="button"
                  className={CHIP}
                  disabled={busy}
                  onClick={() => void start(t(`home.suggestion.${key}.send`))}
                >
                  {(() => {
                    const Icon = SUGGESTION_ICONS[key];
                    return <Icon size={14} strokeWidth={1.8} aria-hidden="true" />;
                  })()}
                  {t(`home.suggestion.${key}.label`)}
                </button>
              ))}
            </div>
          </>
        ) : (
          <div className="rise">
            <SignInCard />
          </div>
        )}

        {failed && <p className={`${STATE} text-accent`}>{t('state.sendFailed')}</p>}
      </div>
    </main>
  );
}
