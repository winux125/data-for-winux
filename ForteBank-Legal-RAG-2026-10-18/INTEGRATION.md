# Контракт между видеопайплайном и Legal RAG

```text
Видео -> JEPA-FULL: бинарный класс + не более одного примерного момента
      -> внешний адаптер: исходные кадры/интервал
      -> визуальный Qwen: наблюдаемые действия и доказательства
      -> ObservationBundle
      -> Legal RAG: поиск -> полная норма -> применение -> объяснение
      -> внешний адаптер результата для UI/API жюри
```

Класс JEPA определяет приоритет проверки, не является юридическим фактом. По нему
нельзя придумывать действие, тип, роль или закон. Для нескольких событий нужен
отдельный механизм предложений/сканирования: финальная JEPA выдаёт максимум один момент.

## Вход

Рабочий пример: `legal_rag/examples/leaving_workplace.json`.

```json
{
  "schema": "legal_rag.input.v1",
  "bundle_id": "video01-moment01",
  "context": {"organization_type": "bank", "event_date": null},
  "actors": [
    {"actor_id": "cashier1", "role": "cashier", "role_status": "confirmed", "fact_ids": ["f1"]}
  ],
  "facts": [
    {"fact_id": "f1", "predicate": "left_workplace", "statement": "Кассир покинул рабочее место",
     "status": "confirmed", "actor_id": "cashier1", "operation_id": "service1",
     "t_start": 20, "t_end": 25, "anchor_sec": 21.4, "evidence_refs": ["frame:21.4"]},
    {"fact_id": "f2", "predicate": "service_in_progress", "statement": "Обслуживание клиента продолжается",
     "status": "unknown", "actor_id": "cashier1", "operation_id": "service1"}
  ]
}
```

Этот пример должен остаться недостаточным: обслуживание не установлено.
`statement` — утверждение о действии, а его истинность задаётся `status`:

- `confirmed`: наблюдение подтверждено;
- `refuted`: подтверждено отсутствие; обязательно доказательство просмотренного контекста;
- `unknown`: установить нельзя. Отсутствующее поле/предикат также не равно false.

Роли имеют отдельные `role_status`: confirmed/inferred/unknown. У предполагаемой
роли нет силы подтверждённой. Для decided-фактов обязательны реальные `evidence_refs`.
Имена/распознавание личности не нужны; `actor_id` — идентификатор участника в сцене.

`operation_id`, участник, объект и время отделяют разные операции. Не объединять
факты разных клиентов в одно нарушение. В `provenance` допустим источник/версия
наблюдений, но запрещены сырые label/score/confidence/jepa и другие classifier-поля:
они сохраняются снаружи RAG.

Канонические предикаты карточек перечислены в `legal_rag/data/rule_cards.json`.
Свободные структурированные предикаты разрешены для поиска иных норм; отсутствие
карточки не означает, что новая категория автоматически проверена.

## Выход

`LegalAssessment.to_dict()` возвращает `schema=legal_rag.output.v1`, bundle_id,
assessments, no_norm, versions, timings_ms, tokens. В каждом assessment:

- `norm`: точный текст, строки, хеш, название, URL, статус и идентификатор нормы;
- `supporting_norms`: связанные фрагменты/определения/область;
- `items` и `mapping`: условия, исключения, состояния и поддерживающие fact IDs;
- `decision`: violation_supported/refuted/exception_applies/insufficient/not_applicable_scope;
- `explanation_text`: описание с кодом вставленными ссылками и evidence IDs;
- `generator`: настоящая модель, fake_scripted или template_fallback — не смешивать в метриках;
- `validation`: вызовы A/B, повторы/ошибки, пакет и scope;
- `publishable.allowed/reason`: отдельный gate публикации;
- `missing` и `decision_reasons`: что мешает выводу.

`no_norm` ограничен просмотренными кандидатами, `exhaustive=false`; это не
сертификат соблюдения всех законов. `insufficient` не является третьим публичным
verdict жюри и не означает `no_violation`. Сервис решает, что перепроверить или
какие данные получить, и не превращает неполную проверку в отсутствие нарушения.

## Qwen внутри RAG и повторное использование

Для draft/reviewed-карточки условия вычисляются из явных predicate mappings;
вызов A не нужен. Для нормы без карточки A читает требования и исключения с
точными цитатами, код вычисляет решение, B объясняет это решение. A/B обслуживает
одна резидентная Qwen в текстовом режиме. Визуальный вызов остаётся внешним.

Если Qwen уже загружена в основном приложении, можно предоставить адаптер
`legal_rag.generate.Generator` через конструктор `LegalRAGRuntime`:

```python
from legal_rag import shared
from legal_rag.pipeline import LegalRAGRuntime

worker = LegalRAGRuntime(shared(), config, generator=your_generator_adapter,
                        index_dir='/absolute/path/legal_index').warm()
result = worker.analyze(observation_bundle)
```

Адаптер реализует `chat(system, user, max_new_tokens) -> Generation`,
`count_tokens(text)` и `describe()`. Для настоящей модели выставляется
`is_real_model=True`; статистика, tokenizer и ограничения длины должны быть
фактическими. Внешние облачные AI API вместо локальной модели не подключать.

Один worker использовать последовательно. В многопроцессном HTTP-сервисе не
создавать отдельные копии Qwen в каждом web worker; очередь/HTTP — внешний слой.

## Обязательная внешняя работа

Извлечь реальные JPEG и PTS, сформировать перечень событий/типов, а затем
точную схему ТЗ: `verdict`, `violations`, `type`, `timecode_sec`, `description`,
`evidence_frames[{timestamp_sec,image_base64}]`. Raw assessment не является этой
схемой. Проверить лимит 5 минут, несколько событий и новый ракурс отдельно.

Правильные ID/цитаты не доказывают смысловую правильность текста Qwen. Нужны
проверенные человеком наблюдения, применимость нормы и отдельная семантическая оценка.
