"use client";

import { getToken } from "firebase/app-check";
import { firebase } from "./firebase";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";
const DEV_SKIP_AUTH = process.env.NEXT_PUBLIC_DEV_SKIP_AUTH === "true";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

/** Call the Cloud Run API with the user's Firebase ID token (+ App Check token). */
export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  if (DEV_SKIP_AUTH) {
    headers["x-dev-uid"] = "dev-user";
  } else {
    const { auth, appCheck } = firebase();
    const user = auth.currentUser;
    if (!user) throw new ApiError(401, "not_signed_in");
    headers.Authorization = `Bearer ${await user.getIdToken()}`;
    if (appCheck) headers["X-Firebase-AppCheck"] = (await getToken(appCheck)).token;
  }

  const res = await fetch(`${API_URL}${path}`, {
    method: init.method ?? "GET",
    headers,
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, (data as { error?: string }).error ?? "request_failed");
  return data as T;
}
