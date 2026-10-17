import type { Metadata } from "next";
import "./globals.css";
import "./themes.css";
import { ThemeProvider } from "@/components/theme-provider";
import { themeInitScript } from "@/lib/theme";
import { getRequestLocale } from "@/lib/locale-server";
import { openingCriticalCss, openingInitScript } from "@/lib/opening-reveal";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getRequestLocale();
  const copy = {
    ru: { title: "Forte Vision - анализ кассовых операций", description: "Рабочее пространство для проверки видеозаписей кассовых операций: события, таймкоды и доказательства." },
    kk: { title: "Forte Vision - кассалық операцияларды талдау", description: "Кассалық операциялардың бейнежазбаларын тексеру: оқиғалар, таймкодтар және дәлелдер." },
    en: { title: "Forte Vision - cash transaction review", description: "Review cash transaction recordings with events, timestamps and evidence." },
  }[locale];
  return { ...copy, icons: { icon: "/brand/forte-mark.svg", shortcut: "/brand/forte-mark.svg" } };
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const locale = await getRequestLocale();
  return (
    <html lang={locale} suppressHydrationWarning>
      <head><style dangerouslySetInnerHTML={{ __html: openingCriticalCss }} /><script dangerouslySetInnerHTML={{ __html: themeInitScript + openingInitScript }} /></head>
      <body className="antialiased"><ThemeProvider initialLocale={locale}>{children}</ThemeProvider></body>
    </html>
  );
}
