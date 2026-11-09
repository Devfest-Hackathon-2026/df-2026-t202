'use client';

import { getApp, getApps, initializeApp, type FirebaseApp } from 'firebase/app';
import { ReCaptchaEnterpriseProvider, initializeAppCheck, type AppCheck } from 'firebase/app-check';
import { connectAuthEmulator, getAuth, type Auth } from 'firebase/auth';
import { connectFirestoreEmulator, getFirestore, type Firestore } from 'firebase/firestore';
import { env } from './env';

// The client only READS Firestore. Every write goes through the API (PLAN.md 5, firestore.rules).
let appCheck: AppCheck | null = null;
let emulatorsConnected = false;

export function firebaseApp(): FirebaseApp {
  if (getApps().length) return getApp();
  // The emulators accept any key; a real project needs the real one.
  return initializeApp({ ...env.firebase, apiKey: env.firebase.apiKey || 'demo-key' });
}

export function auth(): Auth {
  const instance = getAuth(firebaseApp());
  if (env.useEmulators && !emulatorsConnected) {
    connectAuthEmulator(instance, 'http://127.0.0.1:9099', { disableWarnings: true });
    connectFirestoreEmulator(getFirestore(firebaseApp()), '127.0.0.1', 8081);
    emulatorsConnected = true;
  }
  return instance;
}

export function db(): Firestore {
  auth(); // connects the emulators once, before the first read
  return getFirestore(firebaseApp());
}

/** App Check runs only when a site key is set, so local development works without reCAPTCHA. */
export function appCheckInstance(): AppCheck | null {
  if (!env.recaptchaSiteKey || typeof window === 'undefined') return null;
  appCheck ??= initializeAppCheck(firebaseApp(), {
    provider: new ReCaptchaEnterpriseProvider(env.recaptchaSiteKey),
    isTokenAutoRefreshEnabled: true,
  });
  return appCheck;
}
