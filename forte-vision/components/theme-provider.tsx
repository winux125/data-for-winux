"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Check, ChevronRight, Monitor, MoonStar, Sun } from "lucide-react";
import { DropdownMenu as DropdownPrimitive } from "radix-ui";
import { parseTheme, resolveTheme, THEME_KEY, type ThemeMode } from "@/lib/theme";
import { listenMediaQuery, readMediaQuery } from "@/lib/browser-media";
import { LocaleProvider, LocaleToggle, useI18n } from "@/components/locale-provider";
import type { Locale } from "@/lib/i18n";
import "./theme-provider.css";

type ThemeContextValue = { mode: ThemeMode; resolved: "light" | "dark"; setTheme: (mode: ThemeMode) => void };
const ThemeContext = createContext<ThemeContextValue>({ mode: "system", resolved: "light", setTheme: () => {} });

export function ThemeProvider({ children, initialLocale = "ru" }: { children: ReactNode; initialLocale?: Locale }) {
  const [mode, setMode] = useState<ThemeMode>("system");
  const [systemDark, setSystemDark] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const media = readMediaQuery("(prefers-color-scheme: dark)");
    // The first client render must match SSR; browser preferences become available after hydration.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    try { setMode(parseTheme(localStorage.getItem(THEME_KEY))); } catch { /* Keep a usable system default. */ }
    setSystemDark(media?.matches ?? false);
    setReady(true);
    const syncSystem = (event: MediaQueryListEvent) => setSystemDark(event.matches);
    const syncStorage = (event: StorageEvent) => {
      if (event.key === THEME_KEY || event.key === null) setMode(parseTheme(event.newValue));
    };
    const stopMedia = listenMediaQuery(media, syncSystem);
    window.addEventListener("storage", syncStorage);
    return () => { stopMedia(); window.removeEventListener("storage", syncStorage); };
  }, []);

  const resolved = resolveTheme(mode, systemDark);
  useEffect(() => {
    if (!ready) return;
    const root = document.documentElement;
    root.dataset.theme = resolved;
    root.classList.toggle("dark", resolved === "dark");
    root.style.colorScheme = resolved;
  }, [resolved, ready]);

  const setTheme = useCallback((next: ThemeMode) => {
    const safe = parseTheme(next);
    setMode(safe);
    try { localStorage.setItem(THEME_KEY, safe); } catch { /* The current tab still changes theme. */ }
  }, []);
  const value = useMemo(() => ({ mode, resolved, setTheme }), [mode, resolved, setTheme]);
  return <LocaleProvider initialLocale={initialLocale}><ThemeContext.Provider value={value}>{children}</ThemeContext.Provider></LocaleProvider>;
}

export function useTheme() { return useContext(ThemeContext); }

const choices = [
  { mode: "system", label: "Системная тема", shortLabel: "Системная", Icon: Monitor },
  { mode: "light", label: "Светлая тема", shortLabel: "Светлая", Icon: Sun },
  { mode: "dark", label: "Тёмная тема", shortLabel: "Тёмная", Icon: MoonStar },
] as const;

export function ThemeToggle({ compact = false, className = "", menu = false }: { compact?: boolean; className?: string; menu?: boolean }) {
  const { mode, setTheme } = useTheme();
  const { t } = useI18n();
  const active = choices.find(choice => choice.mode === mode) ?? choices[0];
  const Icon = active.Icon;
  const label = t("Тема оформления: {theme}", { theme: t(active.shortLabel) });
  const items = <DropdownPrimitive.RadioGroup value={mode} onValueChange={next => setTheme(parseTheme(next))} aria-label={t("Тема оформления")}>
    {choices.map(({ mode: choice, shortLabel, Icon: ChoiceIcon }) => <DropdownPrimitive.RadioItem className="fv-appearance-option" key={choice} value={choice}>
      <ChoiceIcon size={17} strokeWidth={1.6} aria-hidden="true" /><span>{t(shortLabel)}</span><DropdownPrimitive.ItemIndicator className="fv-appearance-check"><Check size={15} strokeWidth={1.8} aria-hidden="true" /></DropdownPrimitive.ItemIndicator>
    </DropdownPrimitive.RadioItem>)}
  </DropdownPrimitive.RadioGroup>;
  if (menu) return <DropdownPrimitive.Sub>
    <DropdownPrimitive.SubTrigger className={`fv-theme-trigger fv-theme-subtrigger ${className}`} data-compact={compact} aria-label={label} title={label}><Icon size={18} strokeWidth={1.6} aria-hidden="true" /><ChevronRight size={11} aria-hidden="true" /></DropdownPrimitive.SubTrigger>
    <DropdownPrimitive.Portal><DropdownPrimitive.SubContent className="fv-appearance-menu" sideOffset={8} collisionPadding={12}>{items}</DropdownPrimitive.SubContent></DropdownPrimitive.Portal>
  </DropdownPrimitive.Sub>;
  return <DropdownPrimitive.Root>
    <DropdownPrimitive.Trigger asChild><button className={`fv-theme-trigger ${className}`} data-compact={compact} type="button" aria-label={label} title={label}><Icon size={18} strokeWidth={1.6} aria-hidden="true" /></button></DropdownPrimitive.Trigger>
    <DropdownPrimitive.Portal><DropdownPrimitive.Content className="fv-appearance-menu" align="end" sideOffset={8} collisionPadding={12}>{items}</DropdownPrimitive.Content></DropdownPrimitive.Portal>
  </DropdownPrimitive.Root>;
}

export function AppearanceControls({ className = "", menu = false }: { className?: string; menu?: boolean }) {
  return <div className={`fv-appearance-controls ${className}`}><LocaleToggle compact menu={menu} /><ThemeToggle compact menu={menu} /></div>;
}
