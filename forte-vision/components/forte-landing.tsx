"use client"

import { useEffect, useRef, useState } from "react"
import Link from "next/link"
import {
  ArrowDown, ArrowRight, ArrowUpRight, Check, ChevronDown, Clock3,
  FileCheck2, Film, Focus, Menu, MousePointer2, Play, ScanLine,
  ShieldCheck, SquareDashed, Upload, X,
} from "lucide-react"
import CashdeskScene from "@/components/ui/cashdesk-scene"
import { AnalysisPipeline, DEMO_ANALYSIS_RUNS } from "@/components/ui/analysis-pipeline"
import ForteFooter from "@/components/forte-footer"
import { AppearanceControls } from "@/components/theme-provider"
import SiteReveal from "@/components/site-reveal"
import { VisualEffectBoundary } from "@/components/visual-effect-boundary"
import { listenMediaQuery, readMediaQuery } from "@/lib/browser-media"
import { useI18n } from "@/components/locale-provider"
import { landingMessages } from "@/lib/messages/landing"
import "./forte-landing.css"

const navigation = [
  { label: "Возможности", href: "#features" },
  { label: "Как работает", href: "#workflow" },
  { label: "Вопросы", href: "#faq" },
]

const previewEvents = [
  { time: "00:18", end: "00:24", title: "Пересчёт банкнот", text: "Фрагмент для проверки последовательности действий.", position: 22.5 },
  { time: "00:46", end: "00:52", title: "Передача наличных", text: "Проверьте действия кассира в выбранном фрагменте.", position: 57.5 },
  { time: "01:08", end: "01:13", title: "Завершение операции", text: "Сопоставьте завершение операции с её предыдущими этапами.", position: 85 },
]

function Brand({ inverted = false }: { inverted?: boolean }) {
  const { t } = useI18n(landingMessages)
  return <Link className="fl-brand" href="/" aria-label={t("Forte Vision - главная")}>
    {/* The bank's original wordmark is a locally hosted brand asset. */}
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src={`/brand/forte-wordmark-${inverted ? "white" : "burgundy"}.svg`} alt="Forte" width="94" height="32" />
    <span>vision<span className="fl-brand-point" /></span>
  </Link>
}

function ProductPreview() {
  const { t } = useI18n(landingMessages)
  const [selected, setSelected] = useState(1)
  const event = previewEvents[selected]

  return <div className="fl-product-preview" aria-label={t("Интерактивный пример просмотра событий")}>
    <div className="fl-preview-topbar">
      <span className="fl-preview-file"><Film size={15} /> {t("Кассовая операция.mov")}</span>
      <span className="fl-preview-sample">{t("Пример интерфейса")}</span>
    </div>
    <div className="fl-preview-body">
      <div className="fl-preview-monitor">
        <div className="fl-preview-monitor-label"><span /> {t("Схема кассовой зоны")}</div>
        <div className="fl-preview-desk" aria-hidden="true">
          <div className="fl-desk-camera"><div /><span /></div>
          <div className="fl-desk-window" />
          <div className="fl-desk-person"><span /><i /></div>
          <div className="fl-desk-counter"><span /><i /><b /></div>
          <div className={`fl-desk-focus fl-desk-focus-${selected}`}><span /><span /><span /><span /></div>
          <div className="fl-desk-caption"><Focus size={12} /> {t(event.title)}</div>
        </div>
        <div className="fl-preview-player">
          <span className="fl-player-play" aria-hidden="true"><Play size={13} fill="currentColor" /></span>
          <span className="fl-player-time">{event.time} <span>/ 01:20</span></span>
          <span className="fl-player-spacer" />
          <SquareDashed size={14} aria-hidden="true" />
        </div>
        <div className="fl-preview-timeline" aria-label={t("События на временной шкале")}>
          <span className="fl-timeline-line" />
          <span className="fl-timeline-progress" style={{ transform: `scaleX(${event.position / 100})` }} />
          {previewEvents.map((item, i) => <button key={item.time} type="button" className={`fl-timeline-marker${i === selected ? " fl-marker-selected" : ""}`} style={{ left: `${item.position}%` }} aria-label={t("Выбрать событие {time}: {title}", { time: item.time, title: t(item.title) })} aria-pressed={i === selected} onClick={() => setSelected(i)} />)}
        </div>
        <div className="fl-preview-ticks"><span>00:00</span><span>00:40</span><span>01:20</span></div>
      </div>
      <div className="fl-preview-events">
        <div className="fl-preview-events-title"><span>{t("События")}</span><span>03</span></div>
        {previewEvents.map((item, i) => <button key={item.time} type="button" className={`fl-preview-event${i === selected ? " fl-event-selected" : ""}`} onClick={() => setSelected(i)} aria-pressed={i === selected}>
          <span className="fl-event-index">{String(i + 1).padStart(2, "0")}</span>
          <span><strong>{t(item.title)}</strong><small>{item.time} - {item.end}</small></span>
          <ArrowUpRight size={14} />
        </button>)}
        <p className="fl-preview-event-note"><MousePointer2 size={13} aria-hidden="true" /><span>{t("Выберите событие, чтобы посмотреть его детали")}</span></p>
      </div>
    </div>
    <div className="fl-preview-evidence" aria-live="polite" aria-atomic="true">
      <span className="fl-evidence-icon"><FileCheck2 size={18} /></span>
      <div><strong>{t(event.title)}</strong><p>{t(event.text)}</p></div>
      <span className="fl-evidence-time">{event.time}</span>
    </div>
  </div>
}

export default function ForteLanding() {
  const { t } = useI18n(landingMessages)
  const [menuOpen, setMenuOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setMenuOpen(false); menuButtonRef.current?.focus() }
    }
    document.addEventListener("keydown", closeOnEscape)
    return () => document.removeEventListener("keydown", closeOnEscape)
  }, [menuOpen])

  useEffect(() => {
    const desktop = readMediaQuery("(min-width: 1024px)")
    const closeOnDesktop = () => { if (desktop?.matches) setMenuOpen(false) }
    return listenMediaQuery(desktop, closeOnDesktop)
  }, [])

  return <div className="fl-page">
    <VisualEffectBoundary><SiteReveal /></VisualEffectBoundary>
    <a className="fl-skip-link" href="#main-content">{t("Перейти к содержимому")}</a>
    <header className="fl-header">
      <div className="fl-header-inner fl-container">
        <Brand />
        <nav className="fl-desktop-nav" aria-label={t("Основная навигация")}>
          {navigation.map(item => <a key={item.href} href={item.href}>{t(item.label)}</a>)}
        </nav>
        <div className="fl-header-actions">
          <AppearanceControls className="fl-appearance-controls fl-theme-desktop" />
          <a className="fl-button fl-button-compact" href="/app" target="_top">{t("Открыть сервис")} <ArrowUpRight size={15} /></a>
          <button type="button" ref={menuButtonRef} className="fl-menu-button" aria-label={t(menuOpen ? "Закрыть меню" : "Открыть меню")} aria-expanded={menuOpen} aria-controls="fl-mobile-navigation" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X size={22} /> : <Menu size={22} />}</button>
        </div>
      </div>
      {menuOpen && <nav id="fl-mobile-navigation" className="fl-mobile-nav" aria-label={t("Мобильная навигация")}>
        {navigation.map(item => <a key={item.href} href={item.href} onClick={() => setMenuOpen(false)}>{t(item.label)}<ArrowUpRight size={17} /></a>)}
        <a href="/app" target="_top" onClick={() => setMenuOpen(false)}>{t("Открыть сервис")}<ArrowRight size={17} /></a>
        <div className="fl-mobile-theme"><span>{t("Язык и оформление")}</span><AppearanceControls className="fl-appearance-controls" /></div>
      </nav>}
    </header>

    <main id="main-content" tabIndex={-1}>
      <section className="fl-hero fl-container" aria-labelledby="fl-hero-title">
        <div className="fl-hero-copy">
          <div className="fl-eyebrow"><span /> {t("Видеоаналитика кассовых операций")}</div>
          <h1 id="fl-hero-title">{t("Проверяйте")}<br />{t("кассовые операции")}<br /><em>{t("по видеозаписи.")}</em></h1>
          <p>{t("Находите нужный момент по таймкоду, изучайте кадры и сопоставляйте действия кассира с применимым правилом.")}</p>
          <div className="fl-hero-actions">
            <a className="fl-button" href="/app" target="_top">{t("Открыть сервис")} <ArrowUpRight size={18} /></a>
            <a className="fl-hero-secondary" href="#product">{t("Посмотреть интерфейс")} <ArrowDown size={16} /></a>
          </div>
          <div className="fl-demo-label"><span /> {t("Сервис подключён к локальным моделям")}</div>
        </div>
        <div className="fl-hero-visual">
          <div className="fl-visual-top"><span><ScanLine size={14} /> FORTE VISION</span><span>{t("01 / ОБЗОР")}</span></div>
          <div className="fl-scene-grid" aria-hidden="true" />
          <div className="fl-scene"><CashdeskScene /></div>
          <div className="fl-scene-insight"><span className="fl-insight-icon"><Focus size={17} /></span><span><strong>{t("Материалы события")}</strong><small>{t("Таймкод · кадры · описание")}</small></span><Check size={17} /></div>
          <div className="fl-visual-bottom"><span>{t("Схема кассовой операции")}</span><span className="fl-scene-hint"><MousePointer2 size={12} /> {t("Поверните сцену")}</span></div>
        </div>
      </section>

      <div className="fl-principles fl-container" aria-label={t("Принципы продукта")}>
        <span><Clock3 size={18} /> {t("События с таймкодами")}</span>
        <span><Focus size={18} /> {t("Кадры для проверки")}</span>
        <span><ShieldCheck size={18} /> {t("Решение за специалистом")}</span>
      </div>

      <section id="product" className="fl-section fl-product-section fl-container" aria-labelledby="fl-product-title">
        <div className="fl-section-heading">
          <div><div className="fl-section-kicker"><span>01</span> {t("Рабочее пространство")}</div><h2 id="fl-product-title">{t("События и кадры")}<br /><em>{t("рядом с видеозаписью.")}</em></h2></div>
          <p>{t("Видеозапись, список событий и материалы проверки находятся рядом. Выберите событие - и сразу откройте нужный фрагмент.")}</p>
        </div>
        <ProductPreview />
        <p className="fl-example-caption"><span aria-hidden="true" /><span>{t("Интерактивный пример. События и таймкоды условные; схема не является кадром видеозаписи.")}</span></p>
      </section>

      <section id="features" className="fl-features-section" aria-labelledby="fl-features-title">
        <div className="fl-container">
          <div className="fl-section-heading">
            <div><div className="fl-section-kicker"><span>02</span> {t("Возможности")}</div><h2 id="fl-features-title">{t("Таймкоды, кадры")}<br /><em>{t("и источники.")}</em></h2></div>
            <p>{t("Сервис помогает разбирать кассовые операции. Оценку события и окончательное решение принимает проверяющий.")}</p>
          </div>
          <div className="fl-feature-grid">
            <article className="fl-feature"><span className="fl-feature-icon"><Clock3 size={25} strokeWidth={1.4} /></span><span className="fl-feature-number">01</span><h3>{t("Переход к событию")}</h3><p>{t("Открывайте отмеченные моменты по таймкоду и смотрите, что происходило до и после.")}</p><div className="fl-feature-bottom"><span>{t("Видеозапись + таймлайн")}</span><ArrowUpRight size={16} /></div></article>
            <article className="fl-feature"><span className="fl-feature-icon"><Focus size={25} strokeWidth={1.4} /></span><span className="fl-feature-number">02</span><h3>{t("Кадры и описание")}</h3><p>{t("Сопоставляйте наблюдаемое действие с кадрами, которые вернул сервис анализа.")}</p><div className="fl-feature-bottom"><span>{t("Кадры и описание")}</span><ArrowUpRight size={16} /></div></article>
            <article className="fl-feature"><span className="fl-feature-icon"><FileCheck2 size={25} strokeWidth={1.4} /></span><span className="fl-feature-number">03</span><h3>{t("Основание проверки")}</h3><p>{t("Изучайте нормативный источник, если он указан в результате, и проверяйте вывод по материалам.")}</p><div className="fl-feature-bottom"><span>{t("Событие + источник")}</span><ArrowUpRight size={16} /></div></article>
          </div>
        </div>
      </section>

      <section id="workflow" className="fl-section fl-workflow-section fl-container" aria-labelledby="fl-workflow-title">
        <div className="fl-section-heading">
          <div><div className="fl-section-kicker"><span>03</span> {t("Как работает")}</div><h2 id="fl-workflow-title">{t("От загрузки записи")}<br /><em>{t("до проверки событий.")}</em></h2></div>
          <p>{t("Загрузите запись, дождитесь обработки и изучите результат. Для знакомства с интерфейсом можно открыть готовый пример.")}</p>
        </div>
        <div className="fl-workflow-steps">
          <article><div className="fl-workflow-number">01 <Upload size={19} /></div><h3>{t("Добавьте видеозапись")}</h3><p>{t("Выберите файл MOV с записью кассовой операции.")}</p></article>
          <article><div className="fl-workflow-number">02 <ScanLine size={19} /></div><h3>{t("Запустите анализ")}</h3><p>{t("Следите за статусом обработки в рабочем пространстве.")}</p></article>
          <article><div className="fl-workflow-number">03 <FileCheck2 size={19} /></div><h3>{t("Проверьте результат")}</h3><p>{t("Откройте события, кадры и доступные источники.")}</p></article>
        </div>
        <div className="fl-pipeline-wrap">
          <div className="fl-pipeline-heading"><div><span className="fl-pipeline-dot" /><strong>{t("Как проходит анализ")}</strong></div><span>{t("Демонстрация")}</span></div>
          <AnalysisPipeline runs={DEMO_ANALYSIS_RUNS} demo />
          <p className="fl-pipeline-caption">{t("Пример последовательности обработки. Эта анимация не анализирует видеозапись.")}</p>
        </div>
      </section>

      <section id="faq" className="fl-faq-section fl-container" aria-labelledby="fl-faq-title">
        <div className="fl-faq-intro"><div className="fl-section-kicker"><span>04</span> {t("Вопросы")}</div><h2 id="fl-faq-title">{t("Перед первой")}<br /><em>{t("проверкой.")}</em></h2><p>{t("Что нужно знать о файлах, результатах и демонстрационном режиме.")}</p></div>
        <div className="fl-faq-list">
          <details open><summary>{t("Какие видеозаписи можно загружать?")}<ChevronDown size={18} /></summary><p>{t("Сервис рассчитан на файлы MOV с записью кассовых операций. Требования к размеру и доступность обработки отображаются при загрузке в рабочем пространстве.")}</p></details>
          <details><summary>{t("Что будет в результате проверки?")}<ChevronDown size={18} /></summary><p>{t("При подключённом сервисе анализа - итог проверки и найденные события с таймкодами, описанием и кадрами. Нормативное основание отображается, если оно передано вместе с результатом. Отмеченное событие требует проверки специалистом.")}</p></details>
          <details><summary>{t("Чем демонстрация отличается от анализа?")}<ChevronDown size={18} /></summary><p>{t("Демонстрация показывает условный пример интерфейса. Для анализа своей записи откройте рабочее пространство, введите API-ключ и загрузите MOV.")}</p></details>
          <details><summary>{t("Где будут обрабатываться видеозаписи?")}<ChevronDown size={18} /></summary><p>{t("Записи обрабатываются моделями на сервере команды без облачных AI API. Для проверки укажите выданный API-ключ, оставив адрес сервера пустым. Демонстрационные примеры отдельно помечены и не являются результатами анализа.")}</p></details>
          <details><summary>{t("Сервис сам принимает решение о нарушении?")}<ChevronDown size={18} /></summary><p>{t("Нет. Он предоставляет материалы для проверки и указывает на возможные признаки нарушений. Сотрудник изучает фрагмент в контексте и принимает окончательное решение.")}</p></details>
        </div>
      </section>

      <section className="fl-cta-section fl-container" aria-labelledby="fl-cta-title">
        <div className="fl-cta-panel">
          <div className="fl-cta-lines" aria-hidden="true"><span /><span /><span /><span /><span /></div>
          <div className="fl-cta-copy"><div className="fl-cta-eyebrow"><span /> {t("Знакомство с продуктом")}</div><h2 id="fl-cta-title">{t("Откройте сервис")}<br />{t("проверки записей.")}</h2><p>{t("Откройте демонстрационный пример или подключите сервер для проверки своей записи.")}</p><a className="fl-button fl-button-white" href="/app" target="_top">{t("Открыть сервис")} <ArrowUpRight size={18} /></a></div>
          <div className="fl-cta-symbol" aria-hidden="true"><div /><div /><div /><Focus size={66} strokeWidth={1} /></div>
        </div>
      </section>
    </main>

    <ForteFooter />
  </div>
}
