import type { Messages } from "@/lib/i18n";

export const workspaceMessages = {
  "Рабочая зона оставлена без наблюдения": {
    "kk": "Жұмыс аймағы қараусыз қалды",
    "en": "Work area left unattended"
  },
  "Условный пример: сотрудник отходит от рабочего места, на котором остаются предметы, похожие на наличные. Проверяющему необходимо изучить фрагмент и применимое правило.": {
    "kk": "Шартты мысал: қызметкер жұмыс орнынан кетеді, ал орнында қолма-қол ақшаға ұқсас заттар қалады. Тексеруші үзіндіні және қолданылатын ережені қарауы керек.",
    "en": "Illustrative example: an employee leaves a workstation with objects resembling cash. A reviewer must examine the clip and the applicable rule."
  },
  "Передача предмета вне зоны обслуживания": {
    "kk": "Қызмет көрсету аймағынан тыс зат беру",
    "en": "Object passed outside the service area"
  },
  "Условный пример: передача предмета происходит сбоку от обозначенной зоны. По одному кадру нельзя подтвердить, что передаются деньги. Требуется просмотр фрагмента.": {
    "kk": "Шартты мысал: зат белгіленген аймақтың жанында беріледі. Бір кадр арқылы ақша берілгенін растау мүмкін емес. Үзіндіні қарау қажет.",
    "en": "Illustrative example: an object is passed beside the marked area. A single frame cannot confirm that money was exchanged. The clip needs review."
  },
  "Проверка кассовой операции.mov": {
    "kk": "Кассалық операцияны тексеру.mov",
    "en": "Cash transaction review.mov"
  },
  "Операция без замечаний.mov": {
    "kk": "Ескертусіз операция.mov",
    "en": "Transaction with no issues.mov"
  },
  "Фрагмент обслуживания.mov": {
    "kk": "Қызмет көрсету үзіндісі.mov",
    "en": "Service clip.mov"
  },
  "Пример": {
    "kk": "Мысал",
    "en": "Example"
  },
  "Загрузка видео": {
    "kk": "Бейнені жүктеу",
    "en": "Uploading video"
  },
  "Не удалось выйти из аккаунта. Попробуйте ещё раз.": {
    "kk": "Аккаунттан шығу мүмкін болмады. Қайталап көріңіз.",
    "en": "Could not sign out. Please try again."
  },
  "Не удалось выйти из аккаунта. Проверьте соединение и повторите.": {
    "kk": "Аккаунттан шығу мүмкін болмады. Байланысты тексеріп, қайталап көріңіз.",
    "en": "Could not sign out. Check your connection and try again."
  },
  "Выберите видео в формате MOV.": {
    "kk": "MOV форматындағы бейнені таңдаңыз.",
    "en": "Choose a MOV video."
  },
  "Этот файл пуст. Выберите другую запись.": {
    "kk": "Бұл файл бос. Басқа жазбаны таңдаңыз.",
    "en": "This file is empty. Choose another recording."
  },
  "Для этой версии выберите файл размером до 128 МБ.": {
    "kk": "Бұл нұсқа үшін көлемі 128 МБ-тан аспайтын файлды таңдаңыз.",
    "en": "Choose a file up to 128 MB for this version."
  },
  "Выбранные проверки удалены из текущего сеанса": {
    "kk": "Таңдалған тексерулер ағымдағы сеанстан жойылды",
    "en": "Selected checks removed from this session"
  },
  "Проверка удалена из текущего сеанса": {
    "kk": "Тексеру ағымдағы сеанстан жойылды",
    "en": "Check removed from this session"
  },
  "Проверка завершена": {
    "kk": "Тексеру аяқталды",
    "en": "Check complete"
  },
  "Анализ видеозаписи": {
    "kk": "Бейнежазбаны талдау",
    "en": "Analysing recording"
  },
  "Результат готов к проверке": {
    "kk": "Нәтиже тексеруге дайын",
    "en": "Result ready for review"
  },
  "Не удалось обработать видео. Попробуйте ещё раз.": {
    "kk": "Бейнені өңдеу мүмкін болмады. Қайталап көріңіз.",
    "en": "Could not process the video. Please try again."
  },
  "Ожидание отменено. Задание на сервере может продолжаться.": {
    "kk": "Күту тоқтатылды. Сервердегі тапсырма жалғасуы мүмкін.",
    "en": "Waiting cancelled. The server job may still be running."
  },
  "Текущая запись": {
    "kk": "Ағымдағы жазба",
    "en": "Current recording"
  },
  "Передача видео": {
    "kk": "Бейнені жіберу",
    "en": "Video transfer"
  },
  "Передано {progress}% файла.": {
    "kk": "Файлдың {progress}%-ы жіберілді.",
    "en": "{progress}% of the file transferred."
  },
  "Сервер принял запись.": {
    "kk": "Сервер жазбаны қабылдады.",
    "en": "Server received the recording."
  },
  "Обработка": {
    "kk": "Өңдеу",
    "en": "Processing"
  },
  "Ожидается завершение загрузки.": {
    "kk": "Жүктеудің аяқталуы күтілуде.",
    "en": "Waiting for upload to finish."
  },
  "Сервер обрабатывает запись. Детальные этапы не переданы.": {
    "kk": "Сервер жазбаны өңдеп жатыр. Толық кезеңдер жіберілген жоқ.",
    "en": "The server is processing the recording. Detailed stages were not provided."
  },
  "Результат": {
    "kk": "Нәтиже",
    "en": "Result"
  },
  "После ответа сервера откроется результат проверки.": {
    "kk": "Сервер жауап берген соң тексеру нәтижесі ашылады.",
    "en": "The check result will open when the server responds."
  },
  "К содержимому": {
    "kk": "Мазмұнға өту",
    "en": "Skip to content"
  },
  "Закрыть меню": {
    "kk": "Мәзірді жабу",
    "en": "Close menu"
  },
  "Главная навигация": {
    "kk": "Негізгі навигация",
    "en": "Main navigation"
  },
  "Forte Vision - главная": {
    "kk": "Forte Vision - басты бет",
    "en": "Forte Vision - home"
  },
  "Свернуть боковую панель": {
    "kk": "Бүйірлік панельді жию",
    "en": "Collapse sidebar"
  },
  "Рабочее пространство": {
    "kk": "Жұмыс кеңістігі",
    "en": "Workspace"
  },
  "Кассовые операции": {
    "kk": "Кассалық операциялар",
    "en": "Cash transactions"
  },
  "НАВИГАЦИЯ": {
    "kk": "НАВИГАЦИЯ",
    "en": "NAVIGATION"
  },
  "Обзор": {
    "kk": "Шолу",
    "en": "Overview"
  },
  "Проверки": {
    "kk": "Тексерулер",
    "en": "Checks"
  },
  "Правила и источники": {
    "kk": "Ережелер мен дереккөздер",
    "en": "Rules and sources"
  },
  "Обработка видео": {
    "kk": "Бейнені өңдеу",
    "en": "Video processing"
  },
  "На сервере команды, без облачных AI API.": {
    "kk": "Команда серверінде, бұлттық AI API қолданбай.",
    "en": "On the team's server, without cloud AI APIs."
  },
  "Как это работает": {
    "kk": "Қалай жұмыс істейді",
    "en": "How it works"
  },
  "Подключение API": {
    "kk": "API қосылымы",
    "en": "API connection"
  },
  "Помощь": {
    "kk": "Көмек",
    "en": "Help"
  },
  "Открыть меню": {
    "kk": "Мәзірді ашу",
    "en": "Open menu"
  },
  "Развернуть боковую панель": {
    "kk": "Бүйірлік панельді жаю",
    "en": "Expand sidebar"
  },
  "Результат проверки": {
    "kk": "Тексеру нәтижесі",
    "en": "Check result"
  },
  "Идёт проверка": {
    "kk": "Тексеріліп жатыр",
    "en": "Check in progress"
  },
  "API настроен": {
    "kk": "API бапталды",
    "en": "API configured"
  },
  "Демо-режим": {
    "kk": "Демо режимі",
    "en": "Demo mode"
  },
  "Аккаунт: {name}": {
    "kk": "Аккаунт: {name}",
    "en": "Account: {name}"
  },
  "Аккаунт Forte Vision": {
    "kk": "Forte Vision аккаунты",
    "en": "Forte Vision account"
  },
  "Вход через ChatGPT": {
    "kk": "ChatGPT арқылы кіру",
    "en": "Signed in with ChatGPT"
  },
  "Оформление": {
    "kk": "Безендіру",
    "en": "Appearance"
  },
  "Язык": {
    "kk": "Тіл",
    "en": "Language"
  },
  "На главную": {
    "kk": "Басты бетке",
    "en": "Home"
  },
  "Выходим…": {
    "kk": "Шығу…",
    "en": "Signing out…"
  },
  "Выйти из аккаунта": {
    "kk": "Аккаунттан шығу",
    "en": "Sign out"
  },
  "К проверкам": {
    "kk": "Тексерулерге",
    "en": "Back to checks"
  },
  "ДЕМОНСТРАЦИОННЫЙ ПРИМЕР": {
    "kk": "ДЕМОНСТРАЦИЯЛЫҚ МЫСАЛ",
    "en": "DEMONSTRATION"
  },
  "Скачать результат": {
    "kk": "Нәтижені жүктеп алу",
    "en": "Download result"
  },
  "Демонстрационный результат. События условные; реальные видео и кадры не используются.": {
    "kk": "Демонстрациялық нәтиже. Оқиғалар шартты; нақты бейнелер мен кадрлар қолданылмайды.",
    "en": "Demonstration result. Events are illustrative; no real videos or frames are used."
  },
  "Нарушение не обнаружено": {
    "kk": "Бұзушылық анықталмады",
    "en": "No violation detected"
  },
  "Обнаружены признаки возможных нарушений": {
    "kk": "Ықтимал бұзушылық белгілері анықталды",
    "en": "Possible signs of violations detected"
  },
  "Сервис не обнаружил подозрительных событий в записи.": {
    "kk": "Сервис жазбадан күмәнді оқиғаларды анықтамады.",
    "en": "The service found no suspicious events in this recording."
  },
  "Событий для проверки: {count}.": {
    "kk": "Тексерілетін оқиғалар: {count}.",
    "en": "Events to review: {count}."
  },
  "Видеозапись": {
    "kk": "Бейнежазба",
    "en": "Recording"
  },
  "ИСХОДНАЯ ЗАПИСЬ": {
    "kk": "БАСТАПҚЫ ЖАЗБА",
    "en": "ORIGINAL RECORDING"
  },
  "Браузер не воспроизводит этот MOV. Используйте кадры, если сервер передал их.": {
    "kk": "Браузер бұл MOV файлын ойната алмайды. Сервер кадрларды жіберсе, соларды пайдаланыңыз.",
    "en": "Your browser cannot play this MOV. Use the frames if the server provided them."
  },
  "СХЕМА КАССОВОЙ ЗОНЫ": {
    "kk": "КАССАЛЫҚ АЙМАҚ СЫЗБАСЫ",
    "en": "CASH DESK DIAGRAM"
  },
  "Иллюстрация · не кадр видеозаписи": {
    "kk": "Иллюстрация · бейнежазба кадры емес",
    "en": "Illustration · not a video frame"
  },
  "Событие {number}, {time}": {
    "kk": "Оқиға {number}, {time}",
    "en": "Event {number}, {time}"
  },
  "Для реального результата подключите API": {
    "kk": "Нақты нәтиже үшін API қосыңыз",
    "en": "Connect the API for a real result"
  },
  "Видео доступно только в этом сеансе": {
    "kk": "Бейне тек осы сеанста қолжетімді",
    "en": "Video available only in this session"
  },
  "События": {
    "kk": "Оқиғалар",
    "en": "Events"
  },
  "Рассмотреть событие": {
    "kk": "Оқиғаны қарау",
    "en": "Review event"
  },
  "События не найдены": {
    "kk": "Оқиғалар табылмады",
    "en": "No events found"
  },
  "Сервис не обнаружил событий, требующих проверки.": {
    "kk": "Сервис тексеруді қажет ететін оқиғаларды анықтамады.",
    "en": "The service found no events requiring review."
  },
  "СОБЫТИЕ": {
    "kk": "ОҚИҒА",
    "en": "EVENT"
  },
  "Доказательства и основание": {
    "kk": "Дәлелдер мен негіз",
    "en": "Evidence and basis"
  },
  "Кадры-доказательства": {
    "kk": "Дәлел кадрлары",
    "en": "Evidence frames"
  },
  "Кадр события на {time}": {
    "kk": "Оқиға кадры: {time}",
    "en": "Event frame at {time}"
  },
  "Не удалось отобразить кадр.": {
    "kk": "Кадрды көрсету мүмкін болмады.",
    "en": "Could not display the frame."
  },
  "В демонстрации реальные кадры не используются.": {
    "kk": "Демонстрацияда нақты кадрлар қолданылмайды.",
    "en": "No real frames are used in this demonstration."
  },
  "Сервер не передал кадры для этого события.": {
    "kk": "Сервер бұл оқиға үшін кадрлар жіберген жоқ.",
    "en": "The server provided no frames for this event."
  },
  "Основание для проверки": {
    "kk": "Тексеру негізі",
    "en": "Basis for review"
  },
  "Перед подтверждением события проверьте запись и источник.": {
    "kk": "Оқиғаны растау алдында жазба мен дереккөзді тексеріңіз.",
    "en": "Check the recording and source before confirming an event."
  },
  "НОРМАТИВНАЯ БАЗА": {
    "kk": "НОРМАТИВТІК БАЗА",
    "en": "REGULATORY BASIS"
  },
  "Документы и разделы правил, указанные в результатах анализа.": {
    "kk": "Талдау нәтижелерінде көрсетілген құжаттар мен ереже бөлімдері.",
    "en": "Documents and rule sections cited in the analysis results."
  },
  "Источники из результатов": {
    "kk": "Нәтижелердегі дереккөздер",
    "en": "Sources from results"
  },
  "Источник передаётся сервером вместе с событием. Его также можно открыть на странице проверки.": {
    "kk": "Сервер дереккөзді оқиғамен бірге жібереді. Оны тексеру бетінен де ашуға болады.",
    "en": "The server provides a source with each event. You can also open it on the check page."
  },
  "Источников пока нет": {
    "kk": "Дереккөздер әзірше жоқ",
    "en": "No sources yet"
  },
  "Подключите API и загрузите запись. Документы из результата появятся в этом разделе.": {
    "kk": "API қосып, жазбаны жүктеңіз. Нәтижедегі құжаттар осы бөлімде пайда болады.",
    "en": "Connect the API and upload a recording. Documents from the result will appear here."
  },
  "Подключить API": {
    "kk": "API қосу",
    "en": "Connect API"
  },
  "У демонстрационных событий нет нормативных источников.": {
    "kk": "Демонстрациялық оқиғалардың нормативтік дереккөздері жоқ.",
    "en": "Demonstration events have no regulatory sources."
  },
  "КАССОВЫЕ ОПЕРАЦИИ": {
    "kk": "КАССАЛЫҚ ОПЕРАЦИЯЛАР",
    "en": "CASH TRANSACTIONS"
  },
  "Анализ": {
    "kk": "Талдау",
    "en": "Analysis of"
  },
  "кассовых операций": {
    "kk": "кассалық операцияларды",
    "en": "cash transactions"
  },
  "Загрузите запись, чтобы проверить события по таймкодам, кадрам и нормативным источникам.": {
    "kk": "Оқиғаларды таймкодтар, кадрлар және нормативтік дереккөздер арқылы тексеру үшін жазбаны жүктеңіз.",
    "en": "Upload a recording to review events using timecodes, frames and regulatory sources."
  },
  "Посмотреть пример": {
    "kk": "Мысалды көру",
    "en": "View example"
  },
  "СХЕМА АНАЛИЗА": {
    "kk": "ТАЛДАУ СЫЗБАСЫ",
    "en": "ANALYSIS DIAGRAM"
  },
  "Запись": {
    "kk": "Жазба",
    "en": "Recording"
  },
  "Событие": {
    "kk": "Оқиға",
    "en": "Event"
  },
  "Доказательство": {
    "kk": "Дәлел",
    "en": "Evidence"
  },
  "События с таймкодами": {
    "kk": "Таймкодтары бар оқиғалар",
    "en": "Events with timecodes"
  },
  "Связь с правилами": {
    "kk": "Ережелермен байланыс",
    "en": "Links to rules"
  },
  "Локальный анализ": {
    "kk": "Жергілікті талдау",
    "en": "Local analysis"
  },
  "ЗАГРУЗКА ВИДЕО": {
    "kk": "БЕЙНЕНІ ЖҮКТЕУ",
    "en": "VIDEO UPLOAD"
  },
  "Новая проверка": {
    "kk": "Жаңа тексеру",
    "en": "New check"
  },
  "Выберите MOV. После обработки откроется результат с найденными событиями.": {
    "kk": "MOV файлын таңдаңыз. Өңдеуден кейін табылған оқиғалар көрсетілген нәтиже ашылады.",
    "en": "Choose a MOV. After processing, the result will show any events found."
  },
  "Выберите запись": {
    "kk": "Жазбаны таңдаңыз",
    "en": "Choose a recording"
  },
  "Дождитесь анализа": {
    "kk": "Талдауды күтіңіз",
    "en": "Wait for analysis"
  },
  "Проверьте события": {
    "kk": "Оқиғаларды тексеріңіз",
    "en": "Review events"
  },
  "Без облачных AI-сервисов": {
    "kk": "Бұлттық AI сервистерінсіз",
    "en": "Without cloud AI services"
  },
  "Загрузить видеозапись": {
    "kk": "Бейнежазбаны жүктеу",
    "en": "Upload recording"
  },
  "Выбрать видеозапись": {
    "kk": "Бейнежазбаны таңдау",
    "en": "Choose a recording"
  },
  "Загрузить видео: нажмите или перетащите файл": {
    "kk": "Бейнені жүктеу: басыңыз немесе файлды сүйреңіз",
    "en": "Upload video: click or drag a file"
  },
  "Перетащите видео сюда": {
    "kk": "Бейнені осында сүйреңіз",
    "en": "Drag your video here"
  },
  "или выберите файл на компьютере": {
    "kk": "немесе компьютерден файл таңдаңыз",
    "en": "or choose a file on your computer"
  },
  "Выбрать видео": {
    "kk": "Бейнені таңдау",
    "en": "Choose video"
  },
  "MOV · до 128 МБ": {
    "kk": "MOV · 128 МБ-қа дейін",
    "en": "MOV · up to 128 MB"
  },
  "МБ": {
    "kk": "МБ",
    "en": "MB"
  },
  "Предпросмотр недоступен в этом браузере. Файл можно отправить на анализ.": {
    "kk": "Бұл браузерде алдын ала қарау қолжетімсіз. Файлды талдауға жіберуге болады.",
    "en": "Preview is unavailable in this browser. You can still submit the file for analysis."
  },
  "Убрать файл": {
    "kk": "Файлды алып тастау",
    "en": "Remove file"
  },
  "Отменить ожидание": {
    "kk": "Күтуді тоқтату",
    "en": "Cancel waiting"
  },
  "{progress}% загружено": {
    "kk": "{progress}% жүктелді",
    "en": "{progress}% uploaded"
  },
  "Ожидаем результат сервера · до 5 минут": {
    "kk": "Сервер нәтижесін күту · 5 минутқа дейін",
    "en": "Waiting for the server · up to 5 minutes"
  },
  "API настроен для отправки записи": {
    "kk": "Жазбаны жіберу үшін API бапталды",
    "en": "API configured to upload recordings"
  },
  "Для анализа своей записи подключите API": {
    "kk": "Өз жазбаңызды талдау үшін API қосыңыз",
    "en": "Connect the API to analyse your recording"
  },
  "Начать проверку": {
    "kk": "Тексеруді бастау",
    "en": "Start check"
  },
  "РАБОЧЕЕ ПРОСТРАНСТВО": {
    "kk": "ЖҰМЫС КЕҢІСТІГІ",
    "en": "WORKSPACE"
  },
  "Записи и результаты текущего сеанса.": {
    "kk": "Ағымдағы сеанстың жазбалары мен нәтижелері.",
    "en": "Recordings and results from this session."
  },
  "Этапы обработки видео": {
    "kk": "Бейнені өңдеу кезеңдері",
    "en": "Video processing stages"
  },
  "Ваши проверки": {
    "kk": "Сіздің тексерулеріңіз",
    "en": "Your checks"
  },
  "Все проверки": {
    "kk": "Барлық тексерулер",
    "en": "All checks"
  },
  "Найти проверку...": {
    "kk": "Тексеруді іздеу...",
    "en": "Search checks..."
  },
  "Найти проверку": {
    "kk": "Тексеруді іздеу",
    "en": "Search checks"
  },
  "Очистить поиск": {
    "kk": "Іздеуді тазалау",
    "en": "Clear search"
  },
  "Вид проверок": {
    "kk": "Тексерулер көрінісі",
    "en": "Check view"
  },
  "Таблица": {
    "kk": "Кесте",
    "en": "Table"
  },
  "Папки": {
    "kk": "Бумалар",
    "en": "Folders"
  },
  "Удалить выбранные ({count})": {
    "kk": "Таңдалғандарды жою ({count})",
    "en": "Delete selected ({count})"
  },
  "Примеры отмечены в таблице. Реальные проверки хранятся в текущем сеансе.": {
    "kk": "Мысалдар кестеде белгіленген. Нақты тексерулер ағымдағы сеанста сақталады.",
    "en": "Examples are marked in the table. Real checks are kept in this session."
  },
  "{visible} из {total}": {
    "kk": "{total} ішінен {visible}",
    "en": "{visible} of {total}"
  },
  "Проверка сотрудником": {
    "kk": "Қызметкердің тексеруі",
    "en": "Human review"
  },
  "Перед подтверждением события просмотрите фрагмент и проверьте указанный источник.": {
    "kk": "Оқиғаны растау алдында үзіндіні қарап, көрсетілген дереккөзді тексеріңіз.",
    "en": "Review the clip and the cited source before confirming an event."
  },
  "Подробнее о принципе работы": {
    "kk": "Жұмыс қағидаты туралы толығырақ",
    "en": "More about how it works"
  },
  "Анализ кассовых операций": {
    "kk": "Кассалық операцияларды талдау",
    "en": "Cash transaction analysis"
  },
  "О проекте": {
    "kk": "Жоба туралы",
    "en": "About the project"
  },
  "Закрыть уведомление": {
    "kk": "Хабарламаны жабу",
    "en": "Dismiss notification"
  },
  "Кадр-доказательство": {
    "kk": "Дәлел кадры",
    "en": "Evidence frame"
  },
  "Закрыть кадр": {
    "kk": "Кадрды жабу",
    "en": "Close frame"
  },
  "Кадр-доказательство в полном размере": {
    "kk": "Толық өлшемдегі дәлел кадры",
    "en": "Full-size evidence frame"
  },
  "Закрыть окно": {
    "kk": "Терезені жабу",
    "en": "Close dialog"
  },
  "Параметры API сохранены на время сеанса": {
    "kk": "API параметрлері сеанс уақытына сақталды",
    "en": "API settings saved for this session"
  },
  "API отключён": {
    "kk": "API ажыратылды",
    "en": "API disconnected"
  },
  "Как проверить запись": {
    "kk": "Жазбаны қалай тексеруге болады",
    "en": "How to check a recording"
  },
  "Рабочее пространство для анализа визуально наблюдаемых действий при кассовых операциях.": {
    "kk": "Кассалық операциялар кезіндегі көзге көрінетін әрекеттерді талдауға арналған жұмыс кеңістігі.",
    "en": "A workspace for analysing visible actions during cash transactions."
  },
  "Загрузите запись": {
    "kk": "Жазбаны жүктеңіз",
    "en": "Upload a recording"
  },
  "Выберите MOV и укажите выданный API-ключ.": {"kk": "MOV файлын таңдап, берілген API кілтін енгізіңіз.", "en": "Choose a MOV and enter the supplied API key."},
  "Дождитесь результата": {
    "kk": "Нәтижені күтіңіз",
    "en": "Wait for the result"
  },
  "Интерфейс отправляет видео на ваш сервер и запрашивает статус обработки.": {
    "kk": "Интерфейс бейнені серверіңізге жіберіп, өңдеу күйін сұрайды.",
    "en": "The interface uploads the video to your server and requests its processing status."
  },
  "Рассмотрите события": {
    "kk": "Оқиғаларды қараңыз",
    "en": "Review the events"
  },
  "Откройте таймкод, изучите кадры, описание действия и нормативный источник.": {
    "kk": "Таймкодты ашып, кадрларды, әрекет сипаттамасын және нормативтік дереккөзді зерттеңіз.",
    "en": "Open a timecode and examine the frames, action description and regulatory source."
  },
  "Для проверки записи введите выданный API-ключ. Адрес можно оставить пустым: сервер работает на этом же домене. Условные примеры помечены отдельно.": {"kk": "Жазбаны тексеру үшін берілген API кілтін енгізіңіз. Сервер осы доменде жұмыс істейді, мекенжайды бос қалдыруға болады. Шартты мысалдар бөлек белгіленген.", "en": "Enter the supplied API key to review a recording. Leave the address blank to use the server on this domain. Illustrative examples are separately labelled."},
  "Всё понятно": {
    "kk": "Түсінікті",
    "en": "Got it"
  },
  "НОРМАТИВНЫЙ ИСТОЧНИК": {
    "kk": "НОРМАТИВТІК ДЕРЕККӨЗ",
    "en": "REGULATORY SOURCE"
  },
  "Открыть источник": {
    "kk": "Дереккөзді ашу",
    "en": "Open source"
  },
  "ИСТОЧНИК НЕ УКАЗАН": {
    "kk": "ДЕРЕККӨЗ КӨРСЕТІЛМЕГЕН",
    "en": "NO SOURCE PROVIDED"
  },
  "Источник не передан": {
    "kk": "Дереккөз жіберілмеді",
    "en": "Source not provided"
  },
  "В результате нет документа и раздела правила. Проверьте основание перед подтверждением события.": {
    "kk": "Нәтижеде құжат пен ереже бөлімі жоқ. Оқиғаны растау алдында негізді тексеріңіз.",
    "en": "The result includes no document or rule section. Verify the basis before confirming the event."
  },
  "Укажите HTTPS-адрес без ключей и параметров. HTTP доступен только для localhost.": {
    "kk": "Кілттер мен параметрлерсіз HTTPS мекенжайын көрсетіңіз. HTTP тек localhost үшін қолжетімді.",
    "en": "Enter an HTTPS address without keys or parameters. HTTP is available only for localhost."
  },
  "ПОДКЛЮЧЕНИЕ": {
    "kk": "ҚОСЫЛЫМ",
    "en": "CONNECTION"
  },
  "Подключение к серверу": {
    "kk": "Серверге қосылу",
    "en": "Server connection"
  },
  "Укажите адрес API и ключ для обработки записей на сервере команды.": {
    "kk": "Команда серверінде жазбаларды өңдеу үшін API мекенжайы мен кілтін көрсетіңіз.",
    "en": "Enter the API address and key to process recordings on the team's server."
  },
  "Адрес сервера": {
    "kk": "Сервер мекенжайы",
    "en": "Server address"
  },
  "Оставьте пустым для API на этом же домене.": {
    "kk": "API осы доменде болса, бос қалдырыңыз.",
    "en": "Leave blank for an API on the same domain."
  },
  "API-ключ": {
    "kk": "API кілті",
    "en": "API key"
  },
  "Ключ хранится в памяти до перезагрузки страницы.": {
    "kk": "Кілт бет қайта жүктелгенге дейін жадта сақталады.",
    "en": "The key stays in memory until the page reloads."
  },
  "На этом сайте адрес сервера можно оставить пустым. Для API на другом домене нужны HTTPS и разрешённый CORS.": {"kk": "Бұл сайтта сервер мекенжайын бос қалдыруға болады. Басқа домендегі API үшін HTTPS және CORS рұқсаты қажет.", "en": "Leave the server address blank on this site. An API on another domain requires HTTPS and CORS permission."},
  "Сохранить подключение": {
    "kk": "Қосылымды сақтау",
    "en": "Save connection"
  },
  "Отключить API": {
    "kk": "API ажырату",
    "en": "Disconnect API"
  },
  "Все результаты": {
    "kk": "Барлық нәтижелер",
    "en": "All results"
  },
  "Все записи текущего сеанса": {
    "kk": "Ағымдағы сеанстың барлық жазбалары",
    "en": "All recordings in this session"
  },
  "Требуют проверки": {
    "kk": "Тексеруді қажет етеді",
    "en": "Needs review"
  },
  "Есть признаки возможных нарушений": {
    "kk": "Ықтимал бұзушылық белгілері бар",
    "en": "Possible signs of violations"
  },
  "Без замечаний": {
    "kk": "Ескертусіз",
    "en": "No issues"
  },
  "Сервис не обнаружил событий": {
    "kk": "Сервис оқиғаларды анықтамады",
    "en": "The service found no events"
  },
  "Фильтр по результату проверки": {
    "kk": "Тексеру нәтижесі бойынша сүзгі",
    "en": "Filter by check result"
  },
  "Укажите полный адрес сервера, например https://analysis.example.kz.": {
    "kk": "Сервердің толық мекенжайын көрсетіңіз, мысалы https://analysis.example.kz.",
    "en": "Enter the full server address, for example https://analysis.example.kz."
  },
  "Используйте HTTPS. HTTP разрешён только для локального сервера на localhost или loopback.": {
    "kk": "HTTPS қолданыңыз. HTTP тек localhost немесе loopback мекенжайындағы жергілікті серверге рұқсат етіледі.",
    "en": "Use HTTPS. HTTP is only allowed for a local server on localhost or loopback."
  },
  "Адрес сервера не должен содержать пароль, параметры или фрагмент ссылки.": {
    "kk": "Сервер мекенжайында құпиясөз, параметрлер немесе сілтеме фрагменті болмауы керек.",
    "en": "The server address must not contain a password, parameters or URL fragment."
  },
  "Сервер отклонил доступ. Проверьте API-ключ в настройках подключения.": {
    "kk": "Сервер рұқсат бермеді. Қосылым баптауларындағы API кілтін тексеріңіз.",
    "en": "Server access denied. Check the API key in connection settings."
  },
  "Файл превышает ограничение размера на сервере.": {
    "kk": "Файл көлемі сервер шектеуінен асады.",
    "en": "The file exceeds the server's size limit."
  },
  "Сервер не поддерживает этот формат видео. Выберите запись .mov.": {
    "kk": "Сервер бұл бейне форматын қолдамайды. .mov жазбасын таңдаңыз.",
    "en": "The server does not support this video format. Choose a .mov recording."
  },
  "Сервер занят. Повторите попытку немного позже.": {
    "kk": "Сервер бос емес. Біраздан кейін қайталап көріңіз.",
    "en": "The server is busy. Try again shortly."
  },
  "Сервер анализа вернул ошибку HTTP {status}. Попробуйте повторить запрос.": {
    "kk": "Талдау сервері HTTP {status} қатесін қайтарды. Сұрауды қайталап көріңіз.",
    "en": "The analysis server returned HTTP {status}. Try the request again."
  },
  "Не удалось связаться с сервером. Проверьте адрес, доступность сервера, HTTPS и настройки CORS.": {
    "kk": "Серверге қосылу мүмкін болмады. Мекенжайды, сервер қолжетімділігін, HTTPS және CORS баптауларын тексеріңіз.",
    "en": "Could not reach the server. Check its address, availability, HTTPS and CORS settings."
  },
  "Анализ отменён.": {
    "kk": "Талдау тоқтатылды.",
    "en": "Analysis cancelled."
  },
  "Выбранный файл пуст. Выберите другую запись.": {
    "kk": "Таңдалған файл бос. Басқа жазбаны таңдаңыз.",
    "en": "The selected file is empty. Choose another recording."
  },
  "Выберите видео в формате .mov.": {
    "kk": ".mov форматындағы бейнені таңдаңыз.",
    "en": "Choose a .mov video."
  },
  "Сервер не смог обработать запись. Попробуйте другое видео.": {
    "kk": "Сервер жазбаны өңдей алмады. Басқа бейнені қолданып көріңіз.",
    "en": "The server could not process the recording. Try another video."
  },
  "Превышено время ожидания - 5 минут. Проверьте состояние сервера и повторите попытку.": {
    "kk": "Күту уақыты - 5 минут өтті. Сервер күйін тексеріп, қайталап көріңіз.",
    "en": "The 5-minute wait limit was reached. Check the server and try again."
  },
  "Сервер вернул некорректный результат: {detail}.": {
    "kk": "Сервер қате нәтиже қайтарды: {detail}.",
    "en": "The server returned an invalid result: {detail}."
  },
  "не заполнен нормативный источник": {
    "kk": "нормативтік дереккөз толтырылмаған",
    "en": "regulatory source is missing"
  },
  "некорректный пункт нормативного источника": {
    "kk": "нормативтік дереккөз тармағы қате",
    "en": "invalid regulatory source section"
  },
  "некорректная ссылка на источник": {
    "kk": "дереккөз сілтемесі қате",
    "en": "invalid source URL"
  },
  "ссылка на источник должна начинаться с http или https": {
    "kk": "дереккөз сілтемесі http немесе https арқылы басталуы керек",
    "en": "source URL must start with http or https"
  },
  "не заполнены поля события {number}": {
    "kk": "{number}-оқиғаның өрістері толтырылмаған",
    "en": "fields missing for event {number}"
  },
  "некорректный кадр события {number}": {
    "kk": "{number}-оқиғаның кадры қате",
    "en": "invalid frame for event {number}"
  },
  "некорректный идентификатор события {number}": {
    "kk": "{number}-оқиғаның идентификаторы қате",
    "en": "invalid ID for event {number}"
  },
  "отсутствует job_id": {
    "kk": "job_id жоқ",
    "en": "job_id is missing"
  },
  "идентификатор задания изменился": {
    "kk": "тапсырма идентификаторы өзгерді",
    "en": "job ID changed"
  },
  "неизвестный статус задания": {
    "kk": "тапсырма күйі белгісіз",
    "en": "unknown job status"
  },
  "некорректный прогресс обработки": {
    "kk": "өңдеу барысы қате",
    "en": "invalid processing progress"
  },
  "некорректное сообщение об ошибке": {
    "kk": "қате туралы хабарлама дұрыс емес",
    "en": "invalid error message"
  },
  "отсутствует итоговый verdict": {
    "kk": "қорытынды verdict жоқ",
    "en": "final verdict is missing"
  },
  "отсутствует список violations": {
    "kk": "violations тізімі жоқ",
    "en": "violations list is missing"
  },
  "не указаны найденные события": {
    "kk": "табылған оқиғалар көрсетілмеген",
    "en": "detected events are missing"
  },
  "вердикт противоречит списку событий": {
    "kk": "қорытынды оқиғалар тізіміне қайшы",
    "en": "verdict contradicts the event list"
  },
  "ожидался ответ JSON": {
    "kk": "JSON жауабы күтілді",
    "en": "expected a JSON response"
  },
  "Настройки интерфейса": {
    "kk": "Интерфейс баптаулары",
    "en": "Interface settings"
  },
  "Язык и оформление": {
    "kk": "Тіл және безендіру",
    "en": "Language and appearance"
  },
  "Интервалы событий": {
    "kk": "Оқиғалар аралықтары",
    "en": "Event intervals"
  },
  "Время записи": {
    "kk": "Жазба уақыты",
    "en": "Recording time"
  },
  "Контекст ±3 с": {
    "kk": "Контекст ±3 с",
    "en": "Context ±3 s"
  },
  "Событие {number}: {type}. Фрагмент {start}–{end}": {
    "kk": "{number}-оқиға: {type}. Үзінді {start}–{end}",
    "en": "Event {number}: {type}. Clip {start}–{end}"
  },
  "Событие {number}": {
    "kk": "{number}-оқиға",
    "en": "Event {number}"
  },
  "Фрагмент включает до 3 секунд до и после таймкода события.": {
    "kk": "Үзінді оқиға таймкодына дейінгі және кейінгі 3 секундты қамтиды.",
    "en": "The clip includes up to 3 seconds before and after the event timestamp."
  },
  "Таймкод события: {time}": {
    "kk": "Оқиға таймкоды: {time}",
    "en": "Event timestamp: {time}"
  },
  "К видеозаписи": {
    "kk": "Бейнежазбаға оралу",
    "en": "Back to recording"
  },
  "Событие {number} из {count}": {
    "kk": "{count} оқиғаның {number}-сі",
    "en": "Event {number} of {count}"
  },
  "Смотреть фрагмент": {
    "kk": "Үзіндіні көру",
    "en": "Watch clip"
  },
  "Показать интервал": {
    "kk": "Аралықты көрсету",
    "en": "Show interval"
  },
  "Переключение событий": {
    "kk": "Оқиғалар арасында ауысу",
    "en": "Event navigation"
  },
  "Предыдущее": {
    "kk": "Алдыңғы",
    "en": "Previous"
  },
  "Следующее": {
    "kk": "Келесі",
    "en": "Next"
  },
  "Что произошло": {
    "kk": "Не болды",
    "en": "What happened"
  },
  "Просмотр фрагмента": {
    "kk": "Үзіндіні қарау",
    "en": "Clip playback"
  },
  "Вся запись": {
    "kk": "Толық жазба",
    "en": "Whole recording"
  },
  "Нажмите кнопку воспроизведения на видео.": {
    "kk": "Бейнедегі ойнату түймесін басыңыз.",
    "en": "Press the play button on the video."
  },
  "Нажмите на «!», чтобы открыть разбор события.": {
    "kk": "Оқиғаны қарау үшін «!» белгісін басыңыз.",
    "en": "Select an ! marker to open the event review."
  },

  "Выберите файл размером до 10 ГиБ.": {
    "kk": "Өлшемі 10 ГиБ-қа дейінгі файлды таңдаңыз.",
    "en": "Choose a file up to 10 GiB."
  },
  "MOV · до 10 ГиБ": {
    "kk": "MOV · 10 ГиБ-қа дейін",
    "en": "MOV · up to 10 GiB"
  },
  "Повторить подключение": {
    "kk": "Қайта қосылу",
    "en": "Reconnect"
  },
  "Не удалось подключиться к серверу. Повторите подключение.": {
    "kk": "Серверге қосылу мүмкін болмады. Қайта қосылып көріңіз.",
    "en": "Unable to connect. Try reconnecting."
  },
  "Загрузите запись. Документы из результата появятся в этом разделе.": {
    "kk": "Бейнежазбаны жүктеңіз. Нәтижедегі құжаттар осы бөлімде пайда болады.",
    "en": "Upload a recording. Sources from the result will appear here."
  },
  "Выберите MOV. Сервер подключается автоматически.": {
    "kk": "MOV таңдаңыз. Сервер автоматты түрде қосылады.",
    "en": "Choose a MOV file. The server connects automatically."
  },
  "Загрузите видео и запустите проверку. Условные примеры помечены отдельно.": {
    "kk": "Бейнежазбаны жүктеп, тексеруді бастаңыз. Шартты мысалдар бөлек белгіленген.",
    "en": "Upload a video and start a check. Illustrative examples are labelled."
  },

  "Запись в очереди. Заданий впереди: {count}": {
    "kk": "Бейне кезекте. Алдағы тапсырмалар: {count}",
    "en": "Recording queued. Jobs ahead: {count}"
  },
  "Сервер анализирует видео. Результат появится автоматически.": {
    "kk": "Сервер бейнені талдап жатыр. Нәтиже автоматты түрде пайда болады.",
    "en": "The server is analysing the video. The result will appear automatically."
  },
  "Ожидание восстановлено после перезагрузки. Продолжите проверку.": {
    "kk": "Күту қайта жүктеуден кейін қалпына келтірілді. Тексеруді жалғастырыңыз.",
    "en": "Waiting restored after reload. Resume the check."
  }

} satisfies Messages;
