"""Одноразовая миграция старого CSV в коллекцию reminders.

Использование:
    python scripts/migrate_from_csv.py tmp/reminders.csv [--wipe]

`--wipe` — предварительно очистить коллекцию reminders (events не трогаем).
"""
import argparse
import sys
from datetime import datetime

from pymongo import MongoClient

from app.config import Config


UNITS = {'d': 'day', 'w': 'week', 'm': 'month', 'y': 'year'}


def parse_periodic(period: str) -> dict | None:
    if not period or period.lower() in ('none', 'oneshot', '-'):
        return None
    short = period[-1]
    if short not in UNITS:
        raise ValueError(f'Unknown period unit: {period}')
    return {'type': 'static', 'unit': UNITS[short], 'number': int(period[:-1])}


def parse_row(row: dict) -> dict:
    now = datetime.utcnow()
    periodic = parse_periodic(row.get('period', ''))
    oneshot = periodic is None
    return {
        'text': row['text'].replace('\\n', '\n'),
        'description': '',
        'board': row['board'],
        'activate_datetime': datetime.strptime(row['date'], '%Y.%m.%d'),
        'create_datetime': now,
        'last_send_datetime': None,
        'auto_postpone': row.get('auto', '0') == '1',
        'sended': row.get('sended', '0') == '1',
        'archived': False,
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
    documents = []
    for line in lines:
        values = line.split(';')
        if len(values) != len(keys):
            print(f'Skip malformed line: {line[:60]}…', file=sys.stderr)
            continue
        documents.append(parse_row(dict(zip(keys, values))))

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