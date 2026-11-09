/**
 * The home screen creates a trip and opens it at once; the first sentence travels to the trip
 * page through sessionStorage (this tab only), and the trip page sends it. That way the user
 * sees the chat, their message and typing dots instead of a frozen home screen.
 */
const key = (tripId: string) => `firstMessage:${tripId}`;

export function handOffFirstMessage(tripId: string, text: string) {
  try {
    sessionStorage.setItem(key(tripId), text);
  } catch {
    // Storage blocked (private mode): the trip still opens, the user just types it again.
  }
}

/** Returns the sentence once, and forgets it, so a refresh never sends it twice. */
export function takeFirstMessage(tripId: string): string | null {
  try {
    const text = sessionStorage.getItem(key(tripId));
    sessionStorage.removeItem(key(tripId));
    return text;
  } catch {
    return null;
  }
}
