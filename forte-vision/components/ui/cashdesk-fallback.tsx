"use client";

import { useId } from "react";
import { useI18n } from "@/components/locale-provider";
import { productMessages } from "@/lib/messages/product";

export default function SceneFallback() {
  const { t } = useI18n(productMessages)
  const id = useId().replace(/:/g, "")
  return <svg viewBox="0 0 520 320" width="100%" height="100%" role="img" aria-label={t("Схема: видеозапись кассы, анализ операций и доказательства")}>
    <defs><filter id={`${id}-shadow`} x="-30%" y="-50%" width="160%" height="200%"><feGaussianBlur stdDeviation="9" /></filter><linearGradient id={`${id}-plinth`} x2="0" y2="1"><stop stopColor="#FFFFFF" /><stop offset="1" stopColor="#EAE1E6" /></linearGradient></defs>
    <ellipse cx="270" cy="252" rx="179" ry="31" fill="#4A0221" opacity=".06" filter={`url(#${id}-shadow)`} />
    <path d="M63 207 302 130 470 210 228 291Z" fill="#E1D6DD" /><path d="m63 194 239-77 168 80-242 81Z" fill={`url(#${id}-plinth)`} /><path d="M63 194v13l165 84v-13Z" fill="#E6DFE3" />
    <path d="m158 156 112-35 77 37-111 37Z" fill="#FFFFFF" /><path d="m163 164 73 35v64l-73-35Z" fill="#A31551" /><path d="m236 199 106-36v64l-106 36Z" fill="#851044" />
    <path d="m158 156 78 38 111-36v11l-111 37-78-39Z" fill="#F4ECEF" />
    <path d="m182 157 16-5 14 7-16 5Z" fill="#DEDADE" /><path d="m197 156 2-24 8-2v26Z" fill="#4A0221" />
    <path d="m175 95 48 22v40l-48-22Z" fill="#3F2738" /><path d="m180 102 37 17v29l-37-17Z" fill="#FBF8FA" /><path d="m185 110 17 8v4l-17-8Z" fill="#A31551" /><path d="m185 122 26 12v2l-26-12Z" fill="#DFD1D9" />
    <path d="m281 164 16-5 15 7-17 5Z" fill="#D6DED1" /><path d="m278 159 16-5 15 7-17 5Z" fill="#E8ECE2" /><path d="m288 156 5-1 15 7-5 2Z" fill="#A31551" />
    <path d="M123 175V91h7v84Z" fill="#D3C6CF" /><path d="m126 92 33-10 6 4-36 11Z" fill="#D3C6CF" /><path d="m151 73 33-10 21 12-32 11Z" fill="#FFFFFF" /><path d="m151 73 22 13v18l-22-13Z" fill="#F1EAEE" /><path d="m173 86 32-11v19l-32 10Z" fill="#DFD1D9" /><ellipse cx="195" cy="87" rx="6" ry="8" fill="#4A0221" />
    <path d="m339 102 96 44v76l-96-43Z" fill="#4A0221" /><path d="m346 112 81 38v59l-81-37Z" fill="#FFFFFF" /><path d="m353 127 43 20v33l-43-19Z" fill="#EEE2E8" /><path d="m359 144 30 14v16l-30-14Z" fill="#A31551" /><path d="m378 144 13 6v12l-13-6Z" fill="none" stroke="#E2206F" strokeWidth="1.5" /><path d="m403 151 17 8m-17 0 17 8m-17 0 12 6" fill="none" stroke="#B5A5AE" strokeWidth="2" />
    <path d="M381 199v25l10 5v-25Z" fill="#4A0221" /><path d="m369 225 22-7 20 10-22 7Z" fill="#E1D5DC" />
    <path d="m270 148 39-13 29 14-40 13Z" fill="#E2206F" opacity=".09" stroke="#E2206F" strokeWidth="1.5" strokeDasharray="7 18" />
    <path d="m350 239 30-10 24 12-30 10Z" fill="#FFFFFF" stroke="#E0D4DC" /><path d="m359 240 15-5m-10 8 20-6" stroke="#A31551" strokeWidth="2" />
  </svg>
}
