import logging
import time

from flask import Flask, request, session
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import get_config
from .extensions import init_extensions
from .auth import auth_bp
from .main import main_bp
from .cli import register_cli
from .utils import utc_to_local


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    _setup_logging(app)
    init_extensions(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    register_cli(app)

    _register_jinja(app)
    _register_request_hooks(app)
    _register_error_handlers(app)

    return app


def _setup_logging(app: Flask) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler()],
    )


def _register_jinja(app: Flask) -> None:
    @app.template_filter('local_dt')
    def local_dt(dt):
        if not dt:
            return '—'
        return utc_to_local(dt, app.config['TIMEZONE']).strftime('%d.%m.%Y %H:%M')

    @app.template_filter('local_date')
    def local_date(dt):
        if not dt:
            return '—'
        return utc_to_local(dt, app.config['TIMEZONE']).strftime('%d.%m.%Y')

    @app.template_filter('local_input')
    def local_input(dt):
        if not dt:
            return ''
        return utc_to_local(dt, app.config['TIMEZONE']).strftime('%Y-%m-%dT%H:%M')


def _register_request_hooks(app: Flask) -> None:
    @app.before_request
    def before_request():
        request.start_time = time.time()
        session.permanent = True

    @app.after_request
    def after_request(response):
        if hasattr(request, 'start_time'):
            elapsed = time.time() - request.start_time
            app.logger.info(
                "Request: %s %s IP: %s Status: %s Time: %.3fs",
                request.method, request.path,
                request.remote_addr, response.status_code, elapsed,
            )
        return response


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        return e

    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.exception("Unhandled exception occurred")
        return "Internal Server Error", 500