'use client';

import { APIProvider } from '@vis.gl/react-google-maps';
import type { ReactNode } from 'react';
import { env } from '@/lib/env';
import { useLanguage } from '@/lib/i18n';

/**
 * Loads the Maps JavaScript API once for the whole screen, so the itinerary can use the Places
 * library for spot photos, not just the map. The API fixes its language when the script loads,
 * so the page reloads after a language change (PLAN.md 10.3).
 */
export function MapsProvider({ children }: { children: ReactNode }) {
  const language = useLanguage();
  if (!env.mapsBrowserKey) return <>{children}</>;
  return (
    <APIProvider apiKey={env.mapsBrowserKey} language={language} libraries={['geometry', 'places']}>
      {children}
    </APIProvider>
  );
}
