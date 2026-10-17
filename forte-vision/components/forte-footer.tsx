"use client"

import { useEffect, useRef, type PointerEvent } from "react"
import { listenMediaQuery, readMediaQuery } from "@/lib/browser-media"
import { useI18n } from "@/components/locale-provider"
import { landingMessages } from "@/lib/messages/landing"
import "./forte-footer.css"

// The supplied dithered footer treatment, recoloured with the Forte palette.
// Original stochastic fade: sparse above, dense below, with a seamless moving tile.
const DITHER_MASK = `url("data:image/svg+xml,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="360" height="240"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset=".04" stop-color="#000"/><stop offset=".96" stop-color="#fff"/></linearGradient><filter id="f" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency=".45" numOctaves="2" seed="7" stitchTiles="stitch" result="n"/><feColorMatrix in="n" type="matrix" values="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 0 0 0 0 1" result="ng"/><feComposite in="SourceGraphic" in2="ng" operator="arithmetic" k2=".5" k3=".5" result="s"/><feComponentTransfer in="s" result="t"><feFuncR type="discrete" tableValues="0 1"/></feComponentTransfer><feColorMatrix in="t" type="matrix" values="0 0 0 0 1 0 0 0 0 .5 0 0 0 0 0 1 0 0 0 0"/></filter></defs><rect width="100%" height="100%" fill="url(#g)" filter="url(#f)"/></svg>`)}")`

export default function ForteFooter() {
  const { t } = useI18n(landingMessages)
  const bandRef = useRef<HTMLDivElement>(null)
  const fieldRef = useRef<HTMLDivElement>(null)
  const frameRef = useRef<number | null>(null)
  const interactiveRef = useRef(false)
  const visibleRef = useRef(false)

  const clearSpotlight = () => {
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
    frameRef.current = null
    fieldRef.current?.classList.remove("ff-field-lit")
  }

  useEffect(() => {
    const band = bandRef.current
    if (!band) return
    const reduceMotion = readMediaQuery("(prefers-reduced-motion: reduce)")
    const finePointer = readMediaQuery("(hover: hover) and (pointer: fine)")
    const syncPreferences = () => {
      interactiveRef.current = reduceMotion?.matches === false && finePointer?.matches === true
      if (!interactiveRef.current) {
        if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
        frameRef.current = null
        fieldRef.current?.classList.remove("ff-field-lit")
      }
    }
    syncPreferences()
    const stopMotion = listenMediaQuery(reduceMotion, syncPreferences)
    const stopPointer = listenMediaQuery(finePointer, syncPreferences)
    let observer: IntersectionObserver | undefined
    try {
      if (typeof IntersectionObserver === "function") observer = new IntersectionObserver(entries => {
      visibleRef.current = entries[0]?.isIntersecting ?? false
      band.dataset.visible = String(visibleRef.current)
      if (!visibleRef.current) {
        if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
        frameRef.current = null
        fieldRef.current?.classList.remove("ff-field-lit")
      }
      }, { rootMargin: "60px" })
      observer?.observe(band)
    } catch { observer?.disconnect(); observer = undefined }
    if (!observer) {
      // Unsupported observers keep the footer static and fully visible.
      interactiveRef.current = false
      band.dataset.visible = "false"
    }
    return () => {
      observer?.disconnect()
      stopMotion()
      stopPointer()
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
      frameRef.current = null
    }
  }, [])

  const moveSpotlight = (event: PointerEvent<HTMLDivElement>) => {
    const field = fieldRef.current
    if (!interactiveRef.current || !visibleRef.current || event.pointerType !== "mouse" || !field) return
    const rect = field.getBoundingClientRect()
    const x = event.clientX - rect.left
    const y = event.clientY - rect.top
    if (frameRef.current !== null) cancelAnimationFrame(frameRef.current)
    frameRef.current = requestAnimationFrame(() => {
      field.style.setProperty("--ff-pointer-x", `${x}px`)
      field.style.setProperty("--ff-pointer-y", `${y}px`)
      field.classList.add("ff-field-lit")
      frameRef.current = null
    })
  }

  return <footer className="ff-footer">
    <div ref={bandRef} className="ff-band" aria-hidden="true" onPointerMove={moveSpotlight} onPointerLeave={clearSpotlight} onPointerCancel={clearSpotlight}>
      <div ref={fieldRef} className="ff-field"><div className="ff-dots" style={{ maskImage: `radial-gradient(circle, #000 .9px, transparent 1.3px), ${DITHER_MASK}`, WebkitMaskImage: `radial-gradient(circle, #000 .9px, transparent 1.3px), ${DITHER_MASK}` }} /></div>
      <div className="ff-band-inner ff-container"><span className="ff-large-mark">forte</span></div>
    </div>

    <div className="ff-bottom">
      <div className="ff-bottom-inner ff-container"><span>Forte Vision · 2026</span><nav className="ff-footer-options" aria-label={t("Конфиденциальность")}><a href="/privacy">{t("Конфиденциальность")}</a><button type="button" onClick={() => window.dispatchEvent(new CustomEvent("forte:cookie-settings"))}>{t("Настройки cookies")}</button></nav></div>
    </div>
  </footer>
}
