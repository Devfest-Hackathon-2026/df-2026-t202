'use client';

import { X } from 'lucide-react';
import { useState } from 'react';
import { post } from '@/lib/api';
import { useT } from '@/lib/i18n';
import type { Plan, Trip } from '@/lib/types';

/** Plain text for LINE: the plan as a message friends can read without opening a link. */
export function planAsText(plan: Plan, t: (key: string) => string): string {
  const lines = [plan.title];
  for (const day of plan.days) {
    lines.push(
      '',
      `■ ${t('plan.day').replace('{n}', String(day.day))}${day.theme ? ` ${day.theme}` : ''}`,
    );
    for (const stop of day.stops) {
      lines.push(
        `${stop.time} ${stop.name}${stop.note ? `（${stop.note.replace(/\n/g, ' ')}）` : ''}`,
      );
      if (stop.leg)
        lines.push(`　↓ ${t(`leg.${stop.leg.mode}`)} ${stop.leg.minutes}${t('time.min')}`);
    }
  }
  return lines.join('\n');
}

/** S5: the share sheet. The MVP link is view only (F5); editor links are F7, stretch. */
export function ShareSheet({
  trip,
  plan,
  onClose,
}: {
  trip: Trip;
  plan: Plan | null;
  onClose: () => void;
}) {
  const t = useT();
  const [shareId, setShareId] = useState<string | null>(trip.shareId ?? null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  const [copied, setCopied] = useState<'link' | 'text' | null>(null);

  const url =
    shareId && typeof window !== 'undefined' ? `${window.location.origin}/s/${shareId}` : null;

  async function createLink() {
    setBusy(true);
    setFailed(false);
    try {
      const result = await post<{ shareId: string }>(`/trips/${trip.id}/share`);
      setShareId(result.shareId);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  }

  async function copy(value: string, what: 'link' | 'text') {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(what);
    } catch {
      setFailed(true);
    }
  }

  return (
    <>
      <button
        type="button"
        className="absolute inset-0 z-70 border-0 bg-black/35 p-0"
        aria-label={t('action.close')}
        onClick={onClose}
      />
      <section
        className="border border-white/15 bg-stone-900/50 bg-clip-padding shadow-[0_24px_60px_rgba(4,12,26,0.45)] backdrop-blur-2xl absolute inset-x-0 bottom-0 z-80 flex flex-col gap-3 rounded-t-2xl p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] desk:inset-x-auto desk:bottom-4 desk:left-4 desk:w-[440px] desk:rounded-2xl"
        role="dialog"
        aria-label={t('share.open')}
      >
        <header className="flex items-center justify-between gap-3">
          <h2 className="m-0 text-base text-white">{t('share.open')}</h2>
          <button
            type="button"
            className="flex h-9 w-9 items-center justify-center rounded-full border-0 bg-white/15 text-white"
            aria-label={t('action.close')}
            onClick={onClose}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        <p className="m-0 text-[13px] leading-[1.6] text-white/70">{t('share.hint')}</p>

        {url ? (
          <>
            <p className="rounded-xl bg-white/10 px-3 py-2.5 text-xs break-all text-white/80">
              {url}
            </p>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                className="bg-accent text-on-accent disabled:bg-line disabled:text-muted min-h-12 rounded-[14px] border-0 text-[15px] font-semibold"
                onClick={() => void copy(url, 'link')}
              >
                {t('share.copyLink')}
              </button>
              {plan && (
                <button
                  type="button"
                  className="min-h-11 rounded-xl border border-white/25 bg-white/10 text-sm text-white"
                  onClick={() => void copy(planAsText(plan, t), 'text')}
                >
                  {t('share.copyText')}
                </button>
              )}
            </div>
          </>
        ) : (
          <div className="flex flex-col gap-2">
            <button
              type="button"
              className="bg-accent text-on-accent disabled:bg-line disabled:text-muted min-h-12 rounded-[14px] border-0 text-[15px] font-semibold"
              disabled={busy}
              onClick={createLink}
            >
              {busy ? t('state.working') : t('share.create')}
            </button>
          </div>
        )}

        {copied && (
          <p className="m-0 text-[13px] text-white/75">
            {t(copied === 'link' ? 'share.linkCopied' : 'share.textCopied')}
          </p>
        )}
        {failed && <p className="m-0 text-[13px] text-white/75">{t('state.sendFailed')}</p>}
      </section>
    </>
  );
}
