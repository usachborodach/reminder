"""Фоновый планировщик — отдельный процесс.

Запускается systemd-юнитом `reminder-scheduler.service`.
"""
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.scheduler import process_reminders


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)


def main():
    app = create_app()
    interval = app.config['SCHEDULER_INTERVAL']
    logging.info("Scheduler started, interval=%ss", interval)
    while True:
        try:
            process_reminders(app)
        except Exception:
            logging.exception("Scheduler iteration failed")
        time.sleep(interval)


if __name__ == '__main__':
    main()