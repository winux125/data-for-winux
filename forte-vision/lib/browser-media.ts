/** Browser preferences are optional; unsupported APIs must not block the page. */
export function readMediaQuery(query: string): MediaQueryList | null {
  try {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return null;
    const media = window.matchMedia(query);
    return media && typeof media.matches === "boolean" ? media : null;
  } catch {
    return null;
  }
}

type MediaQueryHandler = (event: MediaQueryListEvent) => void;
const noop = () => {};

function safeCleanup(remove: () => void): () => void {
  let stopped = false;
  return () => {
    if (stopped) return;
    stopped = true;
    try { remove(); } catch { /* Browser preference listeners are optional. */ }
  };
}

/** Subscribe using the supported API and always return safe, idempotent cleanup. */
export function listenMediaQuery(media: MediaQueryList | null, handler: MediaQueryHandler): () => void {
  if (!media) return noop;
  try {
    if (typeof media.addEventListener === "function" && typeof media.removeEventListener === "function") {
      media.addEventListener("change", handler);
      return safeCleanup(() => media.removeEventListener("change", handler));
    }
  } catch {
    // Some webviews expose the modern methods but reject their use.
    try { media.removeEventListener?.("change", handler); } catch { /* Continue with the legacy API. */ }
  }
  try {
    if (typeof media.addListener === "function" && typeof media.removeListener === "function") {
      media.addListener(handler);
      return safeCleanup(() => media.removeListener(handler));
    }
  } catch {
    try { media.removeListener?.(handler); } catch { /* No usable preference subscription. */ }
  }
  return noop;
}
