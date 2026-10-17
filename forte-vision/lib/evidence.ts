/** Bounded raster evidence. A bad image never removes the event description. */
export const MAX_FRAME_BYTES = 2 * 1024 * 1024;
export const MAX_EVIDENCE_BYTES = 8 * 1024 * 1024;
export const MAX_FRAMES_PER_EVENT = 3;
export const MAX_IMAGE_SIDE = 4096;
export const MAX_IMAGE_PIXELS = 8 * 1024 * 1024;
export type FrameIssue = "invalid" | "size" | "dimensions" | "budget";
export const FRAME_ISSUE_MESSAGES: Record<FrameIssue, string> = {
  invalid: "Кадр повреждён или имеет неподдерживаемый формат.",
  size: "Кадр превышает лимит 2 МБ.",
  dimensions: "Разрешение кадра превышает допустимый размер.",
  budget: "Кадр не загружен: превышен общий лимит изображений.",
};
export function validImageDimensions(width: number, height: number): boolean {
  return width > 0 && height > 0 && width <= MAX_IMAGE_SIDE && height <= MAX_IMAGE_SIDE && width * height <= MAX_IMAGE_PIXELS;
}
function bytes(payload: string, count: number): Uint8Array {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const data = new Uint8Array(count); let bits = 0; let buffer = 0; let offset = 0;
  for (let i = 0; i < payload.length && offset < count; i++) {
    if (payload[i] === "=") break;
    buffer = (buffer << 6) | alphabet.indexOf(payload[i]); bits += 6;
    if (bits >= 8) { bits -= 8; data[offset++] = (buffer >> bits) & 255; }
  }
  return data;
}
export function inspectEvidence(value: unknown): { source: string | null; bytes: number; issue?: FrameIssue } {
  const reject = (issue: FrameIssue) => ({ source: null, bytes: 0, issue });
  if (typeof value !== "string") return reject("invalid");
  // Bound raw length before trim, regex, decoding, or DOM allocation.
  if (value.length > Math.ceil(MAX_FRAME_BYTES / 3) * 4 + 64) return reject("size");
  const input = value.trim();
  const prefixed = /^data:(image\/(?:png|jpeg));base64,([\s\S]+)$/i.exec(input);
  if (input.startsWith("data:") && !prefixed) return reject("invalid");
  const payload = (prefixed ? prefixed[2] : input).replace(/\s/g, "");
  if (!payload || payload.length % 4 !== 0 || !/^[A-Za-z0-9+/]+={0,2}$/.test(payload)) return reject("invalid");
  const size = payload.length / 4 * 3 - (payload.endsWith("==") ? 2 : payload.endsWith("=") ? 1 : 0);
  if (size > MAX_FRAME_BYTES) return reject("size");
  const mime = payload.startsWith("iVBORw0KGgo") ? "image/png" : payload.startsWith("/9j/") ? "image/jpeg" : null;
  if (!mime || (prefixed && prefixed[1].toLowerCase() !== mime)) return reject("invalid");
  const data = bytes(payload, mime === "image/png" ? Math.min(24,size) : size);
  let width = 0; let height = 0;
  if (mime === "image/png") {
    if (data.length < 24 || String.fromCharCode(...data.slice(12,16)) !== "IHDR") return reject("invalid");
    const uint = (at: number) => data[at] * 16777216 + data[at+1] * 65536 + data[at+2] * 256 + data[at+3];
    width = uint(16); height = uint(20);
  } else {
    // Find a JPEG start-of-frame segment before passing compressed data to img.
    let at = 2;
    while (at + 3 < data.length) {
      if (data[at++] !== 255) return reject("invalid");
      while (data[at] === 255) at++;
      const marker = data[at++];
      if (marker === 0xDA || marker === 0xD9) break;
      if (marker === 0x01 || (marker >= 0xD0 && marker <= 0xD7)) continue;
      const length = data[at] * 256 + data[at+1];
      if (length < 2 || at + length > data.length) return reject("invalid");
      if ([0xC0,0xC1,0xC2,0xC3,0xC5,0xC6,0xC7,0xC9,0xCA,0xCB,0xCD,0xCE,0xCF].includes(marker)) {
        if (length < 8) return reject("invalid");
        height = data[at+3] * 256 + data[at+4]; width = data[at+5] * 256 + data[at+6]; break;
      }
      at += length;
    }
    if (!width || !height) return reject("invalid");
  }
  if (!validImageDimensions(width,height)) return reject("dimensions");
  return { source: `data:${mime};base64,${payload}`, bytes: size };
}
export function evidenceDataUrl(value: unknown): string | null { return inspectEvidence(value).source; }
