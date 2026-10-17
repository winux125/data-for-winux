const RELEASE = "fv-startup-trace-1";
const reported = new Set<string>();

// Only technical error text is sent. Session values and query strings are omitted.
export function clientErrorText(value: unknown, limit = 500): string {
  return (typeof value === "string" ? value : "")
    .replace(/\bBearer\s+[^\s,;]+/gi, "Bearer [redacted]")
    .replace(/((?:access_token|refresh_token|password|api[_-]?key|authorization)["'\s]*[:=]["'\s]*)[^\s,;"']+/gi, "$1[redacted]")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[email]")
    .replace(/https?:\/\/[^\s)]+/g, url => url.split(/[?#]/)[0])
    .slice(0, limit);
}

export function reportClientError(error: unknown, source: "boundary" | "window" | "promise" | "preload") {
  try {
    if (typeof window === "undefined" || reported.size >= 3) return;
    const detail = error && typeof error === "object" ? error as { name?: unknown; message?: unknown; stack?: unknown } : { message: error };
    const message = clientErrorText(detail.message);
    if (!message) return;
    const key = source + message;
    if (reported.has(key)) return;
    reported.add(key);
    void fetch("/api/client-error", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      keepalive: true,
      body: JSON.stringify({
        release: RELEASE, source, path: window.location.pathname,
        name: clientErrorText(detail.name, 80), message,
        stack: clientErrorText(detail.stack, 2500),
      }),
    }).catch(() => {});
  } catch { /* Reporting must never affect the interface. */ }
}
