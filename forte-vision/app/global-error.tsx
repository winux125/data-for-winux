"use client";

import { useEffect, useRef, useState } from "react";
import { clientErrorText, reportClientError } from "@/lib/client-error";
import type { Locale } from "@/lib/i18n";
import { recoveryLocale, startupErrorCopy } from "@/lib/startup-error";

export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  const [locale, setLocale] = useState<Locale>("ru");
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    let cookie = "";
    try { cookie = document.cookie; } catch { /* Recovery works with blocked storage. */ }
    // Locale comes from browser state after hydration; the error shell has no provider.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLocale(recoveryLocale(cookie, document.documentElement.lang));
    heading.current?.focus();
  }, []);
  useEffect(() => { reportClientError(error, "boundary"); }, [error]);
  const copy = startupErrorCopy[locale];

  return <html lang={locale}><head><title>{copy.title}</title><meta name="viewport" content="width=device-width, initial-scale=1" /><style>{`
    @font-face{font-family:Open Sans;src:url('/brand/open-sans-cyrillic.woff2') format('woff2');font-weight:300 800;font-display:swap;unicode-range:U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116}@font-face{font-family:Open Sans;src:url('/brand/open-sans-latin.woff2') format('woff2');font-weight:300 800;font-display:swap;unicode-range:U+0000-00FF}
    *{box-sizing:border-box}body{margin:0;background:#faf8f9;color:#4a0221;font-family:Open Sans,Arial,sans-serif;min-height:100vh;display:grid;place-items:center;padding:28px}
    main{width:min(100%,560px);padding:42px;border:1px solid #e7dfe3;border-radius:24px;background:#fff}img{display:block;margin-bottom:48px}small{font-size:12px;color:#8c737e}h1{font-size:clamp(26px,5vw,36px);font-weight:600;line-height:1.2;letter-spacing:-.03em;margin:12px 0 18px}p{font-size:14px;line-height:1.65;color:#77616d}nav{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}button,a{font:600 13px Open Sans,Arial,sans-serif;min-height:44px;padding:12px 18px;border-radius:9px;text-decoration:none;cursor:pointer;border:1px solid #a31551}button{background:#a31551;color:white}a{color:#a31551;background:white}summary{cursor:pointer;font-size:12px;color:#77616d}details{margin-top:36px;padding-top:20px;border-top:1px solid #eee6ea}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.5 monospace;color:#77616d}button:focus-visible,a:focus-visible,summary:focus-visible{outline:3px solid #edb4cd;outline-offset:4px}@media(max-width:520px){body{padding:16px}main{padding:28px 24px}}
  `}</style></head><body><main aria-labelledby="startup-heading">
    {/* eslint-disable-next-line @next/next/no-img-element */}
    <img src="/brand/forte-wordmark-burgundy.svg" alt="Forte" width="94" height="32" />
    <small>FORTE VISION</small><h1 id="startup-heading" ref={heading} tabIndex={-1}>{copy.heading}</h1>
    <p>{copy.description}</p>
    <nav aria-label={copy.navigation}><button type="button" onClick={() => window.location.reload()}>{copy.reload}</button><a href="/app" target="_top">{copy.open}</a></nav>
    <details><summary>{copy.details}</summary><pre>{clientErrorText(error?.message) || copy.fallback}</pre><small>FV-STARTUP-TRACE-1{error?.digest ? ` · ${clientErrorText(error.digest, 80)}` : ""}</small></details>
  </main></body></html>;
}
