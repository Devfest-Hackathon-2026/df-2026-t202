'use client';

// S8: all of the user's trips as cards with a photo of each place (PLAN.md 10.1). Same dusk photo and
// dark glass as the start screen (web/AGENTS.md glass recipe), so it reads as part of the same app.
import { CalendarDays, ChevronLeft, MapPin, Plus } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { MapsProvider } from '@/components/maps-provider';
import { PlacePhoto } from '@/components/plan/place-photo';
import { GuestNudge, UserMenu } from '@/components/user-menu';
import { useAuthUser } from '@/lib/auth';
import { useLanguage, useT } from '@/lib/i18n';
import { useMyTrips } from '@/lib/trip';
import { tripDates, tripPlace } from '@/lib/trip-format';
import type { Trip } from '@/lib/types';

const GRID = 'grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3';
const GLASS = 'border border-white/15 bg-stone-900/50 backdrop-blur-2xl';
const SHADOW = '[text-shadow:0_1px_6px_rgba(8,24,48,0.45)]';
const NEW_TRIP =
  'text-ink flex min-h-11 items-center gap-1.5 rounded-xl bg-white px-4 text-[14px] font-semibold no-underline shadow-[0_8px_24px_rgba(4,12,26,0.35)] transition-transform hover:-translate-y-px';

export default function TripsPage() {
  const t = useT();
  const router = useRouter();
  const { user, loading: authLoading } = useAuthUser();
  const { trips, loading, error } = useMyTrips(user?.uid);

  useEffect(() => {
    if (!authLoading && !user) router.replace('/'); // the start page has sign-in
  }, [authLoading, user, router]);

  return (
    <MapsProvider>
      <main className="relative isolate min-h-[100svh] text-white">
        {/* The start screen's photo, fixed behind the page, darkened a little so cards and text stay readable. */}
        <div
          aria-hidden="true"
          className="fixed inset-0 -z-10 bg-[url('/dusk.webp')] bg-cover bg-[position:50%_45%]"
        />
        <div
          aria-hidden="true"
          className="fixed inset-0 -z-10 bg-gradient-to-b from-stone-950/35 via-stone-950/10 to-stone-950/55"
        />

        <header className="relative z-40 mx-auto flex max-w-5xl items-center gap-2 px-4 py-3 sm:px-6">
          <Link
            href="/"
            className={`flex min-h-11 items-center gap-1 rounded-xl px-2 text-[14px] text-white no-underline hover:bg-white/10 ${SHADOW}`}
          >
            <ChevronLeft size={18} strokeWidth={1.8} aria-hidden="true" />
            {t('tripsPage.home')}
          </Link>
          <span className="flex-1" />
          {user && <UserMenu user={user} trips={trips} />}
        </header>

        <section className="mx-auto flex max-w-5xl flex-col gap-5 px-4 pt-2 pb-12 sm:px-6">
          <div className="flex items-end justify-between gap-3">
            <div>
              <h1 className={`m-0 text-[28px] font-bold tracking-tight ${SHADOW}`}>
                {t('home.title')}
              </h1>
              {!loading && trips.length > 0 && (
                <p className={`m-0 text-[13px] text-white/80 ${SHADOW}`}>
                  {trips.length === 1
                    ? t('tripsPage.countOne')
                    : t('tripsPage.count').replace('{n}', String(trips.length))}
                </p>
              )}
            </div>
            <Link href="/" className={NEW_TRIP}>
              <Plus size={16} strokeWidth={2.2} aria-hidden="true" />
              {t('home.newTrip')}
            </Link>
          </div>

          {user?.isAnonymous && <GuestNudge className="max-w-md" dark />}

          {authLoading || loading ? (
            <div className={GRID} aria-busy="true" aria-label={t('state.loading')}>
              {[0, 1, 2].map((i) => (
                <div key={i} className={`overflow-hidden rounded-2xl ${GLASS}`}>
                  <div className="aspect-[4/3] animate-pulse bg-white/10" />
                  <div className="flex flex-col gap-2 p-3.5">
                    <div className="h-4 w-2/3 animate-pulse rounded bg-white/15" />
                    <div className="h-3 w-1/3 animate-pulse rounded bg-white/10" />
                  </div>
                </div>
              ))}
            </div>
          ) : error ? (
            <p className={`m-0 rounded-2xl p-4 text-sm ${GLASS}`}>{t('tripsPage.error')}</p>
          ) : trips.length === 0 ? (
            <div className={`flex max-w-md flex-col items-start gap-3 rounded-2xl p-6 ${GLASS}`}>
              <MapPin size={22} strokeWidth={1.8} className="text-white/80" aria-hidden="true" />
              <p className="m-0 text-[16px] font-semibold">{t('tripsPage.emptyTitle')}</p>
              <p className="m-0 text-[13px] text-white/75">{t('tripsPage.emptyBody')}</p>
              <Link href="/" className={NEW_TRIP}>
                <Plus size={16} strokeWidth={2.2} aria-hidden="true" />
                {t('home.newTrip')}
              </Link>
            </div>
          ) : (
            <ul className={`${GRID} m-0 list-none p-0`}>
              {trips.map((trip) => (
                <li key={trip.id}>
                  <TripCard
                    trip={trip}
                    viewer={user ? trip.members[user.uid] === 'viewer' : false}
                  />
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </MapsProvider>
  );
}

function TripCard({ trip, viewer }: { trip: Trip; viewer: boolean }) {
  const t = useT();
  const language = useLanguage();
  const place = tripPlace(trip, t);
  const dates = tripDates(trip, language, t);

  return (
    <Link
      href={`/trips/${trip.id}`}
      className={`group block overflow-hidden rounded-2xl text-white no-underline shadow-[0_12px_32px_rgba(4,12,26,0.35)] transition-transform duration-200 hover:-translate-y-0.5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white ${GLASS}`}
    >
      <PlacePhoto
        placeId={trip.slots.dest?.placeId}
        className="aspect-[4/3] w-full bg-white/5"
        height={480}
        credit
        fallback={
          // No photo (older trips, or Maps unavailable): a soft glass panel with the place's initial.
          <span className="relative flex aspect-[4/3] w-full items-center justify-center overflow-hidden bg-gradient-to-br from-white/25 via-white/10 to-white/0">
            <span className="text-[56px] font-bold text-white/85 [text-shadow:0_2px_12px_rgba(8,24,48,0.4)]">
              {place.trim()[0]?.toUpperCase()}
            </span>
            <MapPin
              size={18}
              strokeWidth={1.8}
              className="absolute bottom-3 left-3 text-white/60"
              aria-hidden="true"
            />
          </span>
        }
      />
      <div className="flex flex-col gap-1.5 p-3.5">
        <span className="truncate text-[17px] font-semibold">{place}</span>
        <span className="flex items-center gap-1.5 text-[13px] text-white/75">
          <CalendarDays size={14} strokeWidth={1.8} aria-hidden="true" />
          {dates ?? t('tripsPage.datesNotSet')}
        </span>
        <span className="flex flex-wrap gap-1.5 pt-0.5">
          <span
            className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
              trip.status === 'ready'
                ? 'text-ink bg-white'
                : trip.status === 'error'
                  ? 'bg-accent text-on-accent'
                  : 'bg-white/15 text-white'
            }`}
          >
            {t(`status.${trip.status}`)}
          </span>
          {viewer && (
            <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-[11px] font-medium text-white">
              {t('tripsPage.shared')}
            </span>
          )}
        </span>
      </div>
    </Link>
  );
}
