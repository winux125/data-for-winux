/** Review context, not a claim about the model's temporal accuracy. */
export const EVENT_CONTEXT_SECONDS = 3;

export function isKnownDuration(duration: number | undefined): duration is number {
  return typeof duration === "number" && Number.isFinite(duration) && duration > 0;
}
export function timecodeIssue(timecode: number, duration?: number): "outside_video" | "unknown_duration" | null {
  if (!Number.isFinite(timecode) || timecode < 0) return "outside_video";
  if (!isKnownDuration(duration)) return "unknown_duration";
  return timecode > duration ? "outside_video" : null;
}
export function getEventWindow(timecode: number, duration?: number) {
  if (timecodeIssue(timecode, duration) !== null || !isKnownDuration(duration)) return null;
  return { start: Math.max(0, timecode - EVENT_CONTEXT_SECONDS), end: Math.min(duration, timecode + EVENT_CONTEXT_SECONDS) };
}

/** Keep nearby markers on separate rows, including their keyboard/touch targets. */
export function layoutEventWindows(timecodes: number[], duration: number | undefined, trackWidth: number) {
  const width = Number.isFinite(trackWidth) ? Math.max(48, trackWidth) : 320;
  if (!isKnownDuration(duration)) return [];
  const limit = duration;
  const laneEnds: number[] = [];
  return timecodes.flatMap((timecode, index) => {
    const range = getEventWindow(timecode, limit);
    if (!range) return [];
    const { start, end } = range;
    const left = start / limit * 100;
    const right = end / limit * 100;
    const position = Number.isFinite(timecode) ? Math.max(0, timecode) : 0;
    const center = Math.min(width - 22, Math.max(22, position / limit * width));
    return [{ index, start, end, left, width: right - left, center, lane: 0 }];
  }).sort((a, b) => a.center - b.center || a.index - b.index).map(item => {
    const start = Math.min(item.left / 100 * width, item.center - 22);
    const end = Math.max((item.left + item.width) / 100 * width, item.center + 22);
    let lane = laneEnds.findIndex(previousEnd => previousEnd + 8 <= start);
    if (lane < 0) lane = laneEnds.length;
    laneEnds[lane] = end;
    return { ...item, center: item.center / width * 100, lane };
  }).sort((a, b) => a.index - b.index);
}

export const MAX_TIMELINE_LANES = 3;
/** Dense connected intervals become one selectable group, retaining every index. */
export function layoutTimelineMarkers(timecodes: number[], duration: number | undefined, trackWidth: number) {
  const windows = layoutEventWindows(timecodes,duration,trackWidth);
  type Marker = Omit<(typeof windows)[number], "index"> & { indices: number[] };
  if (!windows.some(item => item.lane >= MAX_TIMELINE_LANES)) return windows.map(({index,...item}) => ({ ...item, indices:[index] }));
  const width = Number.isFinite(trackWidth) ? Math.max(48,trackWidth) : 320;
  const components: { items: typeof windows; left: number; right: number }[] = [];
  for (const item of [...windows].sort((a,b) => Math.min(a.left,a.center - 22/width*100) - Math.min(b.left,b.center - 22/width*100))) {
    const left = Math.min(item.left,item.center-22/width*100);
    const right = Math.max(item.left+item.width,item.center+22/width*100);
    const previous = components.at(-1);
    if (previous && left < previous.right + 8/width*100) { previous.items.push(item); previous.right = Math.max(previous.right,right); }
    else components.push({items:[item],left,right});
  }
  const markers: Marker[] = components.flatMap(({items}) => {
    if (items.length <= MAX_TIMELINE_LANES) return items.map(({index,...item}) => ({ ...item, indices:[index] }));
    const left = Math.min(...items.map(item=>item.left)); const right = Math.max(...items.map(item=>item.left+item.width));
    return [{ indices: items.map(item=>item.index).sort((a,b)=>a-b), start: Math.min(...items.map(item=>item.start)), end: Math.max(...items.map(item=>item.end)), left, width:right-left,
      center:(Math.min(...items.map(item=>item.center))+Math.max(...items.map(item=>item.center)))/2, lane:0 }];
  });
  return markers;
}
