"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Check, ChevronDown, ChevronRight } from "lucide-react";
import { DropdownMenu as DropdownPrimitive } from "radix-ui";
import { createTranslator, LOCALE_TAGS, parseLocale, serializeLocaleCookie, type Locale, type Messages } from "@/lib/i18n";
import { commonMessages } from "@/lib/messages/common";
import "./theme-provider.css";

type LocaleContextValue = { locale: Locale; localeTag: string; setLocale: (locale: Locale) => void };
const LocaleContext = createContext<LocaleContextValue>({ locale: "ru", localeTag: LOCALE_TAGS.ru, setLocale: () => {} });
const emptyMessages: Messages = {};
const pageTitles: Record<string, Record<Locale, string>> = {
  "/": { ru: "Forte Vision - анализ кассовых операций", kk: "Forte Vision - кассалық операцияларды талдау", en: "Forte Vision - cash transaction review" },
  "/app": { ru: "Проверки - Forte Vision", kk: "Тексерулер - Forte Vision", en: "Reviews - Forte Vision" },
  "/demo": { ru: "Демонстрация - Forte Vision", kk: "Демонстрация - Forte Vision", en: "Demo - Forte Vision" },
  "/privacy": { ru: "Данные и cookie - Forte Vision", kk: "Деректер және cookie - Forte Vision", en: "Data and cookies - Forte Vision" },
};
const missingPageTitles: Record<Locale, string> = { ru: "Страница не найдена - Forte Vision", kk: "Бет табылмады - Forte Vision", en: "Page not found - Forte Vision" };

export function LocaleProvider({ initialLocale = "ru", children }: { initialLocale?: Locale; children: ReactNode }) {
  const [locale, updateLocale] = useState<Locale>(() => parseLocale(initialLocale));

  useEffect(() => {
    document.documentElement.lang = locale;
    document.title = (pageTitles[window.location.pathname] ?? missingPageTitles)[locale];
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    const safe = parseLocale(next);
    updateLocale(safe);
    try { document.cookie = serializeLocaleCookie(safe, window.location.protocol === "https:"); } catch { /* The current tab can still switch language. */ }
  }, []);
  const value = useMemo(() => ({ locale, localeTag: LOCALE_TAGS[locale], setLocale }), [locale, setLocale]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() { return useContext(LocaleContext); }

export function useI18n(messages: Messages = emptyMessages) {
  const { locale, localeTag } = useLocale();
  const t = useMemo(() => createTranslator(locale, messages, commonMessages), [locale, messages]);
  return { locale, localeTag, t };
}

const labels: Record<Locale, string> = { ru: "RU", kk: "ҚАЗ", en: "EN" };
const languageNames: Record<Locale, string> = { ru: "Русский", kk: "Қазақша", en: "English" };
const languages: Locale[] = ["ru", "kk", "en"];

export function LocaleToggle({ compact = true, className = "", menu = false }: { compact?: boolean; className?: string; menu?: boolean }) {
  const { locale, setLocale } = useLocale();
  const { t } = useI18n();
  const label = `${t("Язык интерфейса")}: ${languageNames[locale]}`;
  const items = <DropdownPrimitive.RadioGroup value={locale} onValueChange={next => setLocale(parseLocale(next))} aria-label={t("Язык интерфейса")}>
    {languages.map(language => <DropdownPrimitive.RadioItem className="fv-appearance-option" value={language} key={language} lang={language}>
      <span>{languageNames[language]}</span><DropdownPrimitive.ItemIndicator className="fv-appearance-check"><Check size={15} strokeWidth={1.8} aria-hidden="true" /></DropdownPrimitive.ItemIndicator>
    </DropdownPrimitive.RadioItem>)}
  </DropdownPrimitive.RadioGroup>;
  if (menu) return <DropdownPrimitive.Sub>
    <DropdownPrimitive.SubTrigger className={`fv-locale-switch fv-locale-subtrigger ${className}`} data-compact={compact} aria-label={label} title={label}>
      <span aria-hidden="true">{labels[locale]}</span><ChevronRight size={12} strokeWidth={1.7} aria-hidden="true" />
    </DropdownPrimitive.SubTrigger>
    <DropdownPrimitive.Portal><DropdownPrimitive.SubContent className="fv-appearance-menu" sideOffset={8} collisionPadding={12}>
      {items}
    </DropdownPrimitive.SubContent></DropdownPrimitive.Portal>
  </DropdownPrimitive.Sub>;
  return <DropdownPrimitive.Root>
    <DropdownPrimitive.Trigger asChild><button type="button" className={`fv-locale-switch ${className}`} data-compact={compact} aria-label={label} title={label}>
      <span aria-hidden="true">{labels[locale]}</span><ChevronDown size={11} strokeWidth={1.7} aria-hidden="true" />
    </button></DropdownPrimitive.Trigger>
    <DropdownPrimitive.Portal><DropdownPrimitive.Content className="fv-appearance-menu" align="end" sideOffset={8} collisionPadding={12}>{items}</DropdownPrimitive.Content></DropdownPrimitive.Portal>
  </DropdownPrimitive.Root>;
}
