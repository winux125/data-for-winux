import { LOCALE_COOKIE, parseLocale, type Locale } from "./i18n";

/** Independent of providers: the root boundary also replaces the root layout. */
export function recoveryLocale(cookie: string, documentLanguage?: string): Locale {
  const value = cookie.split(";").map(part => part.trim()).find(part => part.startsWith(`${LOCALE_COOKIE}=`))?.slice(LOCALE_COOKIE.length + 1);
  if (value !== undefined) {
    try { return parseLocale(decodeURIComponent(value)); } catch { /* Fall back to the existing document language. */ }
  }
  return parseLocale(documentLanguage);
}

export const startupErrorCopy = {
  ru: {
    title: "Forte Vision - ошибка загрузки", heading: "Не удалось открыть страницу",
    description: "Интерфейс не запустился. Обновите страницу или откройте рабочее пространство.",
    navigation: "Восстановление страницы", reload: "Обновить страницу", open: "Открыть сервис",
    details: "Сведения об ошибке", fallback: "Ошибка запуска интерфейса",
  },
  kk: {
    title: "Forte Vision - жүктеу қатесі", heading: "Бетті ашу мүмкін болмады",
    description: "Интерфейс іске қосылмады. Бетті жаңартыңыз немесе жұмыс кеңістігін ашыңыз.",
    navigation: "Бетті қалпына келтіру", reload: "Бетті жаңарту", open: "Сервисті ашу",
    details: "Қате туралы мәліметтер", fallback: "Интерфейсті іске қосу қатесі",
  },
  en: {
    title: "Forte Vision - loading error", heading: "Unable to open this page",
    description: "The interface could not start. Reload the page or open the workspace.",
    navigation: "Page recovery", reload: "Reload page", open: "Open service",
    details: "Error details", fallback: "Interface startup error",
  },
} satisfies Record<Locale, Record<string, string>>;
