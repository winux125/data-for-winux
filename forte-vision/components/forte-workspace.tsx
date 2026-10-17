"use client";
/* eslint-disable @next/next/no-img-element -- Local brand SVG and runtime evidence images use native rendering. */
import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, BookOpen, Check, ChevronDown, ChevronRight, CircleCheck, CircleHelp, FileCheck2, FileVideo2, Film, Focus, Info, Layers3, LayoutDashboard, ListChecks, Loader2, LockKeyhole, PanelLeftOpen, PanelLeftClose, Plus, ScanLine, Search, Settings2, ShieldCheck, Home, TriangleAlert, Upload, X } from "lucide-react";
import { Select as SelectPrimitive, DropdownMenu as DropdownPrimitive } from "radix-ui";
import { useI18n } from "@/components/locale-provider";
import { workspaceMessages } from "@/lib/messages/workspace";
import { AppearanceControls } from "@/components/theme-provider";
import CheckFolders from "@/components/check-folders";
import CashdeskScene from "@/components/ui/cashdesk-scene";
import { AnalysisPipeline, DEMO_ANALYSIS_RUNS, type AnalysisRun } from "@/components/ui/analysis-pipeline";
import ChecksTable from "@/components/ui/demo";
import { type Violation } from "@/lib/analysis";
import { CHECK_STATUS_LABELS, isFinishedCheck, isRunningCheck, type StoredCheck } from "@/lib/checks";
import { translateAnalysisMessage } from "@/lib/analysis-messages";
import { useAnalysisJobs } from "@/hooks/use-analysis-jobs";
import CheckResult from "@/components/check-result";
import JobProgress from "@/components/job-progress";
import { EvidenceImage } from "@/components/evidence-image";
import RuleDetails from "@/components/rule-details";
import { useWorkspaceNavigation } from "@/hooks/use-workspace-navigation";
import { useUndoDeletion } from "@/hooks/use-undo-deletion";
import { useApiConnection } from "@/hooks/use-api-connection";
import { CONNECTION_LABELS } from "@/lib/api-connection";
import type { WorkspaceSection } from "@/lib/workspace-navigation";
const DEMO_EVENTS: Violation[] = [
    { type: "Рабочая зона оставлена без наблюдения", timecode_sec: 22, description: "Условный пример: сотрудник отходит от рабочего места, на котором остаются предметы, похожие на наличные. Проверяющему необходимо изучить фрагмент и применимое правило.", evidence_frames: [] },
    { type: "Передача предмета вне зоны обслуживания", timecode_sec: 47, description: "Условный пример: передача предмета происходит сбоку от обозначенной зоны. По одному кадру нельзя подтвердить, что передаются деньги. Требуется просмотр фрагмента.", evidence_frames: [] },
];
const DEMO_RECORDS: StoredCheck[] = [
    { id: "DEMO-001", name: "Проверка кассовой операции.mov", createdAt: "Пример", duration: "01:24", seconds: 84, status: "violation", events: 2, demo: true, result: { job_id: "DEMO-001", status: "done", verdict: "violation", violations: DEMO_EVENTS } },
    { id: "DEMO-002", name: "Операция без замечаний.mov", createdAt: "Пример", duration: "00:56", seconds: 56, status: "no_violation", events: 0, demo: true, result: { job_id: "DEMO-002", status: "done", verdict: "no_violation", violations: [] } },
    { id: "DEMO-003", name: "Фрагмент обслуживания.mov", createdAt: "Пример", duration: "00:38", seconds: 38, status: "violation", events: 1, demo: true, result: { job_id: "DEMO-003", status: "done", verdict: "violation", violations: [{ ...DEMO_EVENTS[1], timecode_sec: 16 }] } },
];
function IconButton({ label, onClick, children, className = "", expanded, controls }: {
    label: string;
    onClick: () => void;
    children: ReactNode;
    className?: string;
    expanded?: boolean;
    controls?: string;
}) {
    return <button className={`fv-icon-button ${className}`} type="button" title={label} aria-label={label} aria-expanded={expanded} aria-controls={controls} onClick={onClick}>{children}</button>;
}
export default function ForteWorkspace() {
    const { t, locale } = useI18n(workspaceMessages);
    const navigation = useWorkspaceNavigation();
    const page = navigation.route.section;
    const [checksView, setChecksView] = useState<"table" | "folders">("table");
    const [menuOpen, setMenuOpen] = useState(false);
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [drawerMode, setDrawerMode] = useState(false);
    const [modal, setModal] = useState<"help" | null>(null);
    const {api,connection,report:reportConnection,retry:retryConnection,maxBytes} = useApiConnection();
    const [toast, setToast] = useState("");
    const [toastTone, setToastTone] = useState<"info" | "error" | "success">("info");
    const notify = (message: string, tone: "info" | "error" | "success" = "info") => { setToastTone(tone); setToast(message); };
    const jobs = useAnalysisJobs(DEMO_RECORDS, notify, reportConnection);
    const { records, setRecords, busyCheck } = jobs;
    const activeId = navigation.route.checkId;
    const active = records.find(record => record.id === activeId) || null;
    const [file, setFile] = useState<File | null>(null);
    const [fileUrl, setFileUrl] = useState("");
    const [fileDuration, setFileDuration] = useState(0);
    const [dragging, setDragging] = useState(false);
    const [fileError, setFileError] = useState("");
    const processing = Boolean(jobs.busyId);
    const stage = busyCheck?.status === "uploading" ? "Загрузка видео" : busyCheck?.status === "reconnecting" ? "Восстановление связи" : "Анализ видеозаписи";
    const [query, setQuery] = useState("");
    const [filter, setFilter] = useState("all");
    const [selected, setSelected] = useState<string[]>([]);
    const [previewError, setPreviewError] = useState(false);
    const [expandedFrame, setExpandedFrame] = useState<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const sidebarRef = useRef<HTMLElement>(null);
    const ownedUrls = useRef(new Set<string>());
    const durationRef = useRef(0);
    const releaseUrl = (url?: string) => {
        if (!url || !ownedUrls.current.has(url)) return;
        URL.revokeObjectURL(url);
        ownedUrls.current.delete(url);
    };
    const liveRecords = useRef(records); const pickedUrl = useRef(fileUrl);
    useEffect(()=>{liveRecords.current=records;pickedUrl.current=fileUrl;},[records,fileUrl]);
    const deletion = useUndoDeletion(records,setRecords,removed=>{
        for(const record of removed)if(record.videoUrl !== pickedUrl.current && !liveRecords.current.some(item=>item.videoUrl===record.videoUrl))releaseUrl(record.videoUrl);
    });
    const undoDeletion = () => {
        const restored = deletion.undo();
        if(!restored){notify("Срок отмены удаления истёк.");return;}
        setSelected(previous=>[...new Set([...previous,...restored.selected])]);
        notify("Проверки восстановлены.","success");
    };
    // Browser Back/Forward dismisses overlays belonging to the previous history entry.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    useEffect(()=>{setMenuOpen(false);setModal(null);setExpandedFrame(null);},[navigation.revision]);
    useEffect(()=>{
        if(activeId)return;
        const heading=document.querySelector<HTMLElement>("#main h1");
        heading?.setAttribute("tabindex","-1");heading?.focus({preventScroll:true});
        window.scrollTo({top:0,behavior:"instant"});
    },[page,activeId,navigation.revision]);
    const discardFile = () => {
        if (processing) return;
        if (!records.some(record => record.videoUrl === fileUrl)) releaseUrl(fileUrl);
        setFile(null); setFileUrl(""); setFileDuration(0); durationRef.current = 0;
        setFileError(""); setPreviewError(false);
        if (inputRef.current) inputRef.current.value = "";
    };
    useEffect(() => { if (!toast)
        return; const id = setTimeout(() => setToast(""), 3800); return () => clearTimeout(id); }, [toast]);
    useEffect(() => { const urls = ownedUrls.current; return () => { urls.forEach(url => URL.revokeObjectURL(url)); }; }, []);
    useEffect(() => {
        if (!modal && !expandedFrame)
            return;
        const previous = document.activeElement as HTMLElement | null;
        const dialog = document.querySelector<HTMLDivElement>(".fv-modal, .fv-frame-dialog");
        const controls = () => Array.from(dialog?.querySelectorAll<HTMLElement>('button, input, select, a[href], [tabindex="0"]') || []).filter(e => !e.matches(':disabled, [hidden], [tabindex="-1"]') && e.getClientRects().length > 0);
        controls()[0]?.focus();
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") {
                setModal(null);
                setExpandedFrame(null);
            }
            if (e.key === "Tab") {
                const els = controls();
                const first = els[0];
                const last = els[els.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last?.focus();
                }
                else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first?.focus();
                }
            }
        };
        const old = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        document.addEventListener("keydown", onKey);
        return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = old; previous?.focus(); };
    }, [modal, expandedFrame]);
    useEffect(() => {
        const media = window.matchMedia("(max-width: 1023px)");
        const sync = () => { setDrawerMode(media.matches); setMenuOpen(false); };
        sync(); media.addEventListener("change", sync);
        return () => media.removeEventListener("change", sync);
    }, []);
    useEffect(() => {
        if (!drawerMode || !menuOpen) return;
        const previous = document.activeElement as HTMLElement | null;
        const panel = sidebarRef.current;
        const controls = () => Array.from(panel?.querySelectorAll<HTMLButtonElement>("button") || []);
        panel?.querySelector<HTMLButtonElement>(".fv-sidebar-close")?.focus();
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") { e.preventDefault(); setMenuOpen(false); }
            if (e.key !== "Tab") return;
            const items = controls(); const first = items[0]; const last = items[items.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
        };
        const old = document.body.style.overflow; document.body.style.overflow = "hidden";
        document.addEventListener("keydown", onKey);
        return () => { document.body.style.overflow = old; document.removeEventListener("keydown", onKey); previous?.focus(); };
    }, [drawerMode, menuOpen]);
    const closeSidebar = () => {
        if (drawerMode) setMenuOpen(false);
        else { setSidebarCollapsed(true); requestAnimationFrame(() => document.querySelector<HTMLButtonElement>(".fv-sidebar-toggle")?.focus()); }
    };
    const toggleSidebar = () => {
        if (drawerMode) { setMenuOpen(open => !open); return; }
        setSidebarCollapsed(!sidebarCollapsed);
        if (sidebarCollapsed) requestAnimationFrame(() => sidebarRef.current?.querySelector<HTMLButtonElement>(".fv-sidebar-close")?.focus());
    };
    const showModal = (value: "help") => { setMenuOpen(false); setModal(value); };
    const navigate = (target: WorkspaceSection) => { navigation.goSection(target); setMenuOpen(false); };
    const newCheck = () => { if (jobs.busyId) { navigation.openCheck(jobs.busyId); setMenuOpen(false); return; } navigate("overview"); requestAnimationFrame(() => document.getElementById("new-check")?.scrollIntoView({ behavior: "smooth", block: "center" })); };
    const openCheck = (id: string) => { const record = records.find(r => r.id === id); if (record) {
        navigation.openCheck(record.id); setMenuOpen(false);
        setPreviewError(false);
        window.scrollTo({ top: 0, behavior: "smooth" });
    } };
    const pickFile = (f?: File) => {
        if (!f || processing)
            return;
        setFileError("");
        if (!/\.mov$/i.test(f.name)) {
            setFileError("Выберите видео в формате MOV.");
            return;
        }
        if (!f.size) {
            setFileError("Этот файл пуст. Выберите другую запись.");
            return;
        }
        if (f.size > maxBytes) {
            setFileError("Выберите файл размером до 10 ГиБ.");
            return;
        }
        if (fileUrl && !records.some(r => r.videoUrl === fileUrl)) {
            URL.revokeObjectURL(fileUrl);
            ownedUrls.current.delete(fileUrl);
        }
        const url = URL.createObjectURL(f);
        ownedUrls.current.add(url);
        setFile(f);
        setFileUrl(url);
        setFileDuration(0);
        durationRef.current = 0;
        setPreviewError(false);
    };
    const removeChecks = (ids: string[]) => {
        if (jobs.busyId && ids.includes(jobs.busyId)) { notify("Сначала остановите ожидание текущей проверки."); return; }
        deletion.remove(ids,selected);
        const removed = new Set(ids); setSelected(previous=>previous.filter(id=>!removed.has(id)));
    };
    const removeCheck = (id: string) => removeChecks([id]);
    const runAnalysis = () => {
        if (!file || processing) return;
        if (!api) { retryConnection(); return; }
        const id = jobs.start(file, fileUrl, durationRef.current || fileDuration, api);
        if (!id) return;
        navigation.openCheck(id); setFile(null); setFileUrl(""); setFileError("");
        if (inputRef.current) inputRef.current.value = "";
    };
    const resumeCheck = (id: string) => {
        if (!api) { retryConnection(); return; }
        jobs.resume(id, api);
    };
    const attachVideo = (record: StoredCheck, selectedFile: File) => {
        if (!/\.mov$/i.test(selectedFile.name) || selectedFile.name !== record.name || (record.fileBytes && selectedFile.size !== record.fileBytes)) {
            notify("Выберите исходный MOV с тем же именем и размером.", "error"); return;
        }
        const url = URL.createObjectURL(selectedFile); ownedUrls.current.add(url);
        releaseUrl(record.videoUrl); jobs.update(record.id, { videoUrl: url });
    };
    const visibleRecords = records.map(record => record.demo ? { ...record, name: t(record.name), createdAt: t(record.createdAt) } : record).filter(r =>
        (!query || `${r.name} ${r.id} ${r.jobId || ""}`.toLowerCase().includes(query.toLowerCase())) &&
        (filter === "all" || (filter === "processing" ? isRunningCheck(r) : r.status === filter)));
    const sourceEvents = records.filter(r => !r.demo && isFinishedCheck(r)).flatMap(r => r.result?.violations || []).filter(v => v.rule?.title);
    const showDemo = () => { navigation.openCheck(DEMO_RECORDS[0].id); setPreviewError(false); };
    const latestRun = busyCheck || records.find(record => !record.demo);
    const completedRun = Boolean(latestRun && isFinishedCheck(latestRun));
    const stoppedRun = latestRun?.status === "failed" ? "failed" : latestRun?.status === "paused" ? "canceled" : null;
    const liveRun: AnalysisRun | undefined = latestRun ? {
        id: latestRun.id, title: latestRun.name, startedAt: latestRun.createdAt,
        stages: [
            { id: "transfer", name: t("Передача видео"), kind: "upload", status: latestRun.jobId ? "passed" : stoppedRun || "running", logs: [{ time: "", message: latestRun.jobId ? t("Сервер принял запись.") : t("Передано {progress}% файла.", { progress: Math.round(latestRun.uploadProgress || 0) }) }] },
            { id: "server", name: t("Обработка"), kind: "analysis", status: completedRun ? "passed" : stoppedRun || (latestRun.jobId ? "running" : "queued"), logs: [{ time: "", message: latestRun.error ? translateAnalysisMessage(latestRun.error, t) : latestRun.progress !== undefined ? t("Обработано {progress}%", { progress: Math.round(latestRun.progress) }) : t(CHECK_STATUS_LABELS[latestRun.status]) }] },
            { id: "result", name: t("Результат"), kind: "evidence", status: completedRun ? "passed" : stoppedRun || "queued", logs: [{ time: "", message: t(completedRun ? "Проверка завершена" : "После ответа сервера откроется результат проверки.") }] },
        ],
    } : undefined;
    return <div className={`fv-workspace ${sidebarCollapsed ? "fv-sidebar-collapsed" : ""} ${drawerMode && menuOpen ? "fv-drawer-open" : ""}`}>
    <a className="fv-skip-link" href="#main">{t("К содержимому")}</a>
    {drawerMode && menuOpen && <button aria-label={t("Закрыть меню")} className="fv-sidebar-scrim" onClick={() => setMenuOpen(false)}/>}
    <aside ref={sidebarRef} id="workspace-sidebar" className={`fv-sidebar ${menuOpen ? "fv-is-open" : ""}`} aria-label={t("Главная навигация")} aria-hidden={drawerMode ? !menuOpen : sidebarCollapsed} inert={Boolean(modal || expandedFrame) || (drawerMode ? !menuOpen : sidebarCollapsed)}>
      <div className="fv-sidebar-header"><button className="fv-brand" onClick={() => navigate("overview")} aria-label={t("Forte Vision - главная")}><img src="/brand/forte-wordmark-burgundy.svg" alt="Forte" width="106" height="32"/><span>vision<span className="fv-brand-dot"/></span></button><IconButton className="fv-sidebar-close" label={drawerMode ? t("Закрыть меню") : t("Свернуть боковую панель")} controls="workspace-sidebar" expanded onClick={closeSidebar}><PanelLeftClose size={16} strokeWidth={1.7}/></IconButton></div>
      <div className="fv-workspace-label"><span className="fv-workspace-mark"><Focus size={16}/></span><div>{t("Рабочее пространство")}<small>{t("Кассовые операции")}</small></div><LockKeyhole size={13}/></div>
      <p className="fv-nav-caption">{t("НАВИГАЦИЯ")}</p>
      <nav className="fv-main-nav">
        <button className={page === "overview" && !active ? "fv-nav-item fv-active" : "fv-nav-item"} aria-current={page === "overview" && !activeId ? "page" : undefined} onClick={() => navigate("overview")}><LayoutDashboard size={18}/><span>{t("Обзор")}</span><ChevronRight size={14}/></button>
        <button className={page === "checks" || active ? "fv-nav-item fv-active" : "fv-nav-item"} aria-current={page === "checks" || activeId ? "page" : undefined} onClick={() => navigate("checks")}><FileCheck2 size={18}/><span>{t("Проверки")}</span><span className="fv-nav-count">{records.length}</span></button>
        <button className={page === "rules" && !active ? "fv-nav-item fv-active" : "fv-nav-item"} aria-current={page === "rules" && !activeId ? "page" : undefined} onClick={() => navigate("rules")}><BookOpen size={18}/><span>{t("Правила и источники")}</span></button>
      </nav>
      <div className="fv-sidebar-bottom">
        <div className="fv-private-card"><span className="fv-private-icon"><ShieldCheck size={21}/></span><strong>{t("Обработка видео")}</strong><p>{t("На сервере команды, без облачных AI API.")}</p><button onClick={() => showModal("help")}>{t("Как это работает")} <ArrowUpRight size={14}/></button></div>
        <button className="fv-nav-item" onClick={() => showModal("help")}><CircleHelp size={18}/><span>{t("Помощь")}</span><ArrowUpRight size={14}/></button>
        <div className="fv-sidebar-foot"><span className="fv-monogram">FV</span><div>Forte Vision<small>Datathon 2026</small></div><span className="fv-version-label">v1.0</span></div>
      </div>
    </aside>
    <div className="fv-workspace-main" inert={Boolean(modal || expandedFrame) || (drawerMode && menuOpen)}>
      <header className="fv-topbar"><div className="fv-breadcrumbs"><IconButton label={drawerMode ? (menuOpen ? t("Закрыть меню") : t("Открыть меню")) : sidebarCollapsed ? t("Развернуть боковую панель") : t("Свернуть боковую панель")} className="fv-sidebar-toggle" expanded={drawerMode ? menuOpen : !sidebarCollapsed} controls="workspace-sidebar" onClick={toggleSidebar}><PanelLeftOpen size={18} strokeWidth={1.7}/></IconButton><span>{t("Рабочее пространство")}</span><ChevronRight size={13}/><strong>{active ? t("Результат проверки") : page === "overview" ? t("Обзор") : page === "checks" ? t("Проверки") : t("Правила и источники")}</strong></div><div className="fv-topbar-actions"><button className="fv-mode-pill" data-connection={api ? connection.state : "unconfigured"} title={t(api ? CONNECTION_LABELS[connection.state] : "Подключение к серверу")} onClick={() => jobs.busyId ? openCheck(jobs.busyId) : retryConnection()}><span />{processing ? t("Идёт проверка") : api ? t(CONNECTION_LABELS[connection.state]) : t("Подключение к серверу")}<ChevronDown size={12}/></button><span className="fv-topbar-divider"/><IconButton label={t("Помощь")} onClick={() => showModal("help")}><CircleHelp size={19}/></IconButton><DropdownPrimitive.Root><DropdownPrimitive.Trigger asChild><button type="button" className="fv-icon-button" aria-label={t("Настройки интерфейса")} title={t("Настройки интерфейса")}><Settings2 size={19}/></button></DropdownPrimitive.Trigger><DropdownPrimitive.Portal><DropdownPrimitive.Content className="fv-account-menu" align="end" sideOffset={10} collisionPadding={16}><DropdownPrimitive.Label className="fv-account-identity"><strong>{t("Настройки интерфейса")}</strong><small>{t("Язык и оформление")}</small></DropdownPrimitive.Label><div className="fv-account-theme"><AppearanceControls menu /></div><DropdownPrimitive.Separator className="fv-account-separator"/><DropdownPrimitive.Item asChild><Link className="fv-account-item" href="/"><Home size={16}/>{t("На главную")}</Link></DropdownPrimitive.Item></DropdownPrimitive.Content></DropdownPrimitive.Portal></DropdownPrimitive.Root></div></header>
      <main id="main" className="fv-main-content" tabIndex={-1}>
        {busyCheck && activeId !== busyCheck.id && <div className="fv-active-job" role="status"><div><Loader2 className="fv-spin" size={17}/><span><strong>{t(CHECK_STATUS_LABELS[busyCheck.status])}</strong><small>{busyCheck.name}</small></span><JobProgress check={busyCheck}/></div><button type="button" className="fv-secondary-button" onClick={() => openCheck(busyCheck.id)}>{t("Открыть проверку")}<ArrowRight size={15}/></button><button type="button" className="fv-text-button" onClick={jobs.cancel}>{t("Отменить ожидание")}</button></div>}
        {active ? <CheckResult key={active.id} check={active}
          onBack={() => navigate("checks")}
          reviewState={navigation.route.review} historyRevision={navigation.revision} onReviewAction={(action,replace)=>navigation.reviewAction(action,replace,active.id,navigation.revision)}
          onExport={() => exportReport(active)} onExpandFrame={setExpandedFrame}
          onMetadata={metadata => jobs.update(active.id, metadata)}
          onCancel={jobs.cancel} onResume={() => resumeCheck(active.id)} onNewCheck={newCheck}
          onAttachFile={selectedFile => attachVideo(active, selectedFile)} busy={processing}

        /> : activeId && jobs.restored ? <section className="fv-route-unavailable"><h1>{t("Проверка недоступна в этом сеансе")}</h1><p>{t("Проверка удалена или её локальная копия не сохранилась после перезагрузки. Если доступна отмена удаления, восстановите её.")}</p><button className="fv-secondary-button" onClick={()=>navigate("checks")}>{t("К проверкам")}</button></section> : page === "rules" ? <>
          <div className="fv-page-heading"><span className="fv-eyebrow">{t("НОРМАТИВНАЯ БАЗА")}</span><h1>{t("Правила и источники")}</h1><p>{t("Документы и разделы правил, указанные в результатах анализа.")}</p></div>
          <div className="fv-rules-intro"><div className="fv-rules-icon"><BookOpen size={32}/></div><div><h2>{t("Источники из результатов")}</h2><p>{t("Источник передаётся сервером вместе с событием. Его также можно открыть на странице проверки.")}</p></div></div>
          {sourceEvents.length ? <div className="fv-rules-list">{sourceEvents.map((v, i) => <div className="fv-evidence-card" key={i}><h3>{v.type}</h3><RuleDetails violation={v}/></div>)}</div> : <div className="fv-sources-empty"><Layers3 size={34}/><h3>{t("Источников пока нет")}</h3><p>{t("Загрузите запись. Документы из результата появятся в этом разделе.")}</p><button className="fv-primary-button" onClick={newCheck}>{t("Новая проверка")} <ArrowUpRight size={16}/></button></div>}
          <div className="fv-notice"><Info size={17}/><span>{t("У демонстрационных событий нет нормативных источников.")}</span></div>
        </> : <>
          {page === "overview" ? <>
            <section className="fv-hero"><div className="fv-hero-copy"><div className="fv-eyebrow"><span className="fv-eyebrow-line"/>{t("КАССОВЫЕ ОПЕРАЦИИ")}</div><h1>{locale === "kk" ? <><em>{t("кассовых операций")}</em> {t("Анализ")}</> : <>{t("Анализ")} <em>{t("кассовых операций")}</em></>}</h1><p>{t("Загрузите запись, чтобы проверить события по таймкодам, кадрам и нормативным источникам.")}</p><button className="fv-hero-link" onClick={showDemo}>{t("Посмотреть пример")} <span><ArrowUpRight size={17}/></span></button></div><div className="fv-hero-scene"><span className="fv-scene-corner fv-top-left"/><span className="fv-scene-corner fv-bottom-right"/><div className="fv-scene-tag"><span />{t("СХЕМА АНАЛИЗА")}</div><CashdeskScene /><div className="fv-scene-legend"><span><i className="fv-legend-dot"/>{t("Запись")}</span><span className="fv-legend-line"/><span>{t("Событие")}</span><span className="fv-legend-line"/><span>{t("Доказательство")}</span></div></div></section>
            <div className="fv-benefit-strip"><div><Focus size={17}/><span>{t("События с таймкодами")}</span></div><div><Film size={17}/><span>{t("Кадры-доказательства")}</span></div><div><BookOpen size={17}/><span>{t("Связь с правилами")}</span></div><div><ShieldCheck size={17}/><span>{t("Локальный анализ")}</span></div></div>
            <section className="fv-upload-section fv-framed" id="new-check"><div className="fv-upload-explainer"><div className="fv-section-index">{t("ЗАГРУЗКА ВИДЕО")}</div><h2>{t("Новая проверка")}</h2><p>{t("Выберите MOV. После обработки откроется результат с найденными событиями.")}</p><div className="fv-upload-steps"><span><i>1</i>{t("Выберите запись")}</span><span><i>2</i>{t("Дождитесь анализа")}</span><span><i>3</i>{t("Проверьте события")}</span></div><div className="fv-upload-secure"><LockKeyhole size={14}/>{t("Без облачных AI-сервисов")}</div></div><div className="fv-upload-body"><div className="fv-upload-body-heading"><span>{t("Загрузить видеозапись")}</span><span className="fv-file-format">MOV</span></div><input type="file" accept=".mov,video/quicktime" ref={inputRef} hidden aria-hidden="true" tabIndex={-1} onChange={e => { pickFile(e.target.files?.[0]); e.target.value = ""; }} aria-label={t("Выбрать видеозапись")} disabled={processing}/>
              {!file ? <button type="button" disabled={processing} className={`fv-dropzone ${dragging ? "fv-dragging" : ""}`} aria-label={t("Загрузить видео: нажмите или перетащите файл")} onClick={() => inputRef.current?.click()} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0]); }}><span className="fv-upload-icon-stack"><span /><span /><span><FileVideo2 size={27} strokeWidth={1.5}/></span></span><strong>{t("Перетащите видео сюда")}</strong><span className="fv-dropzone-description">{t("или выберите файл на компьютере")}</span><span className="fv-choose-file"><Upload size={14}/>{t("Выбрать видео")}</span><small>{t("MOV · до 10 ГиБ")}</small></button> : <div className="fv-selected-file"><div className="fv-file-preview"><video src={fileUrl} muted playsInline preload="metadata" onLoadedMetadata={e => { const seconds = Number.isFinite(e.currentTarget.duration) ? e.currentTarget.duration : 0; durationRef.current = seconds; setFileDuration(seconds); }} onError={() => setPreviewError(true)}/><div className="fv-file-preview-overlay"><FileVideo2 size={25}/></div></div><div className="fv-selected-file-info"><strong>{file.name}</strong><span>{(file.size / 1024 / 1024).toFixed(1)} {t("МБ")} · {file.name.split(".").pop()?.toUpperCase()}</span>{previewError && <small>{t("Предпросмотр недоступен в этом браузере. Файл можно отправить на анализ.")}</small>}</div>{!processing && <IconButton label={t("Убрать файл")} onClick={discardFile}><X size={17}/></IconButton>}</div>}
              {fileError && <div className="fv-file-error" role="alert"><TriangleAlert size={16}/>{translateAnalysisMessage(fileError, t)}</div>}
              {processing ? <div className="fv-processing-state" aria-live="polite"><div><Loader2 className="fv-spin" size={16}/><strong>{t(stage)}</strong><button onClick={jobs.cancel}>{t("Отменить ожидание")}</button></div>{busyCheck && <JobProgress check={busyCheck}/>}</div> : <div className="fv-upload-actions"><p><ShieldCheck size={14}/>{api ? t(CONNECTION_LABELS[connection.state]) : t(connection.state === "checking" ? "Подключение к серверу" : "Не удалось подключиться к серверу. Повторите подключение.")}</p><button className="fv-primary-button" disabled={!file || connection.state === "checking"} onClick={runAnalysis}>{api ? t("Начать проверку") : t("Повторить подключение")}<ArrowUpRight size={17}/></button></div>}
            </div></section>
          </> : <div className="fv-page-heading fv-checks-page-heading"><span className="fv-eyebrow">{t("РАБОЧЕЕ ПРОСТРАНСТВО")}</span><div className="fv-page-title-row"><div><h1>{t("Проверки")}</h1><p>{t("Записи и результаты текущего сеанса.")}</p></div><button className="fv-primary-button" onClick={newCheck}><Plus size={17}/>{t("Новая проверка")}</button></div></div>}
          {page === "overview" && <section className="fv-analysis-pipeline-section" aria-label={t("Этапы обработки видео")}><AnalysisPipeline runs={liveRun ? [liveRun] : DEMO_ANALYSIS_RUNS} demo={!liveRun}/></section>}
          <section className="fv-history-section"><div className="fv-section-heading"><div className="fv-section-title"><h2>{page === "overview" ? t("Ваши проверки") : t("Все проверки")}</h2><span className="fv-count-badge">{records.length}</span></div>{page === "overview" && <button className="fv-text-button" onClick={() => navigate("checks")}>{t("Все проверки")} <ArrowRight size={15}/></button>}</div><div className="fv-table-toolbar"><label className="fv-search-field"><Search size={17}/><input placeholder={t("Найти проверку...")} aria-label={t("Найти проверку")} value={query} onChange={e => { setQuery(e.target.value); setSelected([]); }}/>{query && <button aria-label={t("Очистить поиск")} onClick={() => { setQuery(""); setSelected([]); }}><X size={14}/></button>}</label><div className="fv-table-toolbar-right">{page === "checks" && <div className="fv-view-switch" role="group" aria-label={t("Вид проверок")}><button type="button" aria-pressed={checksView === "table"} onClick={() => { setChecksView("table"); setSelected([]); }}><ListChecks size={15}/><span>{t("Таблица")}</span></button><button type="button" aria-pressed={checksView === "folders"} onClick={() => { setChecksView("folders"); setSelected([]); }}><Layers3 size={15}/><span>{t("Папки")}</span></button></div>}{selected.length > 0 && <button className="fv-text-button fv-danger-text" onClick={() => removeChecks(selected)}>{t("Удалить выбранные ({count})", { count: selected.length })}</button>}<ResultFilter value={filter} onChange={value => { setFilter(value); setSelected([]); }}/></div></div>{page === "checks" && checksView === "folders" ? <CheckFolders records={visibleRecords} onOpen={openCheck}/> : <ChecksTable records={visibleRecords} selectedIds={selected} onOpen={openCheck} onDelete={removeCheck} onSelectionChange={setSelected}/>}<div className="fv-table-footnote"><span><Info size={13}/>{t("Примеры отмечены в таблице. Реальные проверки хранятся в текущем сеансе.")}</span><span>{t("{visible} из {total}", { visible: visibleRecords.length, total: records.length })}</span></div></section>
          {page === "overview" && <section className="fv-bottom-note"><div className="fv-bottom-note-icon"><ScanLine size={22}/></div><div><h3>{t("Проверка сотрудником")}</h3><p>{t("Перед подтверждением события просмотрите фрагмент и проверьте указанный источник.")}</p></div><button onClick={() => showModal("help")} aria-label={t("Подробнее о принципе работы")}><ArrowUpRight size={20}/></button></section>}
        </>}
        <footer className="fv-main-footer"><span>Forte Vision <span className="fv-footer-dot">·</span> Datathon 2026</span><span>{t("Анализ кассовых операций")}</span><button onClick={() => showModal("help")}>{t("О проекте")} <ArrowUpRight size={12}/></button></footer>
      </main>
    </div>
    {(toast || deletion.pending) && <div className="fv-notifications" inert={Boolean(modal || expandedFrame)}>
    {toast && <div className="fv-toast" inert={Boolean(modal || expandedFrame)} data-tone={toastTone} role={toastTone === "error" ? "alert" : "status"}>{toastTone === "error" ? <TriangleAlert size={18}/> : toastTone === "success" ? <CircleCheck size={18}/> : <Info size={18}/>}<span>{translateAnalysisMessage(toast, t)}</span><button aria-label={t("Закрыть уведомление")} onClick={() => setToast("")}><X size={14}/></button></div>}
    {deletion.pending && <div className="fv-undo-toast" role="status" inert={Boolean(modal || expandedFrame)}><Info size={18}/><span>{t("Удалено проверок: {count}. Можно восстановить в течение 10 секунд.",{count:deletion.pending.records.length})}</span><button type="button" onClick={undoDeletion}>{t("Отменить удаление")}</button></div>}
    </div>}
    {expandedFrame && <div className="fv-modal-overlay" onClick={e => { if (e.target === e.currentTarget)
        setExpandedFrame(null); }}><div className="fv-frame-dialog" role="dialog" aria-modal="true" aria-label={t("Кадр-доказательство")}><IconButton label={t("Закрыть кадр")} onClick={() => setExpandedFrame(null)}><X size={20}/></IconButton><EvidenceImage key={expandedFrame} source={expandedFrame} alt={t("Кадр-доказательство в полном размере")}/></div></div>}
    {modal && <div className="fv-modal-overlay" onClick={e => { if (e.target === e.currentTarget)
        setModal(null); }}><div className="fv-modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><IconButton className="fv-modal-close" label={t("Закрыть окно")} onClick={() => setModal(null)}><X size={20}/></IconButton><><span className="fv-modal-symbol"><Focus size={26}/></span><span className="fv-eyebrow">FORTE VISION</span><h2 id="modal-title">{t("Как проверить запись")}</h2><p className="fv-modal-description">{t("Рабочее пространство для анализа визуально наблюдаемых действий при кассовых операциях.")}</p><div className="fv-help-steps">{[{ icon: Upload, title: "Загрузите запись", text: "Выберите MOV. Сервер подключается автоматически." }, { icon: ScanLine, title: "Дождитесь результата", text: "Интерфейс отправляет видео на ваш сервер и запрашивает статус обработки." }, { icon: Focus, title: "Рассмотрите события", text: "Откройте таймкод, изучите кадры, описание действия и нормативный источник." }].map((s, i) => <div key={s.title}><span><s.icon size={19}/></span><div><small>0{i + 1}</small><strong>{t(s.title)}</strong><p>{t(s.text)}</p></div></div>)}</div><div className="fv-notice"><Info size={16}/><span>{t("Загрузите видео и запустите проверку. Условные примеры помечены отдельно.")}</span></div><button className="fv-primary-button fv-full-width" onClick={() => setModal(null)}>{t("Всё понятно")} <Check size={16}/></button></></div></div>}
  </div>;
}
function exportReport(record: StoredCheck) { if (!isFinishedCheck(record)) return; const blob = new Blob([JSON.stringify(record.result, null, 2)], { type: "application/json" }); const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = `${record.demo ? "demo-" : ""}${record.id.replace(/[^a-zA-Z0-9_-]/g, "_")}.json`; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }

const RESULT_FILTERS = [
  { value: "all", label: "Все результаты", description: "Все записи текущего сеанса" },
  { value: "processing", label: "Активные проверки", description: "Загрузка, обработка и восстановление связи" },
  { value: "paused", label: "Ожидание приостановлено", description: "Можно продолжить по номеру задания" },
  { value: "failed", label: "Ошибки проверки", description: "Проверки, требующие внимания" },
  { value: "violation", label: CHECK_STATUS_LABELS.violation, description: "Есть признаки возможных нарушений" },
  { value: "no_violation", label: CHECK_STATUS_LABELS.no_violation, description: "Сервис не обнаружил событий" },
];
function ResultFilter({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  const { t } = useI18n(workspaceMessages);
  return <SelectPrimitive.Root value={value} onValueChange={onChange}>
    <SelectPrimitive.Trigger className="fv-filter-trigger" aria-label={t("Фильтр по результату проверки")}>
      <Settings2 size={16}/><SelectPrimitive.Value/><SelectPrimitive.Icon><ChevronDown size={14}/></SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
    <SelectPrimitive.Portal><SelectPrimitive.Content className="fv-filter-popup" position="popper" align="end" sideOffset={8} collisionPadding={16}>
      <SelectPrimitive.Viewport><SelectPrimitive.Group><SelectPrimitive.Label className="fv-filter-menu-label">{t("Результат проверки")}</SelectPrimitive.Label>
        {RESULT_FILTERS.map(option => <SelectPrimitive.Item className="fv-filter-option" key={option.value} value={option.value}>
          <div className="fv-filter-item-text"><SelectPrimitive.ItemText><span className="fv-filter-label">{t(option.label)}</span></SelectPrimitive.ItemText><span className="fv-filter-description">{t(option.description)}</span></div>
          <SelectPrimitive.ItemIndicator className="fv-filter-indicator"><Check size={16}/></SelectPrimitive.ItemIndicator>
        </SelectPrimitive.Item>)}
      </SelectPrimitive.Group></SelectPrimitive.Viewport>
    </SelectPrimitive.Content></SelectPrimitive.Portal>
  </SelectPrimitive.Root>;
}
