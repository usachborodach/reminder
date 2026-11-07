# Reminder

Веб-сервис напоминалок с автоматической отправкой карточек в [Wekan](https://wekan.github.io/).

Заменяет старую терминальную утилиту: напоминания хранятся в MongoDB, редактируются через веб-интерфейс, а фоновый планировщик создаёт карточки в Wekan по расписанию.

---

## Возможности

- **CRUD напоминаний** через веб-интерфейс (Flask + Bootstrap 5, тёмная тема).
- **Два режима работы**:
  - `auto_postpone = true` — «выстрелил и забыл»: карточка создаётся в Wekan, напоминание автоматически откладывается по `periodic`, за карточкой никто не следит.
  - `auto_postpone = false` — «слежение»: карточка создаётся, сервис ждёт её закрытия (архивации) в Wekan и только потом откладывает напоминание.
- **Периодичность**:
  - `static` — фиксированный шаг (`N дней/недель/месяцев/лет`).
  - `random` — случайный шаг из диапазона `[mindays, maxdays]`.
  - `oneshot` — одноразовые напоминания, после отправки уходят в архив.
- **Календарь** — проекция сработок на 1–2 месяца вперёд (приблизительная для отслеживаемых и `random`).
- **Архив** — просмотр и восстановление заархивированных напоминаний.
- **Лог событий** — все действия (создание, отправка, откладывание, архивация, закрытие карточки) пишутся в коллекцию `events`.
- **Ручные действия** — кнопки «Отложить», «Отправить», «В архив» у каждого напоминания.
- **Аутентификация** — единственный пользователь, задаётся через `.env`.

---

## Архитектура

```
┌─────────────────┐       ┌──────────────┐       ┌─────────────┐
│  nginx (443)    │──────▶│   gunicorn   │──────▶│  MongoDB    │
│                 │       │  (Flask app) │       │  reminder   │
└─────────────────┘       └──────────────┘       └─────────────┘
                                                          ▲
┌─────────────────┐                                       │
│   scheduler.py  │───────────────────────────────────────┘
│  (while True)   │                                       │
└─────────────────┘                                       ▼
        │                                          ┌──────────────┐
        │                                          │  MongoDB     │
        └───────── HTTP POST карточки ────────────▶│  wekan.cards │
                       (Wekan API)                 │  (read-only) │
                                                   └──────────────┘
```

- **Flask** обрабатывает веб-запросы, работает под gunicorn (2 воркера).
- **scheduler.py** — отдельный процесс, раз в `SCHEDULER_INTERVAL` секунд проходит по коллекции и обрабатывает «созревшие» напоминания.
- Разделение на два процесса позволяет не зависеть от количества gunicorn-воркеров и не запускать обработку дважды.

### Коллекции MongoDB (база `reminder`)

**`reminders`** — напоминания:

| Поле | Тип | Описание |
|---|---|---|
| `_id` | ObjectId | |
| `text` | string | Заголовок карточки Wekan |
| `description` | string | Описание карточки (опционально) |
| `board` | string | Имя доски Wekan (`home`, `work`, …) |
| `activate_datetime` | datetime (UTC) | Когда должна сработать |
| `create_datetime` | datetime (UTC) | |
| `last_send_datetime` | datetime / null | |
| `sended` | bool | Отправлено ли уже |
| `auto_postpone` | bool | См. выше |
| `oneshot` | bool | Одноразовое |
| `periodic` | object / null | `{type: 'static', unit, number}` или `{type: 'random', mindays, maxdays}` |
| `link_to_wekan_card` | string / null | `_id` карточки в Wekan (только при `auto_postpone=false`) |
| `archived` | bool | |

**`events`** — append-only лог:

| Поле | Тип | Описание |
|---|---|---|
| `_id` | ObjectId | |
| `reminder_id` | ObjectId | |
| `reminder_text` | string | Дублируется для удобства |
| `type` | string | `created`, `updated`, `sent`, `sent_oneshot`, `postponed`, `postponed_manual`, `archived`, `archived_auto`, `unarchived`, `card_closed`, `send_failed` |
| `datetime` | datetime (UTC) | |
| `details` | object | |

**`wekan.cards`** (внешняя БД `wekan`, read-only) — используется только для проверки `archived` у связанных карточек.

### Логика планировщика

На каждой итерации (`SCHEDULER_INTERVAL`, по умолчанию 60 секунд):

1. `auto_postpone=true, activate_datetime <= now` → отправить в Wekan, `sended=true`, `activate_datetime += periodic`.
2. `auto_postpone=false, sended=false, activate_datetime <= now` → отправить, `sended=true`, запомнить `link_to_wekan_card`.
3. `auto_postpone=false, sended=true, link_to_wekan_card != null` → проверить карточку в `wekan.cards`. Если `archived` или карточки нет — `sended=false`, `link_to_wekan_card=null`, `activate_datetime = now + periodic`.

Для `oneshot=true` после отправки сразу `archived=true`.

---

## Установка

```bash
apt install python3.10-venv
git clone <repo> reminder
cd reminder
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate
```

MongoDB должна быть установлена и доступна (по умолчанию `mongodb://localhost:27017`). Отдельно нужна база `wekan` (если используется режим слежения за карточками).

---

## Конфигурация

```bash
cp .env.example .env
```

Сгенерировать секреты:

```bash
# SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# PASSWORD_HASH
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('мой_пароль'))"
```

### Переменные `.env`

| Переменная | Обязательно | Описание |
|---|---|---|
| `SECRET_KEY` | да | Ключ Flask-сессий |
| `USERNAME` | да | Логин для входа в веб-интерфейс |
| `PASSWORD_HASH` | да | Хэш пароля (`werkzeug.security`) |
| `MONGO_URI` | нет | По умолчанию `mongodb://localhost:27017/reminder` |
| `WEKAN_MONGO_URI` | нет | Если база Wekan на другом инстансе. По умолчанию = `MONGO_URI` |
| `WEKAN_MONGO_DB` | нет | По умолчанию `wekan` |
| `TIMEZONE` | нет | По умолчанию `Europe/Moscow`. Влияет только на ввод/вывод, в БД всё в UTC |
| `SCHEDULER_INTERVAL` | нет | Интервал планировщика в секундах (по умолчанию 60) |
| `WEKAN_URL` | да* | Например, `https://wekan.example.com` |
| `WEKAN_LOGIN` | да* | |
| `WEKAN_PASSWORD` | да* | |
| `WEKAN_AUTHOR_ID` | да* | `_id` пользователя Wekan, от имени которого создаются карточки |
| `WEKAN_BOARDS` | да* | JSON: `{"home": {"board_id": "...", "list_id": "...", "swimlane_id": "..."}, ...}` |

\* — нужно только если отправка в Wekan действительно используется.

Пример `WEKAN_BOARDS`:

```json
{
  "home": {
    "board_id": "eyZsGfRcPAysgBbB3",
    "list_id": "uj8XTX37dMJT7SByr",
    "swimlane_id": "Qh75JghWz3eyAhY9K"
  },
  "work": {
    "board_id": "6nEeTCXHcdq3GaqoT",
    "list_id": "WwR4yf6LbzKgnhaLx",
    "swimlane_id": "xbct7XafyWxqGhhWq"
  }
}
```

Значения `board_id`, `list_id`, `swimlane_id` можно подсмотреть в URL доски Wekan или в MongoDB коллекциях `boards`, `lists`, `swimlanes`.

---

## Миграция старого CSV

Если у вас есть старый CSV с напоминаниями (формат: `date;board;period;auto;sended;text`):

```bash
source .venv/bin/activate
python3 scripts/migrate_from_csv.py tmp/reminders.csv --wipe
```

- `--wipe` — предварительно очистить коллекцию `reminders` (события в `events` не трогаются).
- Поле `oneshot` выставляется автоматически, если в колонке `period` пусто или указан `-`.
- `link_to_wekan_card` всегда `null` — старые данные не хранят связи с карточками.

---

## Локальный запуск

```bash
source .venv/bin/activate

# создать индексы
flask --app wsgi create-index

# веб (порт 8002)
python run.py

# в отдельном терминале — планировщик
python scripts/scheduler.py
```

Одноразовый прогон обработки (для отладки):

```bash
flask --app wsgi process-now
```

---

## Продакшен (systemd + nginx + gunicorn)

Предполагается, что проект лежит в `/root/reminder`.

```bash
# логи
mkdir -p /var/log/reminder

# systemd-юниты
ln -sf /root/reminder/deploy/reminder.service \
       /etc/systemd/system/reminder.service
ln -sf /root/reminder/deploy/reminder-scheduler.service \
       /etc/systemd/system/reminder-scheduler.service
systemctl daemon-reload
systemctl enable --now reminder reminder-scheduler
systemctl status reminder reminder-scheduler

# nginx
ln -sf /root/reminder/deploy/nginx.conf \
       /etc/nginx/sites-enabled/reminder
nginx -t && systemctl restart nginx

# logrotate
ln -sf /root/reminder/deploy/reminder.logrotate \
       /etc/logrotate.d/reminder
```

Сертификаты Let's Encrypt кладутся в `/etc/nginx/ssl/reminder.usachborodach.ru.{crt,key}` (в nginx.conf поменяйте `server_name` и пути под свой домен).

После изменений:

```bash
systemctl restart reminder reminder-scheduler
```

---

## Тесты

```bash
source .venv/bin/activate
pytest -q
```

---

## Структура проекта

```
reminder
├── app/
│   ├── templates/        # Jinja2-шаблоны
│   ├── __init__.py       # create_app, фильтры Jinja
│   ├── auth.py           # логин/логаут
│   ├── cli.py            # create-index, process-now
│   ├── config.py         # конфиг из .env
│   ├── extensions.py     # Mongo, Login, Limiter
│   ├── main.py           # все роуты UI
│   ├── models.py         # работа с reminders/events, логика отправки
│   ├── scheduler.py      # одна итерация обработки
│   ├── utils.py          # таймзоны, periodic, проекции
│   └── wekan.py          # HTTP-клиент Wekan
├── deploy/               # nginx, systemd, logrotate
├── scripts/
│   ├── migrate_from_csv.py
│   └── scheduler.py      # точка входа фонового процесса
├── tests/
├── .env.example
├── .gitignore
├── README.md
├── pytest.ini
├── requirements.txt
├── run.py                # dev-запуск (Flask dev server)
└── wsgi.py               # точка входа gunicorn
```

---

## Ручные операции (curl / flask shell)

Проверить, что планировщик видит напоминание, можно так:

```bash
flask --app wsgi shell
```

```python
from app.extensions import get_db
from app.utils import now_utc
db = get_db()
db.reminders.find_one({'archived': False, 'activate_datetime': {'$lte': now_utc()}})
```

Принудительно обработать:

```bash
flask --app wsgi process-now
```

---

## Известные ограничения

- **Один пользователь** — многопользовательский режим не предусмотрен, `USERNAME`/`PASSWORD_HASH` в `.env`.
- **Нет идемпотентности при двойном нажатии «Отправить»** — теоретически может создать две карточки. Для личного использования приемлемо; при необходимости легко закрывается через `find_one_and_update` до постинга.
- **Календарь приблизительный** для `auto_postpone=false` и `random` — точная дата следующей сработки зависит от того, когда закроется карточка в Wekan.
- **`periodic` типа `random` не проецируется в календарь** — только текущая `activate_datetime`.

---

## Лицензия

Личный проект, без явной лицензии.