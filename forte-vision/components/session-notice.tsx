"use client";

import { Cookie, X } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import { accountMessages } from "@/lib/messages/account";
import { useEffect, useRef, useState } from "react";
import "./session-notice.css";

const ACKNOWLEDGEMENT = "forte-vision-cookie-notice";

export default function SessionNotice() {
  const { t } = useI18n(accountMessages);
  const [open, setOpen] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    try {
      if (!localStorage.getItem(ACKNOWLEDGEMENT)) timer = setTimeout(() => setOpen(true), 1800);
    } catch { /* The notice can still be opened from the footer. */ }
    const reopen = () => {
      if (timer) clearTimeout(timer);
      triggerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      setOpen(true);
      requestAnimationFrame(() => closeRef.current?.focus());
    };
    window.addEventListener("forte:cookie-settings", reopen);
    return () => { if (timer) clearTimeout(timer); window.removeEventListener("forte:cookie-settings", reopen); };
  }, []);

  const dismiss = () => {
    try { localStorage.setItem(ACKNOWLEDGEMENT, "essential"); } catch { /* Dismissal remains available without storage. */ }
    setOpen(false);
    triggerRef.current?.focus();
    triggerRef.current = null;
  };
  if (!open) return null;
  return <section className="fv-cookie-notice" aria-labelledby="fv-cookie-title">
    <div className="fv-cookie-symbol"><Cookie size={23} strokeWidth={1.4} aria-hidden="true" /></div>
    <button ref={closeRef} className="fv-cookie-close" type="button" aria-label={t("Закрыть уведомление о cookies")} onClick={dismiss}><X size={17} aria-hidden="true" /></button>
    <div className="fv-cookie-copy"><h2 id="fv-cookie-title">{t("Настройки браузера")}</h2><p>{t("Тема сохраняется в браузере, язык — в cookie настроек. Регистрация и cookie для входа не нужны.")}</p></div>
    <div className="fv-cookie-actions"><a href="/privacy">{t("Подробнее о данных")}</a><button type="button" onClick={dismiss}>{t("Понятно")}</button></div>
  </section>;
}
