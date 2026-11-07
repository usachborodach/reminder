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
    assert 'random' in describe_periodic({'type': 'random', 'mindays': 1, 'maxdays': 3})