"use client";

import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { VisualEffectBoundary } from "@/components/visual-effect-boundary";
import { readMediaQuery } from "@/lib/browser-media";
import SceneFallback from "./cashdesk-fallback";

export type CashdeskSceneProps = { className?: string; compact?: boolean; active?: boolean };
const CashdeskCanvas = lazy(() => import("./cashdesk-canvas"));

/** Keep the useful SVG on first paint; load optional WebGL only near the viewport and when idle. */
export default function CashdeskScene(props: CashdeskSceneProps) {
  const host = useRef<HTMLDivElement>(null);
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
    if (readMediaQuery("(prefers-reduced-motion: reduce)")?.matches || connection?.saveData) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let idle: number | undefined;
    let scheduled = false;
    const schedule = () => {
      if (scheduled || stopped) return;
      scheduled = true;
      if (typeof window.requestIdleCallback === "function") idle = window.requestIdleCallback(() => { if (!stopped) setEnabled(true); }, { timeout: 2500 });
      else timer = setTimeout(() => { if (!stopped) setEnabled(true); }, 1000);
    };
    const observer = typeof IntersectionObserver === "function" ? new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) { observer?.disconnect(); schedule(); }
    }, { rootMargin: "100px" }) : null;
    if (observer && host.current) observer.observe(host.current);
    else schedule();
    return () => {
      stopped = true; observer?.disconnect();
      if (timer !== undefined) clearTimeout(timer);
      if (idle !== undefined) window.cancelIdleCallback?.(idle);
    };
  }, []);
  const fallback = <div className={`cashdesk-scene ${props.className ?? ""}`} style={{ width: "100%", height: "100%" }}><SceneFallback /></div>;
  return <div ref={host} style={{ width: "100%", height: "100%" }}><VisualEffectBoundary fallback={fallback}><Suspense fallback={fallback}>{enabled ? <CashdeskCanvas {...props} /> : fallback}</Suspense></VisualEffectBoundary></div>;
}
