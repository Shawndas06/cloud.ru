"""
Структурированное логирование
"""
import logging
import sys
from typing import Any, Dict
from shared.config.settings import settings

# Настройка базового логирования
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Создание логгеров для разных модулей
def get_logger(name: str) -> logging.Logger:
    """Получить логгер для модуля"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    return logger


# Глобальные логгеры
api_logger = get_logger("api_gateway")
worker_logger = get_logger("celery_worker")
agent_logger = get_logger("agents")
llm_logger = get_logger("llm_client")

