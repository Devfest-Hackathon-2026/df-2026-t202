import { getApps, initializeApp } from "firebase-admin/app";
import { getAppCheck } from "firebase-admin/app-check";
import { getAuth } from "firebase-admin/auth";
import { getFirestore } from "firebase-admin/firestore";
import { env } from "../env.js";

// On Cloud Run this uses the service account (ADC). Locally it talks to the
// emulators when FIRESTORE_EMULATOR_HOST / FIREBASE_AUTH_EMULATOR_HOST are set.
const app =
  getApps()[0] ?? initializeApp(env.GOOGLE_CLOUD_PROJECT ? { projectId: env.GOOGLE_CLOUD_PROJECT } : undefined);

export const db = getFirestore(app);
export const adminAuth = getAuth(app);
export const appCheck = getAppCheck(app);
