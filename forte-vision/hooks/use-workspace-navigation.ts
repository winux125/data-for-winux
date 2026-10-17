"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { initialReviewState, reviewNavigation, type ReviewAction } from "@/lib/review-navigation";
import { historyPayload, initialWorkspaceRoute, readWorkspaceRoute, routeHash, type WorkspaceRoute, type WorkspaceSection } from "@/lib/workspace-navigation";
export function useWorkspaceNavigation() {
  const [route,setRoute] = useState(initialWorkspaceRoute);
  const [revision,setRevision] = useState(0);
  const traversal = useRef(0);
  const current = useRef(route);
  const write = useCallback((next: WorkspaceRoute, replace = false) => {
    if (JSON.stringify(next) === JSON.stringify(current.current)) return;
    // Preserve playback position on the entry being left as well as its destination.
    try {
      if(!replace)window.history.replaceState(historyPayload(current.current,window.history.state),"",routeHash(current.current));
      window.history[replace?"replaceState":"pushState"](historyPayload(next,window.history.state),"",routeHash(next));
    } catch { /* The interface still works if browser history is unavailable. */ }
    current.current = next; setRoute(next);
  }, []);
  useEffect(() => {
    const initial = readWorkspaceRoute(window.location.hash,window.history.state) || initialWorkspaceRoute;
    // Hash/history are external browser state, unavailable during server rendering.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    current.current = initial; setRoute(initial);
    try { window.history.replaceState(historyPayload(initial,window.history.state),"",routeHash(initial)); } catch { /* Optional history. */ }
    const restore = () => {
      if (window.location.pathname !== "/app") return;
      const next = readWorkspaceRoute(window.location.hash,window.history.state);
      if (!next) return;
      current.current = next; setRoute(next); traversal.current+=1;setRevision(traversal.current);
    };
    window.addEventListener("popstate",restore);
    return () => window.removeEventListener("popstate",restore);
  }, []);
  const goSection = useCallback((section: WorkspaceSection) => write({section,checkId:null,review:initialReviewState}), [write]);
  const openCheck = useCallback((id: string) => write({section:"checks",checkId:id,review:initialReviewState}), [write]);
  const reviewAction = useCallback((action: ReviewAction, replace = false, checkId?: string, revision?: number) => {
    const previous = current.current;
    if (!previous.checkId || (checkId && previous.checkId!==checkId) || (revision!==undefined && revision!==traversal.current)) return;
    if (action.type === "inspect" && typeof action.position === "number" && Number.isFinite(action.position) && action.position >= 0) current.current = {...previous,review:{...previous.review,position:action.position}};
    const next = reviewNavigation(current.current.review,action);
    if (next === current.current.review) return;
    write({...current.current,review:next},replace || action.type === "time");
  }, [write]);
  return {route,revision,goSection,openCheck,reviewAction};
}
