/** Explicit, development-only responses for frontend/browser QA. Never a model. */
import type { Plugin } from "vite";

export function frontendFixtures(): Plugin {
  let scenario = "success";
  let posts = 0;
  const jobs = new Map<string, { polls: number; scenario: string }>();
  const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==";
  return { name: "forte-development-fixtures", apply: "serve", enforce: "pre", configureServer(server) {
    server.middlewares.use((req, res, next) => {
      const url = new URL(req.url || "/", "http://localhost");
      if (url.pathname === "/__frontend-fixtures/layout") {
        const width = [1024, 1280, 1366, 1440].includes(Number(url.searchParams.get("width"))) ? Number(url.searchParams.get("width")) : 1280;
        const locale = ["ru", "kk", "en"].includes(url.searchParams.get("locale") || "") ? url.searchParams.get("locale")! : "ru";
        res.setHeader("Content-Type", "text/html; charset=utf-8");
        res.setHeader("Cache-Control", "no-store");
        res.setHeader("Set-Cookie", `forte-locale=${locale}; Path=/; SameSite=Lax`);
        res.end(`<!doctype html><html lang="ru"><meta charset="utf-8"><title>Frontend viewport lab</title><style>body{margin:0;background:#ece8eb;font:14px Arial,sans-serif}header{padding:10px 16px}a{display:inline-block;margin:0 12px 0 0}iframe{display:block;border:0;background:white}</style><header><b>Тестовый viewport: ${width} × 800 · ${locale}</b><nav>${[1024,1280,1366,1440].map(value=>`<a href="?width=${value}&locale=${locale}">${value} px</a>`).join("")}${["ru","kk","en"].map(value=>`<a href="?width=${width}&locale=${value}">${value}</a>`).join("")}</nav></header><iframe id="review-frame" title="Рабочее пространство ${width} px" width="${width}" height="800" src="/app#workspace/checks"></iframe></html>`);
        return;
      }
      if (url.pathname === "/__frontend-fixtures") {
        if (url.searchParams.get("action") === "finish") jobs.forEach(job => { job.scenario = "success"; job.polls = 3; });
        const selected = url.searchParams.get("scenario");
        if (selected && ["success", "slow", "failed", "reconnect", "outside", "dense", "frames", "unknown-progress"].includes(selected)) { scenario = selected; posts = 0; jobs.clear(); }
        res.setHeader("Content-Type", "text/html; charset=utf-8");
        res.end(`<!doctype html><html lang="ru"><meta charset="utf-8"><title>Frontend fixtures</title><body style="font:16px/1.7 sans-serif;max-width:800px;margin:40px auto"><h1>Тестовые ответы API</h1><p>Только dev. Это не анализ видео и не модель.</p><p>Сценарий: <b>${scenario}</b>. POST загрузки: <b>${posts}</b>. GET статуса: <b>${[...jobs.values()].reduce((n,j)=>n+j.polls,0)}</b>.</p><nav>${["success", "slow", "failed", "reconnect", "outside", "dense", "frames", "unknown-progress"].map(value => `<p><a href="/__frontend-fixtures?scenario=${value}">${value}</a></p>`).join("")}</nav><p><a href="/__frontend-fixtures?action=finish">Завершить существующие задания</a></p><p><a href="/app">Открыть интерфейс</a></p></body></html>`);
        return;
      }
      if (!url.pathname.startsWith("/api/v1/")) { next(); return; }
      const send = (value: unknown, status = 200) => { res.statusCode = status; res.setHeader("Content-Type", "application/json"); res.setHeader("Cache-Control", "no-store"); res.end(JSON.stringify(value)); };
      if (req.headers["x-api-key"] !== "frontend-test-key") { send({ error: "Test key required" }, 401); return; }
      if (url.pathname === "/api/v1/analyze" && req.method === "POST") {
        posts += 1; const id = `fixture-${posts}`; jobs.set(id, { polls: 0, scenario });
        req.on("data", () => {}); req.on("end", () => send({ job_id: id }, 202));
        return;
      }
      const id = decodeURIComponent(url.pathname.split("/").at(-1) || ""); const job = jobs.get(id);
      if (!job || req.method !== "GET") { send({ error: "Test job not found" }, 404); return; }
      job.polls += 1;
      if (job.scenario === "reconnect" && job.polls === 1) { send({ error: "Temporary fixture failure" }, 503); return; }
      if (job.scenario === "slow" || job.scenario === "unknown-progress" || job.polls < 3) { send({ job_id: id, status: "processing", ...(job.scenario === "unknown-progress" ? {} : {progress: Math.min(85, job.polls * 25)}) }); return; }
      if (job.scenario === "failed") { send({ job_id: id, status: "failed", error: "Тестовая ошибка обработки записи" }); return; }
      if (job.scenario === "dense") { send({job_id:id,status:"done",verdict:"violation",violations:Array.from({length:100},(_,i)=>({id:`dense-${i}`,type:`Тестовое событие ${i+1}`,timecode_sec:4,description:`Тестовое описание ${i+1}. Не результат модели.`,evidence_frames:[]}))});return; }
      if (job.scenario === "frames") { send({job_id:id,status:"done",verdict:"violation",violations:[{id:"bad-images",type:"Проверка кадров",timecode_sec:4,description:"Описание события сохранено при ошибках изображений.",evidence_frames:[{timestamp_sec:4,image_base64:Buffer.from(Buffer.from(png,"base64").subarray(0,24)).toString("base64")},{timestamp_sec:4,image_base64:"A".repeat(3*1024*1024)},{timestamp_sec:4,image_base64:png}]}]});return; }
      send({ job_id: id, status: "done", verdict: "violation", violations: [
        { id: "test-event-1", type: "Тестовое событие 1", timecode_sec: job.scenario === "outside" ? 1e9 : 4,
          description: "Тестовое описание первого события. Ответ используется только для проверки интерфейса.", evidence_frames: [{ timestamp_sec: job.scenario === "outside" ? 1e9 : 4, image_base64: png }] },
        { id: "test-event-2", type: "Тестовое событие 2", timecode_sec: 6, description: "Тестовое описание второго события.", evidence_frames: [] },
      ] });
    });
  } };
}
