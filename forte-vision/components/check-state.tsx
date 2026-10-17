"use client";
import { ArrowLeft, ArrowRight, Clock3, Loader2, Pause, TriangleAlert } from "lucide-react";
import { useEffect, useRef } from "react";
import { useI18n } from "@/components/locale-provider";
import { workspaceMessages } from "@/lib/messages/workspace";
import { CHECK_STATUS_LABELS, isRunningCheck, type StoredCheck } from "@/lib/checks";
import { translateAnalysisMessage } from "@/lib/analysis-messages";
import JobProgress from "@/components/job-progress";

export default function CheckState({ check, onBack, onCancel, onResume, onNewCheck, busy = false }: {
  check: StoredCheck; onBack: () => void; onCancel?: () => void; onResume?: () => void; onNewCheck?: () => void; busy?: boolean;
}) {
  const { t } = useI18n(workspaceMessages);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { heading.current?.focus({ preventScroll: true }); }, [check.id]);
  const running = isRunningCheck(check);
  const title = CHECK_STATUS_LABELS[check.status] && !["violation", "no_violation"].includes(check.status) ? CHECK_STATUS_LABELS[check.status] : "Результат недоступен";
  return <section className="fv-job-screen" aria-labelledby="job-heading">
    <button type="button" className="fv-back-link" onClick={onBack}><ArrowLeft size={16}/>{t("К проверкам")}</button>
    <div className="fv-job-heading"><span className="fv-eyebrow">{t("ПРОВЕРКА ВИДЕО")}</span><h1 ref={heading} id="job-heading" tabIndex={-1}>{t(title)}</h1><p>{check.name}</p></div>
    <div className="fv-job-state" data-state={check.status} role={check.status === "failed" ? "alert" : "status"}>
      <span className="fv-job-symbol">{running ? <Loader2 className="fv-spin" size={25}/> : check.status === "paused" ? <Pause size={25}/> : <TriangleAlert size={25}/>}</span>
      <div>
        {running ? <><strong>{t(check.status === "uploading" ? "Передаём запись на сервер" : check.status === "reconnecting" ? "Временно потеряна связь с сервером" : "Сервер обрабатывает запись")}</strong>
          {check.status === "reconnecting" && <p>{t("Повтор запроса статуса: {attempt}. Видео повторно не отправляется.", { attempt: check.retryAttempt || 1 })}</p>}
        </> : <><strong>{t(check.canResume ? "Можно продолжить ожидание по номеру задания" : "Итоговый результат пока недоступен")}</strong><p>{check.error ? translateAnalysisMessage(check.error, t) : t("Готовый результат не передан. Вердикт не отображается.")}</p></>}
        {check.jobId && <p className="fv-job-id">{t("Номер задания")}: <code>{check.jobId}</code></p>}
        {check.baseUrl && <p className="fv-job-server">{t("Сервер")}: {check.baseUrl}</p>}
      </div>
    </div>
    {running && <JobProgress check={check}/>}
    <div className="fv-job-actions">
      {running && onCancel && <button type="button" className="fv-secondary-button" onClick={onCancel}><Pause size={16}/>{t("Отменить ожидание")}</button>}
      {!running && check.canResume && check.jobId && onResume && <button type="button" className="fv-primary-button" disabled={busy} onClick={onResume}><Clock3 size={16}/>{t("Продолжить ожидание")}</button>}
      {!running && onNewCheck && <button type="button" className="fv-secondary-button" disabled={busy} onClick={onNewCheck}>{t("Новая проверка")}<ArrowRight size={16}/></button>}
    </div>
    <p className="fv-job-help">{t("Состояние проверки доступно в истории. Отмена ожидания не останавливает задание на сервере.")}</p>
  </section>;
}
