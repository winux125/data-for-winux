export const REVEAL_SESSION_KEY = "forte-vision:opening-reveal:v2";
export const REVEAL_HOLD_MS = 650;
export const REVEAL_TRANSITION_MS = 1550;
export const REVEAL_TOTAL_MS = REVEAL_HOLD_MS + REVEAL_TRANSITION_MS;
export const REVEAL_FAILSAFE_MS = 4500;

// This tiny bootstrap runs in <head>, before the landing can paint. The SSR veil
// is already in the document; React only animates it after mounting.
export const openingInitScript = `(function(){try{if(window.location.pathname!=='/'||document.visibilityState==='hidden')return;if(typeof window.matchMedia!=='function'||window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;if(typeof window.requestAnimationFrame!=='function'||!window.CSS||!window.CSS.supports('clip-path','inset(0 0 0 0)'))return;if(window.sessionStorage.getItem('${REVEAL_SESSION_KEY}'))return;if(!document.createElement('canvas').getContext('2d'))return;document.documentElement.dataset.fvIntro='pending';window.setTimeout(function(){delete document.documentElement.dataset.fvIntro},${REVEAL_FAILSAFE_MS})}catch(e){}})();`;

// The visibility and opaque veil do not depend on a dynamically loaded stylesheet.
// Without JavaScript or when reduced motion is requested, the normal page paints.
export const openingCriticalCss = `.fsr-reveal{display:none}html[data-fv-intro=pending] .fsr-reveal{display:block;position:fixed;inset:0;z-index:180;pointer-events:none}.fsr-veil{position:absolute;inset:0;display:grid;place-items:center;background:#fbf8fa}html[data-theme=dark] .fsr-veil{background:#191318}@media(prefers-reduced-motion:reduce){html[data-fv-intro=pending] .fsr-reveal{display:none!important}}`;
