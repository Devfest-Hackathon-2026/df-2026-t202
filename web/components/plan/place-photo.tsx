'use client';

import { useMapsLibrary } from '@vis.gl/react-google-maps';
import { ImageOff } from 'lucide-react';
import { useEffect, useState } from 'react';

/** Photo URLs are fetched once per place id and kept for the session. */
const cache = new Map<string, string | null>();

/**
 * The spot's own photo from Google Maps, for stops with no Short. One Place Details call per
 * stop, asking only for `photos` (PLAN.md budget: minimal field masks).
 */
export function PlacePhoto({
  placeId,
  className,
}: {
  placeId?: string | null;
  className?: string;
}) {
  const places = useMapsLibrary('places');
  const [url, setUrl] = useState<string | null>(placeId ? (cache.get(placeId) ?? null) : null);

  useEffect(() => {
    if (!places || !placeId || cache.has(placeId)) return;
    let active = true;
    (async () => {
      try {
        const place = new places.Place({ id: placeId });
        await place.fetchFields({ fields: ['photos'] });
        const uri = place.photos?.[0]?.getURI({ maxHeight: 256 }) ?? null;
        cache.set(placeId, uri);
        if (active) setUrl(uri);
      } catch {
        cache.set(placeId, null); // no photo, or the lookup failed: show the placeholder
      }
    })();
    return () => {
      active = false;
    };
  }, [places, placeId]);

  if (!url) {
    return (
      <span className={`${className} flex items-center justify-center text-white/35`}>
        <ImageOff size={16} strokeWidth={1.6} aria-hidden="true" />
      </span>
    );
  }
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={url} alt="" loading="lazy" className={`${className} object-cover`} />;
}
