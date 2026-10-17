"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { analyzeVideo, formatTime, resolveBaseUrl, resumeAnalysis, VERDICT_LABELS, type ApiConfig, type AnalysisOptions } from "@/lib/analysis";
import { applyJobStatus, checkpointData, isRunningCheck, JOB_CHECKPOINT_KEY, restoreCheckpoints, stopCheck, type StoredCheck } from "@/lib/checks";
import type { ConnectionEvent } from "@/lib/api-connection";

type Notice = (message: string, tone?: "info" | "error" | "success") => void;
export function useAnalysisJobs(initial: StoredCheck[], onNotice: Notice, onConnection?: (config: ApiConfig, event: ConnectionEvent)=>void) {
  const [records, setRecords] = useState<StoredCheck[]>(initial);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [restored, setRestored] = useState(false);
  const recordsRef = useRef(records);
  const noticeRef = useRef(onNotice);
  const connectionRef = useRef(onConnection);
  useEffect(() => { recordsRef.current = records; noticeRef.current = onNotice; connectionRef.current=onConnection; }, [records, onNotice, onConnection]);
  const running = useRef<{ id: string; controller: AbortController } | null>(null);
  const version = useRef(0);
  const update = useCallback((id: string, change: Partial<StoredCheck> | ((record: StoredCheck) => StoredCheck)) => {
    setRecords(previous => previous.map(record => record.id === id ? typeof change === "function" ? change(record) : { ...record, ...change } : record));
  }, []);
  useEffect(() => {
    try { const saved = restoreCheckpoints(sessionStorage.getItem(JOB_CHECKPOINT_KEY));
      setRecords(previous => [...saved.filter(record => !previous.some(existing => existing.id === record.id)), ...previous]);
    } catch { /* Storage is optional. */ }
    setRestored(true);
    return () => { version.current += 1; running.current?.controller.abort(); running.current = null; };
  }, []);
  useEffect(() => {
    if (!restored) return;
    try { sessionStorage.setItem(JOB_CHECKPOINT_KEY, checkpointData(records)); } catch { /* The current tab still works. */ }
  }, [records, restored]);
  useEffect(() => {
    if (!busyId) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [busyId]);

  const execute = useCallback(async (record: StoredCheck, config: ApiConfig, file?: File) => {
    const controller = new AbortController();
    const token = ++version.current;
    running.current = { id: record.id, controller };
    setBusyId(record.id);
    let latest = record;
    const change = (patch: Partial<StoredCheck> | ((item: StoredCheck) => StoredCheck)) => {
      if (version.current !== token) return;
      latest = typeof patch === "function" ? patch(latest) : { ...latest, ...patch };
      update(record.id, patch);
    };
    change({ status: file ? "uploading" : "processing", error: undefined, retryAttempt: 0 });
    const options: AnalysisOptions = {
      signal: controller.signal,
      onRequest:()=>{if(version.current===token)connectionRef.current?.(config,{kind:"request"});},
      onResponse:()=>{if(version.current===token)connectionRef.current?.(config,{kind:"response"});},
      onUploadProgress: uploadProgress => change({ uploadProgress }),
      onStatus: job => change(item => applyJobStatus(item, job)),
      onConnectionChange: connection => { if(version.current===token && connection.state==="reconnecting")connectionRef.current?.(config,{kind:"retry"}); change({ status: connection.state === "reconnecting" ? "reconnecting" : "processing", retryAttempt: connection.attempt, retryAfterMs: connection.retryAfterMs }); },
    };
    try {
      const result = file ? await analyzeVideo(file, { ...config }, options) : await resumeAnalysis(record.jobId!, { ...config }, options);
      if (version.current !== token) return;
      change(item => applyJobStatus(item, result));
      noticeRef.current(VERDICT_LABELS[result.verdict], result.verdict === "no_violation" ? "success" : "info");
    } catch (error) {
      if (version.current !== token) return;
      connectionRef.current?.(config,controller.signal.aborted?{kind:"cancel"}:{kind:"failure",error});
      change(item => stopCheck(item, error, controller.signal.aborted));
      noticeRef.current(latest.error || "Не удалось обработать видео. Попробуйте ещё раз.", controller.signal.aborted ? "info" : "error");
    } finally {
      if (version.current === token) { running.current = null; setBusyId(null); }
    }
  }, [update]);

  const start = useCallback((file: File, videoUrl: string, seconds: number, config: ApiConfig): string | null => {
    if (running.current) return null;
    let baseUrl: string;
    try { baseUrl = resolveBaseUrl(config.baseUrl); } catch (error) { noticeRef.current((error as Error).message, "error"); return null; }
    const id = `local-${globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
    const record: StoredCheck = { id, name: file.name, createdAt: new Date().toISOString(), fileBytes: file.size, videoUrl,
      seconds, duration: seconds > 0 ? formatTime(seconds) : "-", baseUrl, status: "uploading", events: 0, uploadProgress: 0 };
    setRecords(previous => [record, ...previous]);
    void execute(record, { ...config, baseUrl }, file);
    return id;
  }, [execute]);
  const resume = useCallback((id: string, config: ApiConfig) => {
    const record = recordsRef.current.find(item => item.id === id);
    if (running.current || !record?.jobId || !record.canResume || isRunningCheck(record)) return;
    try {
      const baseUrl = resolveBaseUrl(config.baseUrl);
      if (baseUrl !== record.baseUrl) { noticeRef.current("Для продолжения подключите тот же сервер, на который отправлена запись.", "error"); return; }
      void execute(record, { ...config, baseUrl });
    } catch (error) { noticeRef.current((error as Error).message, "error"); }
  }, [execute]);
  const cancel = useCallback(() => running.current?.controller.abort(), []);
  return { records, setRecords, update, start, resume, cancel, busyId, restored, busyCheck: records.find(record => record.id === busyId) };
}
