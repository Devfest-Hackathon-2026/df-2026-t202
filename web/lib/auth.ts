'use client';

import {
  GoogleAuthProvider,
  onAuthStateChanged,
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
    return onAuthStateChanged(auth(), (user) => {
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

export function signOutUser() {
  return signOut(auth());
}
