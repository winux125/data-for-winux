"use client"

import { useI18n } from "@/components/locale-provider"
import type { Locale } from "@/lib/i18n"
import { productMessages } from "@/lib/messages/product"

import { useId, useRef, type CSSProperties, type KeyboardEvent } from "react"
import { ArrowUpRight, ChevronDown, FileVideo2, FolderOpen } from "lucide-react"
import "./glass-folder.css"

export interface GlassFolderFile {
  id: string
  name: string
  /** A real status, duration or other short description supplied by the caller. */
  meta: string
}

export interface GlassFolderProps {
  title: string
  description: string
  files: GlassFolderFile[]
  emptyMessage: string
  variant?: "burgundy" | "rose" | "ivory"
  theme?: "light" | "dark"
  open: boolean
  onOpenChange: (open: boolean) => void
  onFileSelect: (file: GlassFolderFile) => void
  className?: string
}

const BACK_PATH = "M0 56A22 22 0 0 1 22 34L146 34C170 34 172 0 198 0L318 0A22 22 0 0 1 340 22L340 250A22 22 0 0 1 318 272L22 272A22 22 0 0 1 0 250Z"
const FRONT_PATH = "M0 22A22 22 0 0 1 22 0L118 0C144 0 146 32 172 32L318 32A22 22 0 0 1 340 54L340 176A22 22 0 0 1 318 198L22 198A22 22 0 0 1 0 176Z"

export function checkCountLabel(count: number, locale: Locale = "ru"): string {
  if (locale === "kk") return `${count} тексеру`
  if (locale === "en") return `${count} ${count === 1 ? "check" : "checks"}`
  const lastTwo = count % 100
  const last = count % 10
  const noun = lastTwo >= 11 && lastTwo <= 14 ? "проверок" : last === 1 ? "проверка" : last >= 2 && last <= 4 ? "проверки" : "проверок"
  return `${count} ${noun}`
}

/** Adapted from the supplied Glass Folder fragment: an actual back panel,
 * fanned file elements and a frosted pocket hinged on its bottom edge.
 * File data and open state stay controlled; the complete list is always
 * available on expansion, independently of the three visual previews.
 */
export default function GlassFolder({
  title, description, files, emptyMessage, variant = "burgundy", theme,
  open, onOpenChange, onFileSelect, className = "",
}: GlassFolderProps) {
  const { t, locale } = useI18n(productMessages)
  const id = useId().replace(/:/g, "")
  const triggerRef = useRef<HTMLButtonElement>(null)
  const listId = `gf-contents-${id}`
  const titleId = `gf-title-${id}`
  const descriptionId = `gf-description-${id}`
  const preview = files.slice(0, 3)

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape" && open) {
      event.preventDefault()
      event.stopPropagation()
      onOpenChange(false)
      triggerRef.current?.focus()
    }
  }

  return (
    <article
      className={`gf-root ${className}`}
      data-variant={variant}
      data-theme={theme}
      data-open={open ? "true" : "false"}
      aria-labelledby={titleId}
      onKeyDown={onKeyDown}
    >
      <div className="gf-object">
        <svg className="gf-definitions" width="0" height="0" aria-hidden="true" focusable="false">
          <defs>
            <clipPath id={`gf-back-${id}`} clipPathUnits="objectBoundingBox">
              <path d="M0 .206A.065 .081 0 0 1 .065 .125L.429 .125C.5 .125 .506 0 .582 0L.935 0A.065 .081 0 0 1 1 .081L1 .919A.065 .081 0 0 1 .935 1L.065 1A.065 .081 0 0 1 0 .919Z" />
            </clipPath>
            <clipPath id={`gf-front-${id}`} clipPathUnits="objectBoundingBox">
              <path d="M0 .111A.065 .111 0 0 1 .065 0L.347 0C.424 0 .429 .162 .506 .162L.935 .162A.065 .111 0 0 1 1 .273L1 .889A.065 .111 0 0 1 .935 1L.065 1A.065 .111 0 0 1 0 .889Z" />
            </clipPath>
          </defs>
        </svg>
        <div className="gf-stage">
          <div className="gf-object-shadow" aria-hidden="true" />
          <div className="gf-back" style={{ clipPath: `url(#gf-back-${id})` }} aria-hidden="true">
            <div className="gf-art"><span /><span /><span /><i /></div>
            <span className="gf-back-number">FV / {variant === "burgundy" ? "01" : variant === "ivory" ? "02" : "03"}</span>
            <div className="gf-back-sheen" />
          </div>
          <svg className="gf-rim gf-back-rim" viewBox="0 0 340 272" preserveAspectRatio="none" aria-hidden="true"><path d={BACK_PATH} /></svg>

          <div className="gf-files" aria-hidden={!open} inert={!open}>
            {preview.map((file, index) => {
              const slot = preview.length <= 1 ? 0 : index / (preview.length - 1) * 2 - 1
              return <button
                type="button"
                className="gf-sheet"
                key={file.id}
                tabIndex={open ? 0 : -1}
                disabled={!open}
                style={{ "--gf-slot": slot, "--gf-depth": preview.length - index - 1, zIndex: index + 1 } as CSSProperties}
                aria-label={`${t("Открыть проверку")} ${file.name}. ${file.meta}`}
                onClick={() => onFileSelect(file)}
              >
                <span className="gf-sheet-heading"><FileVideo2 size={15} aria-hidden="true" /><span>{file.name}</span><ArrowUpRight size={12} aria-hidden="true" /></span>
                <span className="gf-sheet-meta">{file.meta}</span>
                <span className="gf-sheet-lines" aria-hidden="true"><i /><i /><i /><i /></span>
                <span className="gf-sheet-stamp" aria-hidden="true">FORTE VISION</span>
              </button>
            })}
            {!files.length && <div className="gf-empty-sheet" aria-hidden="true"><FolderOpen size={28} /><span>{t("Пока пусто")}</span></div>}
          </div>

          <div className="gf-front" style={{ clipPath: `url(#gf-front-${id})` }}>
            <div className="gf-front-tint" aria-hidden="true" />
            <div className="gf-front-sheen" aria-hidden="true" />
            <svg className="gf-rim gf-front-rim" viewBox="0 0 340 198" preserveAspectRatio="none" aria-hidden="true"><path d={FRONT_PATH} /></svg>
            <button
              ref={triggerRef}
              type="button"
              className="gf-pocket-button"
              aria-expanded={open}
              aria-controls={listId}
              aria-describedby={descriptionId}
              aria-label={`${t(open ? "Закрыть папку" : "Открыть папку")} «${title}», ${checkCountLabel(files.length, locale)}`}
              onClick={() => onOpenChange(!open)}
            >
              <span className="gf-label"><span className="gf-folder-title" id={titleId}>{title}</span><span className="gf-folder-meta">{checkCountLabel(files.length, locale)}</span></span>
              <span className="gf-pocket-action" aria-hidden="true"><ChevronDown size={20} /></span>
            </button>
          </div>
        </div>
      </div>
      <p className="gf-description" id={descriptionId}>{description}</p>
      <div className="gf-contents" id={listId} hidden={!open}>
        <div className="gf-contents-heading"><span>{t("Содержимое папки")}</span><span>{files.length}</span></div>
        {files.length ? <ul className="gf-content-list">
          {files.map(file => <li key={file.id}><button type="button" onClick={() => onFileSelect(file)}>
            <FileVideo2 className="gf-content-icon" size={18} aria-hidden="true" />
            <span><strong>{file.name}</strong><small>{file.meta}</small></span>
            <ArrowUpRight size={16} aria-hidden="true" />
          </button></li>)}
        </ul> : <p className="gf-empty-message">{emptyMessage}</p>}
        <button type="button" className="gf-close-folder" onClick={() => { onOpenChange(false); triggerRef.current?.focus() }}><ChevronDown size={15} aria-hidden="true" />{t("Свернуть папку")}</button>
      </div>
    </article>
  )
}
