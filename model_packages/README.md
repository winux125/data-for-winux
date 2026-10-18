# Пакеты детекторов

Активный пакет — `jepa_lgbm/` (`JEPA-LGBM-FULL`). Он сохранён без изменений из ZIP владельца, включая manifest, лицензии и описание обучения. Папка `weights/` исключена из Git; восстановление — `python scripts/install_detector.py --archive /path/to/JEPA-LGBM-FULL.zip` из корня сервиса.

Выбор находится в `config/detector.json`, интеграция — в `backend/detector.py`. Контракт: один resident `JepaModel`, последовательные вызовы `predict(video_path)`, JSON с `label`, `violation_detected`, `timecode_sec`, `latency_sec` и ID модели. Положительный класс — сигнал для Qwen, а не готовое юридическое заключение.

Прежний SVM-пакет удалён из рабочего дерева; его история сохранена в Git и отдельной резервной копии. Рабочий backend его не импортирует. Новую версию нужно размещать в отдельном каталоге и выбирать конфигурацией, не переписывая файлы текущего пакета.

Подробности: [docs/JEPA_LGBM_DEPLOYMENT.md](../docs/JEPA_LGBM_DEPLOYMENT.md).
