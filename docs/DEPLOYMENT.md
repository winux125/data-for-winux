# Развёртывание Forte Vision

## Новая установка

Поддерживаемая среда — Linux/systemd, доступная CUDA GPU, Docker, `uv`, Bash и curl. Для текущей VM используется A100 80 GB; другая GPU требует отдельного измерения памяти и времени. Используйте непривилегированного владельца проекта с доступом к Docker и sudo для установки unit-файлов. Путь установки должен быть абсолютным, без пробелов и systemd-спецсимволов.

Клонируйте репозиторий, получите исходный `JEPA-LGBM-FULL.zip` у владельца и выполните из корня:

```bash
export JEPA_ARCHIVE=/absolute/path/JEPA-LGBM-FULL.zip
export HF_HOME="$PWD/models/hf-cache"
bash scripts/bootstrap.sh
```

Скрипт создаёт Python 3.12 окружение, устанавливает закреплённые зависимости/CUDA PyTorch, проверяет пакет JEPA по хэшам, загружает закреплённые revisions Qwen/BGE, проверяет нормативные ресурсы, CUDA и запускает Python-тесты. Интернет нужен на этом этапе. Сам bootstrap не создаёт GPU-инстанс и не включает сервисы. Не запускайте его поверх работающего окружения для обычного обновления исходников.

Имена, revisions, dtype и бюджеты: `config/observer.json`, `config/rag-mvp.json`, `config/detector.json`. Визуальная Qwen хранится в `models/qwen3-vl-8b`, текстовая Qwen и BGE — в `HF_HOME`. Если cache размещён на отдельном диске, экспортируйте один и тот же `HF_HOME` при bootstrap и установке сервисов. На существующей VM cache находится в `/ephemeral/forte-service-models/hf-cache` и сохраняется при переносе структуры.

```bash
export FORTE_PUBLIC_HOST=your-server.example
export FORTE_SITE_ORIGIN=https://your-site.example
bash scripts/install_services.sh
```

Имя сервера передаётся без `https://`, порта и пути. У домена должен быть корректный DNS на VM; для HTTPS доступны порты 80/443. `FORTE_SITE_ORIGIN` можно не задавать при сайте на том же домене. Установка выполняет preflight, сохраняет существующий ключ либо генерирует новый, настраивает browser origin, рендерит systemd/Caddy под фактический каталог и пользователя, собирает frontend из lockfile и запускает сервисы.

Шаблоны в `deploy/` не копируют вручную в `/etc/systemd/system`: в них есть placeholders. Готовые файлы создаёт `scripts/render_deployment.py` в `data/deploy/`. Worker получает `PrivateNetwork=true` и offline-переменные. Caddy читает `data/deploy/Caddyfile`.

`secrets/service.env` имеет права 600. Ключ жюри известен только владельцу; не помещайте его в Git, Docker build args или frontend. API, worker, Caddy и сайт — отдельные процессы; для ожидания моделей проверяйте `/readyz`, не только `/healthz`.

## Проверки перед использованием

```bash
.venv/bin/python scripts/verify_runtime.py
.venv/bin/python scripts/verify_runtime.py --models --cuda
.venv/bin/python -m pytest tests legal_rag/tests -q
curl --fail "https://$FORTE_PUBLIC_HOST/healthz"
curl --fail "https://$FORTE_PUBLIC_HOST/readyz"
.venv/bin/python scripts/public_smoke.py /path/to/negative.mov /path/to/positive.mov \
  --base "https://$FORTE_PUBLIC_HOST"
```

Preflight без `--models` работает без GPU и весов: проверяет загрузку именно `legal_rag/` из этого клона, карточки, нормативные хэши и структуру. Он не доказывает готовность inference. Проверка с флагами дополнительно проверяет закреплённый detector, наличие локальных моделей и CUDA. Полные API-ответы smoke-клиент сохраняет в игнорируемый `data/public-smoke/`, в консоль выводит только техническую сводку. При обрыве GET повторяется опрос того же job_id, новое задание не создаётся. CLI завершится ошибкой при failed/тайм-ауте.

## Сборка frontend отдельно

Из корня проекта:

```bash
docker build -f deploy/Dockerfile.frontend -t forte-vision:deployment forte-vision
```

Это единственный Dockerfile рабочего frontend. Он устанавливает зависимости по `pnpm-lock.yaml`, выполняет typecheck, unit-тесты, lint и production build. Runtime запускается от `node`; внешний порт в systemd опубликован только на 127.0.0.1:3000. Старый образ `forte-vision:deployment` не нужен как базовый слой.

## Обновление существующего сервера

Сначала получите актуальную ветку и сохраните резервную копию исходников, unit-файлов и тега frontend image. Не копируйте в Git `models/`, `data/`, `secrets/` или веса JEPA. Проверьте, что очередь пуста, чтобы не прерывать задания.

Проверьте новый исходный архив в отдельном каталоге с установленными зависимостями. Соберите новый frontend image отдельным тегом, проверьте Python-тесты и `/app` на временном локальном порту. Только затем обновляйте рабочие исходники, рендерите конфигурацию с прежним `HF_HOME`, перезапускайте сервисы и проверяйте ready + положительный/отрицательный API-сценарии. При сбое восстановите сохранённые исходники, units и image tag.

Исходный архив: `.venv/bin/python scripts/package_source.py`. Он включает полный код, нормативные ресурсы и лицензии; исключает веса, секреты, загруженные записи, локальные базы, результаты, зависимости и build-выходы. Чистый клон/исходный архив содержит всё необходимое для проверок RAG без отдельного RAG ZIP. Для настоящего inference дополнительно нужны веса и конфигурация сервера.

## Диагностика

```bash
systemctl status forte-api forte-worker forte-frontend caddy
journalctl -u forte-worker -n 100 --no-pager
docker logs --tail 100 forte-vision
.venv/bin/python scripts/diagnose_legal.py
```

Сырые наблюдения и кадры не публикуйте в общих логах или Git. Ошибка API не должна превращаться в `no_violation`. Сохраняйте исходный job_id для диагностики.

Caddy пишет HTTP-статус, длительность, размер запроса и ответа в `data/logs/http-access.json`. Заголовки запроса/ответа, адрес клиента и тела запросов исключены. Ротация ограничена файлами по 10 МиБ, тремя архивами и сроком 24 часа. Эти журналы остаются приватными и не входят в Git.

При тайм-ауте различайте соединение/TLS, загрузку файла и обработку модели. Сравните клиентские `time_connect`, `time_appconnect`, `time_total` из curl с `duration` в журнале Caddy. Быстрый GET на сервере при медленном клиентском запросе сам по себе не доказывает ошибку модели. После получения `job_id` повторяйте GET того же задания. При потере ответа POST не повторяйте загрузку вслепую: сервер мог уже принять файл.

18.10.2026 повторный положительный прогон через прямой API получил HTTP 202 примерно за 10 секунд и завершился `done/violation` за 70,4 секунды клиента (57,6 секунды inference). Проверены три события и шесть JPEG. До него были тайм-ауты соединения и чтения ответа POST; этот успешный повтор не доказывает, что сетевая проблема устранена. Горячая перезагрузка Caddy включила диагностику, не меняя модели или API-контракт.

Для текущего сабмита предпочтительный API base URL — `https://forte26.vercel.app`, прямой адрес VM остаётся резервным. Используется уже развёрнутый внешний rewrite из `deploy/vercel/vercel.json`, без Vercel Function и без inference у Vercel. Ключ и `/api/v1/*` не меняются. После явного разрешения владельца выполнен один положительный прогон через этот прокси: job `1fce10abbbff443d`, POST 202 за 5,6 с, `done/violation` за 61 с, три события и шесть проверенных JPEG; ошибок клиента в этом прогоне нет. Четыре лёгких запроса и авторизация также прошли. Синтетический файл 30 МиБ дошёл до API и получил ожидаемый 415 из-за расширения `.txt`; это проверяет передачу тела, а не анализ видео такого размера. Максимальный размер прокси этим не установлен. HTTP-заголовки/тела в диагностических логах не сохраняются. Причина прежних сбоев прямого сетевого пути не установлена; изменение точки входа не означает, что этот путь исправлен.

## Проверка публичного UI

После установки frontend-зависимостей и браузеров (`pnpm exec playwright install --with-deps chromium webkit` из forte-vision), из корня проекта:

```bash
node scripts/browser_integrated_qa.cjs
node scripts/browser_api_smoke.cjs /absolute/path/to/negative.mov
```

Первый клиент проверяет языки и размеры экрана; второй загружает реальный отрицательный пример через сайт и ждёт no_violation. Адрес задаётся FORTE_PUBLIC_URL, по умолчанию для smoke — действующий сайт. Модули берутся из forte-vision/node_modules; FORTE_FRONTEND_DIR нужен только при ином расположении frontend. Результаты приватны в data/.
