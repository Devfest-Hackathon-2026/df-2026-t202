'use client';

import { getToken } from 'firebase/app-check';
import { appCheckInstance, auth } from './firebase';
import { env } from './env';

/** Longest chat message the API accepts (api/app/models.py MessageIn.text). */
export const MAX_TEXT_LENGTH = 1000;

/** API error codes the user gets a specific message for (`error.<code>` in the i18n files). */
const KNOWN_ERRORS = [
  'trip_limit_reached',
  'plan_limit_reached',
  'message_limit_reached',
  'service_busy',
  'too_fast',
  'place_not_found',
  'share_full',
  'trip_too_long',
  'date_in_past',
  'date_too_far',
  'budget_too_low',
  'adult_required',
  'group_too_large',
  'infant_needs_adult',
  'too_many_children',
] as const;

/** A failed API call. `code` is the API's `detail` ("plan_limit_reached"), or "http_<status>". */
export class ApiError extends Error {
  constructor(readonly code: string) {
    super(`api_${code}`);
  }
}

/** The i18n key to show for a failed call: a specific message for known limits, else a generic retry. */
export function errorKey(error: unknown): string {
  const code = error instanceof ApiError ? error.code : '';
  return (KNOWN_ERRORS as readonly string[]).includes(code) ? `error.${code}` : 'state.sendFailed';
}

/**
 * The only way to call the Cloud Run API (PLAN.md 9.1). Attaches the Firebase ID token and,
 * when App Check is on, its token. Reads come from Firestore directly.
 */
export async function post<T>(path: string, body: unknown = {}): Promise<T> {
  const user = auth().currentUser;
  if (!user) throw new Error('not_signed_in');

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${await user.getIdToken()}`,
  };
  const check = appCheckInstance();
  if (check) headers['X-Firebase-AppCheck'] = (await getToken(check)).token;

  const response = await fetch(`${env.apiBaseUrl}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as { detail?: unknown } | null;
    throw new ApiError(typeof body?.detail === 'string' ? body.detail : `http_${response.status}`);
  }
  return (await response.json()) as T;
}
