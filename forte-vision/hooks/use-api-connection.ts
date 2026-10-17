"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { resolveBaseUrl, type ApiConfig } from "@/lib/analysis";
import { connectionTransition, sameApiConfig, type ApiConnection, type ConnectionEvent } from "@/lib/api-connection";
const SESSION_KEY = "forte-browser-session-v1";
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
export function useApiConnection() {
  const [api,setApi] = useState<ApiConfig | null>(null);
  const [connection,setConnection] = useState<ApiConnection>({state:"checking"});
  const [attempt,setAttempt] = useState(0);
  const [maxBytes,setMaxBytes] = useState(10 * 1024 ** 3);
  const saved = useRef<ApiConfig | null>(null);
  const retry = useCallback(()=>setAttempt(value=>value+1),[]);
  const report = useCallback((config: ApiConfig, event: ConnectionEvent)=>{
    if(!saved.current || !sameApiConfig(saved.current,config))return;
    setConnection(current=>connectionTransition(current,event,Date.now()));
  },[]);
  useEffect(()=>{
    const controller = new AbortController();
    async function connect() {
      try {
        const response = await fetch("/api/browser/config",{cache:"no-store",signal:controller.signal});
        if(!response.ok)throw new Error("Не удалось подключиться к серверу. Повторите подключение.");
        const config = await response.json();
        if(!record(config) || typeof config.base_url!=="string")throw new Error("Некорректный ответ сервера.");
        const baseUrl = resolveBaseUrl(config.base_url);
        if(typeof config.max_upload_bytes==="number" && Number.isSafeInteger(config.max_upload_bytes) && config.max_upload_bytes>0)setMaxBytes(config.max_upload_bytes);
        let session: {token:string;expires_at:number;baseUrl?:string} | null = null;
        try { const value=JSON.parse(sessionStorage.getItem(SESSION_KEY)||"null");
          if(value?.baseUrl===baseUrl && typeof value.token==="string" && value.expires_at>Date.now()/1000+60)session=value;
        } catch { /* Storage is optional. */ }
        if(!session) {
          const result=await fetch(`${baseUrl}/api/browser/session`,{method:"POST",cache:"no-store",signal:controller.signal});
          if(!result.ok)throw new Error("Не удалось подключиться к серверу. Повторите подключение.");
          const value=await result.json();
          if(!record(value) || typeof value.token!=="string" || typeof value.expires_at!=="number" || !Number.isFinite(value.expires_at))throw new Error("Некорректный ответ сервера.");
          session={token:value.token,expires_at:value.expires_at,baseUrl};
          try { sessionStorage.setItem(SESSION_KEY,JSON.stringify(session)); } catch { /* Memory remains available. */ }
        }
        if(controller.signal.aborted)return;
        const next={baseUrl,apiKey:session.token,browser:true};
        saved.current=next;setApi(next);setConnection({state:"connected",checkedAt:Date.now()});
      } catch(error) {
        if(!controller.signal.aborted)setConnection({state:"unavailable",message:error instanceof Error?error.message:undefined});
      }
    }
    void connect();
    return ()=>controller.abort();
  },[attempt]);
  return {api,connection,report,retry,maxBytes};
}
