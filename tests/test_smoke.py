import os
os.environ.setdefault('SECRET_KEY', 'test')
os.environ.setdefault('USERNAME', 'admin')
os.environ.setdefault('PASSWORD_HASH', 'x')

from app import create_app
from app.utils import compute_next_activate, describe_periodic
from datetime import datetime


def test_app_creates():
    app = create_app()
    assert app is not None
    assert 'auth.login' in app.view_functions
    assert 'main.index' in app.view_functions
    assert 'main.calendar' in app.view_functions


def test_static_periodic():
    base = datetime(2026, 1, 31)
    assert compute_next_activate({'type': 'static', 'unit': 'day', 'number': 1}, base) == datetime(2026, 2, 1)
    assert compute_next_activate({'type': 'static', 'unit': 'month', 'number': 1}, base) == datetime(2026, 2, 28)
    assert compute_next_activate({'type': 'static', 'unit': 'year', 'number': 1}, base) == datetime(2027, 1, 31)


def test_random_periodic():
    base = datetime(2026, 1, 1)
    res = compute_next_activate({'type': 'random', 'mindays': 5, 'maxdays': 10}, base)
    assert 5 <= (res - base).days <= 10


def test_describe():
    assert describe_periodic({'type': 'static', 'unit': 'month', 'number': 3}) == '3 мес.'
    assert describe_periodic({'type': 'random', 'mindays': 1, 'maxdays': 3}) == '~1–3 дн.'


def test_card_description_contains_params():
    from app.models import _build_card_description
    reminder = {
        'description': 'Проверить почту',
        'oneshot': False,
        'periodic': {'type': 'random', 'mindays': 6, 'maxdays': 11},
        'auto_postpone': False,
        'activate_datetime': datetime(2026, 11, 20, 7, 0),
    }
    desc = _build_card_description(reminder, 'Europe/Moscow')
    assert desc.startswith('Проверить почту\n\n')
    assert 'Параметры напоминалки' in desc
    assert '~6–11 дн.' in desc
    assert 'повторяющаяся' in desc
    assert '20.11.2026 10:00' in desc
    # без пользовательского описания — только параметры
    reminder2 = {'oneshot': True, 'auto_postpone': True,
                 'activate_datetime': datetime(2026, 12, 1, 10, 30)}
    desc2 = _build_card_description(reminder2, 'Europe/Moscow')
    assert desc2.startswith('**Параметры напоминалки:**')
    assert 'одноразовая' in desc2