import type { MessageValues } from "./i18n";
type Translator = (source: string, values?: MessageValues) => string;
export function translateAnalysisMessage(message: string, t: Translator): string {
  const serviceErrors: Record<string, string> = {
    publication_not_allowed: "RAG не разрешил публикацию заключения: нормативные карточки требуют проверки специалистом.",
    evidence_insufficient: "Недостаточно подтверждённых наблюдений для итогового результата. Требуется ручная проверка записи.",
    evidence_scope_unresolved: "Не удалось связать заключение с конкретным кадром. Требуется ручная проверка записи.",
    processing_timeout: "Сервер не завершил анализ за отведённое время. Попробуйте повторить проверку.",
    worker_restarted: "Обработка прервана перезапуском сервера. Отправьте запись повторно.",
    analysis_failed: "Не удалось обработать запись. Проверьте видео и повторите отправку.",
  };
  if (serviceErrors[message]) return t(serviceErrors[message]);
  const http = /^Сервер анализа вернул ошибку HTTP (\d+)\. Попробуйте повторить запрос\.$/.exec(message);
  if (http) return t("Сервер анализа вернул ошибку HTTP {status}. Попробуйте повторить запрос.", { status: http[1] });
  const malformed = /^Сервер вернул некорректный результат: (.+)\.$/.exec(message);
  if (malformed) {
    const numbered = /^(не заполнены поля события|некорректный кадр события|некорректный идентификатор события) (\d+)$/.exec(malformed[1]);
    const detail = numbered ? t(`${numbered[1]} {number}`, { number: numbered[2] }) : t(malformed[1]);
    return t("Сервер вернул некорректный результат: {detail}.", { detail });
  }
  return t(message);
}
