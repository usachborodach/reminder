"""Назначить activate_datetime напоминаниям, у которых он равен null.

Такое состояние появлялось из-за бага в check_card_and_postpone(): если
отправленную напоминалку переделывали в oneshot (periodic=None), то при
закрытии карточки в activate_datetime писался null. Баг исправлен; этот
скрипт чинит уже испорченные документы.

По умолчанию ставит текущее время (напоминание станет «просроченным» и
сработает на следующем тике планировщика — либо его можно отложить/архивировать
из интерфейса). Своей датой — --set-datetime (локальное время из TIMEZONE).

По умолчанию — dry-run (только показывает, что будет изменено).
Чтобы применить — флаг --apply.

Использование (из корня проекта):
    python3 scripts/fix_null_activate_datetime.py                     # dry-run
    python3 scripts/fix_null_activate_datetime.py --apply             # поставить now
    python3 scripts/fix_null_activate_datetime.py --apply \
        --set-datetime 2026-11-20T09:00                               # своей датой
    python3 scripts/fix_null_activate_datetime.py --apply --log-event
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pymongo import MongoClient

from app.config import Config
from app.utils import local_to_utc, now_utc, utc_to_local


def main():
    parser = argparse.ArgumentParser(
        description='Назначить activate_datetime напоминаниям с activate_datetime=null.',
    )
    parser.add_argument(
        '--apply', action='store_true',
        help='реально записать изменения (по умолчанию dry-run)',
    )
    parser.add_argument(
        '--set-datetime', metavar='YYYY-MM-DDTHH:MM', default='',
        help='локальная дата (TIMEZONE) вместо текущего времени',
    )
    parser.add_argument(
        '--log-event', action='store_true',
        help='записать событие activate_datetime_fixed в коллекцию events для каждого',
    )
    args = parser.parse_args()

    tz = Config.TIMEZONE
    now = now_utc()
    if args.set_datetime:
        try:
            activate_local = datetime.strptime(args.set_datetime, '%Y-%m-%dT%H:%M')
        except ValueError:
            parser.error('--set-datetime must be YYYY-MM-DDTHH:MM')
        new_activate = local_to_utc(activate_local, tz)
    else:
        new_activate = now

    client = MongoClient(Config.MONGO_URI)
    db = client.get_database()
    collection = db['reminders']

    # Mongo: query {'field': None} матчит и null, и отсутствующее поле
    docs = list(collection.find({'activate_datetime': None}))

    print(f'Now (UTC):   {now.isoformat(sep=" ", timespec="seconds")}')
    print(f'New value:   {new_activate.isoformat(sep=" ", timespec="minutes")} '
          f'({utc_to_local(new_activate, tz).isoformat(sep=" ", timespec="minutes")} {tz})')
    print(f'Matched:     {len(docs)}')
    print()

    if not docs:
        print('Nothing to do.')
        client.close()
        return

    header = (
        f'{"_id":>26}  '
        f'{"archived":<8}  '
        f'{"oneshot":<7}  '
        f'text'
    )
    print(header)
    print('-' * 110)
    for d in docs:
        print(
            f'{str(d["_id"]):>26}  '
            f'{str(d.get("archived", False)):<8}  '
            f'{str(d.get("oneshot", False)):<7}  '
            f'{(d.get("text") or "")[:60]}'
        )

    if not args.apply:
        print()
        print('Dry-run. Pass --apply to actually update.')
        client.close()
        return

    ids = [d['_id'] for d in docs]
    result = collection.update_many(
        {'_id': {'$in': ids}},
        {'$set': {'activate_datetime': new_activate}},
    )
    print()
    print(f'Updated: {result.modified_count}')

    if args.log_event:
        event_docs = [
            {
                'reminder_id': d['_id'],
                'reminder_text': d.get('text', ''),
                'type': 'activate_datetime_fixed',
                'datetime': now,
                'details': {
                    'reason': 'null_activate_datetime',
                    'new_activate': new_activate.isoformat(),
                },
            }
            for d in docs
        ]
        db['events'].insert_many(event_docs)
        print(f'Events written: {len(event_docs)}')

    client.close()


if __name__ == '__main__':
    main()
