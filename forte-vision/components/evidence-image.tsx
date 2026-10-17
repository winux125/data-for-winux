"use client";
/* eslint-disable @next/next/no-img-element -- Local bounded base64 evidence, with explicit decode fallback. */
import { useEffect, useMemo, useRef, useState } from "react";
import { ImageOff, Loader2, Maximize2 } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import { workspaceMessages } from "@/lib/messages/workspace";
import { formatTime, type EvidenceFrame } from "@/lib/analysis";
import { FRAME_ISSUE_MESSAGES, inspectEvidence, validImageDimensions } from "@/lib/evidence";
import { timecodeIssue } from "@/lib/event-window";

export function EvidenceImage({ source, alt, onReady }: { source: string; alt: string; onReady?: (ready: boolean) => void }) {
  const { t } = useI18n(workspaceMessages);
  const [state,setState] = useState<"loading" | "ready" | "error">("loading");
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  return <div className={`fv-safe-image fv-image-${state}`}>
    {state !== "error" && <img src={source} alt={alt} decoding="async" onError={() => { setState("error"); onReady?.(false); }} onLoad={async e => {
      const node = e.currentTarget;
      try {
        if (!validImageDimensions(node.naturalWidth,node.naturalHeight)) throw new Error();
        if (node.decode) await node.decode();
        if (alive.current) { setState("ready"); onReady?.(true); }
      } catch { if (alive.current) { setState("error"); onReady?.(false); } }
    }}/>}
    {state !== "ready" && <div className="fv-image-placeholder" role="status">{state === "loading" ? <Loader2 className="fv-spin" size={20}/> : <ImageOff size={22}/>}<p>{t(state === "loading" ? "Загрузка кадра…" : "Не удалось декодировать кадр. Описание события сохранено.")}</p></div>}
  </div>;
}
export default function EvidenceFrameCard({ frame, duration, onExpand }: { frame: EvidenceFrame; duration?: number; onExpand: (source: string) => void }) {
  const { t } = useI18n(workspaceMessages);
  const image = useMemo(() => inspectEvidence(frame.image_base64), [frame.image_base64]);
  const [ready,setReady] = useState(false);
  const issue = frame.image_issue || image.issue;
  return <div className="fv-frame-card">
    {image.source && !issue ? <button type="button" disabled={!ready} onClick={() => ready && onExpand(image.source!)}>
      <EvidenceImage key={image.source} source={image.source} alt={t("Кадр события на {time}",{time:formatTime(frame.timestamp_sec)})} onReady={setReady}/>
      <span>{formatTime(frame.timestamp_sec)}{ready && <Maximize2 size={13}/>}</span>
    </button> : <div className="fv-image-placeholder" role="status"><ImageOff size={22}/><p>{t(FRAME_ISSUE_MESSAGES[issue || "invalid"])}</p><span>{formatTime(frame.timestamp_sec)}</span></div>}
    {timecodeIssue(frame.timestamp_sec,duration) === "outside_video" && <small className="fv-frame-time-warning">{t("Таймкод кадра вне записи")}</small>}
  </div>;
}
