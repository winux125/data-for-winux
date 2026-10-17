"use client";
import { useI18n } from "@/components/locale-provider";
import { workspaceMessages } from "@/lib/messages/workspace";
import { checkProgress } from "@/lib/check-progress";
import type { StoredCheck } from "@/lib/checks";
export default function JobProgress({ check }: { check: StoredCheck }) {
  const { t } = useI18n(workspaceMessages);
  const percent = checkProgress(check);
  const message = check.stage === "queued" ? t("Запись в очереди. Заданий впереди: {count}",{count:check.queuePosition ?? 0})
    : percent === undefined ? t("Сервер анализирует видео. Результат появится автоматически.")
    : t(check.status === "uploading" ? "{progress}% загружено" : check.status === "reconnecting" ? "Последний прогресс: {progress}%" : "Обработано {progress}%",{progress:Math.round(percent)});
  return <div className="fv-job-progress-block"><p className="fv-progress-label">{message}</p><div className={`fv-job-progress ${percent === undefined ? "fv-indeterminate" : ""}`} role="progressbar" aria-label={t(check.status === "uploading" ? "Передача видео" : "Обработка")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} aria-valuetext={message}><span style={{width:`${percent ?? 35}%`}}/></div></div>;
}
