"use client";

import { useI18n } from "@/components/locale-provider"
import { productMessages } from "@/lib/messages/product"
import * as React from "react";
import { Box, Check, ChevronDown, Circle, Clock3, Download, FileVideo, Image, Info, List, LoaderCircle, Play, ScanLine, ShieldCheck, Upload, X } from "lucide-react";
import { readMediaQuery } from "@/lib/browser-media";
import "./analysis-pipeline.css";

export type AnalysisStatus = "queued" | "running" | "passed" | "failed" | "canceled";
export interface AnalysisLog { time: string; message: string; level?: "info" | "warning" | "error" }
export interface AnalysisStage {
  id: string;
  name: string;
  kind: "upload" | "frames" | "analysis" | "evidence";
  status: AnalysisStatus;
  durationMs?: number;
  logs: AnalysisLog[];
}
export interface AnalysisRun { id: string; title: string; startedAt: string; stages: AnalysisStage[] }
export interface AnalysisPipelineProps {
  runs: AnalysisRun[];
  selectedRunId?: string;
  onRunChange?: (run: AnalysisRun) => void;
  onStageSelect?: (stage: AnalysisStage, run: AnalysisRun) => void;
  onReplay?: (run: AnalysisRun) => void;
  compact?: boolean;
  className?: string;
  demo?: boolean;
}

/** Invented examples for the explicitly labeled interface preview. No model is executed. */
export const DEMO_ANALYSIS_RUNS: AnalysisRun[] = [
  {
    id: "preview-01", title: "Пример проверки", startedAt: "2026-10-17T10:00:00+05:00",
    stages: [
      { id: "upload", name: "Загрузка", kind: "upload", status: "passed", durationMs: 2600, logs: [
        { time: "00:00", message: "Пример: запись принята для проверки." },
        { time: "00:02", message: "Пример: формат файла прочитан." },
      ] },
      { id: "frames", name: "Кадры", kind: "frames", status: "passed", durationMs: 9100, logs: [
        { time: "00:03", message: "Пример: начата подготовка кадров." },
        { time: "00:11", message: "Пример: кадры готовы для следующего этапа." },
      ] },
      { id: "analysis", name: "Анализ", kind: "analysis", status: "passed", durationMs: 24000, logs: [
        { time: "00:12", message: "Пример: проверяются действия в кассовой зоне." },
        { time: "00:35", message: "Пример: отмечен фрагмент для просмотра сотрудником." },
      ] },
      { id: "evidence", name: "Доказательства", kind: "evidence", status: "passed", durationMs: 4200, logs: [
        { time: "00:36", message: "Пример: к событию добавлены таймкод и кадры." },
        { time: "00:40", message: "Пример: результат готов к просмотру." },
      ] },
    ],
  },
  {
    id: "preview-02", title: "Пример ошибки файла", startedAt: "2026-10-17T09:50:00+05:00",
    stages: [
      { id: "upload", name: "Загрузка", kind: "upload", status: "failed", durationMs: 1200, logs: [
        { time: "00:00", message: "Пример: начато чтение файла." },
        { time: "00:01", message: "Пример: файл не удалось прочитать. Выберите другую запись.", level: "error" },
      ] },
      { id: "frames", name: "Кадры", kind: "frames", status: "canceled", logs: [] },
      { id: "analysis", name: "Анализ", kind: "analysis", status: "canceled", logs: [] },
      { id: "evidence", name: "Доказательства", kind: "evidence", status: "canceled", logs: [] },
    ],
  },
];

const STATUS_LABEL: Record<AnalysisStatus, string> = { queued: "В очереди", running: "В работе", passed: "Готово", failed: "Ошибка", canceled: "Остановлено" };
const stageIcon = (kind: AnalysisStage["kind"]) => kind === "upload" ? Upload : kind === "frames" ? Image : kind === "evidence" ? ShieldCheck : ScanLine;
const statusIcon = (status: AnalysisStatus) => status === "passed" ? Check : status === "failed" || status === "canceled" ? X : status === "running" ? LoaderCircle : Circle;
const formatDuration = (ms: number | undefined, localeTag: string, minute: string, second: string) => {
  if (ms === undefined || !Number.isFinite(ms)) return "-";
  const safe = Math.max(0, ms);
  // ICU versions disagree on the Kazakh decimal separator during SSR hydration.
  const numberLocale = localeTag.startsWith("kk") ? "ru-RU" : localeTag;
  return safe >= 60_000 ? `${Math.floor(safe / 60_000)} ${minute} ${Math.floor(safe % 60_000 / 1000)} ${second}` : `${(safe / 1000).toLocaleString(numberLocale, { maximumFractionDigits: 1 })} ${second}`;
};
const runStatus = (stages: AnalysisStage[]): AnalysisStatus => stages.some(stage => stage.status === "failed") ? "failed" : stages.some(stage => stage.status === "running") ? "running" : stages.some(stage => stage.status === "canceled") ? "canceled" : !stages.length || stages.some(stage => stage.status === "queued") ? "queued" : "passed";
const points = (vertices: number[][]) => vertices.map(point => point.map(value => value.toFixed(2)).join(",")).join(" ");

/** The serpentine arrangement preserves reading order when the container wraps. */
function stations(count: number, width: number) {
  const columns = Math.max(1, Math.min(count, Math.floor(width / 122)));
  const rows = Math.ceil(count / columns);
  return {
    height: Math.max(160, rows * 152 + 8),
    nodes: Array.from({ length: count }, (_, index) => {
      const row = Math.floor(index / columns);
      const column = row % 2 ? columns - 1 - index % columns : index % columns;
      const x = (column + .5) * width / columns, y = 72 + row * 152;
      const base = [[x, y - 18], [x + 28, y - 4], [x, y + 10], [x - 28, y - 4]];
      return { x, y, base, roof: base.map(([px, py]) => [px, py - 24]) };
    }),
  };
}

function formatStart(value: string, localeTag: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Время не указано" : new Intl.DateTimeFormat(localeTag, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "Asia/Almaty" }).format(date);
}

/** Displays supplied state. It never uploads files or invokes a remote model. */
export function AnalysisPipeline({ runs, selectedRunId, onRunChange, onStageSelect, onReplay, compact = false, className = "", demo = false }: AnalysisPipelineProps) {
  const { t, localeTag } = useI18n(productMessages);
  const duration = (ms?: number) => formatDuration(ms, localeTag, t("мин"), t("с"));
  const runTitle = (item: AnalysisRun) => demo ? t(item.title) : item.title;
  const stageName = (item: AnalysisStage) => demo ? t(item.name) : item.name;
  const logMessage = (item: AnalysisLog) => demo ? t(item.message) : item.message;
  const [localRunId, setLocalRunId] = React.useState(runs[0]?.id);
  const [selectedStageId, setSelectedStageId] = React.useState<string | null>(null);
  const [view, setView] = React.useState<"pipeline" | "list">("pipeline");
  const [width, setWidth] = React.useState(600);
  const [logFilter, setLogFilter] = React.useState<"all" | "issues">("all");
  const [replayedRun, setReplayedRun] = React.useState<AnalysisRun | null>(null);
  const [isReplaying, setIsReplaying] = React.useState(false);
  const [announcement, setAnnouncement] = React.useState("");
  const plotRef = React.useRef<HTMLDivElement>(null);
  const timers = React.useRef<ReturnType<typeof setTimeout>[]>([]);
  const id = React.useId().replace(/:/g, "");
  const sourceRun = runs.find(item => item.id === (selectedRunId ?? localRunId)) ?? runs[0];
  const run = demo && replayedRun?.id === sourceRun?.id ? replayedRun : sourceRun;
  const stages = run?.stages ?? [];
  const selected = stages.find(stage => stage.id === selectedStageId) ?? stages.find(stage => stage.status === "failed" || stage.status === "running") ?? stages.at(-1);
  const status = runStatus(stages);
  const elapsed = stages.reduce((sum, stage) => sum + (Number.isFinite(stage.durationMs) ? Math.max(0, stage.durationMs ?? 0) : 0), 0);
  const passed = stages.filter(stage => stage.status === "passed").length;
  const scene = React.useMemo(() => stations(stages.length, width), [stages.length, width]);
  const logs = selected?.logs.filter(log => logFilter === "all" || log.level === "error" || log.level === "warning") ?? [];
  const clearTimers = React.useCallback(() => { timers.current.forEach(clearTimeout); timers.current = []; }, []);

  React.useEffect(() => () => clearTimers(), [clearTimers]);
  React.useEffect(() => {
    clearTimers();
    setReplayedRun(null);
    setIsReplaying(false);
    setSelectedStageId(null);
    setLogFilter("all");
    setAnnouncement("");
  }, [sourceRun?.id, demo, clearTimers]);
  React.useEffect(() => {
    const element = plotRef.current;
    if (!element) return;
    const measure = () => setWidth(Math.max(1, element.getBoundingClientRect().width));
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [view, run?.id, stages.length]);

  const chooseStage = (stage: AnalysisStage) => {
    setSelectedStageId(stage.id);
    setLogFilter("all");
    if (run) onStageSelect?.(stage, run);
  };
  const changeRun = (runId: string) => {
    const next = runs.find(item => item.id === runId);
    if (!next) return;
    clearTimers();
    setIsReplaying(false);
    setReplayedRun(null);
    setLocalRunId(runId);
    setSelectedStageId(null);
    setLogFilter("all");
    onRunChange?.(next);
  };
  const replay = () => {
    if (!demo || !sourceRun || isReplaying) return;
    if (onReplay) { onReplay(sourceRun); return; }
    clearTimers();
    setSelectedStageId(null);
    setLogFilter("all");
    if (readMediaQuery("(prefers-reduced-motion: reduce)")?.matches !== false) {
      setReplayedRun({ ...sourceRun, stages: sourceRun.stages.map(stage => ({ ...stage })) });
      setAnnouncement("Демонстрация этапов завершена. Показаны условные данные.");
      return;
    }
    setIsReplaying(true);
    setAnnouncement("Запущена демонстрация этапов. Показаны условные данные.");
    setReplayedRun({ ...sourceRun, stages: sourceRun.stages.map(stage => ({ ...stage, status: "queued", logs: [], durationMs: undefined })) });
    const firstFailure = sourceRun.stages.findIndex(stage => stage.status === "failed" || stage.status === "canceled");
    const previewStages = firstFailure < 0 ? sourceRun.stages : sourceRun.stages.slice(0, firstFailure + 1);
    previewStages.forEach((stage, index) => {
      timers.current.push(setTimeout(() => {
        setReplayedRun(current => current?.id === sourceRun.id ? { ...current, stages: current.stages.map(item => item.id === stage.id ? { ...item, status: "running", logs: stage.logs.slice(0, 1) } : item) } : current);
      }, index * 1100));
      timers.current.push(setTimeout(() => {
        setReplayedRun(current => current?.id === sourceRun.id ? { ...current, stages: current.stages.map(item => item.id === stage.id ? { ...stage } : item) } : current);
      }, index * 1100 + 850));
    });
    timers.current.push(setTimeout(() => {
      setReplayedRun({ ...sourceRun, stages: sourceRun.stages.map(stage => ({ ...stage })) });
      setIsReplaying(false);
      setAnnouncement("Демонстрация этапов завершена. Показаны условные данные.");
    }, previewStages.length * 1100));
  };
  const exportLog = () => {
    if (!run || !selected || !selected.logs.length) return;
    const heading = demo ? `${t("Демонстрация этапов. Условные данные.")}\n\n` : "";
    const blob = new Blob([heading + selected.logs.map(log => `[${log.time}] ${t(log.level === "error" ? "Ошибка" : log.level === "warning" ? "Внимание" : "Информация")}: ${logMessage(log)}`).join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${demo ? "demo-" : ""}${run.id.replace(/[^\w-]/g, "_")}-${selected.id.replace(/[^\w-]/g, "_")}.txt`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };

  return <section className={`fvp-pipeline ${compact ? "fvp-compact" : ""} ${className}`} aria-label={demo ? t("Демонстрация этапов") : t("Этапы проверки")}>
    <span className="fvp-sr-only" role="status" aria-live="polite">{t(announcement)}</span>
    <header className="fvp-header">
      <div className="fvp-heading"><span className="fvp-emblem"><ScanLine size={18} strokeWidth={1.6} aria-hidden="true" /></span><div><h2>{demo ? t("Демонстрация этапов") : t("Этапы проверки")}</h2><p>{demo ? t("Выберите этап и посмотрите детали") : t("Статусы обработки видеозаписи")}</p></div></div>
      <div className="fvp-header-tools">
        <label className="fvp-run-select"><span className="fvp-sr-only">{demo ? t("Выберите пример проверки") : t("Выберите проверку")}</span><select value={sourceRun?.id ?? ""} disabled={!runs.length || isReplaying} onChange={event => changeRun(event.target.value)}>{runs.length ? runs.map(item => <option key={item.id} value={item.id}>{runTitle(item)}</option>) : <option value="">{t("Нет проверок")}</option>}</select><ChevronDown size={13} aria-hidden="true" /></label>
        <div className="fvp-switch" role="group" aria-label={t("Отображение этапов")}><button type="button" aria-label={t("Схема этапов")} aria-pressed={view === "pipeline"} onClick={() => setView("pipeline")}><Box size={15} aria-hidden="true" /><span>{t("Схема")}</span></button><button type="button" aria-label={t("Список этапов")} aria-pressed={view === "list"} onClick={() => setView("list")}><List size={15} aria-hidden="true" /><span>{t("Список")}</span></button></div>
      </div>
    </header>
    {!run ? <div className="fvp-empty"><FileVideo size={26} strokeWidth={1.4} aria-hidden="true" /><strong>{t("Проверок пока нет")}</strong><p>{t("Этапы появятся после загрузки записи.")}</p></div> : <>
      <div className="fvp-stats"><div><span>{t("Состояние")}</span><strong className="fvp-status-value" data-status={status} aria-live="polite">{t(STATUS_LABEL[status])}</strong><small>{demo ? t("Условный результат") : t("Текущая проверка")}</small></div><div><span>{t("Обработка")}</span><strong>{stages.some(stage => stage.durationMs !== undefined) ? duration(elapsed) : "-"}</strong><small>{demo ? t("Время в примере") : t("По данным этапов")}</small></div><div><span>{t("Этапы готовы")}</span><strong>{passed}<em> / {stages.length}</em></strong><small>{demo ? t("В этом примере") : t("В этой проверке")}</small></div></div>
      <div className="fvp-context"><span><FileVideo size={14} aria-hidden="true" /><span>{runTitle(run)}</span></span>{demo && <button type="button" className="fvp-replay" disabled={isReplaying || !stages.length} onClick={replay}><Play size={13} aria-hidden="true" />{isReplaying ? t("Демонстрация идёт…") : t("Повторить демонстрацию")}</button>}</div>
      {!stages.length ? <div className="fvp-empty"><strong>{t("Ожидаем начало обработки")}</strong><p>{t("Детали появятся, когда сервис передаст статусы этапов.")}</p></div> : view === "pipeline" ? <div className="fvp-plot" ref={plotRef} style={{ height: scene.height }}>
        <svg className="fvp-chart" width="100%" height={scene.height} viewBox={`0 0 ${width} ${scene.height}`} role="img" aria-labelledby={`${id}-title ${id}-desc`}><title id={`${id}-title`}>{t("Этапы обработки записи")}</title><desc id={`${id}-desc`}>{stages.map(stage => `${stageName(stage)}: ${t(STATUS_LABEL[stage.status])}`).join(". ")}. {t("Выберите этап, чтобы прочитать детали.")}</desc><defs><marker id={`${id}-arrow`} markerWidth={5} markerHeight={5} refX={4} refY={2.5} orient="auto"><path d="M0,0 L5,2.5 L0,5 Z" fill="var(--fvp-line)" /></marker></defs>
          {scene.nodes.slice(0, -1).map((node, index) => {
            const next = scene.nodes[index + 1];
            const direction = next.x > node.x ? 1 : -1;
            const side = node.x > width / 2 ? 1 : -1;
            const d = next.y === node.y ? `M${node.x + direction * 34},${node.y - 28} L${next.x - direction * 35},${next.y - 28}` : `M${node.x + side * 34},${node.y - 28} H${node.x + side * 53} V${next.y - 28} H${next.x + side * 35}`;
            return <path className="fvp-connector" key={stages[index].id} d={d} fill="none" stroke="var(--fvp-line)" strokeWidth={1.2} strokeDasharray={stages[index].status === "passed" ? undefined : "3 4"} markerEnd={`url(#${id}-arrow)`} />;
          })}
          {scene.nodes.map((node, index) => <g key={stages[index].id} className="fvp-station-block" data-selected={selected?.id === stages[index].id} data-status={stages[index].status}><polygon points={points(node.base.map(([x, y]) => [x, y + 6]))} fill="var(--fvp-ground)" /><polygon className="fvp-left" points={points([node.roof[3], node.roof[2], node.base[2], node.base[3]])} /><polygon className="fvp-right" points={points([node.roof[1], node.roof[2], node.base[2], node.base[1]])} /><polygon className="fvp-roof" points={points(node.roof)} /></g>)}
        </svg>
        {scene.nodes.map((node, index) => {
          const stage = stages[index], Icon = stageIcon(stage.kind), StatusIcon = statusIcon(stage.status);
          return <button type="button" className="fvp-station-button" key={stage.id} data-status={stage.status} aria-pressed={selected?.id === stage.id} aria-label={`${stageName(stage)}: ${t(STATUS_LABEL[stage.status])}. ${stage.durationMs === undefined ? "" : `${t("Время")}: ${duration(stage.durationMs)}.`} ${t("Показать детали этапа.")}`} style={{ left: node.x - 56, top: node.y - 46 }} onClick={() => chooseStage(stage)}><span className="fvp-station-icon"><Icon size={18} strokeWidth={1.6} aria-hidden="true" /></span><strong>{stageName(stage)}</strong><span className="fvp-station-state"><StatusIcon size={12} aria-hidden="true" />{t(STATUS_LABEL[stage.status])}</span><span className="fvp-station-duration">{duration(stage.durationMs)}</span></button>;
        })}
      </div> : <div className="fvp-list">{stages.map(stage => { const Icon = stageIcon(stage.kind), StatusIcon = statusIcon(stage.status); return <button className="fvp-list-row" type="button" key={stage.id} data-status={stage.status} aria-pressed={selected?.id === stage.id} onClick={() => chooseStage(stage)}><Icon size={17} aria-hidden="true" /><span className="fvp-list-name"><strong>{stageName(stage)}</strong><small>{stage.logs.length ? `${t("Записей")}: ${stage.logs.length}` : t("Нет записей")}</small></span><span className="fvp-list-status"><StatusIcon size={13} aria-hidden="true" />{t(STATUS_LABEL[stage.status])}</span><span className="fvp-list-duration">{duration(stage.durationMs)}</span></button>; })}</div>}
      {selected && <div className="fvp-log-panel"><div className="fvp-log-header"><div><strong>{stageName(selected)}</strong><span className="fvp-stage-badge" data-status={selected.status}>{t(STATUS_LABEL[selected.status])}</span></div><div><label className="fvp-log-filter"><span className="fvp-sr-only">{t("Фильтр записей этапа")}</span><select value={logFilter} onChange={event => setLogFilter(event.target.value as "all" | "issues")}><option value="all">{t("Все записи")}</option><option value="issues">{t("Предупреждения и ошибки")}</option></select><ChevronDown size={12} aria-hidden="true" /></label><button type="button" className="fvp-export" onClick={exportLog} aria-label={t("Скачать записи выбранного этапа")} title={t("Скачать записи этапа")} disabled={!selected.logs.length}><Download size={16} aria-hidden="true" /></button></div></div><div className="fvp-log-lines" aria-label={`${t("Детали этапа")} «${stageName(selected)}»`}>{logs.length ? logs.slice(-4).map((log, index) => <div className="fvp-log-line" key={`${log.time}-${index}`} data-level={log.level ?? "info"}><time>{log.time}</time><span>{logMessage(log)}</span></div>) : <p className="fvp-no-logs">{logFilter === "issues" ? t("Предупреждений и ошибок нет.") : selected.status === "queued" ? t("Этот этап ещё не начался.") : selected.status === "canceled" ? t("Этап остановлен. Записей нет.") : t("Записей об этом этапе пока нет.")}</p>}</div>{logs.length > 4 && <details className="fvp-full-logs" key={`${run.id}-${selected.id}-${logFilter}`}><summary>{t("Предыдущие записи")} ({logs.length - 4})<ChevronDown size={13} aria-hidden="true" /></summary>{logs.slice(0, -4).map((log, index) => <div className="fvp-log-line" key={`${log.time}-${index}`} data-level={log.level ?? "info"}><time>{log.time}</time><span>{logMessage(log)}</span></div>)}</details>}</div>}
      <footer className="fvp-footer">{demo ? <span><Info size={13} aria-hidden="true" />{t("Условные данные. Модель не запускается.")}</span> : <span><Clock3 size={13} aria-hidden="true" />{t("Начало")}: {t(formatStart(run.startedAt, localeTag))} · UTC+5</span>}<span>{passed} {t("из")} {stages.length} {t("готово")}</span></footer>
    </>}
  </section>;
}

export default AnalysisPipeline;
