import type { Metadata } from "next";
import { cookies } from "next/headers";
import { LOCALE_COOKIE, parseLocale } from "@/lib/i18n";

export async function getRequestLocale() {
  return parseLocale((await cookies()).get(LOCALE_COOKIE)?.value);
}

export async function localizedMetadata(ruTitle: string, kkTitle: string, enTitle: string, extra: Metadata = {}): Promise<Metadata> {
  const locale = await getRequestLocale();
  return { ...extra, title: { ru: ruTitle, kk: kkTitle, en: enTitle }[locale] };
}
