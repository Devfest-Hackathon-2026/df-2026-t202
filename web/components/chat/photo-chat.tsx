'use client';

import { ArrowUp, Pencil } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { QuestionCard } from '@/components/chat/question-card';
import {
  CardShell,
  Messages,
  TypingBubble,
  useAwaitingReply,
  useFirstCardDelay,
} from '@/components/chat/messages';
import { LanguageNote } from '@/components/language-note';
import { PlanProgress } from '@/components/plan/plan-panel';
import { useT } from '@/lib/i18n';
import { takeFirstMessage } from '@/lib/first-message';
import { useChatActions } from '@/lib/use-chat';
import { useStickToBottom } from '@/lib/use-stick-to-bottom';
import {
  STEP_ORDER,
  type Message,
  type StepKey,
  type Trip,
  type UiCard,
  type UiType,
} from '@/lib/types';

/**
 * The conversation on the start screen, over the dusk photo (PLAN.md 10.1 S1).
 * The map screen only opens once the plan exists.
 */
export function PhotoChat({ trip, messages }: { trip: Trip; messages: Message[] }) {
  const t = useT();
  const [text, setText] = useState('');
  const { send, generate, sending, failed } = useChatActions(trip.id);

  // The sentence typed on the home screen: shown at once as our bubble, then sent from here.
  const [pending, setPending] = useState<string | null>(null);
  useEffect(() => {
    const first = takeFirstMessage(trip.id);
    if (!first) return;
    setPending(first);
    void send({ type: 'text', text: first });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when the trip opens
  }, [trip.id]);
  // Swap the stand-in bubble for the real message the moment it arrives from Firestore.
  const delivered =
    pending != null && messages.some((m) => m.role === 'user' && m.text === pending);
  useEffect(() => {
    if (delivered) setPending(null);
  }, [delivered]);

  const lastAi = [...messages].reverse().find((m) => m.role === 'ai');
  const serverCard = lastAi?.ui ?? null;

  // Every card the server has shown, so an earlier step can be re-opened with its own options.
  const asked = useMemo(() => {
    const seen = new Map<UiType, UiCard>();
    for (const message of messages) if (message.ui) seen.set(message.ui.type, message.ui);
    return seen;
  }, [messages]);

  // "Back" shows an earlier card; a new turn from the server clears it.
  const [back, setBack] = useState<UiType | null>(null);
  // Places picked inside a broad destination, handed to the must-see card when it appears.
  const [plannedMusts, setPlannedMusts] = useState<string[]>([]);
  useEffect(() => setBack(null), [messages.length]);

  // Sending an answer leaves the "back" state: re-answering with the same value writes no new
  // message, so waiting for the transcript to grow would strand the user on the old card.
  const answer = (step: StepKey, value: unknown) => {
    setBack(null);
    return send({ type: 'answer', step, value });
  };

  const card = (back && asked.get(back)) || serverCard;
  // The nearest earlier step the server actually showed a card for. Steps answered in free
  // text never had one, so they are skipped rather than shown without their options.
  const stepIndex =
    card?.type === 'ready' ? STEP_ORDER.length : STEP_ORDER.indexOf(card?.type as StepKey);
  const previous = STEP_ORDER.slice(0, Math.max(stepIndex, 0))
    .reverse()
    .find((step) => asked.has(step));
  const planning = trip.status === 'planning';
  const busy = sending || planning;
  const typing = useAwaitingReply(messages, sending || pending != null, failed) && !planning;
  const cardKey = `${lastAi?.id}-${back ?? ''}-${card?.type}`;
  const cardDelay = useFirstCardDelay(cardKey, messages.length);

  // Follow the conversation down as it grows; a new message always brings it back to the bottom.
  const { scroller, content, toBottom } = useStickToBottom<HTMLDivElement, HTMLDivElement>();
  useEffect(() => toBottom(), [messages.length, cardKey, typing, planning, toBottom]);

  function submit() {
    const value = text.trim();
    if (!value || busy) return;
    setText('');
    void send({ type: 'text', text: value });
  }

  return (
    <div className="mx-auto flex w-full max-w-[760px] min-h-0 flex-1 flex-col gap-3 px-4">
      <div
        ref={scroller}
        // Wider than the column (negative margin + padding), so card shadows fade out instead of being cut.
        className="noscroll -mx-8 min-h-0 flex-1 overflow-y-auto px-8"
      >
        <div
          ref={content}
          className="flex flex-col justify-start gap-3 pt-6 pb-[calc(2rem+env(safe-area-inset-bottom))]"
        >
          <LanguageNote tripLanguage={trip.language} />
          <Messages messages={messages} variant="photo" />
          {pending && !delivered && (
            <p className="text-ink rise max-w-[85%] self-end rounded-[18px_18px_4px_18px] border border-white/60 bg-white/55 px-3.5 py-2 text-[15px] leading-[1.6] whitespace-pre-line backdrop-blur-xl">
              {pending}
            </p>
          )}
          {card && !busy && back && (
            <p className="m-0 flex w-fit items-center gap-1.5 rounded-full border border-white/20 bg-white/15 px-3 py-1.5 text-[12px] text-white backdrop-blur-xl">
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
                onBack={previous ? () => setBack(previous) : undefined}
                onPlanMusts={setPlannedMusts}
                plannedMusts={plannedMusts}
                onEdit={(step) => setBack(step)}
                onAnswer={answer}
                onGenerate={() => {
                  setBack(null);
                  return generate();
                }}
              />
            </CardShell>
          )}
          {typing && <TypingBubble variant="photo" />}
          {planning && (
            <div className="rise rounded-2xl border border-white/15 bg-stone-900/50 p-4 backdrop-blur-2xl">
              <PlanProgress progress={trip.progress ?? 'spots'} />
            </div>
          )}
          {failed && <p className="text-accent m-0 text-[13px]">{t('state.sendFailed')}</p>}
        </div>
      </div>

      {!card && (
        <form
          className="mb-4 flex flex-none flex-col gap-3 rounded-2xl border border-white/15 bg-stone-900/50 bg-clip-padding p-5 shadow-[0_24px_60px_rgba(4,12,26,0.45)] backdrop-blur-2xl"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <textarea
            className="w-full resize-none border-0 bg-transparent p-0 text-[17px] leading-snug text-white outline-none placeholder:text-white/75 [text-shadow:0_1px_6px_rgba(8,24,48,0.45)]"
            rows={2}
            value={text}
            placeholder={t('chat.inputPlaceholder')}
            aria-label={t('chat.input')}
            disabled={busy}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              // Enter sends; Shift+Enter is a new line.
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
          />
          <div className="flex items-end justify-end gap-2">
            <button
              type="submit"
              className="enabled:hover:bg-accent enabled:hover:border-accent flex h-12 w-12 flex-none items-center justify-center rounded-2xl border border-white/25 bg-white/15 text-white transition-colors disabled:text-white/40"
              aria-label={t('chat.send')}
              disabled={busy || !text.trim()}
            >
              <ArrowUp size={20} strokeWidth={2.4} aria-hidden="true" />
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
