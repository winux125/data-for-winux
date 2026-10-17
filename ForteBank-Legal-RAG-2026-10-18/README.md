# ForteBank Legal RAG для интеграции

Передать тиммейту **весь ZIP**, а не одну папку с Python-файлами. Распаковать в
отдельную папку. Код, проверенные нормативные снимки, конфиги, тесты и tokenizer
уже внутри. Для CPU smoke-проверки достаточно Python 3.11+ без дополнительных библиотек.

```text
ForteBank-Legal-RAG/
  README.md                    начать здесь
  INTEGRATION.md               контракт и пример подключения
  pyproject.toml               установка в другой проект через pip
  smoke.py                     быстрая проверка без нейросетей и сети
  configs/                     CPU smoke и CUDA hybrid
  legal_rag/
    api.py, pipeline.py        единый вход анализа
    contracts.py               форматы наблюдений и результата
    retrieve.py, embed.py      BM25 / BGE-M3 / hybrid RRF
    source_packet.py           целые нормы, зависимости и полнота
    apply.py, generate.py      применение нормы, Qwen A/B
    validate.py                проверки и template fallback
    tests/, examples/, data/   тесты, синтетический вход, карточки/лексикон
    resources/
      core/                    исходные пять актов и проверенный bundle
      corpora/legal_corpus_v3/  текущие 54 источника
      corpora/legal_corpus_v2/  прежний корпус только для регрессий
      tokenizer/               tokenizer Qwen и его provenance
  PACKAGE_MANIFEST.json        состав, размеры и SHA-256 файлов
```

В архиве **нет JEPA, видео, кадров датасета, ключей, обучающих прогонов, весов BGE/Qwen
и готового dense-индекса**. Нормативные ресурсы и tokenizer включены; модели и индекс
готовятся отдельно на машине запуска.

## 1 Проверка после распаковки

Открыть терминал в корне распакованной папки:

```bash
python -B smoke.py
python -B -m unittest discover -s legal_rag/tests -t .
```

Smoke проверяет целостность нормативных снимков и цепочку с BM25/карточкой/шаблоном.
Ожидается `R231-22: violation_supported`, `generator: template_fallback`,
`publication_allowed: false`. Это синтетический пример, не прогон Qwen и не
разрешение публикации. Файл `smoke_result.json` содержит полный ответ.

## 2 Подключение в свой проект

В своём виртуальном окружении выполнить:

```bash
python -m pip install /absolute/path/ForteBank-Legal-RAG
```

Эта установка не скачивает веса моделей. Импорт:

```python
from legal_rag import shared
from legal_rag.config import load_config

config = load_config('/absolute/path/ForteBank-Legal-RAG/configs/cuda.json')
rag = shared()
worker = rag.runtime(config, index_dir='/absolute/path/legal_index').warm()
result = worker.analyze(observation_bundle).to_dict()
```

Сначала подготовить модели и индекс, как описано ниже. Для проверки без моделей:

```python
config = load_config('/absolute/path/ForteBank-Legal-RAG/configs/cpu_smoke.json')
result = shared().analyze(observation_bundle, config, template_only=True).to_dict()
```

Сохранять один worker на процесс, вызывать последовательно. `legal_rag/api.py` —
библиотечный API, не HTTP-сервис; фронтенд, HTTP-очередь и адаптер схемы жюри
реализуются в основном проекте тиммейта.

## 3 Настоящие BGE и Qwen

Работать в отдельном окружении, не переустанавливать окружение JEPA автоматически.
Согласованные версии указаны в `legal_rag/requirements-gpu.txt`.

Пример для Linux с подготовленной NVIDIA GPU:

```bash
python -m pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu126
python -m pip install -r legal_rag/requirements-gpu.txt
hf download BAAI/bge-m3 --revision 5617a9f61b028005a4858fdac845db406aefb181
hf download Qwen/Qwen3-VL-4B-Instruct --revision ebb281ec70b05090aa6165b016eac8ec08e71b17
python -B -m legal_rag doctor --config configs/cuda.json
python -B -m legal_rag embed --config configs/cuda.json --output data/legal_index/bge-m3
python -B -m legal_rag analyze --config configs/cuda.json --index-dir data/legal_index/bge-m3 --input legal_rag/examples/leaving_workplace.json --output qwen_result.json
python -B -m legal_rag bench --config configs/cuda.json --run-models --index-dir data/legal_index/bge-m3 --output gpu_bench.json
```

Весов и dense-индекса в передаче пока нет: настоящий BGE/Qwen-прогон в исходной
доступной среде не выполнялся. Сеть нужна для установки/получения публичных весов;
после подготовки inference читает локальные файлы. Наблюдения, кадры и видео во
внешние AI API не отправляются. `--template-only` не использовать при измерении Qwen.

## 4 Что честно передать вместе с кодом

- Код проверен CPU-тестами и синтетическими примерами с scripted/model-free backend.
- По известным 36 dev-запросам core BM25+лексикон находил точный пункт в top-5
  в 34 случаях (94,44%). Это не независимое качество всего каскада.
- Hybrid реализован, но ещё не выбран измеренным сравнением с настоящим BGE.
- Qwen A/B, VRAM, скорость полного каскада и качество объяснений нужно измерить.
- Все 8 карточек draft. Публикация закрыта; имя проверяющего не выдумывать.
  Общие model-read нормы также analysis-only до проверки.
- Результат `insufficient` нельзя автоматически преобразовывать в `no_violation`.
- JEPA и визуальный Qwen не входят в RAG: они готовят наблюдения для него.

Подробный контракт, поля результата и граница интеграции — в `INTEGRATION.md`.
