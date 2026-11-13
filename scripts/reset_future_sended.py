"""Сбросить `sended` в False у напоминаний с activate_datetime в будущем.

Такое состояние (activate_datetime > now И sended=True) — несогласованное:
напоминание ещё не должно было сработать, значит `sended` уже должен быть
False. Появлялось из-за старого бага в send_and_postpone().

По умолчанию — dry-run (только показывает, что будет изменено).
Чтобы применить — флаг --apply.

Использование (из корня проекта):
    python3 scripts/reset_future_sended.py                    # dry-run
    python3 scripts/reset_future_sended.py --apply            # изменить
    python3 scripts/reset_future_sended.py --apply --log-event
    python3 scripts/reset_future_sended.py --apply --include-archived
    python3 scripts/reset_future_sended.py --apply --limit 5  # только первые 5
"""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pymongo import MongoClient

from app.config import Config
from app.utils import now_utc


def main():
    parser = argparse.ArgumentParser(
        description='Сбросить sended в False у напоминаний с activate_datetime в будущем.',
    )
    parser.add_argument(
        '--apply', action='store_true',
        help='реально записать изменения (по умолчанию dry-run)',
    )
    parser.add_argument(
        '--include-archived', action='store_true',
        help='также трогать напоминания в архиве (по умолчанию пропускаются)',
    )
    parser.add_argument(
        '--limit', type=int, default=0,
        help='обработать только первые N совпадений (0 = все)',
    )
    parser.add_argument(
        '--log-event', action='store_true',
        help='записать событие sended_reset в коллекцию events для каждого',
    )
    args = parser.parse_args()

    client = MongoClient(Config.MONGO_URI)
    db = client.get_database()
    collection = db['reminders']

    now = now_utc()
    query = {
        'activate_datetime': {'$gt': now},
        'sended': True,
    }
    if not args.include_archived:
        query['archived'] = False

    cursor = collection.find(query).sort('activate_datetime', 1)
    if args.limit > 0:
        cursor = cursor.limit(args.limit)

    docs = list(cursor)

    print(f'Now (UTC): {now.isoformat(sep=" ", timespec="seconds")}')
    print(f'Matched:   {len(docs)}')
    print()

    if not docs:
        print('Nothing to do.')
        client.close()
        return

    header = (
        f'{"_id":>26}  '
        f'{"activate_datetime":<19}  '
        f'{"auto":<5}  '
        f'{"oneshot":<7}  '
        f'text'
    )
    print(header)
    print('-' * 110)
    for d in docs:
        print(
            f'{str(d["_id"]):>26}  '
            f'{d["activate_datetime"].isoformat(sep=" ", timespec="minutes"):<19}  '
            f'{str(d.get("auto_postpone", False)):<5}  '
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
        {'$set': {'sended': False}},
    )
    print()
    print(f'Updated: {result.modified_count}')

    if args.log_event:
        event_docs = [
            {
                'reminder_id': d['_id'],
                'reminder_text': d.get('text', ''),
                'type': 'sended_reset',
                'datetime': now,
                'details': {'reason': 'future_activate_datetime'},
            }
            for d in docs
        ]
        db['events'].insert_many(event_docs)
        print(f'Events written: {len(event_docs)}')

    client.close()


if __name__ == '__main__':
    main()