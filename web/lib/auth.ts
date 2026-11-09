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
    return onAuthStateChanged(auth(), (user) => setState({ user, loading: false }));
  }, []);

  return state;
}

export function signInWithGoogle() {
  return signInWithPopup(auth(), new GoogleAuthProvider());
}

export function signInAsGuest() {
  return signInAnonymously(auth());
}

export function signOutUser() {
  return signOut(auth());
}
