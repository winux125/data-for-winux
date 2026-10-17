# Handoff — Forte Vision / Datathon 26

Состояние на 18 октября 2026, около 03:15 UTC+5. Этот документ актуальнее README и старого AUDIT. Работа остановлена по просьбе владельца для передачи другому разработчику. **Сервис развёрнут, но готовность выдачи положительных результатов и соблюдение 5 минут пока не достигнуты.**

## 1. Доступы и адреса

Все два NVIDIA API-ключа и ключ API жюри собраны в **`../secrets/HANDOFF_CREDENTIALS.env`**. Это локальный приватный файл, исключённый из Git и production-пакета. В публичные документы и JS ключи не вставлять.

| Назначение | Значение |
|---|---|
| Короткий интерфейс | https://forte26.vercel.app/app |
| Главная | https://forte26.vercel.app/ |
| Прямой интерфейс | https://154.54.100.194.sslip.io/app |
| API origin | https://154.54.100.194.sslip.io |
| Отправка жюри | POST `/api/v1/analyze`, multipart поле `file`, заголовок `X-API-Key` |
| Результат жюри | GET `/api/v1/jobs/{job_id}`, тот же заголовок |
| OpenAPI / HTTP / модели | `/docs`, `/healthz`, `/readyz` |
| VM | `forte-vision-50`, ID `e38mv57ad` |
| SSH | `shadeform`, alias `forte-vision-50`, passwordless sudo |
| Каталог сервера | `/home/shadeform/forte-service` |
| GPU | A100 SXM4 80 GB, 160 GB RAM, диск около 984 GB |
| NVIDIA тип | `massedcompute_A100_sxm4_80G_DGX` |
| Стоимость при создании | $1.656/час; текущий остаток кредитов не проверен |
| Организация целевого $50 аккаунта | `org-3Jij86rSyl9s5ZnIslMn9mnRjDV` |
| Vercel team / project | `winux125s-projects` / `forte26` |
| Dashboard | https://vercel.com/winux125s-projects/forte26 |
| Локальный проект | `C:\Users\winux\Documents\datathon_forte` |

Текущая VM именно в первоначальном аккаунте с $50, как попросил владелец. Обе организации не путать.

На этой Windows-машине SSH настроен в WSL Ubuntu-24.04. Рабочая команда из PowerShell:

```powershell
.venv/Scripts/python.exe scripts/remote.py "cd /home/shadeform/forte-service && systemctl is-active forte-api forte-worker forte-frontend caddy"
wsl -d Ubuntu-24.04 --exec ssh -o ControlPath=none forte-vision-50
```

Для сложного Python без проблем с PowerShell/bash quoting:

```powershell
.venv/Scripts/python.exe scripts/remote.py --python data/check_queue.py
```

`--python` читает локальный файл и исполняет его на сервере через base64, в каталоге проекта. Скрипты с реальными сценами/кадрами не выводить наружу.

WSL Brev: `/home/winux/.local/bin/brev`, версия 0.6.337. Первичные credentials: `/home/winux/.brev/credentials.json`; вторичные: `credentials.forte-secondary.json` рядом. API-ключ уже задаёт scope организации; `active_org.json` может содержать старую организацию. В этой версии нельзя полагаться на команду `brev login --api-key ...` из исходного сообщения: флаг не поддерживается. На другой машине настроить официальный Brev CLI и SSH своим штатным способом с ключом из приватного файла.

Vercel CLI уже авторизован в WSL. Node/npm: `/home/winux/.nvm/versions/node/v22.13.1/bin`. Локальная авторизация: `/home/winux/.local/share/com.vercel.cli/auth.json`; не копировать её в сайт. На другой машине выполнить обычный `vercel login`. Проект связан через `deploy/vercel/.vercel/project.json`.

## 2. Главная проблема RAG — два разных уровня

**`evidence_insufficient` создаёт `backend/pipeline.py`, а не сам RAG.** Исходный RAG возвращает решения отдельных норм: `insufficient`, `violation_supported`, `refuted`, `exception_applies` и др. Обвязка преобразовывала любое недостаточное заключение, даже по дополнительной норме, в ошибку всего видео. При отсутствии опубликованного события JEPA-positive также приводил к этому коду.

Связка частично исправлена: неопределённость по норме должна быть привязана к конкретному событию; неопределённая дополнительная норма и блокировка другой карточки больше не отменяют уже разрешённое событие. Неопределённость не превращается в `no_violation` и факты не усиливаются до confirmed.

**Отдельный неизбежный блокер в переданном пакете: все 8 карточек имеют `human_reviewed=false`, `production_active=false`.** Диагностический запуск подтвердил 0 reviewed / 0 active. Даже `decision=violation_supported` получает `publishable.allowed=false`, `reason=rule_not_production_active`.

Это явно прописано в исходных:

- `ForteBank-Legal-RAG-2026-10-18/README.md` и `INTEGRATION.md`;
- `legal_rag/decide.py::publishable`: только `service`-режим может идти в API соревнования; `dev` не для публикации;
- `legal_rag/pipeline.py`: черновую карточку нельзя обходить повторным свободным чтением той же нормы; generic norm reading тоже analysis-only.

**Требование владельца: RAG и JEPA не менять.** Нельзя просто включить флаги, использовать dev gate, переписать решения, исключить unknown или назвать запрещённое заключение другим типом для обхода. Для полноценной положительной выдачи нужен согласованный с владельцем процесс проверки карточек / обновлённый разрешённый пакет от автора RAG. Сейчас обвязка честно возвращает failed при невозможности итогового вывода. Задача «все нарушения выдаются по ТЗ» этим не выполнена.

Дополнительный дефект связки: всем фактам раньше присваивался один anchor и общий evidence. Внешний `backend/vision.py` теперь получает отдельные `evidence_indices` каждого факта и передаёт настоящие timestamps/refs в bundle. `unknown` и видимое опровержение сохраняются. Для каждого кандидата отдельные actor/operation IDs; никакой идентификации лиц. Улучшение ещё требует проверки на реальных положительных роликах.

Диагностика:

```bash
cd /home/shadeform/forte-service
.venv/bin/python scripts/diagnose_legal.py
```

Полные локальные bundle/ответы RAG сохраняются в `data/legal-audit/<job_id>.json`, приватно, TTL 24 часа. Скрипт печатает только технические счётчики. На момент handoff в audit был только `synthetic.json` от контрактного теста: **это не успешный реальный положительный результат**. При timeout до завершения RAG запись пока не создаётся — полезно добавить сохранение bundle до вызова RAG.

## 3. Что развёрнуто и что не выложено

На VM активны `forte-api`, `forte-worker`, `forte-frontend`, `caddy`. На последней проверке HTTPS `/app` и `/readyz` отвечали 200.

Фронтенд обновлён и собран: image `forte-vision:deployment`, последний image SHA `82e32927a54b1e9534b1da246046f267e84ed51b6f069ee7c2fe3a0f5fd94d32`. Обновлённая страница по Vercel отвечает 200, старого модала в SSR HTML нет. Это не заменяет полноценную браузерную проверку.

**Есть локальная НЕВЫЛОЖЕННАЯ правка `backend/pipeline.py`:** вместо растущего количества перекрывающихся 24-секундных окон сделан ограниченный общий обзор до 24 кадров + 7 кадров вокруг JEPA peak. Цель — оставить время RAG в пределах 285 секунд. Она пока не протестирована и может снизить полноту коротких событий. Решить, проверять или откатить её, прежде чем публиковать.

Remote SHA pipeline на handoff: `de2faa39711622b499e3098506e3ab0fb8dcf6f44fac4438d0f312637a1d5b23`. Локальные SHA и сравнительный marker — `HANDOFF_MANIFEST.json`. `api.py`, `store.py`, `worker.py`, `vision.py` на диске VM совпадали с локальными при проверке; resident worker может продолжать использовать код, импортированный до обновления файлов. Новый worker без нужды посреди чужого задания не перезапускать.

README и AUDIT содержат исторические 128 МиБ, очередь 2, модал настройки. **Это уже устарело; текущие изменения описаны здесь.**

## 4. Новый фронт и транспорт

React 19 / Vinext / Vite / TypeScript / Tailwind, исходный дизайн forte-vision сохранён. Веб-сценарий: открыть `/app`, выбрать MOV, начать проверку. Ручные поля URL/API key, модал, кнопка настройки API и соответствующие инструкции удалены.

- Vercel содержит только внешний rewrite на GPU-сервер: `deploy/vercel/vercel.json`. Это короткий стабильный адрес без загрузки моделей в Vercel.
- Браузер читает `/api/browser/config`; сервер возвращает прямой GPU origin и размер файла.
- `POST /api/browser/session` создаёт подписанный HMAC токен на 24 часа. Origin проверяется по allowlist. Токен в sessionStorage позволяет продолжить после reload.
- Загрузка/получение кадров идут **напрямую браузер → GPU**, минуя Vercel.
- `/api/browser/analyze` и `/api/browser/jobs/{id}` принимают scoped token в `X-API-Key`. Каждое задание привязано к client_id; чужой токен получает 404. Токен браузера не открывает `/api/v1`.
- Ключ жюри не попадает в JS. `/api/v1` по-прежнему требует настоящий `X-API-Key`.
- На сервере в `secrets/service.env` добавлены `FORTE_BROWSER_API_ORIGIN=https://154.54.100.194.sslip.io` и allowlist `FORTE_CORS_ORIGINS=https://forte26.vercel.app,https://154.54.100.194.sslip.io`.
- Privacy RU/KK/EN обновлён под scoped session; help и размер файла переведены.

Нужно проверить реальным браузером: session → direct upload → polling → reload/resume → изоляция вкладок. Старый `scripts/browser_api_smoke.cjs` обновлён под автоматическое подключение, но путь к локальному ролику должен существовать там, где запускается браузер. На VM полного датасета `open/` нет.

## 5. Размеры, очередь и SLA

Лимит увеличен с 128 МиБ до **10 ГиБ**: `backend/settings.py` (10737418240), frontend, Caddy max body 11 GB. Config по короткому URL действительно возвращает 10737418240. Upload multipart остаётся spool-to-disk; затем файл копируется в uploads. Есть запас свободного диска `2 * MAX_BYTES + 1 GiB`; при его исчерпании 507. Не проверена реальная загрузка файла >128 МиБ / 10 ГиБ. Ограничения содержимого видео **не увеличены**: длительность до 180 секунд, до 4096×2160. Веб — MOV, API дополнительно MP4.

Искусственная вместимость 2 задания и 429 удалены. SQLite WAL хранит принятую очередь. Во время warmup задания тоже принимаются. В очередь добавлены client_id / started / attempts, миграция в `store.init()`.

- Один resident GPU worker, не два: параллельный инференс пока не внедрён и не измерен.
- Browser jobs ждут очередь; их 285 секунд анализа считаются от started. Браузер ждёт до 24 часов с возможностью остановить ожидание.
- Jury jobs сохраняют deadline 285 секунд **от приёма**, включая очередь, поскольку у жюри лимит 5 минут. Удаление 429 не гарантирует SLA при перегрузке.
- Queue position добавлен в API и UI; UI убрал обещание «до 5 минут» во время ожидания.
- При рестарте незавершённое задание повторно ставится в очередь один раз; дальнейшая повторная авария → worker_restarted. SIGALRM timeout → failed и перезапуск процесса systemd.
- Обработанные/ошибочные исходники удаляются, результат/кадры/журнал хранятся до 24 часов.

**Реальные ошибки ещё есть.** Последний наш запрос `Х-11.mov`, job `27acb3daddb2407f`, после ожидания очереди вернул `failed / processing_timeout` за **289.657 с**. Другой job `70aa63ea639448bd` выполнялся перед ним; его принадлежность/итог не установлены, мог быть запрос владельца. Не удалять чужие задания ради тестов. Ранее job `661a31b714fd4622` тоже завершился timeout.

До последних изменений: отрицательный `Х-8.mov` — done/no_violation за 29.265 с; положительный `Х-11.mov` — evidence_insufficient за 254.704 с. Это обучающие видео, а не независимая проверка качества.

## 6. Проверки: что зелёное, что красное

- Последний backend pytest на VM: **20 passed**; локально 19 passed / 1 skipped (CUDA-only test).
- Последний frontend typecheck: прошёл после проверки unknown JSON в auto-connect hook.
- Последние frontend unit: **103 passed / 3 failed из 106**. Lint в той же цепочке не выполнялся после падения unit.
- `components/check-result.test.mjs`: ожидает прежний текст «Сервер не сообщил процент»; компонент теперь пишет новый текст. Обновить ожидание с проверкой indeterminate semantics.
- `hooks/workspace-state.test.mjs`: auto-connect остаётся checking в момент assert; затем следующий тест получает connected вместо unavailable. Harness делает только 8 Promise microtask flush, новый hook содержит несколько асинхронных запросов. Проверить корректное ожидание окончания init; вероятна гонка harness, не считать исправленным заранее.
- Последние **74 E2E Chromium/WebKit были зелёными до удаления API модала**. Текущий `tests/e2e/review.spec.ts` адаптирован под scoped browser endpoints, но повторного полного запуска ещё не было.
- Предыдущие 104 исходных теста RAG проходили; в текущем проходе повторно не запускались.
- Исходные ZIP ранее проверены byte-for-byte: JEPA 66 файлов, RAG 241, все совпали. После последних внешних правок повторный hash-check ещё не запускался; пакеты намеренно не редактировались.

Логи на VM: `data/frontend-checks-current.log`, `data/frontend-build-current.log`, предыдущий полный зелёный `data/frontend-checks-complete.log`. Локальный последний API результат: `data/public-smoke-current/Х-11.json`. Тестовый synthetic audit не путать с реальными результатами.

## 7. Архитектура и offline модели

```text
Vercel rewrite → Caddy → forte-vision :3000
                    └→ FastAPI :8000 → SQLite / uploads
Browser large-video transport ────────────┘
                                      ↓
                              один offline GPU worker
                  original JEPA.predict → VisualObserver → original RAG.analyze
```

- JEPA: исходный `JEPA-FULL/runtime.py`, только public `.predict(path)`; веса внутри исходного пакета.
- Внешний video-to-facts адаптер: `backend/vision.py`, локальный Qwen3-VL-8B, `config/observer.json`, `models/qwen3-vl-8b` около 17 GB.
- RAG: **исходный** configs/cuda.json: Qwen3-VL-4B + BGE-M3 / BM25. Логика retrieval/prompt/decision/gate не меняется.
- HF cache: `/ephemeral/forte-service-models/hf-cache`; stock legal index `data/legal_index_stock`. Дополнительная копия BGE — `models/bge-m3`.
- Пин visual 8B: `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`; RAG4B: `ebb281ec70b05090aa6165b016eac8ec08e71b17`; BGE: `5617a9f61b028005a4858fdac845db406aefb181`.
- Для RAG model_id разрешается в **тот же** локальный snapshot через dataclasses.replace: это обход сетевого model_info вызова transformers 4.57 при offline, не другая модель.
- `backend/optimizations.py` ускоряет patch embedding только внешнего 8B observer, не JEPA/RAG.
- Idle VRAM около 27 GB. Worker `PrivateNetwork=true`, HF_HUB_OFFLINE=1 / TRANSFORMERS_OFFLINE=1. После загрузки весов обработка без интернета.
- Видео/кадры/описания сцен запрещено отправлять в облачные AI API. Не выводить их в агентский чат/инструментальные ответы. Технические агрегаты разрешают диагностику без раскрытия содержимого.

## 8. Команды продолжения

Из корня локального проекта:

```powershell
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe scripts/verify_inputs.py
.venv/Scripts/python.exe scripts/package_source.py
wsl -d Ubuntu-24.04 --exec scp -o ControlPath=none /mnt/c/Users/winux/Documents/datathon_forte/source.tar.gz forte-vision-50:/home/shadeform/forte-service/source.tar.gz
```

На VM (после осознанного решения про локальную pipeline правку):

```bash
cd /home/shadeform/forte-service
tar -xzf source.tar.gz
.venv/bin/python -m pytest tests -q
.venv/bin/python scripts/verify_inputs.py
sudo docker build -t forte-vision:deployment -f deploy/Dockerfile.frontend forte-vision
sudo systemctl restart forte-frontend
# Когда нет выполняющегося чужого задания:
sudo systemctl restart forte-api forte-worker
# Caddy читает deploy/Caddyfile прямо из проекта, /etc/caddy/Caddyfile НЕТ:
sudo systemctl restart caddy
```

У Caddy unit нет ExecReload: использовать restart, не reload. TLS Let’s Encrypt. `deploy/Dockerfile.frontend` сейчас инкрементальный FROM `forte-vision:deployment`; подходит текущей VM, **для чистой машины нужно восстановить полный Dockerfile/bootstrap dependencies**. Не принять его за воспроизводимую сборку с нуля.

Frontend QA в уже готовом QA image (Node/pnpm/Chromium/WebKit):

```bash
sudo docker run --rm --network host \
  -v /home/shadeform/forte-service/forte-vision:/src:ro \
  -v /home/shadeform/forte-service/data:/results \
  -e FRONTEND_TEST_URL=https://forte26.vercel.app forte-vision:qa \
  sh -lc 'cp -a /src/. /app/ && pnpm exec vinext typegen && pnpm typecheck && pnpm test && pnpm lint && pnpm test:e2e --workers=4 --reporter=line'
```

Vercel redeploy из WSL:

```bash
export PATH=/home/winux/.nvm/versions/node/v22.13.1/bin:$PATH
cd /mnt/c/Users/winux/Documents/datathon_forte/deploy/vercel
npx --yes vercel@64.5.0 deploy --prod --yes
```

Production без авторизации Vercel проверен HTTP 200. Preview может требовать Vercel Authentication. Не отключать защиту других проектов аккаунта.

`scripts/public_smoke.py` безопасно печатает только статусы/счётчики, но **парсер env сейчас предполагает один ключ в файле** (`split('=',1)[1]`); на VM env уже многострочный, поэтому перед запуском там исправить чтение именно строки FORTE_API_KEY. На локальной машине service.env пока одна строка. Для реального теста на текущей Windows машине:

```powershell
.venv/Scripts/python.exe scripts/public_smoke.py open/videos/Х-11.mov --output data/public-smoke-current
```

Не добавлять новый тест в занятую очередь без учёта SLA: последнее измерение истекло до запуска обработки.

## 9. Другой NVIDIA сервер и расходы

Старая VM **`forte-jepa-rag` / `ppdzcg25r` / `185.216.22.24`**, A100 PCIe, около $1.62/час, принадлежит второй организации `org-3JihwofPz8a0CM9rqvoTY7XRvYR`. Наши API/worker/Caddy там остановлены и disabled, временный frontend контейнер и эксперименты 32B остановлены. **Сама VM не удалена и продолжает расходовать деньги.** Этот тип не поддерживал stop; на ней есть другие файлы/работа, поэтому не удалять без решения владельца и сохранения нужных данных.

Доступ к старой VM через `FORTE_BREV_HOST=forte-jepa-rag` в scripts/remote.py; cert `/home/winux/.brev/ssh-certs/ppdzcg25r`, proxy `global.prd.ga.run.brev.nvidia.com:25219`. WSL `scripts/refresh_secondary_cert.py` временно берёт вторые credentials и восстанавливает первичные в finally; не запускать одновременно с другими Brev командами.

## 10. Приоритет следующему разработчику

1. Согласовать с владельцем/автором RAG публикационный статус карточек. Без этого positive API не станет готовым при запрете изменения пакета.
2. Добить 3 frontend unit failures, затем lint и все E2E, live auto-connect/upload/resume по Vercel.
3. Проверить последнюю локальную sampling правку и задержки по этапам; убрать лишние повторяющиеся visual candidates без смешивания событий; уложить реальные положительные ролики в SLA. Конфигурацию и выводы RAG/JEPA не подменять.
4. Проверить реальные >128 MiB загрузки и поведение нескольких одновременных запросов, disk/spool cleanup, worker retry; ограничить приём осмысленно по ресурсам без фиктивных гарантий.
5. Повторно проверить byte integrity обоих исходных пакетов и обновить README/AUDIT по фактическому результату. Успех только после реального positive done/violation с временем, JPEG и источником; synthetic тест этим не является.
