'use client';

import { ArrowUp, Check, Pencil } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { MAX_TEXT_LENGTH, errorKey, post } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { useStickToBottom } from '@/lib/use-stick-to-bottom';
import {
  STEP_ORDER,
  type Message,
  type StepKey,
  type Trip,
  type UiCard,
  type UiType,
} from '@/lib/types';
import { CardShell, Messages, TypingBubble, useAwaitingReply, useFirstCardDelay } from './messages';
import { QuestionCard } from './question-card';

const STATE_TEXT = 'px-4 py-2 text-[14px] text-muted-strong desk:px-5';

/**
 * S1 chat + S2 slot chips. The server decides the next card; this only renders it
 * and posts answers back (PLAN.md 8.1, 14 rule 5).
 */
export function ChatPanel({
  trip,
  messages,
  loading,
  error,
}: {
  trip: Trip | null;
  messages: Message[];
  loading: boolean;
  error: Error | null;
}) {
  const t = useT();
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  const lastAi = [...messages].reverse().find((m) => m.role === 'ai');

  // Every card the server has shown, so a condition can be re-opened with its own options.
  const asked = useMemo(() => {
    const seen = new Map<UiType, UiCard>();
    for (const message of messages) if (message.ui) seen.set(message.ui.type, message.ui);
    return seen;
  }, [messages]);
  // Tapping a summary chip or a "Your trip" row shows that step's card; a new turn clears it.
  const [back, setBack] = useState<StepKey | null>(null);
  useEffect(() => setBack(null), [messages.length]);

  const card: UiCard | null = back
    ? (asked.get(back) ?? { type: back, options: [] })
    : (lastAi?.ui ?? null);
  const planning = trip?.status === 'planning';
  const busy = sending || planning;
  const hasPlan = Boolean(trip?.currentPlanId);
  const cardKey = `${lastAi?.id}-${back ?? ''}-${card?.type}`;
  const cardDelay = useFirstCardDelay(cardKey, messages.length);
  const typing = useAwaitingReply(messages, sending, failed != null) && !planning;

  // Follow the conversation down as it grows; a new message always brings it back to the bottom.
  const { scroller, content, toBottom } = useStickToBottom<HTMLDivElement, HTMLDivElement>();
  useEffect(() => toBottom(), [messages.length, cardKey, typing, planning, toBottom]);

  async function send(body: Parameters<typeof post>[1]) {
    setBack(null); // re-answering with the same value writes no message: don't strand the user on the old card
    setSending(true);
    setFailed(null);
    try {
      await post('/trips/' + trip!.id + '/messages', body);
    } catch (e) {
      setFailed(errorKey(e));
    } finally {
      setSending(false);
    }
  }

  async function generate() {
    setBack(null);
    setSending(true);
    setFailed(null);
    try {
      await post('/trips/' + trip!.id + '/plan');
    } catch (e) {
      setFailed(errorKey(e));
    } finally {
      setSending(false);
    }
  }

  if (loading) return <p className={STATE_TEXT}>{t('state.loading')}</p>;
  if (error) return <p className={`${STATE_TEXT} text-accent`}>{t('state.error')}</p>;
  if (!trip) return <p className={STATE_TEXT}>{t('state.notFound')}</p>;

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-transparent pt-1 text-ink">
      <div
        className="noscroll flex flex-none gap-1.5 overflow-x-auto border-b border-line-soft px-4 pb-3 desk:px-5"
        aria-label={t('slot.summary')}
      >
        {STEP_ORDER.map((step) => (
          <button
            key={step}
            type="button"
            className={[
              'flex min-h-11 flex-none items-center gap-1 rounded-full border px-3 text-xs whitespace-nowrap transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:opacity-60',
              back === step
                ? 'border-ink bg-fill font-semibold text-ink'
                : trip.slots.status[step] === 'done'
                  ? 'border-line-soft bg-fill-soft font-medium text-ink hover:bg-fill'
                  : 'border-line-soft bg-surface text-muted-strong hover:bg-fill-soft',
            ].join(' ')}
            aria-label={t('card.ready.edit').replace('{what}', t(`slot.${step}`))}
            aria-pressed={back === step}
            disabled={busy}
            onClick={() => setBack(back === step ? null : step)}
          >
            {trip.slots.status[step] === 'done' && (
              <Check size={12} strokeWidth={2.6} aria-hidden="true" />
            )}
            {t(`slot.${step}`)}
          </button>
        ))}
      </div>

      <div ref={scroller} className="noscroll min-h-0 flex-1 overflow-y-auto px-4 desk:px-5">
        <div ref={content} className="flex flex-col gap-3 pt-5 pb-5">
          {messages.length === 0 && <p className={STATE_TEXT}>{t('state.empty')}</p>}
          <Messages messages={messages} variant="sheet" />
          {card && !busy && back && (
            <p className="m-0 flex w-fit items-center gap-1.5 rounded-full border border-line-soft bg-fill-soft px-3 py-1.5 text-[12px] text-muted-strong">
              <Pencil size={13} strokeWidth={1.8} aria-hidden="true" />
              {t('card.editing').replace('{what}', t(`slot.${back}`))}
            </p>
          )}
          {card && !planning && (
            <CardShell key={cardKey} leaving={sending} delay={cardDelay}>
              <QuestionCard
                card={card}
                slots={trip.slots}
                disabled={busy}
                onBack={back ? () => setBack(null) : undefined}
                onEdit={(step) => setBack(step)}
                onAnswer={(step: StepKey, value: unknown) => send({ type: 'answer', step, value })}
                onGenerate={generate}
                hasPlan={hasPlan}
                pendingEdits={trip.pendingEdits}
              />
            </CardShell>
          )}
          {typing && <TypingBubble variant="sheet" />}
          {planning && (
            <p className={STATE_TEXT}>
              {hasPlan ? t('plan.updatingNow') : t(`plan.progress.${trip.progress ?? 'spots'}`)}
            </p>
          )}
          {failed && <p className={`${STATE_TEXT} text-accent`}>{t(failed)}</p>}
        </div>
      </div>

      <form
        className="flex flex-none gap-2 border-t border-line-soft bg-surface/90 backdrop-blur-xl px-4 pt-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] desk:px-5"
        onSubmit={(e) => {
          e.preventDefault();
          const value = text.trim();
          if (!value || busy) return;
          setText('');
          void send({ type: 'text', text: value });
        }}
      >
        <input
          className="min-h-11 min-w-0 flex-1 rounded-xl border border-line bg-fill-soft px-3.5 text-[15px] font-inherit text-ink placeholder:text-muted-strong focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          value={text}
          maxLength={MAX_TEXT_LENGTH}
          placeholder={t('chat.inputPlaceholder')}
          aria-label={t('chat.input')}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
        />
        <button
          type="submit"
          className="bg-accent text-on-accent disabled:bg-line disabled:text-muted flex h-11 w-11 flex-none items-center justify-center rounded-xl border-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          aria-label={t('chat.send')}
          disabled={busy || !text.trim()}
        >
          <ArrowUp size={16} strokeWidth={2.4} aria-hidden="true" />
        </button>
      </form>
    </div>
  );
}
