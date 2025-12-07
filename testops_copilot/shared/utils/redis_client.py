"""
Утилиты для работы с Redis
"""
import redis
from typing import Optional
from shared.config.settings import settings


class RedisClient:
    """Клиент для работы с Redis"""
    
    def __init__(self):
        self._clients = {}
        self.redis_host = settings.redis_host
        self.redis_port = settings.redis_port
        self.redis_db_pubsub = settings.redis_db_pubsub
    
    def get_client(self, db: int = 0) -> redis.Redis:
        """Получить клиент Redis для указанной БД"""
        if db not in self._clients:
            # Используем REDIS_URL если задан, иначе используем настройки
            import os
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                # Парсим URL и извлекаем db
                from urllib.parse import urlparse
                parsed = urlparse(redis_url)
                base_url = f"redis://{parsed.netloc}"
                self._clients[db] = redis.from_url(
                    base_url,
                    db=db,
                    decode_responses=True,
                    socket_connect_timeout=5
                )
            else:
                self._clients[db] = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=db,
                    decode_responses=True,
                    socket_connect_timeout=5
                )
        return self._clients[db]
    
    @property
    def queue(self) -> redis.Redis:
        """Redis для очереди задач (DB 0)"""
        return self.get_client(settings.redis_db_queue)
    
    @property
    def result(self) -> redis.Redis:
        """Redis для результатов (DB 1)"""
        return self.get_client(settings.redis_db_result)
    
    @property
    def cache(self) -> redis.Redis:
        """Redis для кеша (DB 2)"""
        return self.get_client(settings.redis_db_cache)
    
    @property
    def pubsub(self) -> redis.Redis:
        """Redis для Pub/Sub (DB 3)"""
        return self.get_client(settings.redis_db_pubsub)
    
    def publish_event(self, channel: str, event: dict):
        """Опубликовать событие в Redis Pub/Sub"""
        import json
        self.pubsub.publish(channel, json.dumps(event))
    
    def subscribe_channel(self, channel: str):
        """Подписаться на канал (синхронный Redis)"""
        pubsub_obj = self.pubsub.pubsub(ignore_subscribe_messages=True)
        pubsub_obj.subscribe(channel)
        return pubsub_obj
    
    async def subscribe_channel_async(self, channel: str):
        """Подписаться на канал (асинхронный для SSE)"""
        import redis.asyncio as aioredis
        redis_async = aioredis.from_url(
            f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db_pubsub}",
            decode_responses=True
        )
        pubsub_obj = redis_async.pubsub()
        await pubsub_obj.subscribe(channel)
        return pubsub_obj, redis_async


# Глобальный экземпляр
redis_client = RedisClient()

