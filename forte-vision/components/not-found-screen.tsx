"use client";

/* eslint-disable @next/next/no-html-link-for-pages -- Use native document navigation for reliable hosted account routes. */
import { ArrowRight, ArrowUpRight, ScanLine } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import { accountMessages } from "@/lib/messages/account";
import { AppearanceControls } from "@/components/theme-provider";
import "./not-found-screen.css";

export default function NotFoundScreen() {
  const { t } = useI18n(accountMessages);
  return <div className="fn-page">
    <header className="fn-header fn-container">
      <a className="fn-brand" href="/" aria-label={t("Forte Vision - на главную")}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="fn-wordmark-light" src="/brand/forte-wordmark-burgundy.svg" width="91" height="27" alt="Forte" />
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className="fn-wordmark-dark" src="/brand/forte-wordmark-white.svg" width="91" height="27" alt="Forte" />
        <span>Vision</span>
      </a>
      <a className="fn-header-link" href="/app" target="_top">{t("Открыть сервис")}<ArrowUpRight size={15} aria-hidden="true" /></a>
    </header>

    <main className="fn-main fn-container" aria-labelledby="fn-title">
      <div className="fn-layout">
        <div className="fn-visual" aria-hidden="true">
          <div className="fn-grid" />
          <div className="fn-frame"><span /><span /><span /><span /></div>
          <span className="fn-error-number">404</span>
          <span className="fn-scan-point"><ScanLine size={22} strokeWidth={1.4} /></span>
          <div className="fn-visual-caption"><span>FORTE VISION</span><span>{t("СТРАНИЦА НЕ НАЙДЕНА")}</span></div>
        </div>
        <div className="fn-copy">
          <p className="fn-kicker"><span /> {t("ОШИБКА 404")}</p>
          <h1 id="fn-title">{t("Такой страницы нет.")}</h1>
          <p className="fn-description">{t("Проверьте адрес или вернитесь на главную. Оттуда можно войти в сервис и открыть демоверсию.")}</p>
          <a className="fn-primary" href="/">{t("На главную")}<ArrowRight size={17} aria-hidden="true" /></a>
          <a className="fn-demo-link" href="/demo" target="_top">{t("Открыть демоверсию")}<ArrowUpRight size={14} aria-hidden="true" /></a>
        </div>
      </div>
    </main>

    <footer className="fn-footer fn-container"><AppearanceControls /><span>Forte Vision · Datathon 2026</span><a href="/privacy">{t("Данные и cookie")}<ArrowUpRight size={12} aria-hidden="true" /></a></footer>
  </div>;
}
