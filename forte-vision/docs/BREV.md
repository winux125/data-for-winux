# Развёртывание на Brev

Текущая инструкция: [корневой DEPLOYMENT.md](../../docs/DEPLOYMENT.md). Frontend, API и worker разворачиваются вместе. Старый отдельный frontend compose и deploy-brev.sh удалены, чтобы не запускать несовместимый вариант.

Из корня репозитория: `docker build -f deploy/Dockerfile.frontend -t forte-vision:deployment forte-vision`. Установка сервисов — `bash scripts/install_services.sh` после bootstrap и настройки FORTE_PUBLIC_HOST. Это не создаёт новый GPU-инстанс.
