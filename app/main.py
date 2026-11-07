import logging
from datetime import datetime, timedelta

from bson import ObjectId
from bson.errors import InvalidId
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    current_app, abort,
)
from flask_login import login_required

from .extensions import get_db
from .models import reminders, events, log_event, wekan_cards
from .utils import (
    now_utc, local_to_utc, utc_to_local, compute_next_activate,
    describe_periodic, project_occurrences,
)

logger = logging.getLogger(__name__)
main_bp = Blueprint('main', __name__)


def _parse_oid(raw: str) -> ObjectId:
    try:
        return ObjectId(raw)
    except (InvalidId, TypeError):
        abort(404)


def _tz() -> str:
    return current_app.config['TIMEZONE']


# ---------------- index ----------------

@main_bp.route('/')
@login_required
def index():
    docs = list(reminders().find({'archived': False}).sort('activate_datetime', 1))
    now = now_utc()
    tz = _tz()
    for d in docs:
        d['id_str'] = str(d['_id'])
        d['periodic_label'] = 'одноразово' if d.get('oneshot') else describe_periodic(d.get('periodic'))
        d['is_due'] = d['activate_datetime'] <= now
        d['activate_local'] = utc_to_local(d['activate_datetime'], tz)
    return render_template('index.html', reminders=docs, tz=tz)


# ---------------- calendar ----------------

def _parse_month(raw: str | None) -> datetime:
    if raw:
        try:
            return datetime.strptime(raw, '%Y-%m')
        except ValueError:
            pass
    today = utc_to_local(now_utc(), _tz())
    return datetime(today.year, today.month, 1)


@main_bp.route('/calendar')
@login_required
def calendar():
    tz = _tz()
    month_start = _parse_month(request.args.get('month'))
    # следующий месяц
    if month_start.month == 12:
        next_month = datetime(month_start.year + 1, 1, 1)
    else:
        next_month = datetime(month_start.year, month_start.month + 1, 1)

    # окно 2 месяца в local, переводим в UTC для сравнения
    win_start = local_to_utc(month_start, tz)

    # ограничим окно концом следующего месяца
    if next_month.month == 12:
        after_next = datetime(next_month.year + 1, 1, 1)
    else:
        after_next = datetime(next_month.year, next_month.month + 1, 1)
    win_end = local_to_utc(after_next, tz)

    by_day: dict[str, list] = {}

    for r in reminders().find({'archived': False}):
        for occ in project_occurrences(r, win_end):
            dt = occ['dt']
            if dt < win_start:
                continue
            local_dt = utc_to_local(dt, tz)
            key = local_dt.strftime('%Y-%m-%d')
            by_day.setdefault(key, []).append({
                'reminder_id': str(r['_id']),
                'text': r.get('text', ''),
                'board': r.get('board', ''),
                'approximate': occ['approximate'],
                'time': local_dt.strftime('%H:%M'),
            })

    for items in by_day.values():
        items.sort(key=lambda x: (x['time'], x['text']))

    # построим сетку
    first_weekday = month_start.weekday()  # 0=Mon
    weeks = []
    cursor = month_start - timedelta(days=first_weekday)
    end = after_next
    while cursor < end:
        week = []
        for _ in range(7):
            key = cursor.strftime('%Y-%m-%d')
            week.append({
                'date': cursor,
                'in_month': cursor.month == month_start.month,
                'events': by_day.get(key, []),
            })
            cursor += timedelta(days=1)
        weeks.append(week)

    # ссылки на соседние месяцы
    prev_month = month_start - timedelta(days=1)
    prev_month = prev_month.replace(day=1)
    after_next_month = after_next.replace(day=1)

    return render_template(
        'calendar.html',
        month_start=month_start,
        next_month=next_month,
        weeks=weeks,
        prev_month=prev_month.strftime('%Y-%m'),
        next_month_key=after_next_month.strftime('%Y-%m'),
        tz=tz,
    )


# ---------------- archived ----------------

@main_bp.route('/archived')
@login_required
def archived():
    docs = list(reminders().find({'archived': True}).sort('activate_datetime', -1))
    tz = _tz()
    for d in docs:
        d['id_str'] = str(d['_id'])
        d['periodic_label'] = 'одноразово' if d.get('oneshot') else describe_periodic(d.get('periodic'))
        d['activate_local'] = utc_to_local(d['activate_datetime'], tz)
    return render_template('archived.html', reminders=docs, tz=tz)


# ---------------- events ----------------

@main_bp.route('/events')
@login_required
def events_log():
    limit = int(request.args.get('limit', 200))
    limit = max(20, min(limit, 1000))
    docs = list(events().find().sort('datetime', -1).limit(limit))
    tz = _tz()
    for d in docs:
        d['datetime_local'] = utc_to_local(d['datetime'], tz)
    return render_template('events.html', events=docs, limit=limit, tz=tz)


# ---------------- create / edit ----------------

def _form_to_doc(form, existing=None) -> dict:
    tz = _tz()
    text = (form.get('text') or '').strip()
    if not text:
        raise ValueError('text is required')
    board = (form.get('board') or '').strip()
    if not board:
        raise ValueError('board is required')

    activate_raw = form.get('activate_datetime') or ''
    try:
        activate_local = datetime.strptime(activate_raw, '%Y-%m-%dT%H:%M')
    except ValueError:
        raise ValueError('activate_datetime is invalid')
    activate_utc = local_to_utc(activate_local, tz)

    auto_postpone = form.get('auto_postpone') == 'on'
    oneshot = form.get('oneshot') == 'on'
    description = (form.get('description') or '').strip()

    doc = {
        'text': text,
        'description': description,
        'board': board,
        'activate_datetime': activate_utc,
        'auto_postpone': auto_postpone,
        'oneshot': oneshot,
    }

    if oneshot:
        doc['periodic'] = None
    else:
        ptype = form.get('periodic_type', 'static')
        if ptype == 'random':
            mind = int(form.get('mindays') or 1)
            maxd = int(form.get('maxdays') or mind)
            if mind < 1 or maxd < mind:
                raise ValueError('random range invalid')
            doc['periodic'] = {'type': 'random', 'mindays': mind, 'maxdays': maxd}
        else:
            number = int(form.get('periodic_number') or 1)
            unit = form.get('periodic_unit') or 'day'
            if unit not in ('day', 'week', 'month', 'year'):
                raise ValueError('unit invalid')
            doc['periodic'] = {'type': 'static', 'unit': unit, 'number': number}

    return doc


@main_bp.route('/reminder/new', methods=['GET', 'POST'])
@login_required
def reminder_new():
    tz = _tz()
    if request.method == 'POST':
        try:
            doc = _form_to_doc(request.form)
        except ValueError as e:
            flash(str(e), 'danger')
            return render_template(
                'edit.html', reminder=None, form=request.form,
                boards=current_app.config['WEKAN_BOARDS'], tz=tz,
            )

        doc.update({
            'sended': False,
            'create_datetime': now_utc(),
            'last_send_datetime': None,
            'archived': False,
            'link_to_wekan_card': None,
        })
        result = reminders().insert_one(doc)
        doc['_id'] = result.inserted_id
        log_event(doc, 'created')
        flash('Напоминание создано', 'success')
        return redirect(url_for('main.index'))

    # GET — дефолт
    boards = current_app.config['WEKAN_BOARDS']
    default_board = 'work' if 'work' in boards else next(iter(boards), '')

    # Завтра 00:00 в локальной таймзоне (сервер может быть в UTC)
    now_local = utc_to_local(now_utc(), tz)
    default_dt = now_local.replace(hour=0, minute=0, second=0, microsecond=0)

    form = {
        'text': '',
        'description': '',
        'board': default_board,
        'activate_datetime': default_dt.strftime('%Y-%m-%dT%H:%M'),
        'auto_postpone': '',   # выключено
        'oneshot': 'on',       # включено
        'periodic_type': 'static',
        'periodic_number': 1,
        'periodic_unit': 'day',
        'mindays': 6,
        'maxdays': 11,
    }
    return render_template(
        'edit.html', reminder=None, form=form,
        boards=boards, tz=tz,
    )


@main_bp.route('/reminder/<rid>/edit', methods=['GET', 'POST'])
@login_required
def reminder_edit(rid):
    tz = _tz()
    oid = _parse_oid(rid)
    r = reminders().find_one({'_id': oid})
    if not r:
        abort(404)

    if request.method == 'POST':
        try:
            doc = _form_to_doc(request.form, existing=r)
        except ValueError as e:
            flash(str(e), 'danger')
            return render_template(
                'edit.html', reminder=r, form=request.form,
                boards=current_app.config['WEKAN_BOARDS'], tz=tz,
            )

        reminders().update_one({'_id': oid}, {'$set': doc})
        log_event({**r, **doc}, 'updated')
        flash('Сохранено', 'success')
        return redirect(url_for('main.index'))

    # GET — заполним форму из документа
    periodic = r.get('periodic') or {}
    form = {
        'text': r.get('text', ''),
        'description': r.get('description', ''),
        'board': r.get('board', ''),
        'activate_datetime': utc_to_local(r['activate_datetime'], tz).strftime('%Y-%m-%dT%H:%M'),
        'auto_postpone': 'on' if r.get('auto_postpone') else '',
        'oneshot': 'on' if r.get('oneshot') else '',
        'periodic_type': periodic.get('type', 'static'),
        'periodic_number': periodic.get('number', 1),
        'periodic_unit': periodic.get('unit', 'day'),
        'mindays': periodic.get('mindays', 6),
        'maxdays': periodic.get('maxdays', 11),
    }
    return render_template(
        'edit.html', reminder=r, form=form,
        boards=current_app.config['WEKAN_BOARDS'], tz=tz,
    )


# ---------------- actions ----------------

@main_bp.route('/reminder/<rid>/postpone', methods=['POST'])
@login_required
def reminder_postpone(rid):
    oid = _parse_oid(rid)
    r = reminders().find_one({'_id': oid})
    if not r:
        abort(404)

    tz = _tz()
    raw = request.form.get('new_datetime') or ''
    try:
        if raw:
            new_local = datetime.strptime(raw, '%Y-%m-%dT%H:%M')
        else:
            base = max(r['activate_datetime'], now_utc())
            nxt = compute_next_activate(r.get('periodic'), base)
            if nxt is None:
                flash('Для одноразового напоминания укажите дату', 'danger')
                return redirect(url_for('main.index'))
            new_local = utc_to_local(nxt, tz)
    except ValueError:
        flash('Неверная дата', 'danger')
        return redirect(url_for('main.index'))

    new_utc = local_to_utc(new_local, tz)
    reminders().update_one(
        {'_id': oid},
        {'$set': {
            'activate_datetime': new_utc,
            'sended': False,
            'link_to_wekan_card': None,
        }},
    )
    log_event(r, 'postponed_manual', {'new_activate': new_utc.isoformat()})
    flash('Отложено', 'success')
    return redirect(url_for('main.index'))


@main_bp.route('/reminder/<rid>/archive', methods=['POST'])
@login_required
def reminder_archive(rid):
    oid = _parse_oid(rid)
    r = reminders().find_one({'_id': oid})
    if not r:
        abort(404)
    reminders().update_one({'_id': oid}, {'$set': {'archived': True}})
    log_event(r, 'archived')
    flash('В архиве', 'success')
    return redirect(url_for('main.index'))


@main_bp.route('/reminder/<rid>/unarchive', methods=['POST'])
@login_required
def reminder_unarchive(rid):
    oid = _parse_oid(rid)
    r = reminders().find_one({'_id': oid})
    if not r:
        abort(404)
    reminders().update_one({'_id': oid}, {'$set': {'archived': False}})
    log_event(r, 'unarchived')
    flash('Возвращено из архива', 'success')
    return redirect(url_for('main.archived'))


@main_bp.route('/reminder/<rid>/send', methods=['POST'])
@login_required
def reminder_send(rid):
    oid = _parse_oid(rid)
    r = reminders().find_one({'_id': oid})
    if not r:
        abort(404)

    from .models import send_and_postpone, send_and_track

    try:
        if r.get('auto_postpone'):
            send_and_postpone(r)
        else:
            send_and_track(r)
        flash('Отправлено', 'success')
    except Exception as e:
        logger.exception("Manual send failed for %s", oid)
        log_event(r, 'send_failed', {'error': str(e)})
        flash(f'Ошибка отправки: {e}', 'danger')
    return redirect(url_for('main.index'))