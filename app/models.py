import logging
from datetime import datetime

from flask_login import UserMixin

from .extensions import get_db, get_wekan_db
from .utils import now_utc, compute_next_activate

logger = logging.getLogger(__name__)

REMINDERS = 'reminders'
EVENTS = 'events'


class User(UserMixin):
    def __init__(self, username: str):
        self.id = username


def reminders():
    return get_db()[REMINDERS]


def events():
    return get_db()[EVENTS]


def wekan_cards():
    return get_wekan_db()['cards']


def log_event(reminder: dict, event_type: str, details: dict | None = None):
    doc = {
        'reminder_id': reminder['_id'],
        'reminder_text': reminder.get('text', ''),
        'type': event_type,
        'datetime': now_utc(),
    }
    if details:
        doc['details'] = details
    events().insert_one(doc)


# ------------------ Send / postpone logic ------------------

def _post_card(reminder: dict) -> str:
    from flask import current_app
    from .wekan import WekanClient

    client = WekanClient(
        url=current_app.config['WEKAN_URL'],
        login=current_app.config['WEKAN_LOGIN'],
        password=current_app.config['WEKAN_PASSWORD'],
        author_id=current_app.config['WEKAN_AUTHOR_ID'],
        boards=current_app.config['WEKAN_BOARDS'],
    )
    return client.post_card(
        title=reminder.get('text', ''),
        board=reminder.get('board', ''),
        description=reminder.get('description', ''),
    )


def send_and_postpone(reminder: dict) -> None:
    """auto_postpone=True: отправить карточку и сразу отложить."""
    card_id = _post_card(reminder)
    now = now_utc()

    if reminder.get('oneshot'):
        reminders().update_one(
            {'_id': reminder['_id']},
            {'$set': {
                'sended': True,
                'last_send_datetime': now,
                'archived': True,
            }},
        )
        log_event(reminder, 'sent_oneshot', {'card_id': card_id})
        log_event(reminder, 'archived_auto')
        return

    next_dt = compute_next_activate(reminder.get('periodic'), reminder['activate_datetime'])
    reminders().update_one(
        {'_id': reminder['_id']},
        {'$set': {
            'sended': True,
            'last_send_datetime': now,
            'activate_datetime': next_dt,
        }},
    )
    log_event(reminder, 'sent', {'card_id': card_id})
    log_event(reminder, 'postponed', {'new_activate': next_dt.isoformat()})


def send_and_track(reminder: dict) -> None:
    """auto_postpone=False: отправить карточку и начать следить за ней."""
    card_id = _post_card(reminder)
    now = now_utc()

    if reminder.get('oneshot'):
        reminders().update_one(
            {'_id': reminder['_id']},
            {'$set': {
                'sended': True,
                'last_send_datetime': now,
                'archived': True,
            }},
        )
        log_event(reminder, 'sent_oneshot', {'card_id': card_id})
        log_event(reminder, 'archived_auto')
        return

    reminders().update_one(
        {'_id': reminder['_id']},
        {'$set': {
            'sended': True,
            'last_send_datetime': now,
            'link_to_wekan_card': card_id,
        }},
    )
    log_event(reminder, 'sent', {'card_id': card_id})


def check_card_and_postpone(reminder: dict) -> None:
    """Если связанная карточка заархивирована/удалена — отложить."""
    card_id = reminder.get('link_to_wekan_card')
    if not card_id:
        return

    card = wekan_cards().find_one({'_id': card_id})
    is_closed = card is None or bool(card.get('archived'))

    if not is_closed:
        return

    now = now_utc()
    next_dt = compute_next_activate(reminder.get('periodic'), now)

    reminders().update_one(
        {'_id': reminder['_id']},
        {'$set': {
            'sended': False,
            'link_to_wekan_card': None,
            'activate_datetime': next_dt,
        }},
    )
    log_event(reminder, 'card_closed', {'card_id': card_id})
    log_event(reminder, 'postponed', {'new_activate': next_dt.isoformat() if next_dt else None})