# JEPA-LGBM-FULL — запуск на CPU и NVIDIA GPU

Передайте один файл **`JEPA-LGBM-FULL.zip`**. Внутри веса, код, установщик и инструкция. Репозиторий, датасет, Brev, API-ключи и обучение получателю не нужны. Интернет нужен для первой установки зависимостей; после установки модель работает локально без сети.

Обе головы **LightGBM без PCA** и локализатор обучены на **всех 40 уникальных видео**: 21 с нарушением, 19 без, 22 размеченные точки. Энкодер JEPA заморожен. Бывшие train и test включены в обучение. **У этой FULL-модели нет независимого test F1.**

## Быстрый старт

Распакуйте ZIP и откройте терминал в папке `JEPA-LGBM`. Нужен 64-битный Python **3.10–3.13**, рекомендуем 3.11. Для установки и весов предусмотрите около 12 ГБ свободного диска.

Linux:

```bash
python3 install.py --device cuda
python3 run.py --device cuda --video "/path/to/video.mov" --out result.json
```

Компьютер без NVIDIA GPU:

```bash
python3 install.py --device cpu
python3 run.py --device cpu --threads 4 --video "/path/to/video.mov" --out result.json
```

Windows PowerShell/CMD:

```powershell
py -3.11 install.py --device cuda
py -3.11 run.py --device cuda --video "C:\videos\video.mov" --out result.json
```

На Windows без NVIDIA замените `cuda` на `cpu`. Активация окружения не требуется: установщик создаёт `.venv`, а `run.py` использует её Python. Можно использовать `--device auto` и при установке, и при запуске: доступная NVIDIA CUDA → GPU, иначе CPU.

Подтверждённая платформа проверки — Linux x86-64 с NVIDIA L40S. CPU-код включён, **CPU-видеоинференс этой версии не запускался по просьбе владельца**. Время CPU-инференса не измерялось; JEPA на CPU может работать долго. Windows и macOS отдельно не проверены. Для macOS используйте CPU и совместимый с вашей платформой PyTorch; Apple MPS в пакете не используется.

## Зависимости

Установщик ставит PyTorch 2.9.1 + torchvision 0.24.1 (CPU либо CUDA 12.6), scikit-learn 1.7.2, LightGBM 4.6.0 и библиотеки обработки видео. Для NVIDIA нужен совместимый драйвер; отдельный CUDA Toolkit для готовых wheels не требуется. [Официальные команды PyTorch 2.9.1](https://pytorch.org/get-started/previous-versions/#v2-9-1).

Если отсутствует `venv`, на Ubuntu установите `python3-venv`. Если внутри окружения нет pip, установщик использует включённый официальный `get-pip.py`. FFmpeg/FFprobe отдельно ставить не требуется: метаданные читает PyAV, кадры — OpenCV.

LightGBM использует OpenMP. При ошибке `libgomp.so.1` на Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install libgomp1
```

На macOS при ошибке `libomp.dylib`:

```bash
brew install libomp
```

Эти требования описаны в [официальном Python-пакете LightGBM 4.6.0](https://pypi.org/project/lightgbm/4.6.0/). После устранения ошибки повторите `install.py`. На Linux/macOS команды ниже используют `python3`, на Windows можно заменить на `py -3.11`.

## Проверка и варианты запуска

```bash
python3 run.py --check --device cuda
python3 run.py --device cuda --video video.mp4 --out result.json
python3 run.py --device cpu --threads 4 --video video.mp4 --out result.json
```

`--check` проверяет SHA-256 пакета, зависимости и устройство, без обработки видео. При явном `--device cuda` отсутствие CUDA вызывает ошибку. В GPU-режиме энкодер JEPA работает на GPU, небольшие головы LightGBM и локализатора — на CPU. В CPU-режиме весь пайплайн работает на CPU. CPU использует FP32, CUDA — BF16 при поддержке, иначе FP32; около порога возможны численные различия. `--threads` задаёт число CPU-потоков PyTorch.

Из уже подготовленного окружения можно запускать `python inference.py` с теми же аргументами. Версии LightGBM и scikit-learn должны совпадать с зафиксированными в пакете. Не редактируйте файлы весов/кода: проверка целостности отклонит изменения.

## Результат

JSON выводится в stdout и, при `--out`, сохраняется в файл. Пример структуры, числа условные:

```json
{
  "status": "ok",
  "model": "JEPA-LGBM-FULL",
  "label": 1,
  "label_name": "нарушение",
  "violation_detected": true,
  "score": 0.81,
  "threshold": 0.5,
  "timecode_sec": 10.2,
  "timecode": "00:00:10.200",
  "timestamp_status": "estimated",
  "events": [{"timecode_sec": 10.2, "timecode": "00:00:10.200"}]
}
```

`score >= 0.5` → нарушение. При отсутствии нарушения `label=0`, `timecode=null`, `timecode_sec=null`, `events=[]`; локализатор не запускается. При положительном ответе выдаётся максимум один момент. Если выраженного временного пика нет, метка остаётся 1, но таймкод `null` и `timestamp_status="uncertain"`.

Таймкод — приблизительный момент, не подтверждённые границы события. Тип нарушения и объяснение по пунктам правил модель не выдаёт. Ошибки чтения видео возвращают ненулевой код завершения и сообщение в stderr, а не метку «без нарушения».

## Архитектура и обучение

- Один frozen V-JEPA2.1 ViT-L/16 distilled, разрешение 384.
- Ветвь `jepa`: 16 кадров за 8 секунд, 2 fps, шаг окон 4 секунды; StandardScaler → LightGBM, без PCA.
- Ветвь `longdense`: 64 кадра за 16 секунд, 4 fps, шаг окон 8 секунд; StandardScaler → LightGBM, без PCA.
- `score = 0.30 × score(jepa) + 0.70 × score(longdense)`, порог 0.5. **30/70 — доли прогнозов, а не разбиение датасета.** Обе головы обучены на всех 40 видео.
- Настройки взяты из train-only CV прежнего split 28/12: max_depth=2, learning_rate=0.05, min_child_samples=1, 40/100 деревьев, L2=1, balanced sample weights. Веса и порог после FULL-refit не подбирались.
- Single-v6 локализатор: отдельные appearance/motion rankers, refit на всех доступных положительных видео и 22 точках. Контекстная важность рассчитывается по падению raw-margin LightGBM при замене окон, с весами 30/70. Параметры fusion сохранены; точность этой комбинации на независимых видео пока не оценена.

Прежний вариант на 28 train имел CV F1 0.7173 и development-test F1 0.7692. **Это показатели прежней модели, не FULL.** Все 40 видео уже использованы; проверка на них не является независимой оценкой. Подробности обучения — `TRAINING.json`, выполненные проверки — `FULL_VALIDATION.json`.

## Python API

Из папки пакета в его окружении:

```python
from runtime import JepaModel

model = JepaModel(device="cuda", threads=4)
result = model.predict("video.mov")
print(result["label"], result["timecode"])
second = model.predict("another.mp4")
```

Объект загружается один раз, затем обрабатывает видео последовательно. Для CPU используйте `device="cpu"`. Не вызывайте один объект одновременно из нескольких потоков.

## Содержимое

- `install.py`, `run.py` — установка и запуск без активации окружения.
- `inference.py`, `runtime.py` — CLI и Python API.
- `weights/encoder.pt`, `weights/heads.joblib` — все веса.
- `model.json` — настройки и SHA-256; `TRAINING.json` — FULL-refit; `FULL_VALIDATION.json` — проверки.
- `forte_vlm/`, `vendor/vjepa2/`, `tools/` — необходимые исходники, лицензии и bootstrap pip.
- `examples/` — JSON GPU-примеров, без исходных видео или датасета.

PyTorch + sklearn/LightGBM сохраняют весь видеопайплайн и поддерживают CPU/GPU; ONNX для запуска не требуется. Исходный JEPA commit `204698b45b3712590f06245fbfba32d3be539812`; сохранённые EMA-тензоры не менялись. Лицензии исходного encoder находятся в `vendor/vjepa2/`.
