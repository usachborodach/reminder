import logging

from flask import Flask

from .extensions import get_db
from .models import (
    send_and_postpone, send_and_track, check_card_and_postpone,
)
from .utils import now_utc

logger = logging.getLogger(__name__)


def process_reminders(app: Flask) -> None:
    with app.app_context():
        _process()


def _process() -> None:
    now = now_utc()
    db = get_db()

    # 1) auto_postpone=True — пришло время, шлём и сразу откладываем
    for r in db.reminders.find({
        'archived': False,
        'auto_postpone': True,
        'activate_datetime': {'$lte': now},
    }):
        try:
            send_and_postpone(r)
        except Exception:
            logger.exception("Failed to send auto reminder %s", r['_id'])

    # 2) auto_postpone=False и ещё не отправлено — шлём и начинаем следить
    for r in db.reminders.find({
        'archived': False,
        'auto_postpone': False,
        'sended': False,
        'activate_datetime': {'$lte': now},
    }):
        try:
            send_and_track(r)
        except Exception:
            logger.exception("Failed to send tracked reminder %s", r['_id'])

    # 3) отслеживаемые — проверяем, закрыта ли карточка
    for r in db.reminders.find({
        'archived': False,
        'auto_postpone': False,
        'sended': True,
        'link_to_wekan_card': {'$ne': None},
    }):
        try:
            check_card_and_postpone(r)
        except Exception:
            logger.exception("Failed to check card for reminder %s", r['_id'])