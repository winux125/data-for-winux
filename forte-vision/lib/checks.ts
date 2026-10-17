import { AnalysisError, isCompletedJob, resolveBaseUrl, type CompletedJob, type Job, type Verdict } from "@/lib/analysis";

export type CheckStatus = Verdict | "uploading" | "processing" | "reconnecting" | "paused" | "failed";
export interface CheckRecord {
  id: string;
  jobId?: string;
  name: string;
  createdAt: string;
  duration: string;
  status: CheckStatus;
  events: number;
  demo?: boolean;
}
export interface StoredCheck extends CheckRecord {
  result?: Job;
  videoUrl?: string;
  fileBytes?: number;
  seconds?: number;
  baseUrl?: string;
  uploadProgress?: number;
  progress?: number;
  stage?: string;
  queuePosition?: number;
  error?: string;
  canResume?: boolean;
  retryAttempt?: number;
  retryAfterMs?: number;
}
export const CHECK_STATUS_LABELS: Record<CheckStatus, string> = {
  violation: "Обнаружены признаки возможных нарушений", no_violation: "Нарушение не обнаружено",
  uploading: "Загрузка видео", processing: "В обработке", reconnecting: "Восстановление связи",
  paused: "Ожидание приостановлено", failed: "Ошибка проверки",
};
export function isRunningCheck(check: Pick<CheckRecord, "status">): boolean {
  return check.status === "uploading" || check.status === "processing" || check.status === "reconnecting";
}
export function isFinishedCheck(check: StoredCheck): check is StoredCheck & { status: Verdict; result: CompletedJob } {
  return isCompletedJob(check.result) && check.status === check.result.verdict;
}
export function applyJobStatus(check: StoredCheck, job: Job): StoredCheck {
  if (isCompletedJob(job)) return { ...check, jobId: job.job_id, status: job.verdict, result: job, events: job.violations.length, progress: 100, canResume: false, error: undefined, retryAttempt: 0 };
  return { ...check, jobId: job.job_id, status: job.status, result: undefined, progress: job.progress,
    stage: job.stage, queuePosition: job.queue_position,
    error: job.status === "failed" ? job.error : undefined, canResume: job.status === "processing", retryAttempt: 0 };
}
export function stopCheck(check: StoredCheck, error: unknown, aborted: boolean): StoredCheck {
  const canResume = Boolean(check.jobId) && !(error instanceof AnalysisError && error.code === "job_failed");
  const paused = aborted || (error instanceof AnalysisError && error.retryable);
  return { ...check, status: paused ? "paused" : "failed", result: undefined, canResume, retryAttempt: 0,
    error: aborted ? "Ожидание отменено. Задание на сервере может продолжаться."
      : error instanceof Error ? error.message : "Не удалось обработать видео. Попробуйте ещё раз." };
}

export const JOB_CHECKPOINT_KEY = "forte-job-checkpoints-v1";
/** Metadata for unfinished jobs only. Never persist keys, File, blob URLs, results or frames. */
export function checkpointData(records: StoredCheck[]): string {
  return JSON.stringify(records.filter(record => !record.demo && record.jobId && (record.canResume || isRunningCheck(record))).slice(0, 20).map(record => ({
    id: record.id, jobId: record.jobId, name: record.name, createdAt: record.createdAt, duration: record.duration,
    seconds: record.seconds, fileBytes: record.fileBytes, baseUrl: record.baseUrl,
  })));
}
export function restoreCheckpoints(raw: string | null): StoredCheck[] {
  try {
    const data: unknown = JSON.parse(raw || "[]");
    if (!Array.isArray(data)) return [];
    const seen = new Set<string>();
    return data.slice(0, 20).flatMap((value: unknown) => {
      if (!value || typeof value !== "object") return [];
      const item = value as Record<string, unknown>;
      if (!["id", "jobId", "name", "createdAt", "duration", "baseUrl"].every(key => typeof item[key] === "string" && (item[key] as string).length > 0 && (item[key] as string).length <= 1024)) return [];
      if (seen.has(item.id as string)) return [];
      try { resolveBaseUrl(item.baseUrl as string); } catch { return []; }
      seen.add(item.id as string);
      return [{ id: item.id as string, jobId: item.jobId as string, name: item.name as string, createdAt: item.createdAt as string,
        duration: item.duration as string, baseUrl: item.baseUrl as string,
        seconds: typeof item.seconds === "number" && Number.isFinite(item.seconds) && item.seconds > 0 ? item.seconds : undefined,
        fileBytes: typeof item.fileBytes === "number" && Number.isFinite(item.fileBytes) && item.fileBytes > 0 ? item.fileBytes : undefined,
        status: "paused" as const, events: 0, canResume: true, error: "Ожидание восстановлено после перезагрузки. Продолжите проверку." }];
    });
  } catch { return []; }
}
