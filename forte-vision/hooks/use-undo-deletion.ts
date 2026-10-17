"use client";
import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import type { StoredCheck } from "@/lib/checks";
import { restoreDeletion, stageDeletion, type DeletedBatch } from "@/lib/undo-deletion";
export function useUndoDeletion(records: StoredCheck[], setRecords: Dispatch<SetStateAction<StoredCheck[]>>, onPurge: (removed: StoredCheck[])=>void) {
  const [pending,setPending] = useState<DeletedBatch | null>(null);
  const current = useRef(records); const batch = useRef<DeletedBatch | null>(null);
  const purge = useRef(onPurge); const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(()=>{current.current=records;purge.current=onPurge;},[records,onPurge]);
  useEffect(()=>()=>{if(timer.current)clearTimeout(timer.current);},[]);
  const remove = useCallback((ids: string[], selected: string[]) => {
    if(batch.current && Date.now()>=batch.current.deadline){purge.current(batch.current.records);batch.current=null;if(timer.current)clearTimeout(timer.current);}
    const next = stageDeletion(current.current,ids,batch.current,selected,Date.now());
    if (!next || next === batch.current) return;
    if (timer.current) clearTimeout(timer.current);
    batch.current = next; setPending(next);
    const removed = new Set(ids); current.current = current.current.filter(record=>!removed.has(record.id));
    setRecords(previous=>previous.filter(record=>!removed.has(record.id)));
    timer.current = setTimeout(()=>{
      if (batch.current !== next) return;
      batch.current=null;setPending(null);timer.current=null;purge.current(next.records);
    },Math.max(0,next.deadline-Date.now()));
  },[setRecords]);
  const undo = useCallback(()=>{
    const saved=batch.current; if(!saved)return null;
    if (Date.now() >= saved.deadline) { if(timer.current)clearTimeout(timer.current);timer.current=null;batch.current=null;setPending(null);purge.current(saved.records);return null; }
    if(timer.current)clearTimeout(timer.current);timer.current=null;batch.current=null;setPending(null);
    current.current=restoreDeletion(current.current,saved);
    setRecords(previous=>restoreDeletion(previous,saved)); return saved;
  },[setRecords]);
  return {pending,remove,undo};
}
