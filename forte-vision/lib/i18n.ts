export type Locale = "ru" | "kk" | "en";
export type Messages = Record<string, { kk: string; en: string }>;
export type MessageValues = Record<string, string | number>;

export const LOCALE_COOKIE = "forte-locale";
export const LOCALE_TAGS: Record<Locale, string> = { ru: "ru-RU", kk: "kk-KZ", en: "en-GB" };

export function parseLocale(value: unknown): Locale {
  if (typeof value !== "string") return "ru";
  const language = value.trim().toLowerCase().split(/[-_]/, 1)[0];
  return language === "kk" || language === "en" ? language : "ru";
}

export function serializeLocaleCookie(locale: Locale, secure = false): string {
  return `${LOCALE_COOKIE}=${parseLocale(locale)}; Path=/; Max-Age=31536000; SameSite=Lax${secure ? "; Secure" : ""}`;
}

export function createTranslator(locale: Locale, messages: Messages = {}, common: Messages = {}) {
  return (source: string, values?: MessageValues): string => {
    const translated = locale === "ru" ? source : messages[source]?.[locale] || common[source]?.[locale] || source;
    if (!values) return translated;
    return translated.replace(/\{([^{}]+)\}/g, (placeholder, key: string) =>
      Object.prototype.hasOwnProperty.call(values, key) ? String(values[key]) : placeholder,
    );
  };
}
