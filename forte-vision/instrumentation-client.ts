import { reportClientError } from "@/lib/client-error";

if (typeof window !== "undefined") {
  window.addEventListener("error", event => {
    if (event instanceof ErrorEvent) reportClientError(event.error ?? event.message, "window");
  });
  window.addEventListener("unhandledrejection", event => reportClientError(event.reason, "promise"));
  window.addEventListener("vite:preloadError", event => reportClientError((event as Event & { payload?: unknown }).payload, "preload"));
}
