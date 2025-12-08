# Shared Components - Подробное объяснение для Junior разработчиков

## 📋 Содержание
1. [Что такое Shared Components?](#что-такое-shared-components)
2. [Структура Shared](#структура-shared)
3. [Config - Настройки приложения](#config---настройки-приложения)
4. [Database Utils - Работа с БД](#database-utils---работа-с-бд)
5. [Redis Client - Кеширование и Pub/Sub](#redis-client---кеширование-и-pubsub)
6. [LLM Client - Работа с AI](#llm-client---работа-с-ai)
7. [Logger - Логирование](#logger---логирование)
8. [Полезные ссылки](#полезные-ссылки)

---

## Что такое Shared Components?

**Shared Components** - это общие утилиты и компоненты, которые используются во всех микросервисах.

**Зачем выносить в shared?**
- **DRY (Don't Repeat Yourself)** - не дублировать код
- **Единообразие** - все сервисы используют одинаковые утилиты
- **Легкость изменений** - изменил в одном месте, работает везде
- **Тестируемость** - общие компоненты тестируются один раз

**Аналогия:** Как общая библиотека - все могут использовать одни и те же функции.

---

## Структура Shared

```
shared/
├── config/
│   └── settings.py          # Настройки приложения
├── models/
│   └── database.py         # SQLAlchemy модели
└── utils/
    ├── database.py          # Утилиты для работы с БД
    ├── redis_client.py      # Клиент Redis
    ├── llm_client.py        # Клиент LLM API
    └── logger.py            # Логирование
```

---

## Config - Настройки приложения

### Файл: `shared/config/settings.py`

**Назначение:** Централизованное хранение всех настроек приложения.

### Pydantic Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Настройки приложения"""
    
    # API Gateway
    api_gateway_host: str = "0.0.0.0"
    api_gateway_port: int = 8000
    api_gateway_reload: bool = True
    
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "testops_copilot"
    postgres_user: str = "testops"
    postgres_password: str = "testops_password"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
```

**Что делает Pydantic Settings:**
- Автоматически читает переменные из `.env` файла
- Валидирует типы данных
- Предоставляет значения по умолчанию
- Поддерживает переменные окружения

**Полезная ссылка:** [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

### Computed Properties

```python
@property
def database_url(self) -> str:
    # Проверяем переменную окружения DATABASE_URL (для Docker)
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    # Или используем POSTGRES_HOST если задан
    host = os.getenv("POSTGRES_HOST", self.postgres_host)
    return f"postgresql://{self.postgres_user}:{self.postgres_password}@{host}:{self.postgres_port}/{self.postgres_db}"
```

**Зачем computed properties?**
- Гибкость - можно задать `DATABASE_URL` целиком или отдельные параметры
- Удобство - не нужно вручную формировать URL
- Docker-friendly - поддерживает переменные окружения из Docker Compose

**Пример использования:**
```python
from shared.config.settings import settings

# Использование настроек
db_url = settings.database_url
redis_url = settings.redis_url
```

### Глобальный экземпляр

```python
# Глобальный экземпляр настроек
settings = Settings()
```

**Почему глобальный?**
- Создается один раз при импорте
- Все модули используют один экземпляр
- Эффективно по памяти

**Альтернатива:** Можно использовать dependency injection, но для настроек глобальный экземпляр проще.

---

## Database Utils - Работа с БД

### Файл: `shared/utils/database.py`

**Назначение:** Утилиты для работы с базой данных через SQLAlchemy.

### Создание Engine

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,      # Проверка соединения перед использованием
    pool_size=20,            # Размер пула соединений
    max_overflow=30,        # Максимум дополнительных соединений
    echo=False               # Логирование SQL запросов (False в продакшене)
)
```

**Что такое connection pool?**
- Пул соединений - набор готовых соединений с БД
- Вместо создания нового соединения каждый раз, берем из пула
- Эффективнее и быстрее

**Параметры:**
- `pool_size=20` - 20 постоянных соединений
- `max_overflow=30` - еще 30 временных, если нужно
- `pool_pre_ping=True` - проверяет соединение перед использованием (если БД перезапустилась, соединение пересоздается)

**Полезная ссылка:** [SQLAlchemy Engine Configuration](https://docs.sqlalchemy.org/en/20/core/engines.html#engine-configuration)

### Session Factory

```python
SessionLocal = sessionmaker(
    autocommit=False,    # Не коммитить автоматически
    autoflush=False,     # Не флашить автоматически
    bind=engine
)
```

**Session** - это единица работы с БД. Все операции в рамках одной сессии.

**Параметры:**
- `autocommit=False` - коммитим вручную (контроль транзакций)
- `autoflush=False` - флашим вручную (контроль когда отправлять запросы)

### Context Manager для сессий

```python
from contextlib import contextmanager

@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Контекстный менеджер для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
        db.commit()  # Коммитим при успехе
    except Exception as e:
        db.rollback()  # Откатываем при ошибке
        print(f"Database error: {e}")
        raise
    finally:
        db.close()  # Закрываем сессию
```

**Как работает:**
1. Создается сессия
2. `yield db` - возвращает сессию
3. После блока `with`:
   - Если успех - `db.commit()`
   - Если ошибка - `db.rollback()`
   - Всегда - `db.close()`

**Пример использования:**
```python
with get_db() as db:
    user = db.query(User).filter(User.email == "test@example.com").first()
    user.last_login_at = datetime.utcnow()
    # Автоматически коммитится при выходе из блока
```

**Почему context manager?**
- Гарантирует закрытие сессии (даже при ошибке)
- Автоматический commit/rollback
- Чистый код (не нужно помнить про close)

**Полезная ссылка:** [Python Context Managers](https://docs.python.org/3/library/contextlib.html)

### Dependency для FastAPI

```python
def get_db_dependency():
    """Dependency для FastAPI"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Использование в FastAPI:**
```python
from fastapi import Depends

@router.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db_dependency)):
    user = db.query(User).filter(User.user_id == user_id).first()
    return user
```

**Как работает:**
- FastAPI автоматически вызывает `get_db_dependency()` перед обработчиком
- Передает результат (`db`) в функцию
- После выполнения закрывает сессию

**Почему `yield` вместо `return`?**
- `yield` позволяет выполнить код после обработчика (закрытие сессии)
- FastAPI поддерживает generator dependencies

**Полезная ссылка:** [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)

### Инициализация БД

```python
def init_db():
    """Инициализация базы данных - создание таблиц"""
    Base.metadata.create_all(bind=engine)
```

**Что происходит:**
- Создаются все таблицы, определенные в моделях SQLAlchemy
- Вызывается при старте приложения

**Когда вызывается:**
- При запуске API Gateway (в `lifespan`)

---

## Redis Client - Кеширование и Pub/Sub

### Файл: `shared/utils/redis_client.py`

**Назначение:** Клиент для работы с Redis (кеш, Pub/Sub, очереди).

### Структура Redis DB

В проекте используется несколько Redis баз данных:
- **DB 0** - очередь задач (Celery broker)
- **DB 1** - результаты задач (Celery backend)
- **DB 2** - кеш (LLM ответы, временные данные)
- **DB 3** - Pub/Sub (уведомления в реальном времени)

**Почему несколько DB?**
- Разделение данных по назначению
- Легче управлять (можно очистить кеш, не трогая очереди)
- Производительность (меньше данных в каждой DB)

### Класс RedisClient

```python
class RedisClient:
    """Клиент для работы с Redis"""
    
    def __init__(self):
        self._clients = {}  # Кеш клиентов для каждой DB
    
    def get_client(self, db: int = 0) -> redis.Redis:
        """Получить клиент Redis для указанной БД"""
        if db not in self._clients:
            redis_url = os.getenv("REDIS_URL")
            if redis_url:
                # Парсим URL и извлекаем db
                from urllib.parse import urlparse
                parsed = urlparse(redis_url)
                base_url = f"redis://{parsed.netloc}"
                self._clients[db] = redis.from_url(
                    base_url,
                    db=db,
                    decode_responses=True,  # Автоматически декодировать bytes в str
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
```

**Что происходит:**
- Кеширует клиенты для каждой DB (не создает каждый раз новый)
- Поддерживает `REDIS_URL` (для Docker) или отдельные параметры
- `decode_responses=True` - автоматически декодирует bytes в str (удобнее работать)

### Properties для разных DB

```python
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
```

**Использование:**
```python
from shared.utils.redis_client import redis_client

# Кеширование
redis_client.cache.set("key", "value", ex=3600)  # TTL 1 час
value = redis_client.cache.get("key")

# Pub/Sub
redis_client.publish_event("channel", {"status": "completed"})
```

### Pub/Sub - Уведомления в реальном времени

```python
def publish_event(self, channel: str, event: dict):
    """Опубликовать событие в Redis Pub/Sub"""
    import json
    self.pubsub.publish(channel, json.dumps(event))
```

**Как работает Pub/Sub:**
1. Publisher публикует сообщение в канал
2. Все подписчики на этот канал получают сообщение
3. Используется для уведомлений в реальном времени

**Пример:**
```python
# В Worker (публикация)
redis_client.publish_event(
    f"request:{request_id}",
    {"status": "processing", "step": "generation"}
)

# В API Gateway (подписка через SSE)
# См. документацию по API Gateway
```

**Полезная ссылка:** [Redis Pub/Sub](https://redis.io/docs/manual/pubsub/)

---

## LLM Client - Работа с AI

### Файл: `shared/utils/llm_client.py`

**Назначение:** Клиент для работы с Cloud.ru Foundation Models API (LLM).

### Архитектура

```
LLMClient
├── IAM API (получение токена)
└── Foundation Models API (генерация)
```

**Почему два API?**
- IAM API - аутентификация (получение access token)
- Foundation Models API - генерация (использует токен)

### Получение токена

```python
async def _get_access_token(self) -> str:
    """Получение access token через IAM API"""
    import time
    
    # Проверка кеша токена
    if self._access_token and self._token_expires_at:
        if time.time() < self._token_expires_at - 300:  # Обновляем за 5 минут до истечения
            return self._access_token
    
    # Получение нового токена
    async with httpx.AsyncClient() as client:
        response = await client.post(
            self.iam_url,
            json={
                "keyId": self.key_id,
                "secret": self.key_secret
            },
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        
        self._access_token = data["access_token"]
        expires_in = data.get("expires_in", 3600)
        self._token_expires_at = time.time() + expires_in
        
        return self._access_token
```

**Что происходит:**
1. Проверяет, есть ли валидный токен в памяти
2. Если нет или скоро истечет - получает новый
3. Сохраняет токен и время истечения
4. Возвращает токен

**Зачем кешировать токен?**
- Токен действует час (обычно)
- Не нужно получать новый при каждом запросе
- Экономит время и ресурсы

### Генерация через LLM

```python
async def generate(
    self,
    prompt: str,
    system_prompt: str = "",
    model: str = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    use_cache: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """Генерация через LLM API"""
    
    if model is None:
        model = self.default_model
    
    # Проверка кеша
    if use_cache:
        cache_key = f"llm_cache:{hashlib.sha256((system_prompt + prompt + model).encode()).hexdigest()}"
        cached = redis_client.cache.get(cache_key)
        if cached:
            return json.loads(cached)
    
    # Формирование запроса
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    # Вызов API с retry
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Используем OpenAI клиент если доступен
            if self._openai_client:
                response = await self._openai_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                # Преобразование ответа
                result = {
                    "choices": [{
                        "message": {
                            "role": response.choices[0].message.role,
                            "content": response.choices[0].message.content
                        }
                    }],
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
                
                # Сохранение в кеш
                if use_cache:
                    redis_client.cache.setex(
                        cache_key,
                        3600,  # TTL 1 час
                        json.dumps(result)
                    )
                
                return result
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(base_delay * (2 ** attempt))  # Exponential backoff
```

**Что происходит:**
1. Проверяет кеш (если `use_cache=True`)
2. Формирует сообщения (system + user prompt)
3. Вызывает LLM API с retry (до 3 попыток)
4. Сохраняет результат в кеш
5. Возвращает ответ

**Кеширование:**
- Кеш ключ = хеш от (system_prompt + prompt + model)
- TTL = 1 час
- Экономит деньги и время

**Retry с exponential backoff:**
- При ошибке ждет 1s, 2s, 4s перед следующей попыткой
- Помогает при временных сбоях

**Полезная ссылка:** [Exponential Backoff](https://en.wikipedia.org/wiki/Exponential_backoff)

### Генерация Embeddings

```python
async def generate_embeddings(self, text: str) -> list:
    """
    Генерация embeddings для semantic similarity
    
    Использует hash-based подход (быстро, без зависимостей от torch)
    """
    try:
        # Hash-based embeddings
        hash_obj = hashlib.sha256(text.encode('utf-8'))
        hash_bytes = hash_obj.digest()
        
        # Создаем 384-мерный вектор
        embedding = []
        for i in range(384):
            byte_idx = i % len(hash_bytes)
            next_byte_idx = (i + 1) % len(hash_bytes)
            value = (hash_bytes[byte_idx] + hash_bytes[next_byte_idx] * 256) / 65535.0
            embedding.append(float(value))
        
        # Нормализация
        import math
        norm = math.sqrt(sum(x*x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]
        
        return embedding
    except Exception as e:
        # Fallback
        hash_obj = hashlib.sha256(text.encode('utf-8'))
        return [float(b) / 255.0 for b in hash_obj.digest()[:384]]
```

**Что такое embeddings?**
- Числовые векторы, представляющие смысл текста
- Похожие тексты имеют похожие векторы
- Используется для semantic similarity

**Почему hash-based?**
- Быстро (не нужен ML модель)
- Детерминировано (одинаковый текст = одинаковый вектор)
- Без зависимостей

**В будущем:** Можно использовать настоящие embeddings от LLM API.

---

## Logger - Логирование

### Файл: `shared/utils/logger.py`

**Назначение:** Централизованное логирование для всех компонентов.

### Структура логгера

```python
import logging
from shared.config.settings import settings

# Создание логгеров для разных компонентов
api_logger = logging.getLogger("api_gateway")
agent_logger = logging.getLogger("agents")
llm_logger = logging.getLogger("llm")
worker_logger = logging.getLogger("workers")
```

**Почему разные логгеры?**
- Можно настроить разные уровни логирования
- Легче фильтровать логи
- Структурированное логирование

### Настройка логирования

```python
def setup_logging():
    """Настройка логирования"""
    log_level = getattr(settings, 'log_level', 'INFO')
    log_format = getattr(settings, 'log_format', 'json')
    
    if log_format == 'json':
        # JSON формат для production
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # Текстовый формат для разработки
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
```

**Форматы:**
- **JSON** - для production (легко парсить)
- **Text** - для разработки (читаемо)

**Уровни логирования:**
- `DEBUG` - детальная информация для отладки
- `INFO` - общая информация
- `WARNING` - предупреждения
- `ERROR` - ошибки
- `CRITICAL` - критические ошибки

### Использование

```python
from shared.utils.logger import api_logger

api_logger.info("Request received", extra={"user_id": user_id, "endpoint": "/generate"})
api_logger.error("Error processing request", exc_info=True)
```

**`exc_info=True`** - включает traceback в лог (для отладки).

---

## Полезные ссылки

### Pydantic

- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [Pydantic Documentation](https://docs.pydantic.dev/)

### SQLAlchemy

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [SQLAlchemy Engine Configuration](https://docs.sqlalchemy.org/en/20/core/engines.html#engine-configuration)
- [SQLAlchemy Session Basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)

### Redis

- [Redis Documentation](https://redis.io/docs/)
- [Redis Pub/Sub](https://redis.io/docs/manual/pubsub/)
- [Redis Python Client](https://redis.readthedocs.io/)

### FastAPI

- [FastAPI Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)

### Python

- [Python Context Managers](https://docs.python.org/3/library/contextlib.html)
- [Python Logging](https://docs.python.org/3/library/logging.html)

---

## Часто задаваемые вопросы

### Q: Почему использовать глобальный экземпляр settings?

**A:** Настройки не меняются во время выполнения, поэтому глобальный экземпляр проще и эффективнее. Для данных, которые меняются, лучше использовать dependency injection.

### Q: Зачем кешировать Redis клиенты?

**A:** Создание нового клиента каждый раз - дорого. Кеширование позволяет переиспользовать соединения.

### Q: Почему hash-based embeddings, а не настоящие?

**A:** Для MVP hash-based достаточно. В будущем можно заменить на настоящие embeddings от LLM API для лучшей точности.

### Q: Зачем кешировать LLM ответы?

**A:** 
- Экономит деньги (не платим за повторные запросы)
- Быстрее (не ждем ответ от API)
- Детерминировано (одинаковый промпт = одинаковый ответ)

---

## Заключение

Shared Components - это фундамент системы, который:
- Предоставляет общие утилиты
- Обеспечивает единообразие
- Упрощает разработку
- Улучшает поддерживаемость

Понимание shared компонентов необходимо для работы с любым микросервисом!

