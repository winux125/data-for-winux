import { inspectEvidence, MAX_EVIDENCE_BYTES, MAX_FRAMES_PER_EVENT, type FrameIssue } from "@/lib/evidence";
export { evidenceDataUrl } from "@/lib/evidence";

/** Browser-only integration with the separate video analysis service. */
export type Verdict = "violation" | "no_violation";
export const VERDICT_LABELS: Record<Verdict, string> = {
  violation: "Обнаружены признаки возможных нарушений",
  no_violation: "Нарушение не обнаружено",
};
export type JobStatus = "processing" | "done" | "failed";

export interface RuleReference {
  title: string;
  section?: string;
  url?: string;
}

export interface EvidenceFrame {
  timestamp_sec: number;
  image_base64: string;
  /** Client-side placeholder reason; unavailable payload is discarded. */
  image_issue?: FrameIssue;
}

export interface Violation {
  id?: string;
  type: string;
  timecode_sec: number;
  description: string;
  evidence_frames: EvidenceFrame[];
  omitted_evidence_frames?: number;
  rule?: RuleReference;
}

interface JobBase {
  job_id: string;
  stage?: string;
  queue_position?: number;
  error?: string;
  /** Optional server-reported percentage, from 0 to 100. */
  progress?: number;
}
export type CompletedJob = JobBase & { status: "done"; verdict: Verdict; violations: Violation[] };
export type Job = CompletedJob | (JobBase & { status: "processing" | "failed"; verdict?: never; violations?: never });

export function isCompletedJob(job: Job | undefined): job is CompletedJob {
  return Boolean(job && job.status === "done" && Array.isArray(job.violations)
    && ((job.verdict === "violation" && job.violations.length > 0)
      || (job.verdict === "no_violation" && job.violations.length === 0)));
}

export class AnalysisError extends Error {
  constructor(message: string, public code: "network" | "http" | "timeout" | "invalid_response" | "job_failed", public retryable = false, public httpStatus?: number) {
    super(message);
    this.name = "AnalysisError";
  }
}

export interface ApiConfig {
  /** HTTPS service origin; empty means the current site's origin. */
  baseUrl: string;
  /** Runtime value only. Never persist this value in browser storage. */
  apiKey: string;
  browser?: boolean;
}

export interface AnalysisOptions {
  signal?: AbortSignal;
  onRequest?: () => void;
  /** Emitted only after a real, validated API response, never for a local resume placeholder. */
  onResponse?: () => void;
  /** Actual browser upload percentage, from 0 to 100. */
  onUploadProgress?: (percent: number) => void;
  onStatus?: (job: Job) => void;
  onConnectionChange?: (connection: { state: "connected" | "reconnecting"; attempt: number; retryAfterMs: number }) => void;
}

const TIMEOUT_MS = 5 * 60 * 1000;
const POLL_INTERVAL_MS = 1_500;
export const MAX_API_RESPONSE_BYTES = 16 * 1024 * 1024;
function oversizedResponse(): AnalysisError { return new AnalysisError("Ответ сервера превышает лимит 16 МБ. Уменьшите размер кадров на сервере.", "invalid_response"); }

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function validSeconds(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= 0;
}

function malformed(detail: string): Error {
  return new AnalysisError(`Сервер вернул некорректный результат: ${detail}.`, "invalid_response");
}

export function formatTime(seconds: number): string {
  const total = Number.isFinite(seconds) ? Math.max(0, Math.floor(seconds)) : 0;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const rest = String(total % 60).padStart(2, "0");
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, "0")}:${rest}`
    : `${String(minutes).padStart(2, "0")}:${rest}`;
}

function parseRule(value: unknown): RuleReference | undefined {
  if (value === undefined || value === null) return undefined;
  if (!object(value) || !nonEmptyString(value.title)) throw malformed("не заполнен нормативный источник");
  const rule: RuleReference = { title: value.title };
  if (value.section !== undefined) {
    if (!nonEmptyString(value.section)) throw malformed("некорректный пункт нормативного источника");
    rule.section = value.section;
  }
  if (value.url !== undefined) {
    if (typeof value.url !== "string") throw malformed("некорректная ссылка на источник");
    try {
      const url = new URL(value.url);
      if (url.protocol !== "https:" && url.protocol !== "http:") throw new Error();
      rule.url = url.href;
    } catch {
      throw malformed("ссылка на источник должна начинаться с http или https");
    }
  }
  return rule;
}

function parseViolation(value: unknown, index: number, budget: { remaining: number }): Violation {
  if (!object(value) || !nonEmptyString(value.type) || !validSeconds(value.timecode_sec)
    || !nonEmptyString(value.description) || !Array.isArray(value.evidence_frames)) {
    throw malformed(`не заполнены поля события ${index + 1}`);
  }
  const frames: EvidenceFrame[] = value.evidence_frames.slice(0, MAX_FRAMES_PER_EVENT).map((frame: unknown) => {
    if (!object(frame) || !validSeconds(frame.timestamp_sec)) throw malformed(`некорректный кадр события ${index + 1}`);
    const image = inspectEvidence(frame.image_base64);
    const issue = image.issue || (image.bytes > budget.remaining ? "budget" : undefined);
    if (issue || !image.source) return { timestamp_sec: frame.timestamp_sec, image_base64: "", image_issue: issue || "invalid" };
    budget.remaining -= image.bytes;
    return { timestamp_sec: frame.timestamp_sec, image_base64: image.source };
  });
  const violation: Violation = {
    type: value.type,
    timecode_sec: value.timecode_sec,
    description: value.description,
    evidence_frames: frames,
  };
  if (value.evidence_frames.length > MAX_FRAMES_PER_EVENT) violation.omitted_evidence_frames = value.evidence_frames.length - MAX_FRAMES_PER_EVENT;
  if (value.id !== undefined) {
    if (!nonEmptyString(value.id)) throw malformed(`некорректный идентификатор события ${index + 1}`);
    violation.id = value.id;
  }
  const rule = parseRule(value.rule);
  if (rule) violation.rule = rule;
  return violation;
}

function parseJob(value: unknown, expectedId?: string): Job {
  if (!object(value) || !nonEmptyString(value.job_id)) throw malformed("отсутствует job_id");
  if (expectedId && value.job_id !== expectedId) throw malformed("идентификатор задания изменился");
  if (value.status !== "processing" && value.status !== "done" && value.status !== "failed") {
    throw malformed("неизвестный статус задания");
  }
  const job: JobBase = { job_id: value.job_id };
  if(typeof value.stage === "string" && value.stage.length <= 64)job.stage=value.stage;
  if(typeof value.queue_position === "number" && Number.isSafeInteger(value.queue_position) && value.queue_position >= 0)job.queue_position=value.queue_position;
  if (value.progress !== undefined) {
    if (typeof value.progress !== "number" || !Number.isFinite(value.progress)
      || value.progress < 0 || value.progress > 100) throw malformed("некорректный прогресс обработки");
    job.progress = value.progress;
  }
  if (value.error !== undefined && value.error !== null) {
    if (typeof value.error !== "string") throw malformed("некорректное сообщение об ошибке");
    job.error = value.error;
  }
  if (value.status === "done") {
    if (value.verdict !== "violation" && value.verdict !== "no_violation") {
      throw malformed("отсутствует итоговый verdict");
    }
    if (!Array.isArray(value.violations)) throw malformed("отсутствует список violations");
    const budget = { remaining: MAX_EVIDENCE_BYTES };
    const violations = value.violations.map((value,index) => parseViolation(value,index,budget));
    if (value.verdict === "violation" && violations.length === 0) throw malformed("не указаны найденные события");
    if (value.verdict === "no_violation" && violations.length > 0) throw malformed("вердикт противоречит списку событий");
    return { ...job, status: "done", verdict: value.verdict, violations };
  }
  return { ...job, status: value.status };
}

export function resolveBaseUrl(raw: string): string {
  let url: URL;
  try {
    const fallback = typeof window !== "undefined" ? window.location.origin : undefined;
    url = new URL(raw.trim() || fallback || "");
  } catch {
    throw new Error("Укажите полный адрес сервера, например https://analysis.example.kz.");
  }
  const loopback = url.hostname === "localhost" || url.hostname.endsWith(".localhost")
    || url.hostname === "[::1]" || /^127(?:\.\d{1,3}){3}$/.test(url.hostname)
    // The managed preview is HTTP and isolated; this exception is same-origin only.
    || (url.hostname === "terminal.local" && typeof window !== "undefined" && window.location.origin === url.origin);
  if (url.protocol !== "https:" && !(url.protocol === "http:" && loopback)) {
    throw new Error("Используйте HTTPS. HTTP разрешён только для локального сервера на localhost или loopback.");
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new Error("Адрес сервера не должен содержать пароль, параметры или фрагмент ссылки.");
  }
  return url.href.replace(/\/+$/, "");
}

function httpError(status: number): Error {
  const message = status === 401 || status === 403 ? "Сервер отклонил доступ. Проверьте API-ключ в настройках подключения."
    : status === 413 ? "Файл превышает ограничение размера на сервере."
      : status === 415 ? "Сервер не поддерживает этот формат видео. Выберите запись .mov."
        : status === 429 ? "Сервер занят. Повторите попытку немного позже."
          : `Сервер анализа вернул ошибку HTTP ${status}. Попробуйте повторить запрос.`;
  return new AnalysisError(message, "http", status === 408 || status === 429 || status >= 500, status);
}

function networkError(): Error {
  return new AnalysisError("Не удалось связаться с сервером. Проверьте адрес, доступность сервера, HTTPS и настройки CORS.", "network", true);
}

function abortError(): Error {
  const error = new Error("Анализ отменён.");
  error.name = "AbortError";
  return error;
}

function readJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    throw malformed("ожидался ответ JSON");
  }
}

function uploadVideo(file: File, endpoint: string, apiKey: string, signal: AbortSignal,
  onProgress?: AnalysisOptions["onUploadProgress"]): Promise<Job> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(abortError());
    const xhr = new XMLHttpRequest();
    const onAbort = () => xhr.abort();
    const cleanup = () => signal.removeEventListener("abort", onAbort);
    xhr.open("POST", endpoint);
    xhr.setRequestHeader("Accept", "application/json");
    if (apiKey.trim()) xhr.setRequestHeader("X-API-Key", apiKey.trim());
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress?.(Math.min(100, (event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      cleanup();
      if (xhr.status < 200 || xhr.status >= 300) return reject(httpError(xhr.status));
      try {
        if (new TextEncoder().encode(xhr.responseText).byteLength > MAX_API_RESPONSE_BYTES) throw oversizedResponse();
        const body = readJson(xhr.responseText);
        // Creation only guarantees job_id. A missing status means the newly
        // accepted task is processing; polling responses remain strict.
        resolve(parseJob(object(body) && body.status === undefined ? { ...body, status: "processing" } : body));
      } catch (error) {
        reject(error);
      }
    };
    xhr.onerror = () => { cleanup(); reject(networkError()); };
    xhr.onprogress = event => { if (event.loaded > MAX_API_RESPONSE_BYTES) { cleanup(); reject(oversizedResponse()); xhr.abort(); } };
    xhr.onabort = () => { cleanup(); reject(abortError()); };
    signal.addEventListener("abort", onAbort, { once: true });
    const data = new FormData();
    data.append("file", file, file.name);
    onProgress?.(0);
    xhr.send(data);
  });
}

async function limitedResponse(response: Response): Promise<unknown> {
  const declared = Number(response.headers?.get("content-length"));
  if (declared > MAX_API_RESPONSE_BYTES) { try { await response.body?.cancel(); } catch { /* Reject size regardless of cancellation support. */ } throw oversizedResponse(); }
  if (!response.body?.getReader) {
    const text = await response.text();
    if (new TextEncoder().encode(text).byteLength > MAX_API_RESPONSE_BYTES) throw oversizedResponse();
    return readJson(text);
  }
  const reader = response.body.getReader(); const decoder = new TextDecoder();
  let size = 0; let text = "";
  try {
    while (true) {
      const part = await reader.read(); if (part.done) break;
      size += part.value.byteLength;
      if (size > MAX_API_RESPONSE_BYTES) { try { await reader.cancel(); } catch { /* Size error stays terminal. */ } throw oversizedResponse(); }
      text += decoder.decode(part.value,{stream:true});
    }
    return readJson(text + decoder.decode());
  } finally { reader.releaseLock(); }
}

function pause(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(abortError());
    const onAbort = () => { clearTimeout(timer); reject(abortError()); };
    const timer = setTimeout(() => { signal.removeEventListener("abort", onAbort); resolve(); }, ms);
    signal.addEventListener("abort", onAbort, { once: true });
  });
}

async function operation(config: ApiConfig, options: AnalysisOptions, start: (baseUrl: string, signal: AbortSignal) => Promise<Job>, initialDelay: number): Promise<CompletedJob> {
  const baseUrl = resolveBaseUrl(config.baseUrl);
  const controller = new AbortController();
  const onExternalAbort = () => controller.abort();
  let timedOut = false;
  if (options.signal?.aborted) throw abortError();
  options.signal?.addEventListener("abort", onExternalAbort, { once: true });
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, config.browser ? 24 * 60 * 60 * 1000 : TIMEOUT_MS);
  try {
    let job = await start(baseUrl, controller.signal);
    options.onStatus?.(job);
    let failures = 0;
    let delay = initialDelay;
    while (job.status === "processing") {
      if (delay) await pause(delay, controller.signal);
      try {
        let response: Response;
        options.onRequest?.();
        try { response = await fetch(`${baseUrl}/api/${config.browser ? "browser" : "v1"}/jobs/${encodeURIComponent(job.job_id)}`, {
          signal: controller.signal,
          cache: "no-store",
          headers: { Accept: "application/json", ...(config.apiKey.trim() ? { "X-API-Key": config.apiKey.trim() } : {}) },
        }); } catch { if (controller.signal.aborted) throw abortError(); throw networkError(); }
        if (!response.ok) throw httpError(response.status);
        let body: unknown;
        try { body = await limitedResponse(response); } catch (error) { if (controller.signal.aborted) throw abortError(); if (error instanceof AnalysisError) throw error; throw networkError(); }
        job = parseJob(body, job.job_id);
        options.onResponse?.();
        if (failures) options.onConnectionChange?.({ state: "connected", attempt: 0, retryAfterMs: 0 });
        failures = 0;
        delay = POLL_INTERVAL_MS;
        options.onStatus?.(job);
      } catch (error) {
        if (controller.signal.aborted) throw abortError();
        if (!(error instanceof AnalysisError) || !error.retryable || failures >= 3) throw error;
        failures += 1;
        delay = POLL_INTERVAL_MS * 2 ** (failures - 1);
        options.onConnectionChange?.({ state: "reconnecting", attempt: failures, retryAfterMs: delay });
      }
    }
    if (job.status === "failed") throw new AnalysisError(job.error?.trim() || "Сервер не смог обработать запись. Попробуйте другое видео.", "job_failed");
    if (!isCompletedJob(job)) throw malformed("отсутствует итоговый verdict");
    return job;
  } catch (error) {
    if (timedOut) throw new AnalysisError(config.browser ? "Истекло время сеанса. Обновите страницу." : "Превышено время ожидания - 5 минут. Проверьте состояние сервера и повторите попытку.", "timeout", true);
    if (controller.signal.aborted) throw abortError();
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", onExternalAbort);
  }
}

/** POST is sent exactly once. Only safe status requests are retried. */
export async function analyzeVideo(file: File, config: ApiConfig, options: AnalysisOptions = {}): Promise<CompletedJob> {
  if (!file.size) throw new Error("Выбранный файл пуст. Выберите другую запись.");
  if (!/\.mov$/i.test(file.name)) throw new Error("Выберите видео в формате .mov.");
  return operation(config, options, async (baseUrl, signal) => {
    options.onRequest?.();
    const job=await uploadVideo(file, `${baseUrl}/api/${config.browser ? "browser" : "v1"}/analyze`, config.apiKey, signal, options.onUploadProgress);
    options.onResponse?.();return job;
  }, POLL_INTERVAL_MS);
}

/** Resume a known job with GET only. No File or new upload is needed. */
export async function resumeAnalysis(jobId: string, config: ApiConfig, options: AnalysisOptions = {}): Promise<CompletedJob> {
  if (!nonEmptyString(jobId)) throw malformed("отсутствует job_id");
  return operation(config, options, async () => ({ job_id: jobId, status: "processing" }), 0);
}
