'use client';

import { collection, doc, onSnapshot, orderBy, query, where } from 'firebase/firestore';
import { useEffect, useState } from 'react';
import { db } from './firebase';
import type { Message, PlanDoc, Trip } from './types';

/**
 * Reads come straight from Firestore; only the API writes (PLAN.md 5).
 * `error` is set when the listener fails, so views can show an error state.
 */
export function useTrip(tripId: string) {
  const [trip, setTrip] = useState<Trip | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    return onSnapshot(
      doc(db(), 'trips', tripId),
      (snap) => {
        setTrip(snap.exists() ? ({ id: snap.id, ...snap.data() } as Trip) : null);
        setLoading(false);
      },
      (err) => {
        setError(err);
        setLoading(false);
      },
    );
  }, [tripId]);

  return { trip, loading, error };
}

export function useMessages(tripId: string) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    setLoading(true);
    const q = query(collection(db(), 'trips', tripId, 'messages'), orderBy('createdAt'));
    return onSnapshot(
      q,
      (snap) => {
        setMessages(snap.docs.map((d) => ({ id: d.id, ...d.data() }) as Message));
        setLoading(false);
      },
      (err) => {
        setError(err);
        setLoading(false);
      },
    );
  }, [tripId]);

  return { messages, loading, error };
}

/** The current plan of a trip (trips/{tripId}/plans/{planId}). */
export function usePlan(tripId: string, planId: string | null | undefined) {
  const [plan, setPlan] = useState<PlanDoc | null>(null);
  const [loading, setLoading] = useState(Boolean(planId));
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!planId) {
      setPlan(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    return onSnapshot(
      doc(db(), 'trips', tripId, 'plans', planId),
      (snap) => {
        setPlan(snap.exists() ? ({ id: snap.id, ...snap.data() } as PlanDoc) : null);
        setLoading(false);
      },
      (err) => {
        setError(err);
        setLoading(false);
      },
    );
  }, [tripId, planId]);

  return { plan, loading, error };
}

/**
 * "My trips". The query must match the read rule in firestore.rules, so it filters on the
 * members map and sorts on the client.
 */
export function useMyTrips(uid: string | undefined) {
  const [trips, setTrips] = useState<Trip[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!uid) {
      setTrips([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    const q = query(collection(db(), 'trips'), where(`members.${uid}`, 'in', ['owner', 'viewer']));
    return onSnapshot(
      q,
      (snap) => {
        const rows = snap.docs.map(
          (d) => ({ id: d.id, ...d.data() }) as Trip & { updatedAt?: { seconds?: number } },
        );
        rows.sort((a, b) => (b.updatedAt?.seconds ?? 0) - (a.updatedAt?.seconds ?? 0));
        setTrips(rows);
        setLoading(false);
      },
      (err) => {
        setError(err);
        setLoading(false);
      },
    );
  }, [uid]);

  return { trips, loading, error };
}
