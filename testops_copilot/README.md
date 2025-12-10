# TestOps Copilot

**AI-ассистент для автоматизации работы QA-инженера**

Автоматическая генерация тест-кейсов на основе требований и спецификаций с использованием Cloud.ru Evolution Foundation Model.

---

## Быстрый старт

### Требования
- Docker и Docker Compose
- Python 3.10+
- PostgreSQL 15+ с расширением pgvector
- Redis 7+

### Запуск проекта

```bash
# Переход в директорию проекта
cd testops_copilot

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл, добавив необходимые ключи API

# Запуск всех сервисов
docker-compose up -d

# Проверка статуса
docker-compose ps
```

### Проверка работоспособности

```bash
# Health check
curl http://localhost:8000/health

# API документация
open http://localhost:8000/docs
```

---

## Основные возможности

### Генерация тестов
- **UI тесты** - автоматический анализ веб-страниц и генерация Playwright тестов
- **API тесты** - генерация на основе OpenAPI спецификаций
- **Поддержка формата** - Allure TestOps as Code (Python)

### Валидация и оптимизация
- **Многоуровневая валидация** - синтаксис, семантика, логика, безопасность
- **Дедупликация** - поиск и удаление дубликатов тестов
- **Анализ покрытия** - проверка соответствия требованиям

### Интеграции
- **GitHub/GitLab** - автоматический commit тестов в репозиторий
- **Jira/Allure TestOps** - интеграция с системами управления тестами
- **Email уведомления** - оповещения о завершении генерации

### Мониторинг
- **Real-time обновления** - Server-Sent Events для отслеживания прогресса
- **Prometheus метрики** - мониторинг производительности
- **Логирование** - детальные логи всех операций

---

## Архитектура

Проект построен на микросервисной архитектуре:

```
┌─────────────┐
│   Frontend  │  React 19 + TypeScript
└──────┬──────┘
       │
┌──────▼──────┐
│ API Gateway │  FastAPI - единая точка входа
└──────┬──────┘
       │
   ┌───┴───┐
   │       │
┌──▼──┐ ┌─▼────┐
│Redis│ │Celery│  Асинхронная обработка
└──┬──┘ └─┬────┘
   │      │
┌──▼──────▼──┐
│  Workers   │  Генерация, валидация, оптимизация
└──────┬─────┘
       │
┌──────▼──────┐
│   Agents    │  AI-агенты для различных задач
└──────┬──────┘
       │
┌──────▼──────┐
│ PostgreSQL  │  Хранение данных и checkpoints
└─────────────┘
```

### Компоненты

**API Gateway** (`api_gateway/`)
- FastAPI приложение
- REST API endpoints
- Middleware (CORS, rate limiting, logging)
- SSE streaming для real-time обновлений

**Workers** (`workers/`)
- Celery workers для асинхронной обработки
- Workflow генерации тестов
- LangGraph для оркестрации агентов

**Agents** (`agents/`)
- **ReconnaissanceAgent** - анализ веб-страниц
- **GeneratorAgent** - генерация тестов через LLM
- **ValidatorAgent** - валидация тестов
- **OptimizerAgent** - оптимизация и дедупликация
- **SafetyGuard** - проверка безопасности кода
- **TestPlanGeneratorAgent** - генерация тест-планов

**Shared** (`shared/`)
- Утилиты для работы с БД, Redis, LLM
- Конфигурация приложения
- Модели данных

---

## API Endpoints

### Генерация тестов

```bash
# Генерация UI тестов
POST /api/v1/generate/test-cases
{
  "url": "https://example.com",
  "requirements": ["Проверить главную страницу"],
  "test_type": "both",
  "use_langgraph": true
}

# Генерация API тестов
POST /api/v1/generate/api-tests
{
  "openapi_url": "https://api.example.com/openapi.json",
  "endpoints": ["/users", "/posts"]
}
```

### Управление задачами

```bash
# Получение статуса задачи
GET /api/v1/tasks/{task_id}?include_tests=true

# Возобновление workflow
POST /api/v1/tasks/{task_id}/resume
```

### Поиск и экспорт

```bash
# Поиск тестов
GET /api/v1/tests?search=calculator&test_type=automated&page=1

# Экспорт тестов
GET /api/v1/tests/export?format=zip&request_id={request_id}
```

### Валидация и оптимизация

```bash
# Валидация теста
POST /api/v1/validate/tests
{
  "test_code": "def test_example(): assert True",
  "validation_level": "full"
}

# Оптимизация тестов
POST /api/v1/optimize/tests
{
  "tests": [...],
  "requirements": [...]
}
```

Полная документация API доступна по адресу: `http://localhost:8000/docs`

---

## Конфигурация

Основные настройки в файле `.env`:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/testops_copilot

# Redis
REDIS_URL=redis://localhost:6379/0

# Cloud.ru API
CLOUD_RU_API_KEY=your_api_key
CLOUD_RU_KEY_ID=your_key_id
CLOUD_RU_KEY_SECRET=your_key_secret

# Email
EMAIL_NOTIFICATIONS_ENABLED=false
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=user@example.com
SMTP_PASSWORD=password
```

---

## Тестирование

### Запуск тестов

```bash
# Unit тесты
pytest tests/unit/

# Integration тесты
pytest tests/integration/

# Все тесты
pytest tests/
```

### Покрытие кода

```bash
pytest --cov=agents --cov=api_gateway --cov=workers tests/
```

---

## Документация

Подробная документация для разработчиков находится в папке `testops_copilot/docs/`:

- **[00_OVERVIEW.md](testops_copilot/docs/00_OVERVIEW.md)** - Общий обзор системы
- **[01_API_GATEWAY.md](testops_copilot/docs/01_API_GATEWAY.md)** - API Gateway
- **[02_WORKERS.md](testops_copilot/docs/02_WORKERS.md)** - Celery Workers
- **[03_AGENTS.md](testops_copilot/docs/03_AGENTS.md)** - AI-агенты
- **[04_SHARED.md](testops_copilot/docs/04_SHARED.md)** - Общие компоненты
- **[05_DATABASE.md](testops_copilot/docs/05_DATABASE.md)** - Модели базы данных
- **[06_TODO.md](testops_copilot/docs/06_TODO.md)** - Что осталось реализовать

---

## Разработка

### Структура проекта

```
testops_copilot/
├── api_gateway/          # FastAPI приложение
│   ├── routers/          # API endpoints
│   └── middleware/       # Middleware
├── workers/              # Celery workers
│   └── tasks/            # Асинхронные задачи
├── agents/               # AI-агенты
│   ├── generator/        # Генерация тестов
│   ├── validator/        # Валидация
│   ├── optimizer/        # Оптимизация
│   └── reconnaissance/   # Анализ страниц
├── shared/               # Общие компоненты
│   ├── config/           # Конфигурация
│   ├── models/           # Модели данных
│   └── utils/            # Утилиты
├── tests/                # Тесты
│   ├── unit/             # Unit тесты
│   └── integration/      # Integration тесты
└── docs/                 # Документация
```

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Запуск в режиме разработки

```bash
# API Gateway
uvicorn api_gateway.main:app --reload --port 8000

# Celery Worker
celery -A workers.celery_app worker --loglevel=info

# Flower (мониторинг Celery)
celery -A workers.celery_app flower --port=5555
```

---

## Мониторинг

### Prometheus метрики

```bash
curl http://localhost:8000/metrics
```

### Flower (Celery)

```bash
open http://localhost:5555
```

### Логи

```bash
# Логи API Gateway
docker-compose logs -f api_gateway

# Логи Workers
docker-compose logs -f celery_worker
```

---

## Отладка

### Проверка подключений

```bash
# Проверка БД
docker-compose exec postgres psql -U testops -d testops_copilot

# Проверка Redis
docker-compose exec redis redis-cli ping

# Проверка Celery
celery -A workers.celery_app inspect active
```

### Частые проблемы

**Проблема:** Ошибка подключения к БД
```bash
# Решение: Проверьте DATABASE_URL в .env
docker-compose restart postgres
```

**Проблема:** Celery задачи не выполняются
```bash
# Решение: Проверьте Redis и перезапустите worker
docker-compose restart redis celery_worker
```

---

## Статус проекта

### Реализовано

- [x] Генерация UI и API тестов
- [x] Валидация и оптимизация тестов
- [x] Интеграция с GitHub/GitLab
- [x] LangGraph workflow с checkpointing
- [x] Safety Guard (4 уровня защиты)
- [x] Поиск и фильтрация тестов
- [x] Экспорт тестов (ZIP, JSON, YAML)
- [x] Email уведомления
- [x] Real-time обновления (SSE)
- [x] Prometheus метрики
- [x] Unit и integration тесты

### В разработке

- [ ] JWT аутентификация
- [ ] API Keys управление
- [ ] Скриншоты элементов
- [ ] Redis RediSearch для vector search
- [ ] Grafana dashboards
- [ ] CI/CD pipelines

Полный список задач: [testops_copilot/docs/06_TODO.md](testops_copilot/docs/06_TODO.md)

---

## Вклад в проект

1. Fork проекта
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменения (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

---

## Лицензия

Проект разработан для Cloud.ru

---

## Контакты

- **Документация:** [testops_copilot/docs/](testops_copilot/docs/)
- **Issues:** Создайте issue в репозитории
- **API Docs:** http://localhost:8000/docs

---

**Версия:** 1.0.0  
**Последнее обновление:** 2024
