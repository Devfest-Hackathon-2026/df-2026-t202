'use client';

import {
  GoogleAuthProvider,
  linkWithPopup,
  onIdTokenChanged,
  signInAnonymously,
  signInWithPopup,
  signOut,
  type User,
} from 'firebase/auth';
import { useEffect, useState } from 'react';
import { auth } from './firebase';

export type AuthState = { user: User | null; loading: boolean };

/** Google sign-in for trip owners; anonymous sign-in is for shared pages (PLAN.md 4, 11). */
export function useAuthUser(): AuthState {
  const [state, setState] = useState<AuthState>({ user: null, loading: true });

  useEffect(() => {
    // Token changes include sign-in, sign-out and a guest becoming a Google user (same uid,
    // new token), so the menu updates after linking.
    return onIdTokenChanged(auth(), (user) => {
      // Local development skips the sign-in screen: a guest session starts by itself.
      if (!user && isLocalhost()) {
        // If guest sign-in is off for the project, fall back to the normal sign-in screen.
        void signInAsGuest().catch(() => setState({ user: null, loading: false }));
        return;
      }
      setState({ user, loading: false });
    });
  }, []);

  return state;
}

function isLocalhost() {
  return typeof window !== 'undefined' && window.location.hostname === 'localhost';
}

// One guest sign-in at a time, even when several components ask for one at once.
let guestSignIn: Promise<unknown> | null = null;

export function signInWithGoogle() {
  return signInWithPopup(auth(), new GoogleAuthProvider());
}

export function signInAsGuest() {
  guestSignIn ??= signInAnonymously(auth()).finally(() => (guestSignIn = null));
  return guestSignIn;
}

/**
 * Turn the guest account into a Google account. The uid stays the same, so the guest's trips and
 * limits carry over. Resolves "exists" when that Google account is already a Tripi user (Firebase
 * can't merge two accounts); the caller then offers to sign in to it instead.
 */
export async function linkGuestWithGoogle(): Promise<'linked' | 'exists'> {
  const user = auth().currentUser;
  if (!user) throw new Error('not_signed_in');
  try {
    await linkWithPopup(user, new GoogleAuthProvider());
    await user.reload(); // pick up the Google name and photo
    return 'linked';
  } catch (e) {
    if ((e as { code?: string }).code === 'auth/credential-already-in-use') return 'exists';
    throw e;
  }
}

export function signOutUser() {
  return signOut(auth());
}
