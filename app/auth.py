import logging

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash, current_app,
)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from .models import User
from .extensions import login_manager

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


@login_manager.user_loader
def load_user(user_id):
    if user_id == current_app.config['USERNAME']:
        return User(user_id)
    return None


def _verify(username: str, password: str) -> bool:
    return (
        username == current_app.config['USERNAME']
        and check_password_hash(current_app.config['PASSWORD_HASH'], password)
    )


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if _verify(username, password):
            login_user(User(username), remember=True)
            logger.info("User %s logged in from %s", username, request.remote_addr)
            return redirect(request.args.get('next') or url_for('main.index'))
        logger.warning("Failed login for %s from %s", username, request.remote_addr)
        flash('Неверный логин или пароль', 'danger')
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logger.info("User %s logged out", current_user.id)
    logout_user()
    return redirect(url_for('auth.login'))