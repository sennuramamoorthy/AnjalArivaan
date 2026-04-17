"""Celery application factory + beat schedule for background jobs.

Primary job: daily briefing fan-out at 06:00 Asia/Kolkata for every active
user. Triggered by celery-beat; per-user work is a separate task so fan-out
is resilient to per-user failures.
"""

from __future__ import annotations

try:
    from celery import Celery
    from celery.schedules import crontab
except ImportError:  # pragma: no cover - allow import without celery at dev time
    Celery = None  # type: ignore[assignment]
    crontab = None  # type: ignore[assignment]

from src.config import get_settings


def create_celery_app() -> "Celery":
    """Build the Celery app with Redis broker + RedBeat scheduler."""
    if Celery is None:
        raise RuntimeError(
            "celery is not installed — add `celery[redis]` to project dependencies."
        )

    settings = get_settings()
    app = Celery(
        "anjal_api",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
        include=["src.workers.tasks.daily_briefing"],
    )

    app.conf.update(
        timezone="Asia/Kolkata",
        enable_utc=False,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
        task_default_queue="default",
        beat_scheduler="redbeat.RedBeatScheduler",
        redbeat_redis_url=settings.celery_broker_url,
    )

    app.conf.beat_schedule = {
        "daily_briefing_fanout_0600_ist": {
            "task": "src.workers.tasks.daily_briefing.run_for_all_users",
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "default"},
        },
    }

    return app


# Lazy module-level handle so `celery -A src.workers.celery_app:celery_app` works.
celery_app = None


def _ensure_app() -> "Celery":
    global celery_app
    if celery_app is None:
        celery_app = create_celery_app()
    return celery_app
