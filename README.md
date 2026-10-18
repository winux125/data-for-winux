# Forte Vision

Сервис проверки видеозаписей кассовых операций · Datathon 26, ForteBank.

[Сайт](https://forte26.vercel.app/app) · [API](https://forte26.vercel.app/docs) · [Развёртывание](docs/DEPLOYMENT.md) · [RAG и Qwen](docs/LEGAL_RAG_QWEN_README.md)

## Рабочая схема

```text
MOV → JEPA + LightGBM
    ├─ отрицательный класс → no_violation, без Qwen/RAG
    └─ положительный класс → исходные кадры → Qwen3-VL-8B → структурированные факты
       → BM25 + BGE-M3 / RRF → полный нормативный контекст → Qwen3-VL-4B
       → violations: действие, таймкод, JPEG, объяснение и источник
```

Все модели исполняются на сервере. GPU worker работает без сети. Аудио и идентификация лиц не используются. Поиск и генерация реализованы в одном пакете `legal_rag/`, без накладываемых при запуске патчей и без зависимости от исходного ZIP RAG. Qdrant и reranker не используются.

Режим MVP — `possible_indications`: результат показывает визуальные признаки с нормативным контекстом для проверки человеком. Неизвестные условия сохраняются, карточки не получают фиктивной человеческой подписи. Подробности — [политика MVP](docs/RAG_MVP_POLICY.md).

## Структура

```text
backend/                      API, очередь, видео, Qwen observer и связка моделей
legal_rag/                    единственная рабочая реализация RAG
  data/                       карточки, словарь и конфигурация; входят в Git
  resources/                  54 нормативных снимка, метаданные и tokenizer
  tests/                      проверки RAG
model_packages/jepa_lgbm/      неизменённый пакет активного детектора
  weights/                    веса из ZIP владельца; вне Git
forte-vision/                 интерфейс RU / KK / EN, темы, локальные ассеты
config/                       конфигурации сервиса и моделей
deploy/                       Dockerfile и шаблоны systemd/Caddy
scripts/                      установка, preflight, тестовый клиент, упаковка
tests/                        backend и установка из чистого дерева
docs/                         инструкции и датированные отчёты
models/                       Qwen/BGE и cache; вне Git
data/                         задания, индекс, результаты; вне Git
secrets/                      ключ и переменные окружения; вне Git
```

Прежние SVM-пакет, исходный RAG и overlays удалены из рабочего дерева. Их история сохранена в Git, а перед переносом сделаны отдельные резервные копии. Runtime не использует старые каталоги и не откатывается на них автоматически.

## Установка на GPU-сервер

Нужны Linux с systemd, NVIDIA/CUDA, Docker, `uv`, доступ к публичным весам при установке и ZIP `JEPA-LGBM-FULL.zip` от владельца. Код, нормативная база и исходники детектора находятся в Git. Тяжёлые веса, ключи и конкурсные видео туда не входят.

```bash
git clone https://github.com/winux125/datathon-forte.git
cd datathon-forte
export JEPA_ARCHIVE=/absolute/path/JEPA-LGBM-FULL.zip
bash scripts/bootstrap.sh
export FORTE_PUBLIC_HOST=your-server.example
export FORTE_SITE_ORIGIN=https://your-server.example
bash scripts/install_services.sh
```

Bootstrap предназначен для новой установки. На существующем сервере не пересоздавайте `.venv` и не меняйте веса без необходимости. Порядок обновления, настройка cache и проверка готовности — [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## API жюри

```bash
export FORTE_API_URL=https://forte26.vercel.app
# FORTE_API_KEY задаётся владельцем отдельно.
curl -X POST "$FORTE_API_URL/api/v1/analyze" \
  -H "X-API-Key: $FORTE_API_KEY" -F "file=@video.mov"
curl "$FORTE_API_URL/api/v1/jobs/JOB_ID" -H "X-API-Key: $FORTE_API_KEY"
```

POST возвращает HTTP 202, `job_id`, `status=processing`. GET — `processing`, `done` или `failed`. При `done`: `verdict=violation|no_violation` и список `violations`. Каждое событие содержит `type`, `timecode_sec`, `description`, 1–3 исходных JPEG/base64 и полный нормативный источник в `rule`; ссылка также включена в обязательное описание. Ошибка обработки не подменяется чистым вердиктом.

Для сабмита используется `https://forte26.vercel.app`: существующий Vercel rewrite передаёт HTTP на ту же NVIDIA VM; модели остаются локальными. Прямой адрес VM `https://154.54.100.194.sslip.io` сохранён как резервный с теми же путями и ключом. После тайм-аутов прямого соединения проверен полный положительный прогон через Vercel: POST 202 за 5,6 с, конечный результат за 61 с, три события и шесть валидных JPEG. Отдельно проверена передача синтетического файла 30 МиБ. Это ограниченные проверки доступности, не гарантия отсутствия будущих сетевых сбоев или поддержки через прокси предельных 10 ГиБ.

Сайт подключается к API автоматически через ограниченную браузерную сессию. Ключ жюри не передаётся в код frontend. При размещении отдельно задайте `FORTE_SITE_ORIGIN`; Vercel rewrite находится в `deploy/vercel/`.

Лимиты сервиса: до 10 ГиБ, до 180 секунд, до 4096×2160. Дедлайн API жюри — 285 секунд от приёма задания. Предельный размер и параллельная нагрузка отдельно не подтверждены. Одна GPU обслуживает задания последовательно.

## Проверки

Текущая развёрнутая сборка после переноса: **85aa3f138fadb7fb**. Проверены 210 Python, 108 frontend unit, 74 browser E2E, пять реальных внешних API-заданий и загрузка через публичный сайт. Сетевые повторы и ограничения — в [отчёте переноса](docs/REPOSITORY_LAYOUT_2026-10-18.md).

```bash
.venv/bin/python scripts/verify_runtime.py
.venv/bin/python scripts/verify_runtime.py --models --cuda
.venv/bin/python -m pytest tests legal_rag/tests -q
cd forte-vision
corepack enable
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test
pnpm lint
pnpm build
pnpm start
```

Frontend — самостоятельный Node-сервер. Сборка не требует `.openai/hosting.json`, сессии Sites, Cloudflare или заранее собранного образа Forte. Команды frontend E2E — в [его README](forte-vision/README.md).

До переноса структуры успешно проверены пять внешних API-запусков: [отчёт](docs/JURY_API_FIVE_RUNS_2026-10-18.md). Результаты повторной проверки новой структуры фиксируются в [отчёте переноса](docs/REPOSITORY_LAYOUT_2026-10-18.md). Прогоны на обучающих видео являются проверкой интеграции, а не независимыми F1/precision/recall.

Исходные [handoff](docs/HANDOFF.md) и [аудит](docs/AUDIT.md) — исторические документы. Для текущих путей и запуска используйте этот README и DEPLOYMENT.md.

Для локальной CPU-проверки в отдельной копии проекта достаточно Python 3.11+ и requirements-test.txt. Qwen и веса не загружаются. Например, Windows:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.venv\Scripts\python.exe scripts/verify_runtime.py
.venv\Scripts\python.exe -m pytest tests legal_rag/tests -q
```

Один Torch-зависимый тест в CPU-профиле пропускается. Этот профиль проверяет RAG и контракты, но не реальное восприятие Qwen.
