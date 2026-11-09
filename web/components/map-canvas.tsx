'use client';

import { Map, Marker, Polyline, useMap } from '@vis.gl/react-google-maps';
import { useEffect } from 'react';
import { env } from '@/lib/env';
import { useT } from '@/lib/i18n';
import type { Day, Stop } from '@/lib/types';

/** Kyushu, the demo region. Used until the trip has places of its own. */
const DEFAULT_CENTER = { lat: 32.9, lng: 130.8 };
const DEFAULT_ZOOM = 7;

/** One color per day, matching --day-1..7 in globals.css. */
const DAY_COLORS = ['#d9443b', '#2563eb', '#059669', '#b45309', '#7c3aed', '#db2777', '#0f766e'];

export function dayColor(day: number): string {
  return DAY_COLORS[(day - 1) % DAY_COLORS.length];
}

export type MapSelection = { day: number; index: number } | null;

function located(stop: Stop): stop is Stop & { lat: number; lng: number } {
  return typeof stop.lat === 'number' && typeof stop.lng === 'number';
}

/**
 * The map fills the screen; the sheet sits over it (PLAN.md 10.1).
 * The Maps JavaScript API fixes its language when the script loads, so the page reloads
 * after a language change (PLAN.md 10.3).
 */
export function MapCanvas({
  days = [],
  activeDay,
  selected,
  onSelect,
  bottomInset = 0,
}: {
  days?: Day[];
  activeDay?: number | null;
  selected?: MapSelection;
  onSelect?: (selection: MapSelection) => void;
  bottomInset?: number;
}) {
  const t = useT();

  if (!env.mapsBrowserKey) {
    return (
      <div className="bg-map-land absolute inset-0">
        <p className="text-muted-strong absolute inset-x-0 top-[76px] m-0 px-6 text-center text-[13px]">
          {t('map.noKey')}
        </p>
      </div>
    );
  }

  return (
    <div className="bg-map-water absolute inset-0">
      <Map
        defaultCenter={DEFAULT_CENTER}
        defaultZoom={DEFAULT_ZOOM}
        gestureHandling="greedy"
        disableDefaultUI
        style={{ width: '100%', height: '100%' }}
      >
        <Routes days={days} activeDay={activeDay} selected={selected} onSelect={onSelect} />
        <FitToDays
          days={days}
          activeDay={activeDay}
          selected={selected}
          bottomInset={bottomInset}
        />
      </Map>
    </div>
  );
}

function Routes({
  days,
  activeDay,
  selected,
  onSelect,
}: {
  days: Day[];
  activeDay?: number | null;
  selected?: MapSelection;
  onSelect?: (selection: MapSelection) => void;
}) {
  return (
    <>
      {days.map((day, dayIndex) => {
        const dimmed = activeDay != null && activeDay !== day.day;
        const color = dayColor(day.day);
        // The plan has no leg from the last stop of a day to the first stop of the next one
        // (PLAN.md 7.3), so the overnight move is drawn dashed, in the arriving day's colour.
        const previousDay = days[dayIndex - 1];
        const from = previousDay?.stops[previousDay.stops.length - 1];
        const to = day.stops[0];

        return (
          <div key={day.day}>
            {/* One line per leg. The Routes API gives a polyline for most of them; a ferry or a
                flight has none (leg.estimate), so those are drawn as a dashed straight line
                rather than left as a gap in the route. */}
            {from && to && located(from) && located(to) && (
              <Polyline
                path={[
                  { lat: from.lat, lng: from.lng },
                  { lat: to.lat, lng: to.lng },
                ]}
                strokeOpacity={0}
                icons={[
                  {
                    icon: {
                      path: 'M 0,-1 0,1',
                      strokeColor: color,
                      strokeOpacity: dimmed ? 0.25 : 0.7,
                      strokeWeight: dimmed ? 2 : 3,
                      scale: 3,
                    },
                    offset: '0',
                    repeat: '14px',
                  },
                ]}
              />
            )}
            {day.stops.map((stop, index) => {
              const leg = stop.leg;
              const next = day.stops[index + 1];
              if (!leg) return null;

              if (leg.polyline) {
                return (
                  <Polyline
                    key={`${day.day}-${index}`}
                    encodedPath={leg.polyline}
                    strokeColor={color}
                    strokeWeight={dimmed ? 2 : 4}
                    strokeOpacity={dimmed ? 0.25 : 0.9}
                  />
                );
              }

              if (!located(stop) || !next || !located(next)) return null;
              return (
                <Polyline
                  key={`${day.day}-${index}`}
                  path={[
                    { lat: stop.lat, lng: stop.lng },
                    { lat: next.lat, lng: next.lng },
                  ]}
                  strokeOpacity={0}
                  icons={[
                    {
                      icon: {
                        path: 'M 0,-1 0,1',
                        strokeColor: color,
                        strokeOpacity: dimmed ? 0.3 : 0.9,
                        strokeWeight: dimmed ? 2 : 3,
                        scale: 3,
                      },
                      offset: '0',
                      repeat: '14px',
                    },
                  ]}
                />
              );
            })}
            {day.stops.map((stop, index) =>
              located(stop) ? (
                <Marker
                  key={stop.id}
                  position={{ lat: stop.lat, lng: stop.lng }}
                  title={stop.name}
                  opacity={dimmed ? 0.35 : 1}
                  zIndex={selected?.day === day.day && selected.index === index ? 10 : 1}
                  label={{
                    text: String(index + 1),
                    color: '#ffffff',
                    fontSize: '11px',
                    fontWeight: '700',
                  }}
                  icon={{
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: selected?.day === day.day && selected.index === index ? 14 : 11,
                    fillColor: color,
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: 2.5,
                  }}
                  onClick={() => onSelect?.({ day: day.day, index })}
                />
              ) : null,
            )}
          </div>
        );
      })}
    </>
  );
}

/** Keeps the route in the part of the map the sheet does not cover. */
function FitToDays({
  days,
  activeDay,
  selected,
  bottomInset,
}: {
  days: Day[];
  activeDay?: number | null;
  selected?: MapSelection;
  bottomInset: number;
}) {
  const map = useMap();

  useEffect(() => {
    if (!map) return;
    const shown = activeDay != null ? days.filter((d) => d.day === activeDay) : days;
    const points = shown.flatMap((day) => day.stops.filter(located));
    if (points.length === 0) return;

    if (selected) {
      const day = days.find((d) => d.day === selected.day);
      const stop = day?.stops[selected.index];
      if (stop && located(stop)) {
        // Close in on the place, so its surroundings are readable (not just "somewhere in Kyushu").
        map.panTo({ lat: stop.lat, lng: stop.lng });
        map.setZoom(15);
        return;
      }
    }

    const bounds = new google.maps.LatLngBounds();
    for (const stop of points) bounds.extend({ lat: stop.lat, lng: stop.lng });
    map.fitBounds(bounds, { top: 80, left: 32, right: 32, bottom: bottomInset + 24 });
  }, [map, days, activeDay, selected, bottomInset]);

  return null;
}
