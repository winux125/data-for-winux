import type { StoredCheck } from "@/lib/checks";
export const DELETE_UNDO_MS = 10_000;
export interface DeletedBatch { records: StoredCheck[]; order: string[]; selected: string[]; deadline: number }
export function stageDeletion(current: StoredCheck[], ids: string[], previous: DeletedBatch | null, selected: string[], now: number): DeletedBatch | null {
  const requested = new Set(ids); const removed = current.filter(record=>requested.has(record.id));
  if (!removed.length) return previous;
  const order = previous ? [...current.map(record=>record.id).filter(id=>!previous.order.includes(id)),...previous.order] : current.map(record=>record.id);
  return {records:[...(previous?.records || []),...removed], order, selected:[...new Set([...(previous?.selected || []),...selected])],deadline:now+DELETE_UNDO_MS};
}
export function restoreDeletion(current: StoredCheck[], batch: DeletedBatch): StoredCheck[] {
  const result = [...current]; const ids = new Set(result.map(record=>record.id));
  const deleted = new Map(batch.records.map(record=>[record.id,record]));
  for (let at = batch.order.length-1; at >= 0; at--) {
    const id = batch.order[at]; const record = deleted.get(id);
    if (!record || ids.has(id)) continue;
    const next = batch.order.slice(at+1).find(id=>ids.has(id));
    const previous = [...batch.order.slice(0,at)].reverse().find(id=>ids.has(id));
    const index = next ? result.findIndex(item=>item.id===next) : previous ? result.findIndex(item=>item.id===previous)+1 : result.length;
    result.splice(index,0,record); ids.add(id);
  }
  return result;
}
