"""
Celery приложение для асинхронных задач
"""
from celery import Celery
from shared.config.settings import settings

# Создание Celery приложения
celery_app = Celery(
    "testops_copilot",
    broker=settings.celery_broker,
    backend=settings.celery_result,
    include=[
        "workers.tasks.generate_workflow",
        "workers.tasks.generate_api_workflow",
        "workers.tasks.langgraph_workflow"
    ]
)

# Конфигурация Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.celery_task_timeout,
    task_soft_time_limit=settings.celery_task_timeout - 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

# Импорт задач (для регистрации)
from workers.tasks.generate_workflow import generate_test_cases_task
from workers.tasks.generate_api_workflow import generate_api_tests_task

# Экспорт задач для использования в роутерах
__all__ = ["celery_app", "generate_test_cases_task", "generate_api_tests_task"]


