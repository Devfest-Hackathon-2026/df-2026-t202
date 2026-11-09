'use client';

import { getToken } from 'firebase/app-check';
import { appCheckInstance, auth } from './firebase';
import { env } from './env';

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
    const detail = await response.text().catch(() => '');
    throw new Error(`api_${response.status}${detail ? `: ${detail}` : ''}`);
  }
  return (await response.json()) as T;
}
