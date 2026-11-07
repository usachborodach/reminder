from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from pymongo import MongoClient

login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)

mongo = None
wekan_mongo = None


def init_extensions(app) -> None:
    global mongo, wekan_mongo

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    limiter.init_app(app)

    mongo = MongoClient(app.config['MONGO_URI'])
    wekan_uri = app.config['WEKAN_MONGO_URI']
    if wekan_uri and wekan_uri != app.config['MONGO_URI']:
        wekan_mongo = MongoClient(wekan_uri)
    else:
        wekan_mongo = mongo


def get_db():
    return mongo.get_database()


def get_wekan_db():
    from flask import current_app
    return wekan_mongo[current_app.config['WEKAN_MONGO_DB']]