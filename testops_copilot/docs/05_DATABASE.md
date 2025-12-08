# Database Models - Подробное объяснение для Junior разработчиков

## 📋 Содержание
1. [Что такое ORM и SQLAlchemy?](#что-такое-orm-и-sqlalchemy)
2. [Структура базы данных](#структура-базы-данных)
3. [Модель User - Пользователи](#модель-user---пользователи)
4. [Модель Request - Запросы на генерацию](#модель-request---запросы-на-генерацию)
5. [Модель TestCase - Тест-кейсы](#модель-testcase---тест-кейсы)
6. [Модель GenerationMetric - Метрики](#модель-generationmetric---метрики)
7. [Модель CoverageAnalysis - Анализ покрытия](#модель-coverageanalysis---анализ-покрытия)
8. [Модель SecurityAuditLog - Аудит безопасности](#модель-securityauditlog---аудит-безопасности)
9. [Relationships - Связи между таблицами](#relationships---связи-между-таблицами)
10. [Полезные ссылки](#полезные-ссылки)

---

## Что такое ORM и SQLAlchemy?

### ORM (Object-Relational Mapping)

**ORM** - это техника, которая позволяет работать с базой данных через объекты Python вместо SQL запросов.

**Без ORM (чистый SQL):**
```python
cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
row = cursor.fetchone()
user = User(email=row[0], username=row[1], ...)
```

**С ORM (SQLAlchemy):**
```python
user = db.query(User).filter(User.email == email).first()
```

**Преимущества ORM:**
- Читаемый код (Python вместо SQL)
- Автоматическая валидация типов
- Защита от SQL инъекций
- Миграции схемы БД

**Недостатки:**
- Может быть медленнее для сложных запросов
- Нужно понимать, как ORM генерирует SQL

**Полезная ссылка:** [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

### SQLAlchemy

**SQLAlchemy** - это популярная ORM для Python.

**Основные компоненты:**
- **Engine** - соединение с БД
- **Session** - единица работы с БД
- **Models** - классы, представляющие таблицы
- **Query** - построение запросов

---

## Структура базы данных

### ER-диаграмма

```
┌──────────┐
│   User   │
└────┬─────┘
     │ 1
     │
     │ *
┌────▼─────┐
│ Request  │
└────┬─────┘
     │ 1
     │
     │ *
┌────▼──────┐      ┌──────────────┐
│ TestCase  │      │GenerationMetric│
└───────────┘      └──────────────┘
     │                    │
     │ *                  │ *
     │                    │
     │                    │
┌────▼────────────┐  ┌────▼────────────┐
│SecurityAuditLog │  │CoverageAnalysis │
└─────────────────┘  └─────────────────┘
```

### Таблицы

1. **users** - пользователи системы
2. **requests** - запросы на генерацию тестов
3. **test_cases** - сгенерированные тест-кейсы
4. **generation_metrics** - метрики производительности агентов
5. **coverage_analysis** - анализ покрытия требований
6. **security_audit_log** - аудит безопасности

---

## Модель User - Пользователи

### Определение модели

```python
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

class User(Base):
    """Пользователи системы"""
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    organization = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    api_key = Column(String(64), unique=True, nullable=True)
    api_quota_daily = Column(Integer, default=100)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    requests = relationship("Request", back_populates="user")
```

### Разбор полей

**`user_id`** - UUID, primary key
- `UUID(as_uuid=True)` - PostgreSQL UUID тип
- `primary_key=True` - первичный ключ
- `default=uuid.uuid4` - автоматическая генерация UUID

**`email`** - уникальный email пользователя
- `unique=True` - уникальное значение
- `nullable=False` - обязательное поле

**`hashed_password`** - хешированный пароль
- `nullable=True` - может быть NULL (для OAuth пользователей)

**`is_active`** - активен ли пользователь
- `default=True` - по умолчанию активен
- Можно деактивировать без удаления

**`created_at`** - время создания
- `server_default=func.now()` - устанавливается сервером при создании
- `timezone=True` - с часовым поясом

**`updated_at`** - время обновления
- `onupdate=func.now()` - автоматически обновляется при изменении

**Полезная ссылка:** [SQLAlchemy Column Types](https://docs.sqlalchemy.org/en/20/core/type_basics.html)

### Relationships

```python
requests = relationship("Request", back_populates="user")
```

**Что это значит:**
- У пользователя может быть много запросов
- Связь один-ко-многим (One-to-Many)

**Использование:**
```python
user = db.query(User).filter(User.email == "test@example.com").first()
user_requests = user.requests  # Список всех запросов пользователя
```

---

## Модель Request - Запросы на генерацию

### Определение модели

```python
class Request(Base):
    """Запросы пользователей на генерацию тестов"""
    __tablename__ = "requests"
    
    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    url = Column(Text, nullable=False)
    requirements = Column(JSONB, nullable=False, default=[])
    test_type = Column(String(20), nullable=False)  # manual, automated, both
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed
    result_summary = Column(JSONB, default={})
    error_message = Column(Text, nullable=True)
    celery_task_id = Column(String(255), nullable=True)
    langgraph_thread_id = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="requests")
    test_cases = relationship("TestCase", back_populates="request", cascade="all, delete-orphan")
    generation_metrics = relationship("GenerationMetric", back_populates="request", cascade="all, delete-orphan")
    coverage_analysis = relationship("CoverageAnalysis", back_populates="request", cascade="all, delete-orphan")
    security_audit_logs = relationship("SecurityAuditLog", back_populates="request", cascade="all, delete-orphan")
```

### Разбор полей

**`request_id`** - UUID запроса
- Primary key
- Используется для отслеживания статуса

**`user_id`** - связь с пользователем
- `ForeignKey("users.user_id")` - внешний ключ
- `ondelete="SET NULL"` - при удалении пользователя, user_id становится NULL
- `nullable=True` - может быть NULL (анонимные запросы)

**`url`** - URL для тестирования
- `Text` - неограниченная длина строки

**`requirements`** - требования пользователя
- `JSONB` - JSON тип в PostgreSQL (индексируемый, быстрый)
- `default=[]` - по умолчанию пустой список

**Пример:**
```python
requirements = ["Проверить вход", "Проверить регистрацию"]
```

**`status`** - статус запроса
- `pending` - ожидает обработки
- `processing` - обрабатывается
- `completed` - завершен успешно
- `failed` - завершен с ошибкой
- `cancelled` - отменен

**`result_summary`** - сводка результатов
- `JSONB` - JSON объект
- Пример: `{"tests_generated": 10, "tests_validated": 8, "tests_optimized": 7}`

**`celery_task_id`** - ID задачи Celery
- Используется для отслеживания задачи
- Можно проверить статус через Celery API

**`retry_count`** - количество попыток
- Увеличивается при ошибке
- Если `retry_count >= max_retries` - задача не повторяется

### Relationships

```python
test_cases = relationship("TestCase", back_populates="request", cascade="all, delete-orphan")
```

**`cascade="all, delete-orphan"`** - что это значит?
- При удалении Request удаляются все связанные TestCase
- `delete-orphan` - удаляет TestCase, которые остались без Request

**Использование:**
```python
request = db.query(Request).filter(Request.request_id == request_id).first()
test_cases = request.test_cases  # Список всех тестов для этого запроса
```

---

## Модель TestCase - Тест-кейсы

### Определение модели

```python
class TestCase(Base):
    """Сгенерированные тест-кейсы"""
    __tablename__ = "test_cases"
    
    test_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False)
    test_name = Column(String(255), nullable=False)
    test_code = Column(Text, nullable=False)
    test_type = Column(String(20), nullable=False)  # manual, automated
    allure_feature = Column(String(255), nullable=True)
    allure_story = Column(String(255), nullable=True)
    allure_title = Column(Text, nullable=True)
    allure_severity = Column(String(20), nullable=True)  # blocker, critical, normal, minor, trivial
    allure_tags = Column(JSONB, default=[])
    code_hash = Column(String(64), nullable=False)  # SHA256
    ast_hash = Column(String(64), nullable=True)
    semantic_embedding = Column(Text, nullable=True)  # VECTOR(768) - будет через pgvector
    covered_requirements = Column(JSONB, default=[])
    priority = Column(Integer, default=5)  # 1-10
    validation_status = Column(String(20), default="passed")  # passed, failed, warning
    validation_issues = Column(JSONB, default=[])
    safety_risk_level = Column(String(20), default="SAFE")  # SAFE, LOW, MEDIUM, HIGH, CRITICAL
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(UUID(as_uuid=True), ForeignKey("test_cases.test_id", ondelete="SET NULL"), nullable=True)
    similarity_score = Column(DECIMAL(5, 4), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    request = relationship("Request", back_populates="test_cases")
    security_audit_logs = relationship("SecurityAuditLog", back_populates="test_case", cascade="all, delete-orphan")
```

### Разбор полей

**`test_code`** - Python код теста
- `Text` - неограниченная длина (тесты могут быть длинными)

**`code_hash`** - SHA256 хеш кода
- Используется для дедупликации (поиск точных дубликатов)
- `nullable=False` - всегда должен быть

**`ast_hash`** - хеш AST (Abstract Syntax Tree)
- Используется для поиска семантически похожих тестов
- Игнорирует форматирование и комментарии

**`semantic_embedding`** - векторное представление теста
- Для semantic similarity (поиск похожих тестов)
- В будущем будет через pgvector

**`covered_requirements`** - какие требования покрывает тест
- `JSONB` - список индексов требований
- Пример: `[0, 2, 5]` - покрывает требования 0, 2, 5

**`validation_status`** - результат валидации
- `passed` - прошел валидацию
- `failed` - не прошел валидацию
- `warning` - есть предупреждения

**`safety_risk_level`** - уровень риска безопасности
- `SAFE` - безопасен
- `LOW` - низкий риск
- `MEDIUM` - средний риск
- `HIGH` - высокий риск
- `CRITICAL` - критический риск

**`is_duplicate`** - является ли дубликатом
- `True` - это дубликат другого теста
- Используется для фильтрации

**`duplicate_of`** - ссылка на оригинальный тест
- Self-referential foreign key
- Если `is_duplicate=True`, указывает на оригинал

**`similarity_score`** - оценка схожести с другим тестом
- `DECIMAL(5, 4)` - от 0.0000 до 0.9999
- Используется для semantic similarity

### Self-Referential Relationship

```python
duplicate_of = Column(UUID(as_uuid=True), ForeignKey("test_cases.test_id", ondelete="SET NULL"), nullable=True)
```

**Что это значит:**
- Тест может ссылаться на другой тест в той же таблице
- Используется для хранения информации о дубликатах

**Пример:**
```python
# Оригинальный тест
test1 = TestCase(test_id=uuid1, test_name="Test Login", ...)

# Дубликат
test2 = TestCase(test_id=uuid2, test_name="Test Login", is_duplicate=True, duplicate_of=uuid1)
```

---

## Модель GenerationMetric - Метрики

### Определение модели

```python
class GenerationMetric(Base):
    """Метрики производительности агентов"""
    __tablename__ = "generation_metrics"
    
    metric_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False)
    agent_name = Column(String(50), nullable=False)  # reconnaissance, generator, validator, optimizer
    step_number = Column(Integer, nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False)
    duration_ms = Column(Integer, nullable=False)
    llm_model = Column(String(100), nullable=True)
    llm_tokens_input = Column(Integer, nullable=True)
    llm_tokens_output = Column(Integer, nullable=True)
    llm_tokens_total = Column(Integer, nullable=True)
    llm_cost_usd = Column(DECIMAL(10, 6), nullable=True)
    status = Column(String(20), nullable=False)  # success, failed, retry
    error_message = Column(Text, nullable=True)
    agent_metrics = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    request = relationship("Request", back_populates="generation_metrics")
```

### Назначение

**GenerationMetric** хранит метрики производительности каждого агента:
- Время выполнения
- Использование LLM (токены, стоимость)
- Статус выполнения
- Дополнительные метрики

**Зачем это нужно:**
- Мониторинг производительности
- Оптимизация (какой агент медленный?)
- Анализ стоимости (сколько стоит генерация?)
- Отладка (где произошла ошибка?)

### Разбор полей

**`agent_name`** - имя агента
- `reconnaissance` - анализ страницы
- `generator` - генерация тестов
- `validator` - валидация
- `optimizer` - оптимизация

**`step_number`** - порядковый номер шага
- Для отслеживания последовательности выполнения

**`duration_ms`** - длительность в миллисекундах
- Вычисляется: `(completed_at - started_at).total_seconds() * 1000`

**`llm_tokens_total`** - общее количество токенов
- Используется для расчета стоимости

**`llm_cost_usd`** - стоимость в долларах
- Вычисляется на основе модели и количества токенов

**`agent_metrics`** - дополнительные метрики
- `JSONB` - гибкая структура
- Пример: `{"tests_generated": 10, "validation_errors": 2}`

---

## Модель CoverageAnalysis - Анализ покрытия

### Определение модели

```python
class CoverageAnalysis(Base):
    """Анализ покрытия требований"""
    __tablename__ = "coverage_analysis"
    
    coverage_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False)
    requirement_text = Column(Text, nullable=False)
    requirement_index = Column(Integer, nullable=False)
    is_covered = Column(Boolean, default=False)
    covering_tests = Column(JSONB, default=[])  # Array of test_id
    coverage_count = Column(Integer, default=0)
    coverage_score = Column(DECIMAL(5, 4), nullable=True)
    coverage_details = Column(JSONB, default={})
    has_gap = Column(Boolean, default=True)
    gap_description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    request = relationship("Request", back_populates="coverage_analysis")
```

### Назначение

**CoverageAnalysis** анализирует, какие требования покрыты тестами.

**Зачем это нужно:**
- Убедиться, что все требования покрыты
- Найти пробелы в покрытии
- Приоритизировать тесты

### Разбор полей

**`requirement_text`** - текст требования
- Оригинальный текст требования пользователя

**`requirement_index`** - индекс требования
- Позиция в списке требований (0, 1, 2, ...)

**`is_covered`** - покрыто ли требование
- `True` - есть хотя бы один тест
- `False` - нет тестов

**`covering_tests`** - список тестов, покрывающих требование
- `JSONB` - массив UUID тестов
- Пример: `["uuid1", "uuid2"]`

**`coverage_count`** - количество тестов
- `len(covering_tests)`

**`coverage_score`** - оценка покрытия (0.0 - 1.0)
- `1.0` - идеальное покрытие
- `0.5` - частичное покрытие
- `0.0` - нет покрытия

**`has_gap`** - есть ли пробел
- `True` - требование не покрыто или покрыто недостаточно

**`gap_description`** - описание пробела
- Текст с рекомендациями

---

## Модель SecurityAuditLog - Аудит безопасности

### Определение модели

```python
class SecurityAuditLog(Base):
    """Аудит безопасности - все проверки Safety Guard"""
    __tablename__ = "security_audit_log"
    
    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), ForeignKey("requests.request_id", ondelete="CASCADE"), nullable=False)
    test_id = Column(UUID(as_uuid=True), ForeignKey("test_cases.test_id", ondelete="SET NULL"), nullable=True)
    security_layer = Column(String(20), nullable=False)  # static, ast, behavioral, sandbox
    risk_level = Column(String(20), nullable=False)  # SAFE, LOW, MEDIUM, HIGH, CRITICAL
    issues = Column(JSONB, default=[])
    blocked_patterns = Column(JSONB, default=[])
    action_taken = Column(String(50), nullable=False)  # allowed, blocked, warning, regenerate
    details = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    request = relationship("Request", back_populates="security_audit_logs")
    test_case = relationship("TestCase", back_populates="security_audit_logs")
```

### Назначение

**SecurityAuditLog** хранит все проверки безопасности Safety Guard.

**Зачем это нужно:**
- Аудит безопасности (кто и когда проверил)
- Отладка (почему тест был заблокирован?)
- Анализ (какие паттерны опасны?)

### Разбор полей

**`security_layer`** - уровень проверки
- `static` - статический анализ (regex)
- `ast` - анализ AST
- `behavioral` - поведенческий анализ
- `sandbox` - выполнение в песочнице (в будущем)

**`risk_level`** - уровень риска
- `SAFE` - безопасен
- `LOW` - низкий риск
- `MEDIUM` - средний риск
- `HIGH` - высокий риск
- `CRITICAL` - критический риск

**`issues`** - найденные проблемы
- `JSONB` - массив проблем
- Пример: `[{"type": "missing_decorator", "message": "Отсутствует @allure.feature"}]`

**`blocked_patterns`** - заблокированные паттерны
- `JSONB` - массив паттернов
- Пример: `["eval(", "exec(", "os.system("]`

**`action_taken`** - действие
- `allowed` - разрешено
- `blocked` - заблокировано
- `warning` - предупреждение
- `regenerate` - требуется регенерация

**`details`** - дополнительные детали
- `JSONB` - гибкая структура
- Пример: `{"line_number": 42, "context": "..."}`

---

## Relationships - Связи между таблицами

### One-to-Many (Один-ко-многим)

**User → Request**
```python
# В User
requests = relationship("Request", back_populates="user")

# В Request
user = relationship("User", back_populates="requests")
user_id = Column(UUID, ForeignKey("users.user_id"))
```

**Один пользователь → много запросов**

**Request → TestCase**
```python
# В Request
test_cases = relationship("TestCase", back_populates="request", cascade="all, delete-orphan")

# В TestCase
request = relationship("Request", back_populates="test_cases")
request_id = Column(UUID, ForeignKey("requests.request_id", ondelete="CASCADE"))
```

**Один запрос → много тестов**

### Cascade Options

**`ondelete="CASCADE"`** - при удалении Request удаляются все TestCase
**`ondelete="SET NULL"`** - при удалении User, user_id в Request становится NULL
**`cascade="all, delete-orphan"`** - при удалении Request удаляются все связанные TestCase

**Полезная ссылка:** [SQLAlchemy Relationships](https://docs.sqlalchemy.org/en/20/orm/relationships.html)

### Использование Relationships

```python
# Получить все запросы пользователя
user = db.query(User).filter(User.email == "test@example.com").first()
requests = user.requests  # Список всех запросов

# Получить все тесты для запроса
request = db.query(Request).filter(Request.request_id == request_id).first()
test_cases = request.test_cases  # Список всех тестов

# Получить метрики для запроса
metrics = request.generation_metrics  # Список всех метрик
```

---

## Полезные ссылки

### SQLAlchemy

- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [SQLAlchemy ORM Tutorial](https://docs.sqlalchemy.org/en/20/tutorial/orm_data_manipulation.html)
- [SQLAlchemy Relationships](https://docs.sqlalchemy.org/en/20/orm/relationships.html)
- [SQLAlchemy Column Types](https://docs.sqlalchemy.org/en/20/core/type_basics.html)

### PostgreSQL

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [PostgreSQL JSONB](https://www.postgresql.org/docs/current/datatype-json.html)
- [PostgreSQL UUID](https://www.postgresql.org/docs/current/datatype-uuid.html)

### Database Design

- [Database Normalization](https://en.wikipedia.org/wiki/Database_normalization)
- [ER Diagrams](https://www.lucidchart.com/pages/er-diagrams)

---

## Часто задаваемые вопросы

### Q: Почему использовать UUID вместо auto-increment ID?

**A:** 
- UUID уникальны глобально (можно объединять БД)
- Не раскрывают информацию (сколько записей в БД)
- Безопаснее (нельзя угадать следующий ID)

**Недостатки:**
- Больше места (16 байт vs 4-8 байт)
- Медленнее индексация

### Q: Зачем JSONB вместо JSON?

**A:** 
- JSONB индексируется (быстрее поиск)
- JSONB нормализуется (удаляет дубликаты ключей)
- JSONB поддерживает операторы (например, `@>` для поиска)

**Полезная ссылка:** [PostgreSQL JSONB vs JSON](https://www.postgresql.org/docs/current/datatype-json.html#JSON-INDEXING)

### Q: Что такое cascade и зачем оно нужно?

**A:** Cascade определяет, что происходит с дочерними записями при удалении родительской.

**Примеры:**
- `CASCADE` - удалить дочерние записи
- `SET NULL` - установить NULL в foreign key
- `RESTRICT` - запретить удаление, если есть дочерние записи

### Q: Зачем хранить code_hash и ast_hash?

**A:**
- `code_hash` - для поиска точных дубликатов (быстро)
- `ast_hash` - для поиска семантически похожих тестов (игнорирует форматирование)

---

## Заключение

Database Models - это структура данных системы, которая:
- Определяет, какие данные хранятся
- Устанавливает связи между данными
- Обеспечивает целостность данных
- Упрощает работу с данными через ORM

Понимание моделей необходимо для работы с данными в системе!

