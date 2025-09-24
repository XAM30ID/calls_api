import os

from celery import Celery

# Локальное подключение к Redis
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Создание объекта Celery
celery_app = Celery(
    "worker",
    broker=redis_url,
    backend=redis_url
)

# Автоматическое обнаружение задач в приложении
celery_app.autodiscover_tasks(['app'])

# Настройка Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
)