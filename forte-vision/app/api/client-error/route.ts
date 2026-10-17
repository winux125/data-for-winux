export const dynamic = "force-dynamic";

const MAX_BYTES = 6 * 1024;
const headers = { "Cache-Control": "private, no-store", "Vary": "Origin", "X-Content-Type-Options": "nosniff" };
const limits = { release: 80, source: 80, path: 120, name: 80, message: 500, stack: 2500 } as const;

function reply(status: number) {
  return new Response(null, { status, headers });
}

function redact(value: string, limit: number) {
  return value
    .replace(/\bBearer\s+[^\s"'`,;<>]+/gi, "Bearer [redacted]")
    .replace(/((?:["']?\b(?:password|passwd|token|access_token|refresh_token|id_token|api[_-]?key|authorization|secret|client_secret)\b["']?)\s*[:=]\s*)(?:"[^"]*"|'[^']*'|[^\s,;}\])<>]+)/gi, "$1[redacted]")
    .replace(/\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b/g, "[redacted]")
    .replace(/\b(?:sk[-_]|sb_secret_)[A-Za-z0-9_-]+\b/g, "[redacted]")
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "[email]")
    .replace(/(https?:\/\/)[^\s/@]+:[^\s/@]+@/gi, "$1[redacted]@")
    .replace(/\?[^\s"'<>)]*/g, "?[redacted]")
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
    .slice(0, limit);
}

export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin || request.headers.get("sec-fetch-site") === "cross-site") return reply(403);
  if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") return reply(415);
  const declaredLength = request.headers.get("content-length");
  if (declaredLength !== null && /^\d+$/.test(declaredLength) && Number(declaredLength) > MAX_BYTES) return reply(413);
  if (!request.body) return reply(400);

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let byteLength = 0;
  let body: unknown;
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      byteLength += value.byteLength;
      if (byteLength > MAX_BYTES) {
        await reader.cancel().catch(() => {});
        return reply(413);
      }
      chunks.push(value);
    }
    const bytes = new Uint8Array(byteLength);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    body = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } catch { return reply(400); }
  finally { reader.releaseLock(); }

  if (!body || typeof body !== "object" || Array.isArray(body)) return reply(400);
  const fields = body as Record<string, unknown>;
  if (typeof fields.message !== "string" || !fields.message.trim()) return reply(400);
  const safe: Record<string, string> = {};
  for (const [key, limit] of Object.entries(limits)) {
    if (typeof fields[key] === "string") safe[key] = redact(fields[key], limit);
  }
  console.error("forte-client-error", JSON.stringify(safe));
  return reply(204);
}
