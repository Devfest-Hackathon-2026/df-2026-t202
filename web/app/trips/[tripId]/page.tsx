'use client';

// One trip, two phases (PLAN.md 10.1):
//   while the chat is collecting conditions, the conversation sits over the start photo;
//   once a plan exists, the map takes the screen and the sheet holds the chat and itinerary.
import { use, useMemo, useState } from 'react';
import { BottomSheet, type SheetStop } from '@/components/bottom-sheet';
import { ChatPanel } from '@/components/chat/chat-panel';
import { PhotoChat } from '@/components/chat/photo-chat';
import { DayTabs } from '@/components/day-tabs';
import { MapCanvas, type MapSelection } from '@/components/map-canvas';
import { MapsProvider } from '@/components/maps-provider';
import { PlanPanel } from '@/components/plan/plan-panel';
import { SpotPanel } from '@/components/plan/spot-panel';
import { ShareSheet } from '@/components/share-sheet';
import { SheetHeader } from '@/components/sheet-header';
import { SheetTabs, type SheetTab } from '@/components/sheet-tabs';
import { TripTopBar } from '@/components/trip-top-bar';
import { UserMenu } from '@/components/user-menu';
import { useAuthUser } from '@/lib/auth';
import { useT } from '@/lib/i18n';
import { useMessages, useMyTrips, usePlan, useTrip } from '@/lib/trip';
import { PANEL_TEXT, PANEL_WRAP, SCREEN } from './screen';

export default function TripPage({ params }: { params: Promise<{ tripId: string }> }) {
  const { tripId } = use(params);
  const t = useT();
  const { user, loading: authLoading } = useAuthUser();
  const { trips } = useMyTrips(user?.uid);
  const { trip, loading: tripLoading, error: tripError } = useTrip(tripId);
  const { messages, loading: messagesLoading, error: messagesError } = useMessages(tripId);
  const {
    plan: planDoc,
    loading: planLoading,
    error: planError,
  } = usePlan(tripId, trip?.currentPlanId);

  const [stop, setStop] = useState<SheetStop>('half');
  const [tab, setTab] = useState<SheetTab>('plan');
  const [activeDay, setActiveDay] = useState<number | null>(null);
  const [selected, setSelected] = useState<MapSelection>(null);
  const [sharing, setSharing] = useState(false);

  const plan = planDoc?.plan ?? null;
  const days = useMemo(() => plan?.days ?? [], [plan]);

  const selectedDay = selected ? days.find((d) => d.day === selected.day) : undefined;

  // Tapping a stop zooms the map to it and opens its Short, or its photo when it has none.
  function openStop(day: number, index: number) {
    setSelected({ day, index });
    setActiveDay(day);
  }

  if (authLoading || tripLoading || messagesLoading) {
    return <p className={PANEL_TEXT}>{t('state.loading')}</p>;
  }
  if (tripError || messagesError) return <p className={PANEL_TEXT}>{t('state.error')}</p>;
  if (!user) return <p className={PANEL_TEXT}>{t('auth.signInNeeded')}</p>;
  if (!trip) return <p className={PANEL_TEXT}>{t('state.notFound')}</p>;

  // ---- Phase 1: still collecting conditions, or building the plan ----
  if (!trip.currentPlanId) {
    return (
      <main className="relative flex h-[100svh] flex-col bg-[url('/dusk.webp')] bg-cover bg-[position:50%_45%]">
        <header className="flex flex-none items-center justify-end gap-2 px-4 py-3">
          <UserMenu user={user} trips={trips} />
        </header>
        <PhotoChat trip={trip} messages={messages} />
      </main>
    );
  }

  // ---- Phase 2: the plan exists, so the map takes over ----
  return (
    <MapsProvider>
      <main className={SCREEN}>
        <MapCanvas
          days={days}
          activeDay={activeDay}
          selected={selected}
          onSelect={(next) => next && openStop(next.day, next.index)}
          bottomInset={240}
        />

        <TripTopBar
          name={plan?.title || trip.slots.dest?.label || t('trip.untitled')}
          sub={t(`status.${trip.status}`)}
          onShare={() => setSharing(true)}
        />

        {/* One row at the top right: the day switcher, then the account button (the trips list,
          the language, and the way home). */}
        <div className="absolute top-3 right-3 z-40 flex items-center gap-2 desk:top-5 desk:right-5">
          {days.length > 0 && (
            <DayTabs
              days={days}
              activeDay={activeDay}
              onDayChange={setActiveDay}
              variant="floating"
            />
          )}
          <UserMenu user={user} trips={trips} />
        </div>

        <BottomSheet stop={stop} onStopChange={setStop}>
          <SheetHeader
            name={plan?.title || trip.slots.dest?.label || t('trip.untitled')}
            sub={t(`status.${trip.status}`)}
            onShare={() => setSharing(true)}
          />
          <SheetTabs tab={tab} onTabChange={setTab} />
          <div
            className={PANEL_WRAP}
            role="tabpanel"
            id={`sheet-panel-${tab}`}
            aria-labelledby={`sheet-tab-${tab}`}
          >
            {tab === 'chat' ? (
              <ChatPanel trip={trip} messages={messages} loading={false} error={null} />
            ) : (
              <PlanPanel
                trip={trip}
                plan={plan}
                loading={planLoading}
                error={planError}
                activeDay={activeDay}
                onDayChange={setActiveDay}
                onSelectStop={openStop}
                onOpenShorts={openStop}
                onShare={() => setSharing(true)}
              />
            )}
          </div>
        </BottomSheet>

        {selected && (
          <SpotPanel
            days={days}
            selected={selected}
            onSelect={(next) => openStop(next.day, next.index)}
            onClose={() => setSelected(null)}
          />
        )}

        {sharing && <ShareSheet trip={trip} plan={plan} onClose={() => setSharing(false)} />}
      </main>
    </MapsProvider>
  );
}
