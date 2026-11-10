'use client'; // Error boundaries must be Client Components

import { useEffect } from 'react';
import { useT } from '@/lib/i18n';

/**
 * Shown when a page throws while rendering (for example bad data in a plan), instead of a blank
 * screen. Trips live in Firestore, so a reload loses nothing.
 */
export default function ErrorPage({ error }: { error: unknown }) {
  const t = useT();

  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="flex min-h-[100svh] flex-col items-center justify-center gap-3 bg-surface px-4 text-center text-ink">
      <h1 className="m-0 text-lg font-bold">{t('error.pageTitle')}</h1>
      <p className="text-muted-strong m-0 text-sm">{t('error.pageBody')}</p>
      <button
        type="button"
        className="bg-ink min-h-11 rounded-xl border-0 px-5 text-sm font-semibold text-surface"
        onClick={() => window.location.reload()}
      >
        {t('error.reload')}
      </button>
    </main>
  );
}
