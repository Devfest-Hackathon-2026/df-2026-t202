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

/**
 * A pale, quiet base map so the coloured day routes are what you see first:
 * no points of interest or transit icons, soft land and water, lighter labels and roads.
 */
const QUIET_MAP: google.maps.MapTypeStyle[] = [
  { featureType: 'poi', stylers: [{ visibility: 'off' }] },
  { featureType: 'transit', stylers: [{ visibility: 'off' }] },
  { featureType: 'road', elementType: 'labels.icon', stylers: [{ visibility: 'off' }] },
  { featureType: 'landscape', stylers: [{ color: '#eeeeea' }] },
  { featureType: 'water', stylers: [{ color: '#cfe1ea' }] },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#ffffff' }, { lightness: 20 }],
  },
  { featureType: 'road.highway', elementType: 'geometry', stylers: [{ color: '#f6f6f2' }] },
  {
    featureType: 'administrative',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#d6d6d0' }],
  },
  { elementType: 'labels.text.fill', stylers: [{ color: '#8a8a86' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#ffffff' }, { weight: 3 }] },
];

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
        styles={QUIET_MAP}
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
        const weight = dimmed ? 3 : 5;
        const opacity = dimmed ? 0.2 : 0.9;
        // The plan has no leg from the last stop of a day to the first stop of the next one
        // (PLAN.md 7.3); that overnight move is drawn in the leaving day's colour, so the trip
        // reads as one continuous line.
        const previousDay = days[dayIndex - 1];
        const from = previousDay?.stops[previousDay.stops.length - 1];
        const to = day.stops[0];
        const showOvernight = activeDay == null;

        return (
          <div key={day.day}>
            {showOvernight && from && to && located(from) && located(to) && (
              <Polyline
                path={[
                  { lat: from.lat, lng: from.lng },
                  { lat: to.lat, lng: to.lng },
                ]}
                strokeColor={dayColor(previousDay.day)}
                strokeWeight={5}
                strokeOpacity={0.9}
                zIndex={1}
              />
            )}
            {day.stops.map((stop, index) => {
              const leg = stop.leg;
              const next = day.stops[index + 1];
              if (!leg) return null;
              // A real route from the Routes API follows the road. Train, ferry and flight legs
              // have none (Routes has no transit data for Japan), so they are a straight line.
              if (leg.polyline) {
                return (
                  <Polyline
                    key={`${day.day}-${index}`}
                    encodedPath={leg.polyline}
                    strokeColor={color}
                    strokeWeight={weight}
                    strokeOpacity={opacity}
                    zIndex={dimmed ? 1 : 2}
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
                  strokeColor={color}
                  strokeWeight={weight}
                  strokeOpacity={opacity}
                  zIndex={dimmed ? 1 : 2}
                />
              );
            })}
            {day.stops.map((stop, index) => {
              if (!located(stop)) return null;
              const isSelected = selected?.day === day.day && selected.index === index;
              return (
                <Marker
                  key={stop.id}
                  position={{ lat: stop.lat, lng: stop.lng }}
                  title={stop.name}
                  opacity={dimmed ? 0.35 : 1}
                  zIndex={isSelected ? 1000 : dimmed ? 1 : 100 - index}
                  label={{
                    text: String(index + 1),
                    color: '#ffffff',
                    fontSize: isSelected ? '13px' : '11px',
                    fontWeight: '700',
                  }}
                  icon={{
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: isSelected ? 15 : 11,
                    fillColor: color,
                    fillOpacity: 1,
                    strokeColor: '#ffffff',
                    strokeWeight: isSelected ? 3.5 : 2.5,
                  }}
                  onClick={() => onSelect?.({ day: day.day, index })}
                />
              );
            })}
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
