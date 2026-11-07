import json
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _load_boards():
    raw = os.getenv('WEKAN_BOARDS', '{}')
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/reminder')
    WEKAN_MONGO_URI = os.getenv('WEKAN_MONGO_URI') or MONGO_URI
    WEKAN_MONGO_DB = os.getenv('WEKAN_MONGO_DB', 'wekan')

    WEKAN_URL = os.getenv('WEKAN_URL', '')
    WEKAN_LOGIN = os.getenv('WEKAN_LOGIN', '')
    WEKAN_PASSWORD = os.getenv('WEKAN_PASSWORD', '')
    WEKAN_AUTHOR_ID = os.getenv('WEKAN_AUTHOR_ID', '')
    WEKAN_BOARDS = _load_boards()

    TIMEZONE = os.getenv('TIMEZONE', 'Europe/Moscow')
    SCHEDULER_INTERVAL = int(os.getenv('SCHEDULER_INTERVAL', '60'))

    USERNAME = os.getenv('USERNAME')
    PASSWORD_HASH = os.getenv('PASSWORD_HASH')

    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = True

    RATELIMIT_DEFAULT = "120 per minute"
    RATELIMIT_STORAGE_URI = "memory://"


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


_CONFIGS = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': Config,
}


def get_config(name: str | None = None):
    if name is None:
        name = os.getenv('FLASK_ENV', 'default')
    return _CONFIGS.get(name, Config)