import { initialReviewState, type ReviewState } from "@/lib/review-navigation";
export type WorkspaceSection = "overview" | "checks" | "rules";
export interface WorkspaceRoute { section: WorkspaceSection; checkId: string | null; review: ReviewState }
export const initialWorkspaceRoute: WorkspaceRoute = { section:"overview", checkId:null, review:initialReviewState };
export const WORKSPACE_HISTORY_KEY = "forteWorkspaceNavigationV1";
const validId = (value: unknown): value is string => typeof value === "string" && /^[A-Za-z0-9_.-]{1,200}$/.test(value);
const seconds = (value: unknown): value is number => typeof value === "number" && Number.isFinite(value) && value >= 0;
export function routeHash(route: WorkspaceRoute): string {
  let hash = `#workspace/${route.section}`;
  if (route.checkId) hash += `/${encodeURIComponent(route.checkId)}`;
  if (route.checkId && route.review.screen === "event" && route.review.eventIndex !== null) hash += `/event/${route.review.eventIndex+1}`;
  return hash;
}
export function readWorkspaceRoute(hash: string, state?: unknown): WorkspaceRoute | null {
  if (hash && !hash.startsWith("#workspace/")) return null;
  const parts = hash.replace(/^#workspace\//, "").split("/");
  const section: WorkspaceSection = ["overview","checks","rules"].includes(parts[0]) ? parts[0] as WorkspaceSection : "overview";
  let checkId: string | null = null;
  try { const value = decodeURIComponent(parts[1] || ""); if (section === "checks" && validId(value)) checkId = value; } catch { /* Untrusted fragment. */ }
  const index = parts[2] === "event" && /^[1-9]\d{0,5}$/.test(parts[3] || "") ? Number(parts[3])-1 : null;
  let review: ReviewState = { ...initialReviewState, screen:checkId && index !== null ? "event":"video", eventIndex:checkId ? index:null };
  const saved = state && typeof state === "object" ? (state as Record<string,unknown>)[WORKSPACE_HISTORY_KEY] : null;
  if (saved && typeof saved === "object") {
    const value = saved as WorkspaceRoute;
    if (value.section === section && value.checkId === checkId && value.review?.screen === review.screen && (review.screen === "video" || value.review.eventIndex === index)) {
      const selected = value.review.eventIndex;
      const clip = value.review.clip;
      review = { ...review, position:seconds(value.review.position) ? value.review.position:0,
        eventIndex:checkId && Number.isInteger(selected) && selected !== null && selected >= 0 && selected < 1e6 ? selected:review.eventIndex,
        clip:review.screen === "video" && clip && seconds(clip.start) && seconds(clip.end) && clip.end >= clip.start ? {start:clip.start,end:clip.end}:null };
    }
  }
  return {section,checkId,review};
}
/** Whitelist navigation metadata; never put files, credentials or results into history. */
export function historyPayload(route: WorkspaceRoute, previous: unknown): Record<string,unknown> {
  return { ...(previous && typeof previous === "object" ? previous:{}), [WORKSPACE_HISTORY_KEY]:{
    section:route.section, checkId:route.checkId,
    review:{screen:route.review.screen,eventIndex:route.review.eventIndex,position:route.review.position,clip:route.review.clip ? {start:route.review.clip.start,end:route.review.clip.end}:null},
  } };
}
