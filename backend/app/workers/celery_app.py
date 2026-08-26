from celery import Celery
from celery.schedules import crontab

from app.core.config import settings


celery_app = Celery(  # type: ignore[no-untyped-call]
    "agenthive",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.media_tasks",
        "app.workers.channel_token_tasks",
    ],
)

celery_app.conf.update(
    accept_content=["json"],
    enable_utc=True,
    result_serializer="json",
    task_serializer="json",
    task_track_started=True,
    timezone="UTC",
    worker_prefetch_multiplier=1,
    beat_schedule={
        # Refresh expiring WeCom/DingTalk access tokens every 15 minutes.
        # Tokens live 2h; the 300s safety margin means a token is refreshed
        # ~5 min before expiry, leaving ample headroom.
        "refresh-channel-tokens": {
            "task": "agenthive.channel.refresh_expiring_tokens",
            "schedule": crontab(minute="*/15"),
        },
    },
)
