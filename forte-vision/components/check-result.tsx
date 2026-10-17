"use client";

import { useEffect, useReducer, useRef, useState } from "react";
import { ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, BookOpen, CheckCheck, CircleCheck, Clock3, Film, Focus, Info, LockKeyhole, Loader2, Play, TriangleAlert, Video } from "lucide-react";
import { useI18n } from "@/components/locale-provider";
import EventTimeline from "@/components/event-timeline";
import CashdeskScene from "@/components/ui/cashdesk-scene";
import RuleDetails from "@/components/rule-details";
import CheckState from "@/components/check-state";
import EvidenceFrameCard from "@/components/evidence-image";
import { isFinishedCheck, type StoredCheck } from "@/lib/checks";
import { formatTime, VERDICT_LABELS } from "@/lib/analysis";
import { getEventWindow, isKnownDuration, timecodeIssue } from "@/lib/event-window";
import { initialReviewState, reviewNavigation, type ReviewAction, type ReviewState } from "@/lib/review-navigation";
import { workspaceMessages } from "@/lib/messages/workspace";

export type ReviewCheck = StoredCheck;
interface CheckResultProps {
  check: ReviewCheck;
  onBack: () => void;
  onExport: () => void;
  onMetadata: (metadata: { seconds: number; duration: string }) => void;
  onExpandFrame: (source: string) => void;
  onCancel?: () => void;
  onResume?: () => void;
  onNewCheck?: () => void;
  onAttachFile?: (file: File) => void;
  busy?: boolean;
  reviewState?: ReviewState;
  historyRevision?: number;
  onReviewAction?: (action: ReviewAction, replace?: boolean)=>void;
}
export default function CheckResult(props: CheckResultProps) {
  return isFinishedCheck(props.check) ? <CompletedReview {...props}/> : <CheckState {...props}/>;
}
function CompletedReview({ check, onBack, onExport, onMetadata, onExpandFrame, onAttachFile, reviewState, historyRevision = 0, onReviewAction }: CheckResultProps) {
  const { t } = useI18n(workspaceMessages);
  const [localNavigation,localDispatch] = useReducer(reviewNavigation,initialReviewState);
  const navigation = reviewState || localNavigation;
  const dispatch = (action: ReviewAction, replace = false) => onReviewAction ? onReviewAction(action,replace):localDispatch(action);
  const [playback,setPlayback] = useState<{source?: string; state:"loading"|"ready"|"error"}>({source:check.videoUrl,state:"loading"});
  const playerState = check.demo ? "ready" : !check.videoUrl ? "missing" : playback.source === check.videoUrl ? playback.state : "loading";
  const [playHint, setPlayHint] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const playWhenReady = useRef(false);
  const focusFrames = useRef(false);
  const framesHeading = useRef<HTMLHeadingElement>(null);
  const events = check.result?.violations || [];
  const event = navigation.eventIndex === null ? null : events[navigation.eventIndex];
  const duration = isKnownDuration(check.seconds) ? check.seconds : undefined;
  const invalidTimecodes = events.filter(item => timecodeIssue(item.timecode_sec, duration) === "outside_video").length;
  const invalidFrameTimes = events.flatMap(item => item.evidence_frames).filter(frame => timecodeIssue(frame.timestamp_sec, duration) === "outside_video").length;
  const range = event ? getEventWindow(event.timecode_sec, duration) : null;
  const eventScreen = navigation.screen === "event" && event;
  const currentEvents = events.flatMap((item, index) => {
    const window = getEventWindow(item.timecode_sec, duration);
    return window && navigation.position >= window.start && navigation.position <= window.end ? [index] : [];
  });
  const previousHistoryRevision = useRef(historyRevision);
  const currentIndex = navigation.eventIndex !== null && currentEvents.includes(navigation.eventIndex)
    ? navigation.eventIndex : currentEvents[0];

  useEffect(() => {
    // This is a new screen, not a scroll to a second copy of the same content.
    window.scrollTo({ top: 0, behavior: "instant" });
    const target = focusFrames.current ? framesHeading.current : headingRef.current;
    target?.focus({preventScroll:true});
    if (focusFrames.current) target?.scrollIntoView({block:"start"});
    focusFrames.current = false;
  }, [navigation.screen, navigation.eventIndex, historyRevision]);
  useEffect(()=>{
    if(previousHistoryRevision.current===historyRevision)return;
    previousHistoryRevision.current=historyRevision;playWhenReady.current=false;
    const video=videoRef.current;if(!video)return;
    video.pause();if(video.readyState>0)video.currentTime=Math.min(navigation.position,Number.isFinite(video.duration)?video.duration:navigation.position);
  },[historyRevision,navigation.position]);

  const inspectEvent = (index: number) => {
    if (!events[index]) return;
    const video = videoRef.current;
    const position = video?.currentTime ?? navigation.position;
    video?.pause();
    playWhenReady.current = false;
    dispatch({ type: "inspect", index, count: events.length, position });
  };
  const backToVideo = () => {
    playWhenReady.current = false;
    dispatch({ type: "back_to_video" });
  };
  const watchClip = () => {
    if (!range || playerState !== "ready") return;
    setPlayHint(false);
    playWhenReady.current = Boolean(check.videoUrl);
    dispatch({ type: "watch_clip", ...range });
  };

  const showFrames = () => {
    if (!events.length) return;
    if (eventScreen) { framesHeading.current?.focus(); framesHeading.current?.scrollIntoView({block:"start",behavior:"smooth"}); return; }
    focusFrames.current = true;
    const index = navigation.eventIndex ?? Math.max(0,events.findIndex(item=>item.evidence_frames.length>0));
    inspectEvent(index);
  };
  const failVideo = (video: HTMLVideoElement) => {
    if (videoRef.current !== video) return;
    video.pause(); playWhenReady.current = false; setPlayHint(false);
    setPlayback({source:check.videoUrl,state:"error"}); dispatch({type:"full_video"},true);
  };
  return <section id="review-screen" className="fv-result-review" aria-labelledby="review-heading">
    <div className="fv-result-heading fv-review-heading">
      <button type="button" className="fv-back-link" onClick={eventScreen ? backToVideo : onBack}><ArrowLeft size={16}/>{t(eventScreen ? "К видеозаписи" : "К проверкам")}</button>
      <span className="fv-eyebrow">{check.demo ? t("ДЕМОНСТРАЦИОННЫЙ ПРИМЕР") : check.jobId || check.id}{eventScreen && <> · {t("Событие {number} из {count}", { number: (navigation.eventIndex ?? 0) + 1, count: events.length })}</>}</span>
      <div className="fv-page-title-row">
        <div><h1 id="review-heading" ref={headingRef} tabIndex={-1}>{eventScreen ? check.demo ? t(event.type) : event.type : t("Видеозапись")}</h1><p>{check.demo ? t(check.name) : check.name}</p></div>
        {eventScreen ? playerState === "error" ? <button type="button" className="fv-secondary-button" onClick={showFrames}><Focus size={16}/>{t("К кадрам и описанию")}</button> : <button type="button" className="fv-primary-button" disabled={!range || playerState !== "ready"} onClick={watchClip}><Play size={16}/>{t(playerState === "loading" ? "Видео загружается…" : playerState === "missing" ? "Добавьте исходную запись" : check.demo ? "Показать интервал" : "Смотреть фрагмент")}</button> : <button type="button" className="fv-secondary-button" onClick={onExport}><ArrowDownToLine size={16}/>{t("Скачать результат")}</button>}
      </div>
    </div>

    {navigation.screen === "event" && !event && <div className="fv-notice" role="alert"><Info size={17}/><span>{t("Событие по этой ссылке не найдено. Выберите событие из списка.")}</span></div>}
    {eventScreen ? <div className="fv-event-detail-screen">
      {playerState === "error" && <div className="fv-notice" role="status"><TriangleAlert size={17}/><span>{t("Видео недоступно для воспроизведения. Кадры и описание события можно проверить отдельно.")}</span></div>}
      <nav className="fv-event-navigation" aria-label={t("Переключение событий")}>
        <button type="button" className="fv-secondary-button" disabled={navigation.eventIndex === 0} onClick={() => inspectEvent((navigation.eventIndex ?? 0) - 1)}><ArrowLeft size={15}/>{t("Предыдущее")}</button>
        <span>{t("Событие {number} из {count}", { number: (navigation.eventIndex ?? 0) + 1, count: events.length })}</span>
        <button type="button" className="fv-secondary-button" disabled={navigation.eventIndex === events.length - 1} onClick={() => inspectEvent((navigation.eventIndex ?? 0) + 1)}>{t("Следующее")}<ArrowRight size={15}/></button>
      </nav>
      {timecodeIssue(event.timecode_sec, duration) && <div className="fv-notice fv-time-warning" role="alert"><TriangleAlert size={17}/><span>{t(timecodeIssue(event.timecode_sec, duration) === "outside_video" ? "Таймкод события вне границ записи. Фрагмент недоступен; исходное время сохранено." : "Длительность записи не определена. Интервал пока нельзя проверить или воспроизвести.")}</span></div>}
      <section className="fv-event-explanation" aria-labelledby="event-explanation-title">
        <div className="fv-event-explanation-heading"><h2 id="event-explanation-title">{t("Что произошло")}</h2><span className="fv-timecode"><Clock3 size={13}/>{range ? `${formatTime(range.start)}–${formatTime(range.end)}` : formatTime(event.timecode_sec)}</span></div>
        <p>{check.demo ? t(event.description) : event.description}</p>
        <small>{t("Таймкод события: {time}", { time: formatTime(event.timecode_sec) })} · {range ? t("Контекст ±3 с") : t("Интервал не подтверждён")}</small>
      </section>
      <div className="fv-evidence-grid fv-review-evidence-grid">
        <section className="fv-evidence-card" aria-labelledby="event-frames-title"><h2 ref={framesHeading} id="event-frames-title" tabIndex={-1}><Focus size={17}/>{t("Кадры-доказательства")}</h2>
          {event.evidence_frames.length ? <div className="fv-evidence-frames">{event.evidence_frames.map((frame,index)=><EvidenceFrameCard key={`${navigation.eventIndex}-${index}`} frame={frame} duration={duration} onExpand={onExpandFrame}/>)}</div> : <div className="fv-evidence-empty"><Film size={28}/><p>{check.demo ? t("В демонстрации реальные кадры не используются.") : t("Сервер не передал кадры для этого события.")}</p></div>}
          {Boolean(event.omitted_evidence_frames) && <p className="fv-frame-limit-note">{t("Показаны первые 3 кадра. Дополнительных кадров: {count}.",{count:event.omitted_evidence_frames!})}</p>}
        </section>
        <section className="fv-evidence-card fv-rule-card" aria-labelledby="event-rule-title"><h2 id="event-rule-title"><BookOpen size={17}/>{t("Основание для проверки")}</h2><RuleDetails violation={event}/><p className="fv-human-note"><Info size={14}/><span>{t("Перед подтверждением события проверьте запись и источник.")}</span></p></section>
      </div>
    </div> : <div className="fv-recording-overview">
      <div role="status" className={`fv-verdict-banner ${check.status === "no_violation" ? "fv-clear" : "fv-flagged"}`}><span className="fv-verdict-icon">{check.status === "no_violation" ? <CircleCheck size={23}/> : <Focus size={23}/>}</span><div><strong>{t(VERDICT_LABELS[check.status === "no_violation" ? "no_violation" : "violation"])}</strong><p>{check.status === "no_violation" ? t("Сервис не обнаружил подозрительных событий в записи.") : t("Событий для проверки: {count}.", { count: events.length })}</p></div><span className="fv-result-state"><CheckCheck size={14}/>{t("Проверка завершена")}</span></div>
      {check.demo && <p className="fv-review-demo-note"><Info size={15}/>{t("Демонстрационный результат. События условные; реальные видео и кадры не используются.")}</p>}
      {(!duration || invalidTimecodes > 0 || invalidFrameTimes > 0) && <div className="fv-notice fv-time-warning" role="status"><TriangleAlert size={17}/><span>{t(!duration ? "Длительность записи не определена. Интервалы появятся после чтения метаданных видео." : "Есть таймкоды вне границ записи. Они сохранены в списке событий и не переносятся к концу видео.")}</span></div>}
      <section className="fv-video-panel fv-recording-panel" aria-labelledby="review-video-title">
        <div className="fv-panel-header"><h2 id="review-video-title"><Film size={17}/>{t(navigation.clip ? "Просмотр фрагмента" : "Видеозапись")}</h2><span>{navigation.clip ? `${formatTime(navigation.clip.start)}–${formatTime(navigation.clip.end)}` : check.duration}</span></div>
        <div className="fv-video-stage">
          {check.videoUrl ? <>
            <video ref={videoRef} aria-label={t("Видеозапись")} src={check.videoUrl} controls={playerState === "ready"} aria-hidden={playerState === "error"} tabIndex={playerState === "error" ? -1 : undefined} playsInline muted preload="auto"
              onLoadStart={() => setPlayback(previous => previous.source === check.videoUrl && previous.state === "error" ? previous : {source:check.videoUrl,state:"loading"})}
              onCanPlay={e => {
                const video = e.currentTarget;
                setPlayback({source:check.videoUrl,state:"ready"});
                if (playWhenReady.current) { playWhenReady.current = false; void video.play().catch(error => { if (videoRef.current !== video) return; if (error?.name === "NotSupportedError") failVideo(video); else if (error?.name !== "AbortError") setPlayHint(true); }); }
              }}
              onLoadedMetadata={event => {
                const video = event.currentTarget;
                const seconds = video.duration;
                if (Number.isFinite(seconds) && seconds > 0 && seconds !== check.seconds) onMetadata({ seconds, duration: formatTime(seconds) });
                video.currentTime = Math.min(navigation.position, Number.isFinite(seconds) ? seconds : navigation.position);
              }}
              onPlay={event => {
                if (navigation.clip && (event.currentTarget.currentTime < navigation.clip.start || event.currentTarget.currentTime >= navigation.clip.end)) event.currentTarget.currentTime = navigation.clip.start;
              }}
              onTimeUpdate={event => {
                const video = event.currentTarget;
                let seconds = video.currentTime;
                if (navigation.clip && !video.paused && seconds >= navigation.clip.end) { video.pause(); seconds = navigation.clip.end; video.currentTime = seconds; }
                dispatch({ type: "time", seconds });
              }}
              onSeeked={event => dispatch({ type: "time", seconds: event.currentTarget.currentTime })}
              onError={e => failVideo(e.currentTarget)}/>
            <span className="fv-video-stamp">{t("ИСХОДНАЯ ЗАПИСЬ")}</span>
            {playerState === "loading" && <div className="fv-player-loading" role="status"><Loader2 className="fv-spin" size={24}/><p>{t("Видео загружается…")}</p></div>}
            {playerState === "error" && <div className="fv-player-failure" role="alert"><Film size={30}/><strong>{t("Видео недоступно для воспроизведения")}</strong><p>{t("Браузер не поддерживает кодек или запись повреждена. Проверьте событие по кадрам и описанию.")}</p>{events.length>0 && <button type="button" className="fv-secondary-button" onClick={showFrames}><Focus size={16}/>{t("К кадрам и описанию")}</button>}</div>}
          </> : check.demo ? <div className="fv-demo-video"><CashdeskScene compact active={false}/><div className="fv-demo-video-label"><span><Video size={14}/>{t("СХЕМА КАССОВОЙ ЗОНЫ")}</span><small>{t("Иллюстрация · не кадр видеозаписи")}</small></div></div> : <div className="fv-missing-video"><Film size={30}/><p>{t("Исходная запись недоступна после перезагрузки. Добавьте тот же MOV для просмотра; повторная отправка на сервер не нужна.")}</p>{onAttachFile && <label className="fv-secondary-button">{t("Добавить исходную запись")}<input type="file" accept=".mov,video/quicktime" onChange={event => { const file = event.target.files?.[0]; if (file) onAttachFile(file); event.target.value = ""; }}/></label>}</div>}
          {currentIndex !== undefined && <button type="button" className="fv-video-event-alert" onClick={() => inspectEvent(currentIndex)} aria-controls="review-screen"><TriangleAlert size={16}/><span>{t("Событие {number}", { number: currentIndex + 1 })}</span><ArrowUpRight size={14}/></button>}
        </div>
        {navigation.clip && playerState !== "error" && <div className="fv-review-clip-mode"><span><Clock3 size={14}/>{t("Просмотр фрагмента")} {formatTime(navigation.clip.start)}–{formatTime(navigation.clip.end)}</span><button type="button" onClick={() => dispatch({ type: "full_video" })}>{t("Вся запись")}<ArrowUpRight size={14}/></button></div>}
        {playHint && playerState === "ready" && <p className="fv-review-play-hint">{t("Нажмите кнопку воспроизведения на видео.")}</p>}
        <EventTimeline events={events} duration={duration} currentTime={navigation.position} selectedIndex={navigation.eventIndex ?? -1} onSelect={inspectEvent} demo={Boolean(check.demo)} />
        <div className="fv-video-caption"><LockKeyhole size={13}/>{check.demo ? t("Для реального результата подключите API") : t("Видео доступно только в этом сеансе")}</div>
      </section>
    </div>}
    <div className="fv-notice fv-review-legal"><Info size={17}/><span>{t("Результат является подсказкой для проверки человеком, а не окончательным юридическим или дисциплинарным заключением.")}</span></div>
  </section>;
}
