export interface ReviewState {
  screen: "video" | "event";
  eventIndex: number | null;
  position: number;
  clip: { start: number; end: number } | null;
}

export const initialReviewState: ReviewState = {
  screen: "video", eventIndex: null, position: 0, clip: null,
};

export type ReviewAction =
  | { type: "inspect"; index: number; count: number; position?: number }
  | { type: "back_to_video" }
  | { type: "watch_clip"; start: number; end: number }
  | { type: "full_video" }
  | { type: "time"; seconds: number };

export function reviewNavigation(state: ReviewState, action: ReviewAction): ReviewState {
  switch (action.type) {
    case "inspect": {
      if (!Number.isInteger(action.index) || action.index < 0 || action.index >= action.count) return state;
      const position = typeof action.position === "number" && Number.isFinite(action.position) && action.position >= 0
        ? action.position : state.position;
      return { screen: "event", eventIndex: action.index, position, clip: null };
    }
    case "back_to_video":
      return { ...state, screen: "video", clip: null };
    case "watch_clip":
      if (state.eventIndex === null || !Number.isFinite(action.start) || !Number.isFinite(action.end)
        || action.start < 0 || action.end < action.start) return state;
      return { ...state, screen: "video", position: action.start, clip: { start: action.start, end: action.end } };
    case "full_video":
      return { ...state, screen: "video", clip: null };
    case "time":
      if (state.screen !== "video" || !Number.isFinite(action.seconds) || action.seconds < 0 || action.seconds === state.position) return state;
      return { ...state, position: action.seconds };
  }
}
