"""One-time copy alignment for the supplied frontend; no ML package edits."""
from pathlib import Path
root = Path(__file__).resolve().parents[1] / 'forte-vision'
for name in ['components/forte-workspace.tsx', 'lib/messages/workspace.ts']:
    path = root / name
    path.write_text(path.read_text(encoding='utf-8').replace('250', '128'), encoding='utf-8')

replacements = {
    'Сейчас доступен фронтенд. Примеры иллюстрируют интерфейс. Модель и сервер подключаются отдельно.': (
        'Для проверки записи введите выданный API-ключ. Адрес можно оставить пустым: сервер работает на этом же домене. Условные примеры помечены отдельно.',
        'Жазбаны тексеру үшін берілген API кілтін енгізіңіз. Сервер осы доменде жұмыс істейді, мекенжайды бос қалдыруға болады. Шартты мысалдар бөлек белгіленген.',
        'Enter the supplied API key to review a recording. Leave the address blank to use the server on this domain. Illustrative examples are separately labelled.'),
    'Выберите MOV. Для анализа укажите адрес API команды.': (
        'Выберите MOV и укажите выданный API-ключ.', 'MOV файлын таңдап, берілген API кілтін енгізіңіз.', 'Choose a MOV and enter the supplied API key.'),
    'Для размещённого сайта нужен HTTPS-сервер с разрешённым CORS. Локальный API подключайте при локальном запуске фронтенда.': (
        'На этом сайте адрес сервера можно оставить пустым. Для API на другом домене нужны HTTPS и разрешённый CORS.',
        'Бұл сайтта сервер мекенжайын бос қалдыруға болады. Басқа домендегі API үшін HTTPS және CORS рұқсаты қажет.',
        'Leave the server address blank on this site. An API on another domain requires HTTPS and CORS permission.'),
    'Демонстрация показывает заранее подготовленный пример работы интерфейса. Она не анализирует загруженное видео. Обработка собственных записей станет доступна после подключения сервиса анализа.': (
        'Демонстрация показывает условный пример интерфейса. Для анализа своей записи откройте рабочее пространство, введите API-ключ и загрузите MOV.',
        'Демонстрация интерфейстің шартты мысалын көрсетеді. Өз жазбаңызды талдау үшін жұмыс кеңістігін ашып, API кілтін енгізіңіз және MOV жүктеңіз.',
        'The demo is an illustrative interface example. To analyse your recording, open the workspace, enter the API key and upload a MOV.'),
    'Обработка, хранение и удаление данных на подключённом сервере зависят от этого сервера. Отмена ожидания в интерфейсе не гарантирует остановку задания на сервере.': (
        'На сервере этого сайта исходное видео удаляется после обработки или ошибки. Результат и кадры хранятся до 24 часов. Отмена ожидания не останавливает задание. Для другого API действуют правила его владельца.',
        'Бұл сайт серверінде бастапқы бейне өңдеу не қате аяқталған соң жойылады. Нәтиже мен кадрлар 24 сағатқа дейін сақталады. Күтуді тоқтату тапсырманы тоқтатпайды. Басқа API үшін оның иесінің ережелері қолданылады.',
        'On this site server, the original video is deleted after processing or failure. Results and frames are retained for up to 24 hours. Cancelling the wait does not stop the job. Other APIs follow their owners policies.'),
    'Доступен демонстрационный режим': ('Сервис подключён к локальным моделям', 'Сервис жергілікті модельдерге қосылған', 'Service connected to local models'),
    'По требованиям кейса обработка должна выполняться локально, без передачи записей в облачные AI API. В демонстрационном режиме видео не отправляется на анализ. Перед рабочим использованием необходимо подключить среду обработки организации.': (
        'Записи обрабатываются моделями на сервере команды без облачных AI API. Для проверки укажите выданный API-ключ, оставив адрес сервера пустым. Демонстрационные примеры отдельно помечены и не являются результатами анализа.',
        'Жазбалар бұлттық AI API қолданбай команда серверінде өңделеді. Тексеру үшін берілген API кілтін енгізіп, сервер мекенжайын бос қалдырыңыз. Демонстрациялық мысалдар бөлек белгіленген және талдау нәтижелері емес.',
        'Recordings are processed by models on the team server without cloud AI APIs. Enter the supplied API key and leave the server address blank. Demo examples are separately labelled and are not analysis results.'),
}
for old, (ru, kk, en) in replacements.items():
    for component in (root / 'components').glob('*.tsx'):
        content = component.read_text(encoding='utf-8')
        if old in content:
            component.write_text(content.replace(old, ru), encoding='utf-8')
    for messages in (root / 'lib/messages').glob('*.ts'):
        content = messages.read_text(encoding='utf-8')
        import re, json
        pattern = re.escape(json.dumps(old, ensure_ascii=False)) + r':\s*\{.*?\n  \}'
        replacement = json.dumps(ru, ensure_ascii=False) + ': ' + json.dumps({'kk': kk, 'en': en}, ensure_ascii=False)
        content, count = re.subn(pattern, lambda _: replacement, content, flags=re.S)
        if count:
            messages.write_text(content, encoding='utf-8')
