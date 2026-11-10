'use client';

// S6: the shared page. View only, no sign-in needed (anonymous auth) — PLAN.md 10.1, 11.1.
import { use, useEffect, useMemo, useState } from 'react';
import { DayTabs } from '@/components/day-tabs';
import { MapCanvas, type MapSelection } from '@/components/map-canvas';
import { MapsProvider } from '@/components/maps-provider';
import { PlanPanel } from '@/components/plan/plan-panel';
import { SpotPanel } from '@/components/plan/spot-panel';
import { BottomSheet, type SheetStop } from '@/components/bottom-sheet';
import { SheetHeader } from '@/components/sheet-header';
import { TripTopBar } from '@/components/trip-top-bar';
import { errorKey, post } from '@/lib/api';
import { signInAsGuest, useAuthUser } from '@/lib/auth';
import { useT } from '@/lib/i18n';
import { usePlan, useTrip } from '@/lib/trip';
import { PANEL_TEXT, PANEL_WRAP, SCREEN } from '../../trips/[tripId]/screen';

export default function SharePage({ params }: { params: Promise<{ shareId: string }> }) {
  const { shareId } = use(params);
  const t = useT();
  const { user, loading: authLoading } = useAuthUser();
  const [tripId, setTripId] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null); // i18n key of the error

  // Sign in anonymously, then join the share: the API adds the viewer to trips.members.
  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      void signInAsGuest().catch(() => setFailed('share.notFound'));
      return;
    }
    let active = true;
    post<{ tripId: string }>(`/shares/${shareId}/join`)
      .then((result) => active && setTripId(result.tripId))
      .catch((e) => {
        // A full share says so; anything else is shown as a missing link.
        const key = errorKey(e);
        if (active) setFailed(key === 'error.share_full' ? key : 'share.notFound');
      });
    return () => {
      active = false;
    };
  }, [authLoading, user, shareId]);

  if (failed) return <p className={PANEL_TEXT}>{t(failed)}</p>;
  if (!tripId) return <p className={PANEL_TEXT}>{t('state.loading')}</p>;
  return <SharedTrip tripId={tripId} />;
}

function SharedTrip({ tripId }: { tripId: string }) {
  const t = useT();
  const { trip, loading: tripLoading, error: tripError } = useTrip(tripId);
  const {
    plan: planDoc,
    loading: planLoading,
    error: planError,
  } = usePlan(tripId, trip?.currentPlanId);

  const [stop, setStop] = useState<SheetStop>('half');
  const [activeDay, setActiveDay] = useState<number | null>(null);
  const [selected, setSelected] = useState<MapSelection>(null);

  const plan = planDoc?.plan ?? null;
  const days = useMemo(() => plan?.days ?? [], [plan]);

  const selectedDay = selected ? days.find((d) => d.day === selected.day) : undefined;

  // Tapping a stop zooms the map to it and opens its Short, or its photo when it has none.
  function openStop(day: number, index: number) {
    setSelected({ day, index });
    setActiveDay(day);
    setStop('peek'); // on a phone the sheet would otherwise sit under the panel
  }

  const title = plan?.title || trip?.slots.dest?.label || t('share.title');

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

        {/* View only: no share button on a shared page. */}
        <TripTopBar name={title} sub={t('share.viewOnly')} />
        {days.length > 0 && (
          <div className="absolute top-3 right-3 z-40 flex items-center gap-2 desk:top-5 desk:right-5">
            <DayTabs
              days={days}
              activeDay={activeDay}
              onDayChange={setActiveDay}
              variant="floating"
            />
          </div>
        )}

        <BottomSheet stop={stop} onStopChange={setStop}>
          <SheetHeader name={title} sub={t('share.viewOnly')} />
          <div className={PANEL_WRAP}>
            <PlanPanel
              trip={trip}
              plan={plan}
              loading={tripLoading || planLoading}
              error={tripError ?? planError}
              activeDay={activeDay}
              onDayChange={setActiveDay}
              onSelectStop={openStop}
              onOpenShorts={openStop}
            />
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
      </main>
    </MapsProvider>
  );
}
