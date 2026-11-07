"""Одноразовая миграция старого CSV в коллекцию reminders.

Использование (из корня проекта):
    python3 scripts/migrate_from_csv.py tmp/reminders.csv [--wipe]

`--wipe` — предварительно очистить коллекцию reminders (events не трогаем).
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pymongo import MongoClient

from app.config import Config
from app.utils import now_utc, compute_next_activate


UNITS = {'d': 'day', 'w': 'week', 'm': 'month', 'y': 'year'}


def parse_periodic(period: str) -> dict | None:
    if not period or period.lower() in ('none', 'oneshot', '-'):
        return None
    short = period[-1]
    if short not in UNITS:
        raise ValueError(f'Unknown period unit: {period}')
    return {'type': 'static', 'unit': UNITS[short], 'number': int(period[:-1])}


def fast_forward(dt: datetime, periodic: dict | None, now: datetime) -> datetime:
    """Промотать dt вперёд по periodic до ближайшего будущего."""
    if dt > now or not periodic:
        return dt
    for _ in range(1000):
        dt = compute_next_activate(periodic, dt)
        if dt > now:
            return dt
    return compute_next_activate(periodic, now)


def parse_row(row: dict, now: datetime) -> dict:
    periodic = parse_periodic(row.get('period', ''))
    oneshot = periodic is None
    auto = row.get('auto', '0') == '1'
    sended_in_csv = row.get('sended', '0') == '1'
    activate = datetime.strptime(row['date'], '%Y.%m.%d')

    archived = False
    sended = False

    if oneshot:
        # Одноразовое, уже отправленное в прошлом — сразу в архив.
        if sended_in_csv and activate <= now:
            archived = True
    elif auto:
        # Авто-отправка: fast_forward обязателен (иначе catch-up пачкой).
        # sended игнорируем — начнём с чистого листа.
        if activate <= now:
            activate = fast_forward(activate, periodic, now)
        sended = False
    else:
        # Трекинг по карточке (auto=0):
        #   sended=1 → карточка уже создана старой утилитой, висит в Wekan,
        #              не пересоздаём. Пользователь сам найдёт её в Wekan
        #              и закроет, а потом нажмёт «Отложить» здесь.
        #   sended=0 → сработает штатно, когда наступит дата.
        # activate_datetime не трогаем — «просроченные» должны оставаться
        # в прошлом, чтобы было видно, что они ждут внимания.
        sended = sended_in_csv

    return {
        'text': row['text'].replace('\\n', '\n'),
        'description': '',
        'board': row['board'],
        'activate_datetime': activate,
        'create_datetime': now,
        'last_send_datetime': None,
        'auto_postpone': auto,
        'sended': sended,
        'archived': archived,
        'oneshot': oneshot,
        'link_to_wekan_card': None,
        'periodic': periodic,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_path')
    parser.add_argument('--wipe', action='store_true')
    args = parser.parse_args()

    with open(args.csv_path, encoding='utf-8') as f:
        lines = f.read().splitlines()

    keys = lines.pop(0).split(';')
    now = now_utc()
    documents = []
    for line in lines:
        values = line.split(';')
        if len(values) != len(keys):
            print(f'Skip malformed line: {line[:60]}…', file=sys.stderr)
            continue
        documents.append(parse_row(dict(zip(keys, values)), now))

    client = MongoClient(Config.MONGO_URI)
    collection = client.get_database()['reminders']

    if args.wipe:
        deleted = collection.delete_many({})
        print(f'Deleted: {deleted.deleted_count}')

    if documents:
        result = collection.insert_many(documents)
        print(f'Inserted: {len(result.inserted_ids)}')

    client.close()


if __name__ == '__main__':
    main()