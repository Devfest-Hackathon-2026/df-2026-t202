'use client';

import { useMapsLibrary } from '@vis.gl/react-google-maps';
import { ImageOff } from 'lucide-react';
import { useEffect, useState, type ReactNode } from 'react';

type Photo = { url: string; credit: string | null } | null;

/** Photos are fetched once per place id and size, and kept for the session. */
const cache = new Map<string, Photo>();

/**
 * The place's own photo from Google Maps. One Place Details call per place, asking only for
 * `photos` (PLAN.md budget: minimal field masks). Must be inside MapsProvider.
 *
 * `height`: the size to ask Google for (px). `credit`: show the photographer's name, which
 * Google requires wherever a Places photo is shown large. `fallback`: shown with no photo.
 */
export function PlacePhoto({
  placeId,
  className,
  height = 256,
  credit = false,
  fallback,
}: {
  placeId?: string | null;
  className?: string;
  height?: number;
  credit?: boolean;
  fallback?: ReactNode;
}) {
  const places = useMapsLibrary('places');
  const key = placeId ? `${placeId}:${height}` : '';
  const [photo, setPhoto] = useState<Photo>(key ? (cache.get(key) ?? null) : null);

  useEffect(() => {
    if (!places || !key || cache.has(key)) {
      if (key && cache.has(key)) setPhoto(cache.get(key) ?? null);
      return;
    }
    let active = true;
    (async () => {
      try {
        const place = new places.Place({ id: placeId! });
        await place.fetchFields({ fields: ['photos'] });
        const first = place.photos?.[0];
        const found: Photo = first
          ? {
              url: first.getURI({ maxHeight: height }),
              credit: first.authorAttributions?.[0]?.displayName ?? null,
            }
          : null;
        cache.set(key, found);
        if (active) setPhoto(found);
      } catch {
        cache.set(key, null); // no photo, or the lookup failed: show the placeholder
      }
    })();
    return () => {
      active = false;
    };
  }, [places, key, placeId, height]);

  if (!photo) {
    return (
      fallback ?? (
        <span className={`${className} flex items-center justify-center text-white/35`}>
          <ImageOff size={16} strokeWidth={1.6} aria-hidden="true" />
        </span>
      )
    );
  }
  return (
    <span className={`${className} relative block overflow-hidden`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={photo.url} alt="" loading="lazy" className="h-full w-full object-cover" />
      {credit && photo.credit && (
        <span className="absolute right-1.5 bottom-1 max-w-[70%] truncate rounded bg-black/45 px-1.5 py-0.5 text-[10px] text-white/90">
          © {photo.credit}
        </span>
      )}
    </span>
  );
}
