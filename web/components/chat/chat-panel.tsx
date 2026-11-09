'use client';

import { ArrowUp, Check } from 'lucide-react';
import { useEffect, useState } from 'react';
import { post } from '@/lib/api';
import { useT } from '@/lib/i18n';
import { useStickToBottom } from '@/lib/use-stick-to-bottom';
import { STEP_ORDER, type Message, type StepKey, type Trip } from '@/lib/types';
import { CardShell, Messages, TypingBubble, useAwaitingReply, useFirstCardDelay } from './messages';
import { QuestionCard } from './question-card';

const STATE_TEXT = 'px-4 py-2 text-[13px] text-white/70 desk:px-[18px]';

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
  const card = lastAi?.ui ?? null;
  const planning = trip?.status === 'planning';
  const busy = sending || planning;
  const cardKey = `${lastAi?.id}-${card?.type}`;
  const cardDelay = useFirstCardDelay(cardKey, messages.length);
  const typing = useAwaitingReply(messages, sending, failed != null) && !planning;

  // Follow the conversation down as it grows; a new message always brings it back to the bottom.
  const { scroller, content, toBottom } = useStickToBottom<HTMLDivElement, HTMLDivElement>();
  useEffect(() => toBottom(), [messages.length, cardKey, typing, planning, toBottom]);

  async function send(body: Parameters<typeof post>[1]) {
    setSending(true);
    setFailed(null);
    try {
      await post('/trips/' + trip!.id + '/messages', body);
    } catch (e) {
      setFailed(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  async function generate() {
    setSending(true);
    setFailed(null);
    try {
      await post('/trips/' + trip!.id + '/plan');
    } catch (e) {
      setFailed(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  }

  if (loading) return <p className={STATE_TEXT}>{t('state.loading')}</p>;
  if (error) return <p className={`${STATE_TEXT} text-accent`}>{t('state.error')}</p>;
  if (!trip) return <p className={STATE_TEXT}>{t('state.notFound')}</p>;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        className="noscroll flex flex-none gap-1.5 overflow-x-auto px-4 pb-2 desk:px-[18px]"
        aria-label={t('slot.summary')}
      >
        {STEP_ORDER.map((step) => (
          <span
            key={step}
            className={[
              'flex flex-none items-center gap-1 rounded-full border px-3 py-1.5 text-xs whitespace-nowrap',
              trip.slots.status[step] === 'done'
                ? 'border-white/20 bg-white/15 font-semibold text-white'
                : 'border-white/10 bg-transparent text-white/55',
            ].join(' ')}
          >
            {trip.slots.status[step] === 'done' && (
              <Check size={12} strokeWidth={2.6} aria-hidden="true" />
            )}
            {t(`slot.${step}`)}
          </span>
        ))}
      </div>

      <div ref={scroller} className="noscroll min-h-0 flex-1 overflow-y-auto px-4 desk:px-[18px]">
        <div ref={content} className="flex flex-col gap-2.5 pt-4 pb-5">
          {messages.length === 0 && <p className={STATE_TEXT}>{t('state.empty')}</p>}
          <Messages messages={messages} variant="sheet" />
          {card && !planning && (
            <CardShell key={cardKey} leaving={sending} delay={cardDelay}>
              <QuestionCard
                card={card}
                slots={trip.slots}
                disabled={busy}
                onAnswer={(step: StepKey, value: unknown) => send({ type: 'answer', step, value })}
                onGenerate={generate}
              />
            </CardShell>
          )}
          {typing && <TypingBubble variant="sheet" />}
          {planning && (
            <p className={STATE_TEXT}>{t(`plan.progress.${trip.progress ?? 'spots'}`)}</p>
          )}
          {failed && <p className={`${STATE_TEXT} text-accent`}>{t('state.sendFailed')}</p>}
        </div>
      </div>

      <form
        className="flex flex-none gap-2 border-t border-white/15 px-4 pt-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] desk:px-[18px]"
        onSubmit={(e) => {
          e.preventDefault();
          const value = text.trim();
          if (!value || busy) return;
          setText('');
          void send({ type: 'text', text: value });
        }}
      >
        <input
          className="min-h-11 min-w-0 flex-1 rounded-full border border-white/25 bg-white/10 px-3.5 font-inherit text-white placeholder:text-white/50"
          value={text}
          placeholder={t('chat.inputPlaceholder')}
          aria-label={t('chat.input')}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
        />
        <button
          type="submit"
          className="bg-accent text-on-accent disabled:bg-line disabled:text-muted flex h-11 w-11 flex-none items-center justify-center rounded-full border-0"
          aria-label={t('chat.send')}
          disabled={busy || !text.trim()}
        >
          <ArrowUp size={16} strokeWidth={2.4} aria-hidden="true" />
        </button>
      </form>
    </div>
  );
}
