import calendar
import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


_local_tz_cache: dict[str, ZoneInfo] = {}


def _local_tz(name: str) -> ZoneInfo:
    if name not in _local_tz_cache:
        _local_tz_cache[name] = ZoneInfo(name)
    return _local_tz_cache[name]


def now_utc() -> datetime:
    """Текущее UTC-время без tzinfo (как его хранит MongoDB)."""
    return datetime.utcnow()


def local_to_utc(naive_local: datetime, tz_name: str) -> datetime:
    """Naïve local -> naïve UTC."""
    aware = naive_local.replace(tzinfo=_local_tz(tz_name))
    return aware.astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_local(naive_utc: datetime, tz_name: str) -> datetime:
    """Naïve UTC -> naïve local."""
    aware = naive_utc.replace(tzinfo=timezone.utc)
    return aware.astimezone(_local_tz(tz_name)).replace(tzinfo=None)


def add_months(dt: datetime, months: int) -> datetime:
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def compute_next_activate(periodic: dict | None, base: datetime) -> datetime | None:
    if not periodic:
        return None
    ptype = periodic.get('type', 'static')

    if ptype == 'static':
        unit = periodic['unit']
        number = int(periodic['number'])
        if unit == 'day':
            return base + timedelta(days=number)
        if unit == 'week':
            return base + timedelta(weeks=number)
        if unit == 'month':
            return add_months(base, number)
        if unit == 'year':
            return add_months(base, number * 12)
    elif ptype == 'random':
        mind = int(periodic.get('mindays', 1))
        maxd = int(periodic.get('maxdays', mind))
        days = random.randint(mind, maxd)
        return base + timedelta(days=days)

    raise ValueError(f'Unknown periodic: {periodic}')


UNIT_LABELS = {'day': 'дн.', 'week': 'нед.', 'month': 'мес.', 'year': 'г.'}


def describe_periodic(periodic: dict | None) -> str:
    if not periodic:
        return '—'
    if periodic.get('type') == 'random':
        return f"~{periodic.get('mindays')}–{periodic.get('maxdays')} дн."
    return f"{periodic['number']} {UNIT_LABELS.get(periodic['unit'], periodic['unit'])}"


def describe_reminder_params(reminder: dict, tz: str) -> str:
    """Краткое описание параметров напоминалки для description карточки Wekan."""
    lines = ['**Параметры напоминалки:**', '']
    if reminder.get('oneshot'):
        lines.append('- Тип: одноразовая (oneshot)')
    else:
        lines.append('- Тип: повторяющаяся')
        lines.append(f"- Период: {describe_periodic(reminder.get('periodic'))}")
    if reminder.get('auto_postpone'):
        lines.append('- Отсрочка: автоматическая, сразу после отправки (auto_postpone)')
    else:
        lines.append('- Отсрочка: после закрытия карточки в Wekan')
    dt = reminder.get('activate_datetime')
    if dt:
        local = utc_to_local(dt, tz)
        lines.append(f"- Сработка: {local.strftime('%d.%m.%Y %H:%M')} ({tz})")
    return '\n'.join(lines)


def project_occurrences(reminder: dict, until_dt: datetime, max_iter: int = 200):
    """Вернуть список будущих сработок напоминалки до `until_dt`."""
    if reminder.get('archived'):
        return []

    occurrences = []
    current = reminder['activate_datetime']

    if current <= until_dt:
        occurrences.append({'dt': current, 'approximate': False})

    if reminder.get('oneshot'):
        return occurrences

    periodic = reminder.get('periodic')
    if not periodic or periodic.get('type') == 'random':
        return occurrences

    approximate = not reminder.get('auto_postpone', False)

    for _ in range(max_iter):
        try:
            current = compute_next_activate(periodic, current)
        except Exception:
            break
        if current > until_dt:
            break
        occurrences.append({'dt': current, 'approximate': approximate})

    return occurrences