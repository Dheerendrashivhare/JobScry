"""Celery application + beat schedule (CLAUDE.md §14, Celery + Redis — not APScheduler)."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ajh",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.scheduler.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # A provider run can be slow (Apify actors block); don't let Celery kill it early.
    task_soft_time_limit=25 * 60,
    task_time_limit=30 * 60,
    worker_max_tasks_per_child=50,
)

celery_app.conf.beat_schedule = {
    "daily-pipeline": {
        "task": "ajh.dispatch_daily_pipelines",
        "schedule": crontab(hour=3, minute=0),  # 03:00 UTC daily
    },
}
