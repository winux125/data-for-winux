import { AnalysisError, resolveBaseUrl, type ApiConfig } from "@/lib/analysis";
export type ConnectionState = "unverified" | "checking" | "connected" | "reconnecting" | "unavailable" | "rejected" | "error" | "stale";
export interface ApiConnection { state: ConnectionState; checkedAt?: number; message?: string }
export type ConnectionEvent = {kind:"request"|"response"|"retry"|"cancel"|"expire"} | {kind:"failure";error:unknown};
export const CONNECTION_LABELS: Record<ConnectionState,string> = {
  unverified:"Связь не проверена",checking:"Проверка связи",connected:"Связь подтверждена",reconnecting:"Восстановление связи",
  unavailable:"Нет ответа API",rejected:"Доступ к API отклонён",error:"Ошибка ответа API",stale:"Ответ был ранее",
};
export function sameApiConfig(first: ApiConfig | null, second: ApiConfig | null): boolean {
  if(!first || !second)return first===second;
  try {return resolveBaseUrl(first.baseUrl)===resolveBaseUrl(second.baseUrl) && first.apiKey.trim()===second.apiKey.trim();}catch{return false;}
}
export function connectionTransition(current: ApiConnection, event: ConnectionEvent, now: number): ApiConnection {
  if(event.kind==="request")return current.state==="connected" || current.state==="reconnecting" ? current:{...current,state:"checking",message:undefined};
  if(event.kind==="response")return {state:"connected",checkedAt:now};
  if(event.kind==="retry")return {...current,state:"reconnecting",message:undefined};
  if(event.kind==="cancel")return {...current,state:current.checkedAt ? "stale":"unverified",message:undefined};
  if(event.kind==="expire")return current.state==="connected" ? {...current,state:"stale"}:current;
  if(event.kind!=="failure")return current;
  if(event.error instanceof AnalysisError && event.error.code==="job_failed")return current;
  const state: ConnectionState = event.error instanceof AnalysisError
    ? event.error.httpStatus===401 || event.error.httpStatus===403 ? "rejected"
      : event.error.code==="network" || event.error.code==="timeout" ? "unavailable":"error" : "error";
  return {...current,state,message:event.error instanceof Error ? event.error.message:undefined};
}
