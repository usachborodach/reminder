import click
from flask import Flask
from pymongo import ASCENDING

from .extensions import get_db


def register_cli(app: Flask) -> None:
    @app.cli.command('create-index')
    def create_index():
        """Индексы для reminders и events."""
        db = get_db()
        db.reminders.create_index([('archived', ASCENDING), ('activate_datetime', ASCENDING)])
        db.reminders.create_index([('auto_postpone', ASCENDING), ('sended', ASCENDING)])
        db.events.create_index([('reminder_id', ASCENDING), ('datetime', ASCENDING)])
        db.events.create_index([('datetime', ASCENDING)])
        click.echo('Индексы созданы')

    @app.cli.command('process-now')
    def process_now():
        """Прогнать обработку напоминаний один раз (для отладки)."""
        from .scheduler import process_reminders
        process_reminders(app._get_current_object())
        click.echo('Готово')