export type ThemeMode = "system" | "light" | "dark";
export const THEME_KEY = "forte-vision-theme";

export function parseTheme(value: unknown): ThemeMode {
  return value === "light" || value === "dark" ? value : "system";
}

export function resolveTheme(mode: ThemeMode, systemDark: boolean): "light" | "dark" {
  return mode === "system" ? (systemDark ? "dark" : "light") : mode;
}

// Runs before the page is painted. A blocked storage API never blocks the page.
export const themeInitScript = `(function(){try{var t='system';try{var s=localStorage.getItem('${THEME_KEY}');if(s==='light'||s==='dark')t=s}catch(e){}var d=t==='dark'||(t==='system'&&window.matchMedia&&window.matchMedia('(prefers-color-scheme: dark)').matches);var r=document.documentElement;r.dataset.theme=d?'dark':'light';r.classList.toggle('dark',d);r.style.colorScheme=d?'dark':'light'}catch(e){}})();`;
