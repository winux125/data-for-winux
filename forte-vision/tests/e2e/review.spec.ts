import { test, expect, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { auditTextContrast } from "../support/contrast";
import { THEME_KEY } from "../../lib/theme";
const recording = fileURLToPath(new URL("./fixtures/review.mov", import.meta.url));
const done = (time = 4) => ({ job_id: "browser-job", status: "done", verdict: "violation", violations: [
  { id: "e1", type: "Тестовое событие 1", timecode_sec: time, description: "Первое тестовое описание.", evidence_frames: [] },
  { id: "e2", type: "Тестовое событие 2", timecode_sec: 6, description: "Второе тестовое описание.", evidence_frames: [] },
] });
test.beforeEach(async ({page}) => {
  await page.route("**/api/browser/config", route=>route.fulfill({json:{base_url:"",max_upload_bytes:10*1024**3}}));
  await page.route("**/api/browser/session", route=>route.fulfill({json:{token:"frontend-scoped-test-session",expires_at:Date.now()/1000+86400}}));
});
async function configure(page: Page) {
  await expect(page.locator(".fv-mode-pill")).toHaveAttribute("data-connection","connected");
  await expect(page.getByRole("button",{name:"Подключение API",exact:true})).toHaveCount(0);
}
async function upload(page: Page) {
  await page.getByLabel("Выбрать видеозапись", { exact: true }).setInputFiles(recording);
  await page.getByRole("button", { name: "Начать проверку", exact: true }).click();
}
async function start(page: Page) { await page.goto("/app"); await configure(page); await upload(page); }
async function clickVisibleCheckbox(page: Page, name: string) {
  const checkbox = page.getByRole("checkbox", { name, exact: true });
  // React Aria intentionally clips the native input. Users click its visible label.
  await checkbox.locator("xpath=ancestor::label[1]").click();
  await expect(checkbox).toBeChecked();
}

test("upload → processing → event → bounded clip → full video → back", async ({ page }) => {
  let posts = 0; let polls = 0;
  await page.route("**/api/browser/analyze", route => { posts++; return route.fulfill({ json: { job_id: "browser-job" }, status: 202 }); });
  await page.route("**/api/browser/jobs/browser-job", route => route.fulfill({ json: ++polls < 2 ? { job_id: "browser-job", status: "processing", progress: 47 } : done() }));
  await start(page);
  await expect(page.getByText("Проверка завершена", { exact: true })).toHaveCount(0);
  await expect(page.locator("#review-heading")).toHaveText("Видеозапись");
  await page.getByRole("button", { name: /Событие 1: Тестовое событие 1/ }).click();
  await expect(page.locator("#review-heading")).toHaveText("Тестовое событие 1");
  await expect(page.getByText("Первое тестовое описание.", { exact: true })).toHaveCount(1);
  await page.getByRole("button", { name: "Смотреть фрагмент", exact: true }).click();
  const video = page.locator(".fv-video-stage video");
  await expect.poll(() => video.evaluate((node: HTMLVideoElement) => node.duration)).toBeGreaterThan(11);
  await video.evaluate((node: HTMLVideoElement) => { node.currentTime = 6.9; void node.play(); });
  await expect.poll(() => video.evaluate((node: HTMLVideoElement) => node.paused)).toBe(true);
  expect(await video.evaluate((node: HTMLVideoElement) => node.currentTime)).toBeCloseTo(7, 0);
  await page.getByRole("button", { name: "Вся запись", exact: true }).click();
  await video.evaluate((node: HTMLVideoElement) => { node.currentTime = 8; });
  await page.getByRole("button", { name: /Событие 2: Тестовое событие 2/ }).click();
  await page.getByRole("button", { name: "К видеозаписи", exact: true }).click();
  await expect.poll(() => video.evaluate((node: HTMLVideoElement) => node.currentTime)).toBeCloseTo(8, 0);
  expect(posts).toBe(1);
});

test("active job remains in history; pause and resume never upload twice", async ({ page }) => {
  let posts = 0; let finish = false;
  await page.route("**/api/browser/analyze", route => { posts++; return route.fulfill({ json: { job_id: "browser-job" } }); });
  await page.route("**/api/browser/jobs/browser-job", route => route.fulfill({ json: finish ? done() : { job_id: "browser-job", status: "processing", progress: 47 } }));
  await start(page);
  await expect(page.locator("#job-heading")).toHaveText("В обработке");
  await page.getByRole("button", { name: /^Проверки\s*\d/ }).click();
  await expect(page.locator(".checks-table-desktop").getByText("В обработке", { exact: true })).toBeVisible();
  await page.locator(".fv-active-job").getByRole("button", { name: "Открыть проверку", exact: true }).click();
  await page.getByRole("button", { name: "Отменить ожидание", exact: true }).click();
  await expect(page.locator("#job-heading")).toHaveText("Ожидание приостановлено");
  finish = true;
  await page.getByRole("button", { name: "Продолжить ожидание", exact: true }).click();
  await expect(page.locator("#review-heading")).toHaveText("Видеозапись");
  expect(posts).toBe(1);
});

test("one temporary GET failure recovers without a new POST", async ({ page }) => {
  let posts = 0; let polls = 0;
  await page.route("**/api/browser/analyze", route => { posts++; return route.fulfill({ json: { job_id: "browser-job" } }); });
  await page.route("**/api/browser/jobs/browser-job", route => ++polls === 1 ? route.abort("failed") : route.fulfill({ json: done() }));
  await start(page);
  await expect(page.locator("#job-heading")).toHaveText("Восстановление связи");
  await expect(page.locator("#review-heading")).toHaveText("Видеозапись");
  expect(posts).toBe(1); expect(polls).toBe(2);
});

test("failed server job has an error screen and no completed verdict or export", async ({ page }) => {
  await page.route("**/api/browser/analyze", route => route.fulfill({ json: { job_id: "browser-job" } }));
  await page.route("**/api/browser/jobs/browser-job", route => route.fulfill({ json: { job_id: "browser-job", status: "failed", error: "Ошибка тестового задания" } }));
  await start(page);
  await expect(page.locator("#job-heading")).toHaveText("Ошибка проверки");
  await expect(page.getByRole("button", { name: "Скачать результат", exact: true })).toHaveCount(0);
  await expect(page.getByText("Проверка завершена", { exact: true })).toHaveCount(0);
});

test("out-of-range time is visible but never becomes an end-of-video clip", async ({ page }) => {
  await page.route("**/api/browser/analyze", route => route.fulfill({ json: { job_id: "browser-job" } }));
  await page.route("**/api/browser/jobs/browser-job", route => route.fulfill({ json: done(1e9) }));
  await start(page);
  await expect(page.locator("#review-heading")).toHaveText("Видеозапись");
  await expect(page.locator(".fv-unplaced-events").getByText("Вне границ записи", { exact: false })).toBeVisible();
  await page.locator(".fv-unplaced-events").getByRole("button").click();
  await expect(page.getByRole("button", { name: "Смотреть фрагмент", exact: true })).toBeDisabled();
  await expect(page.getByText("Таймкод события вне границ записи.", { exact: false })).toBeVisible();
});

test("reload restores job metadata without a key or blob, then GET-only resume works", async ({ page }) => {
  let posts = 0; let finish = false;
  await page.route("**/api/browser/analyze", route => { posts++; return route.fulfill({ json: { job_id: "browser-job" } }); });
  await page.route("**/api/browser/jobs/browser-job", route => route.fulfill({ json: finish ? done() : { job_id: "browser-job", status: "processing" } }));
  await start(page);
  await expect(page.locator("#job-heading")).toHaveText("В обработке");
  await page.getByRole("button", { name: "Отменить ожидание", exact: true }).click();
  await expect(page.locator("#job-heading")).toHaveText("Ожидание приостановлено");
  const checkpoint = await page.evaluate(() => sessionStorage.getItem("forte-job-checkpoints-v1"));
  expect(checkpoint).toContain("browser-job"); expect(checkpoint).not.toContain("frontend-test-key"); expect(checkpoint).not.toContain("blob:");
  await page.reload(); await configure(page);
  // Reload preserves the review hash. Open history before selecting the restored row.
  await page.locator(".fv-main-nav").getByRole("button", { name: /^Проверки\s*\d/ }).click();
  await page.locator(".checks-table-desktop").getByRole("button", { name: "review.mov", exact: true }).click();
  finish = true;
  await page.getByRole("button", { name: "Продолжить ожидание", exact: true }).click();
  await expect(page.locator("#review-heading")).toHaveText("Видеозапись");
  await expect(page.getByText("Исходная запись недоступна после перезагрузки.", { exact: false })).toBeVisible();
  await page.getByLabel("Добавить исходную запись").setInputFiles(recording);
  await expect.poll(() => page.locator(".fv-video-stage video").evaluate((node: HTMLVideoElement) => node.duration)).toBeGreaterThan(11);
  expect(posts).toBe(1);
});

for (const width of [375, 768, 1366]) test(`history and sticky header at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 }); await page.goto("/app");
  await page.waitForLoadState("networkidle");
  await expect(page.locator(".fv-topbar")).toHaveCSS("position", "sticky");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  if (width <= 640) await expect(page.locator(".checks-table-mobile")).toBeVisible();
  else {
    const badge = page.locator(".checks-table-desktop .check-status--violation").first();
    await expect(badge).toBeVisible();
    // WebKit can replace the streamed SSR collection during hydration. Require a
    // connected, laid-out badge rather than measuring a detached intermediate node.
    await expect.poll(async () => badge.evaluate(node => {
      const height = node.getBoundingClientRect().height;
      const line = parseFloat(getComputedStyle(node).lineHeight);
      return node.isConnected && height > 0 && Number.isFinite(line) ? height / (line * 2 + 10) : Infinity;
    })).toBeLessThanOrEqual(1);
  }
});

test("dense timeline opens all 100 events without growing to 100 rows", async ({ page }) => {
  const violations=Array.from({length:100},(_,i)=>({...done().violations[0],id:`e${i}`,type:`Событие теста ${i+1}`}));
  await page.route("**/api/browser/analyze",route=>route.fulfill({json:{job_id:"browser-job"}}));
  await page.route("**/api/browser/jobs/browser-job",route=>route.fulfill({json:{...done(),violations}}));
  await start(page);
  const group=page.getByRole("button",{name:/Группа: 100 событий/});await expect(group).toBeVisible();
  expect(await page.locator(".fv-timeline-track").evaluate(n=>n.getBoundingClientRect().height)).toBeLessThanOrEqual(144);
  await group.click();await expect(page.locator(".fv-timeline-list li")).toHaveCount(20);
  for(let i=0;i<4;i++) await page.locator(".fv-event-list-pages").getByRole("button",{name:"Следующее",exact:true}).click();
  await page.locator(".fv-timeline-list").getByRole("button",{name:/100 Событие теста 100/}).click();
  await expect(page.locator("#review-heading")).toHaveText("Событие теста 100");
});

test("unsupported MOV replaces playback with access to evidence", async ({ page }) => {
  await page.route("**/api/browser/analyze",route=>route.fulfill({json:{job_id:"browser-job"}}));
  await page.route("**/api/browser/jobs/browser-job",route=>route.fulfill({json:done()}));
  await page.goto("/app");await configure(page);
  // A valid codec can be supported by one browser and unsupported by another.
  // Deliberately corrupt synthetic bytes exercise the decoder fallback on both.
  await page.getByLabel("Выбрать видеозапись",{exact:true}).setInputFiles({name:"unsupported.mov",mimeType:"video/quicktime",buffer:Buffer.from("invalid synthetic MOV for decoder fallback")});
  await page.getByRole("button",{name:"Начать проверку",exact:true}).click();
  await expect(page.getByText("Видео недоступно для воспроизведения",{exact:true})).toBeVisible();
  await expect(page.locator(".fv-video-stage video")).not.toHaveAttribute("controls","");
  await page.getByRole("button",{name:"К кадрам и описанию",exact:true}).click();
  await expect(page.getByText("Первое тестовое описание.",{exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Смотреть фрагмент",exact:true})).toHaveCount(0);
  await expect(page.locator("#event-frames-title")).toBeFocused();
});

test("decoding a damaged frame keeps the description and disables enlargement", async ({ page }) => {
  const invalid="iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB";
  await page.route("**/api/browser/analyze",route=>route.fulfill({json:{job_id:"browser-job"}}));
  await page.route("**/api/browser/jobs/browser-job",route=>route.fulfill({json:{...done(),violations:[{...done().violations[0],evidence_frames:[{timestamp_sec:4,image_base64:invalid}]}]}}));
  await start(page);await page.getByRole("button",{name:/Событие 1: Тестовое событие 1/}).click();
  await expect(page.getByText("Не удалось декодировать кадр. Описание события сохранено.",{exact:true})).toBeVisible();
  await expect(page.locator(".fv-frame-card > button")).toBeDisabled();
  await expect(page.getByText("Первое тестовое описание.",{exact:true})).toBeVisible();
});

test("server progress updates in detail and in global status, then becomes indeterminate when absent", async ({ page }) => {
  let progress:number|undefined=47;
  await page.route("**/api/browser/analyze",route=>route.fulfill({json:{job_id:"browser-job"}}));
  await page.route("**/api/browser/jobs/browser-job",route=>route.fulfill({json:{job_id:"browser-job",status:"processing",progress}}));
  await start(page);await expect(page.getByRole("progressbar",{name:"Обработка",exact:true})).toHaveAttribute("aria-valuenow","47");
  await page.getByRole("button",{name:"Правила и источники",exact:true}).click();
  await expect(page.locator(".fv-active-job").getByText("Обработано 47%",{exact:true})).toBeVisible();
  progress=undefined;
  await expect(page.locator(".fv-active-job").getByRole("progressbar")).not.toHaveAttribute("aria-valuenow",/./);
  await page.locator(".fv-active-job").getByRole("button",{name:"Отменить ожидание",exact:true}).click();
});

test("browser connects automatically without asking for a jury key", async ({page})=>{
  let requests=0;
  await page.route("**/api/browser/analyze",route=>{requests++;return route.fulfill({json:{job_id:"browser-job"}});});
  await page.route("**/api/browser/jobs/browser-job",route=>{requests++;return route.fulfill({json:done()});});
  await page.goto("/app");await configure(page);expect(requests).toBe(0);
  await expect(page.getByLabel("API-ключ")).toHaveCount(0);
  await upload(page);await expect(page.locator("#review-heading")).toHaveText("Видеозапись");
  await expect(page.locator(".fv-mode-pill")).toHaveAttribute("data-connection","connected");
});

test("browser back and forward reproduce section, recording and event navigation", async ({ page }) => {
  await page.goto("/app");await page.getByRole("button",{name:/^Проверки 3$/}).click();
  await page.locator(".checks-table-desktop").getByRole("button",{name:"Проверка кассовой операции.mov",exact:true}).click();
  await page.getByRole("button",{name:/Событие 1: Рабочая зона/}).click();await page.getByRole("button",{name:"Следующее",exact:true}).click();
  await expect(page).toHaveURL(/#workspace\/checks\/DEMO-001\/event\/2$/);
  await page.goBack();await expect(page.locator("#review-heading")).toHaveText("Рабочая зона оставлена без наблюдения");
  await page.goBack();await expect(page.locator("#review-heading")).toHaveText("Видеозапись");
  await page.goBack();await expect(page.locator(".fv-checks-page-heading h1")).toHaveText("Проверки");
  await page.goForward();await expect(page.locator("#review-heading")).toHaveText("Видеозапись");
  await page.goForward();await expect(page.locator("#review-heading")).toHaveText("Рабочая зона оставлена без наблюдения");
});

test("Undo survives section navigation and restores the original local video", async ({ page }) => {
  await page.route("**/api/browser/analyze",route=>route.fulfill({json:{job_id:"browser-job"}}));await page.route("**/api/browser/jobs/browser-job",route=>route.fulfill({json:done()}));
  await start(page);await expect(page.locator("#review-heading")).toHaveText("Видеозапись");await page.getByRole("button",{name:"К проверкам",exact:true}).click();
  await page.locator(".checks-table-desktop").getByRole("button",{name:"Удалить проверку review.mov",exact:true}).click();
  await expect(page.locator(".checks-table-desktop").getByRole("button",{name:"review.mov",exact:true})).toHaveCount(0);
  await page.getByRole("button",{name:"Правила и источники",exact:true}).click();await page.getByRole("button",{name:"Отменить удаление",exact:true}).click();
  await page.getByRole("button",{name:/^Проверки 4$/}).click();await page.locator(".checks-table-desktop").getByRole("button",{name:"review.mov",exact:true}).click();
  await expect.poll(()=>page.locator(".fv-video-stage video").evaluate((node:HTMLVideoElement)=>node.duration)).toBeGreaterThan(11);
});

test("an expired deletion has no Undo, and an unavailable result URL is explicit", async ({ page }) => {
  await page.goto("/app#workspace/checks/DEMO-001");await expect(page.locator("#review-heading")).toHaveText("Видеозапись");await page.getByRole("button",{name:"К проверкам",exact:true}).click();
  await page.locator(".checks-table-desktop").getByRole("button",{name:"Удалить проверку Проверка кассовой операции.mov",exact:true}).click();
  await expect(page.getByRole("button",{name:"Отменить удаление",exact:true})).toBeVisible();
  await expect(page.getByRole("button",{name:"Отменить удаление",exact:true})).toHaveCount(0,{timeout:12000});
  await page.goBack();await expect(page.getByRole("heading",{name:"Проверка недоступна в этом сеансе",exact:true})).toBeVisible();
});

test("keyboard upload has one visible target, a working skip link, and semantic current navigation", async ({ page }) => {
  await page.goto("/app");
  await page.waitForLoadState("networkidle");
  const nativeInput = page.locator('input[type="file"]');
  await expect(nativeInput).toHaveAttribute("hidden", "");
  await expect(nativeInput).toHaveAttribute("tabindex", "-1");
  const uploadButton = page.getByRole("button", { name: "Загрузить видео: нажмите или перетащите файл", exact: true });
  await uploadButton.focus();
  const chooser = page.waitForEvent("filechooser");
  await page.keyboard.press("Space");
  await (await chooser).setFiles([]);
  await expect(uploadButton).toBeFocused();
  await page.keyboard.press("Tab");
  expect(await page.evaluate(() => document.activeElement?.matches('input[type="file"]'))).toBe(false);
  const skip = page.getByRole("link", { name: "К содержимому", exact: true });
  await skip.focus(); await page.keyboard.press("Enter");
  await expect(page.locator("#main")).toBeFocused();
  await page.getByRole("button", { name: "Правила и источники", exact: true }).click();
  await expect(page.locator('.fv-main-nav [aria-current="page"]')).toHaveCount(1);
  await expect(page.locator('.fv-main-nav [aria-current="page"]')).toHaveText("Правила и источники");
  await expect(page.locator("#main h1")).toBeFocused();
});

for (const copy of [
  { locale: "ru", open: "Открыть сервис", overview: "Обзор", checks: "Проверки", selectAll: "Выбрать все видимые проверки", announcement: "3" },
  { locale: "kk", open: "Сервисті ашу", overview: "Шолу", checks: "Тексерулер", selectAll: "Көрінетін барлық тексеруді таңдау", announcement: "3 элемент таңдалды." },
  { locale: "en", open: "Open service", overview: "Overview", checks: "Checks", selectAll: "Select all visible checks", announcement: "3 items selected." },
]) test(`shared controls and current section follow ${copy.locale}`, async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: "forte-locale", value: copy.locale, url: baseURL! }]);
  await page.goto("/privacy");
  await expect(page.locator("html")).toHaveAttribute("lang", copy.locale);
  await expect(page.getByRole("link", { name: copy.open, exact: true })).toBeVisible();
  await page.goto("/app");
  await expect(page.locator('.fv-main-nav [aria-current="page"]')).toHaveText(copy.overview);
  await page.locator(".fv-main-nav").getByRole("button", { name: new RegExp(`^${copy.checks}\\s*3$`) }).click();
  await expect(page.locator('.fv-main-nav [aria-current="page"]')).toHaveText(new RegExp(copy.checks));
  await expect(page.locator("#main h1")).toBeFocused();
  await clickVisibleCheckbox(page, copy.selectAll);
  await expect(page.getByRole("log").filter({ hasText: copy.announcement })).toHaveCount(1);
});

// Real browser viewports, rather than changing the width of a single container.
for (const locale of ["ru", "kk", "en"]) for (const width of [1024, 1280, 1366, 1440]) {
  test(`laptop warning wraps without clipping: ${locale} at ${width}px`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: "forte-locale", value: locale, url: baseURL! }]);
    await page.setViewportSize({ width, height: 800 });
    await page.goto("/app#workspace/checks");
    await expect(page.locator("#main h1")).toHaveText(locale === "ru" ? "Проверки" : locale === "kk" ? "Тексерулер" : "Checks");
    await page.evaluate(() => document.fonts.ready);
    await expect(page.locator(".checks-table-desktop")).toBeVisible();
    const column = await page.locator(".checks-table-content thead th:nth-child(2)").boundingBox();
    expect(column!.width).toBeCloseTo(220, 0);
    const warnings = await page.locator(".checks-table-desktop .check-status").evaluateAll(nodes => nodes.map(element => {
      const style = getComputedStyle(element);
      return { lines: Math.max(1, Math.round((element.getBoundingClientRect().height - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)) / parseFloat(style.lineHeight))), clipped: element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1 };
    }));
    for (const warning of warnings) { expect(warning.lines).toBeLessThanOrEqual(2); expect(warning.clipped).toBe(false); }
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false);
  });
}


for (const theme of ["light", "dark"]) for (const route of ["/app#workspace/checks", "/app#workspace/overview"]) {
  test(`secondary text contrast: ${theme} ${route}`, async ({ page, context, baseURL }) => {
    await context.addCookies([{ name: "forte-locale", value: "en", url: baseURL! }]);
    await page.addInitScript(({ key, mode }) => localStorage.setItem(key, mode), { key: THEME_KEY, mode: theme });
    await page.goto(route);
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    await expect(page.locator(".fv-history-section")).toHaveCSS("background-color", theme === "dark" ? "rgb(28, 22, 30)" : "rgb(255, 255, 255)");
    await page.evaluate(() => document.fonts.ready);
    const audit = await page.evaluate(auditTextContrast);
    expect(audit.checked).toBeGreaterThan(30);
    expect(audit.failures).toEqual([]);
    await clickVisibleCheckbox(page, "Select all visible checks");
    const selectedAudit = await page.evaluate(auditTextContrast);
    expect(selectedAudit.failures).toEqual([]);
  });
}
