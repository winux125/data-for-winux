"use client";

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { listenMediaQuery, readMediaQuery } from "@/lib/browser-media";
import { REVEAL_HOLD_MS, REVEAL_SESSION_KEY, REVEAL_TOTAL_MS, REVEAL_TRANSITION_MS } from "@/lib/opening-reveal";
import { useI18n } from "@/components/locale-provider";
import { revealMessages } from "@/lib/messages/reveal";
import "./site-reveal.css";

const CELL = 13;
const BAND_PX = 76;
const GLYPHS = ".:+=*#░▒";

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const smoothstep = (value: number) => { const t = clamp(value); return t * t * (3 - 2 * t); };

/**
 * A short spatial ASCII dissolve over the real, already-rendered landing page.
 * The landing is never hidden, cloned, made inert or dependent on this effect.
 * Storage/canvas failures and reduced motion all leave the page immediately usable.
 */
export function SiteReveal() {
  const { t } = useI18n(revealMessages);
  const [active, setActive] = useState(true);
  const panelRef = useRef<HTMLDivElement>(null);
  const veilRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const skipRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<() => void>(() => setActive(false));

  useEffect(() => {
    const root = document.documentElement;
    try {
      if (root.dataset.fvIntro !== "pending" || document.visibilityState === "hidden" || readMediaQuery("(prefers-reduced-motion: reduce)")?.matches !== false) {
        delete root.dataset.fvIntro;
        // Hydrate optional animation from browser visibility/storage without hiding SSR content.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setActive(false);
        return;
      }
      window.sessionStorage.setItem(REVEAL_SESSION_KEY, "seen");
    } catch {
      delete root.dataset.fvIntro;
      setActive(false);
    }
  }, []);

  useEffect(() => {
    if (!active || document.documentElement.dataset.fvIntro !== "pending") return;
    let frame = 0;
    let finished = false;
    let observer: MutationObserver | undefined;
    const finish = () => {
      if (finished) return;
      finished = true;
      cancelAnimationFrame(frame);
      delete document.documentElement.dataset.fvIntro;
      setActive(false);
    };
    closeRef.current = finish;
    // Independent of RAF: a stalled drawing callback must never leave a veil up.
    const deadline = window.setTimeout(finish, REVEAL_TOTAL_MS + 160);
    const canvas = canvasRef.current;
    const veil = veilRef.current;
    const panel = panelRef.current;
    let context: CanvasRenderingContext2D | null = null;
    try { context = canvas?.getContext("2d") ?? null; } catch { /* Optional canvas. */ }
    if (!canvas || !veil || !panel || !context) {
      finish();
      return () => window.clearTimeout(deadline);
    }
    const ctx = context;
    let width = 1;
    let height = 1;
    let accent = "#a31551";
    let ink = "#4a0221";
    const syncColors = () => {
      ink = getComputedStyle(panel).color;
      accent = skipRef.current ? getComputedStyle(skipRef.current).color : ink;
    };
    const resize = () => {
      width = Math.max(1, window.innerWidth);
      height = Math.max(1, window.innerHeight);
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      syncColors();
    };
    const hideOnNavigation = (event: Event) => {
      if (event.type === "focusin" && skipRef.current?.contains(event.target as Node)) return;
      finish();
    };
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") finish();
    };
    const handleVisibility = () => {
      if (document.visibilityState === "hidden") finish();
    };
    const preference = readMediaQuery("(prefers-reduced-motion: reduce)");
    const handlePreference = () => { if (preference?.matches !== false) finish(); };
    const stopPreference = listenMediaQuery(preference, handlePreference);
    const startedAt = performance.now();

    const draw = (now: number) => {
      if (finished) return;
      try {
        const elapsed = now - startedAt;
        const progress = smoothstep((elapsed - REVEAL_HOLD_MS) / REVEAL_TRANSITION_MS);
        const frontX = -BAND_PX + progress * (width + BAND_PX * 2);
        // A single outgoing decorative panel is clipped at the same spatial front
        // as the ASCII band. The actual page always sits intact underneath.
        veil.style.clipPath = `inset(0 0 0 ${clamp(frontX / width) * 100}%)`;
        ctx.clearRect(0, 0, width, height);
        ctx.font = `${CELL - 2}px ui-monospace, SFMono-Regular, Consolas, monospace`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        const firstCol = Math.max(0, Math.floor((frontX - BAND_PX) / CELL));
        const lastCol = Math.min(Math.ceil(width / CELL), Math.ceil((frontX + BAND_PX) / CELL));
        const rows = Math.ceil(height / CELL);
        const glyphFrame = Math.floor(elapsed / 85);
        for (let row = 0; row < rows; row++) {
          for (let col = firstCol; col < lastCol; col++) {
            const x = col * CELL + CELL / 2;
            const y = row * CELL + CELL / 2;
            const distance = Math.abs(x - frontX);
            const density = 1 - smoothstep(distance / BAND_PX);
            if (density < .04) continue;
            const seed = Math.abs((row * 37 + col * 23 + glyphFrame * 11) % 101);
            if (seed / 101 > density * .88) continue;
            ctx.globalAlpha = density * .55;
            ctx.fillStyle = distance < BAND_PX * .3 ? accent : ink;
            ctx.fillText(GLYPHS[(row * 11 + col * 7 + glyphFrame) % GLYPHS.length], x, y);
          }
        }
        ctx.globalAlpha = 1;
        if (elapsed >= REVEAL_TOTAL_MS) finish();
        else frame = requestAnimationFrame(draw);
      } catch {
        finish();
      }
    };

    try {
      resize();
      observer = new MutationObserver(syncColors);
      observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class", "style"] });
      window.addEventListener("resize", resize, { passive: true });
      window.addEventListener("pointerdown", hideOnNavigation, { capture: true, passive: true });
      window.addEventListener("wheel", hideOnNavigation, { passive: true });
      window.addEventListener("touchstart", hideOnNavigation, { passive: true });
      document.addEventListener("focusin", hideOnNavigation);
      document.addEventListener("keydown", handleKey);
      document.addEventListener("visibilitychange", handleVisibility);
      frame = requestAnimationFrame(draw);
    } catch {
      finish();
    }
    return () => {
      finished = true;
      cancelAnimationFrame(frame);
      window.clearTimeout(deadline);
      observer?.disconnect();
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointerdown", hideOnNavigation, { capture: true });
      window.removeEventListener("wheel", hideOnNavigation);
      window.removeEventListener("touchstart", hideOnNavigation);
      document.removeEventListener("focusin", hideOnNavigation);
      document.removeEventListener("keydown", handleKey);
      document.removeEventListener("visibilitychange", handleVisibility);
      stopPreference();
      closeRef.current = () => setActive(false);
    };
  }, [active]);

  if (!active) return null;
  return <div className="fsr-reveal" ref={panelRef}>
    <div className="fsr-decoration" aria-hidden="true">
      <div className="fsr-veil" ref={veilRef}>
        <div className="fsr-brand">
          {/* Local SVGs need no image optimization or additional client runtime. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <div className="fsr-lockup"><img className="fsr-wordmark-light" src="/brand/forte-wordmark-burgundy.svg" alt="" width={190} height={60} /><img className="fsr-wordmark-dark" src="/brand/forte-wordmark-white.svg" alt="" width={190} height={60} /><span>vision<span className="fsr-brand-dot" /></span></div>
          <p>{t("Проверка кассовых операций")}</p>
        </div>
      </div>
      <canvas ref={canvasRef} className="fsr-canvas" />
    </div>
    <button className="fsr-skip" type="button" ref={skipRef} onClick={() => closeRef.current()} aria-label={t("Пропустить вступительную анимацию")}><span>{t("Пропустить")}</span><X size={15} strokeWidth={1.5} aria-hidden="true" /></button>
  </div>;
}

export default SiteReveal;
