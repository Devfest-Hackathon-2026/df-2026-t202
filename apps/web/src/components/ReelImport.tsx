"use client";

import type { ReelExtraction } from "@rtt/shared";
import { parseReelUrl } from "@rtt/shared";
import { GoogleAuthProvider, onAuthStateChanged, signInWithPopup, type User } from "firebase/auth";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { firebase, firebaseConfigured } from "@/lib/firebase";

const DEV_SKIP_AUTH = process.env.NEXT_PUBLIC_DEV_SKIP_AUTH === "true";

type Result = { id: string; cached: boolean; extraction: ReelExtraction };

export function ReelImport() {
  const [user, setUser] = useState<User | null>(null);
  const [url, setUrl] = useState("");
  const [caption, setCaption] = useState("");
  const [needsCaption, setNeedsCaption] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  useEffect(() => {
    if (DEV_SKIP_AUTH || !firebaseConfigured) return;
    return onAuthStateChanged(firebase().auth, setUser);
  }, []);

  const signedIn = DEV_SKIP_AUTH || Boolean(user);
  const parsed = url ? parseReelUrl(url) : null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    if (!parsed) return setError("That link isn't a YouTube, Instagram or TikTok video.");
    setBusy(true);
    try {
      const res = await api<Result>("/v1/reels", {
        method: "POST",
        body: { url, caption: caption || undefined },
      });
      setResult(res);
      setNeedsCaption(false);
    } catch (err) {
      if (err instanceof ApiError && err.code === "caption_required") {
        setNeedsCaption(true);
        setError("We can't watch Instagram/TikTok videos directly yet — paste the post caption below.");
      } else if (err instanceof ApiError && err.code === "rate_limited") {
        setError("Too many imports this hour. Try again later.");
      } else {
        setError("Couldn't read that reel. Try another link.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (!signedIn) {
    return (
      <button
        className="rounded-xl bg-ink px-5 py-3 font-medium text-paper disabled:opacity-50"
        disabled={!firebaseConfigured}
        onClick={() => signInWithPopup(firebase().auth, new GoogleAuthProvider())}
      >
        {firebaseConfigured ? "Sign in with Google" : "Add Firebase config in .env.local to sign in"}
      </button>
    );
  }

  return (
    <section className="flex flex-col gap-4">
      <form onSubmit={submit} className="flex flex-col gap-3">
        <input
          className="rounded-xl border border-line bg-white px-4 py-3 outline-none focus:border-ink"
          placeholder="https://www.youtube.com/shorts/…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          inputMode="url"
        />
        {needsCaption && (
          <textarea
            className="min-h-28 rounded-xl border border-line bg-white px-4 py-3 outline-none focus:border-ink"
            placeholder="Paste the post caption"
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
          />
        )}
        <button
          className="rounded-xl bg-accent px-5 py-3 font-medium text-white disabled:opacity-50"
          disabled={busy || !url}
        >
          {busy ? "Gemini is watching…" : "Analyze reel"}
        </button>
      </form>

      {error && <p className="text-sm text-accent">{error}</p>}

      {result && (
        <article className="flex flex-col gap-3 rounded-2xl border border-line bg-white p-5">
          <p className="text-muted">{result.extraction.summary}</p>
          {result.extraction.vibeTags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {result.extraction.vibeTags.map((t) => (
                <span key={t} className="rounded-full bg-paper px-3 py-1 text-sm">
                  {t}
                </span>
              ))}
            </div>
          )}
          <ul className="flex flex-col gap-2">
            {result.extraction.places.map((p) => (
              <li key={p.name} className="flex flex-col">
                <span className="font-medium">
                  {p.name}
                  {p.city ? <span className="text-muted"> · {p.city}</span> : null}
                </span>
                {p.note && <span className="text-sm text-muted">{p.note}</span>}
              </li>
            ))}
          </ul>
          {result.cached && <p className="text-xs text-muted">From cache — this reel was analyzed before.</p>}
        </article>
      )}
    </section>
  );
}
