"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { TriangleAlert } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import { formatTime, type Violation } from "@/lib/analysis";
import { isKnownDuration, layoutTimelineMarkers, timecodeIssue } from "@/lib/event-window";
import { workspaceMessages } from "@/lib/messages/workspace";

export default function EventTimeline({ events, duration, currentTime, selectedIndex, onSelect, demo = false }: {
  events: Violation[];
  duration?: number;
  currentTime: number;
  selectedIndex: number;
  onSelect: (index: number) => void;
  demo?: boolean;
}) {
  const { t } = useI18n(workspaceMessages);
  const trackRef = useRef<HTMLDivElement>(null);
  const [trackWidth, setTrackWidth] = useState(320);
  useEffect(() => {
    const node = trackRef.current;
    if (!node) return;
    const measure = () => setTrackWidth(node.getBoundingClientRect().width || 320);
    measure();
    if (typeof ResizeObserver === "function") {
      const observer = new ResizeObserver(measure);
      observer.observe(node);
      return () => observer.disconnect();
    }
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  const markers = useMemo(() => layoutTimelineMarkers(events.map(event => event.timecode_sec), duration, trackWidth), [events, duration, trackWidth]);
  const unplaced = events.flatMap((event, index) => timecodeIssue(event.timecode_sec, duration) ? [{ event, index }] : []);
  const lanes = Math.max(1, ...markers.map(marker => marker.lane + 1));
  const [group,setGroup] = useState<number[] | null>(null);
  const [listOpen,setListOpen] = useState(() => unplaced.length > 0 || selectedIndex >= 0);
  const [page,setPage] = useState(() => Math.floor(Math.max(0,selectedIndex)/20));
  const listHeading = useRef<HTMLHeadingElement>(null);
  const list = group || events.map((_,index)=>index);
  const pageCount = Math.max(1,Math.ceil(list.length/20));
  const safePage = Math.min(page,pageCount-1);
  const openGroup = (indices: number[]) => { setGroup(indices); setPage(Math.max(0,Math.floor(indices.indexOf(selectedIndex)/20))); setListOpen(true); requestAnimationFrame(() => { listHeading.current?.focus(); listHeading.current?.scrollIntoView({block:"nearest"}); }); };
  const rowHeight = 48;
  return <div className="fv-event-timeline">
    <div className="fv-timeline-heading"><strong>{t(events.length ? "Интервалы событий" : "Время записи")}</strong>{events.length > 0 && <span>{t("Контекст ±3 с")}</span>}</div>
    <div ref={trackRef} className="fv-timeline-track" role="group" aria-label={t("Интервалы событий")} style={{ height: isKnownDuration(duration) ? `${lanes * rowHeight}px` : "0px" }}>
      {isKnownDuration(duration) && Array.from({ length: lanes }, (_, lane) => <span key={lane} className="fv-timeline-lane" style={{ top: `${lane * rowHeight + 24}px` }} />)}
      {isKnownDuration(duration) && <span className="fv-timeline-playhead" style={{ left: `${Math.min(100, Math.max(0, currentTime / duration * 100))}%` }} />}
      {markers.map(marker => {
        const index = marker.indices[0]; const event = events[index]; const grouped = marker.indices.length > 1;
        const active = marker.indices.some(index => { const time = events[index].timecode_sec; return currentTime >= Math.max(0,time-3) && currentTime <= Math.min(duration || 0,time+3); });
        const selected = marker.indices.includes(selectedIndex);
        const title = grouped ? t("Группа: {count} событий. {start}–{end}. Открыть список.",{count:marker.indices.length,start:formatTime(marker.start),end:formatTime(marker.end)}) : t("Событие {number}: {type}. Фрагмент {start}–{end}", {
          number:index+1,type:demo?t(event.type):event.type,start:formatTime(marker.start),end:formatTime(marker.end),
        });
        return <div key={marker.indices.join("-")} className={`fv-timeline-event ${selected ? "fv-selected" : ""} ${active ? "fv-current" : ""}`}>
          <span className="fv-timeline-range" style={{left:`${marker.left}%`,width:`${marker.width}%`,top:`${marker.lane*rowHeight+20}px`}}/>
          <button type="button" className={`fv-timeline-marker ${grouped ? "fv-marker-group" : ""}`} style={{left:`${marker.center}%`,top:`${marker.lane*rowHeight+24}px`}} title={title} aria-label={title} aria-current={!grouped && selected?"true":undefined} aria-expanded={grouped ? listOpen && group?.join(",") === marker.indices.join(",") : undefined} aria-controls={grouped?"timeline-event-list":"review-screen"} onClick={()=>grouped?openGroup(marker.indices):onSelect(index)}>{grouped?<span>{marker.indices.length}</span>:<TriangleAlert size={15} aria-hidden="true"/>}</button>
        </div>;
      })}
    </div>
    <div className="fv-timeline-times"><span>{formatTime(currentTime)}</span><span>{isKnownDuration(duration) ? formatTime(duration) : t("Длительность неизвестна")}</span></div>
    {events.length > 0 && <div className="fv-timeline-list-control"><button type="button" className="fv-text-button" aria-expanded={listOpen} aria-controls="timeline-event-list" onClick={()=>{setGroup(null);setPage(0);setListOpen(!listOpen || Boolean(group));}}>{t("Все события ({count})",{count:events.length})}</button>{markers.some(marker=>marker.indices.length>1) && <small>{t("Плотные маркеры объединены. Выберите число, чтобы открыть события группы.")}</small>}</div>}
    {listOpen && <section id="timeline-event-list" className="fv-timeline-list" aria-label={t("Список событий")}>
      <h3 ref={listHeading} tabIndex={-1}>{group?t("События в группе: {count}",{count:list.length}):t("Все события ({count})",{count:events.length})}</h3>
      <ol>{list.slice(safePage*20,(safePage+1)*20).map(index=>{
        const event=events[index]; const issue=timecodeIssue(event.timecode_sec,duration);
        return <li key={index} className={issue?"fv-unplaced-events":""}><button type="button" aria-current={selectedIndex===index?"true":undefined} onClick={()=>onSelect(index)}><span className="fv-event-list-number">{String(index+1).padStart(2,"0")}</span><span>{demo?t(event.type):event.type}<small>{formatTime(event.timecode_sec)} · {t(issue==="outside_video"?"Вне границ записи":issue?"Интервал не подтверждён":"Контекст ±3 с")}</small></span></button></li>;
      })}</ol>
      {pageCount>1 && <nav className="fv-event-list-pages" aria-label={t("Страницы списка событий")}><button className="fv-secondary-button" disabled={safePage===0} onClick={()=>setPage(safePage-1)}>{t("Предыдущее")}</button><span role="status">{t("Страница {page} из {count}",{page:safePage+1,count:pageCount})}</span><button className="fv-secondary-button" disabled={safePage===pageCount-1} onClick={()=>setPage(safePage+1)}>{t("Следующее")}</button></nav>}
    </section>}
    {events.length > 0 && <p className="fv-timeline-hint">{t("Нажмите на «!», чтобы открыть разбор события.")} {t("Фрагмент включает до 3 секунд до и после таймкода события.")}</p>}
  </div>;
}
