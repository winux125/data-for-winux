# Forte Vision frontend

Интерфейс Datathon ForteBank: React 19, TypeScript, Vinext/Vite, Tailwind, HeroUI. RU/KK/EN, темы, исходное видео, события, кадры и полные нормативные цитаты. Брендовые ассеты и шрифты локальные.

Рабочий сайт: https://forte26.vercel.app/app. HTTPS сервер: https://154.54.100.194.sslip.io/app.

Интерфейс автоматически получает конфигурацию и ограниченную сессию через `/api/browser/config` и `/api/browser/session`; ключ жюри в frontend не встраивается. Загружается реальный файл, далее опрашивается задание. Демо помечено отдельно. Лимит размера — 10 ГиБ; предельный размер и нагрузка отдельно не подтверждены. Текущий backend и политика результата описаны в [основном README](../README.md).

## Разработка

Node.js 22.13+ и pnpm версии из package.json:

```bash
corepack enable
pnpm install --frozen-lockfile
pnpm dev -- --port 5173
```

```bash
pnpm typecheck
pnpm test
pnpm lint
pnpm build
pnpm start
```

`pnpm start` запускает Node production server на 0.0.0.0:3000. Сессия Sites, ignored `.openai/hosting.json` и Cloudflare bindings не нужны. Production build не подключает тестовые fixtures.

## Браузерные тесты

```bash
pnpm exec playwright install --with-deps chromium webkit
FORTE_FRONTEND_FIXTURES=1 pnpm test:e2e
```

Fixtures синтетические. Для проверки уже запущенного тестового экземпляра задайте `FRONTEND_TEST_URL`; не подключайте fixtures к production API. Реальные видео проверяются через публичные API и UI отдельно.

Dockerfile расположен в корне проекта: [deploy/Dockerfile.frontend](../deploy/Dockerfile.frontend). Команда из родительского каталога: `docker build -f deploy/Dockerfile.frontend -t forte-vision:deployment forte-vision`. Порядок установки и переменные origin: [DEPLOYMENT.md](../docs/DEPLOYMENT.md).
