# Логирование и проверка системы

## Добавленное логирование

### 1. Генератор тестов (`agents/generator/generator.py`)

Добавлено детальное логирование:
- `[GENERATION]` - логи процесса генерации
- Информация о длине сгенерированного кода
- Количество извлеченных тестов
- Информация о каждом тесте (декораторы, тип)
- Предупреждения при отсутствии тестов

**Пример логов:**
```
[GENERATION] LLM generated code (code_length=5000, test_type=both, url=https://...)
[GENERATION] Extracted 25 tests from generated code (tests_count=25, expected_manual=15, expected_automated=10)
[GENERATION] Test 1 info (has_decorators=True, is_manual=False, code_length=200)
```

### 2. Валидатор (`agents/validator/validator_agent.py`)

Добавлено детальное логирование:
- `[VALIDATOR]` - логи процесса валидации
- Результаты каждого этапа валидации (syntax, semantic, logic, safety)
- Детальная информация о score и ошибках
- Предупреждения при обнаружении проблем

**Пример логов:**
```
[VALIDATOR] Starting validation (level=full)
[VALIDATOR] Syntax validation passed
[VALIDATOR] Semantic validation passed (warnings: 2)
[VALIDATOR] Validation completed (passed=True, score=100, syntax_errors=0, semantic_errors=0, warnings=2)
```

### 3. Workflow генерации (`workers/tasks/generate_workflow.py`)

Добавлено детальное логирование:
- `[GENERATION]` - логи начала и завершения генерации
- `[VALIDATION]` - логи процесса валидации каждого теста
- `[STATUS]` - логи определения статуса каждого теста
- Детальная информация о каждом этапе

**Пример логов:**
```
[GENERATION] Starting test generation (request_id=..., url=..., test_type=both)
[GENERATION] Test generation completed (tests_generated=25)
[VALIDATION] Starting validation of 25 tests for request ...
[VALIDATION] Test 1 validation result (passed=True, score=100, has_decorators=True)
[STATUS] Test 'test_example' status determination (validation_status=passed)
```

### 4. API Workflow (`workers/tasks/generate_api_workflow.py`)

Добавлено аналогичное логирование для API тестов:
- `[GENERATION]` - логи генерации API тестов
- `[VALIDATION]` - логи валидации API тестов
- `[STATUS]` - логи определения статуса

## Проверка работы системы

### Способ 1: Скрипт проверки

Запустите скрипт проверки:
```bash
python scripts/test_system.py
```

Скрипт проверяет:
1. ✅ Инициализацию генератора
2. ✅ Работу валидатора
3. ✅ Логику определения статуса

### Способ 2: Проверка через Docker

1. **Проверка логов API Gateway:**
```bash
docker-compose logs -f api_gateway | grep -E "\[GENERATION\]|\[VALIDATION\]|\[STATUS\]"
```

2. **Проверка логов Celery Worker:**
```bash
docker-compose logs -f celery_worker | grep -E "\[GENERATION\]|\[VALIDATION\]|\[STATUS\]"
```

3. **Проверка всех логов:**
```bash
docker-compose logs -f | grep -E "\[GENERATION\]|\[VALIDATION\]|\[STATUS\]|\[VALIDATOR\]"
```

### Способ 3: Тестовая генерация через API

1. **Генерация UI тестов:**
```bash
curl -X POST "http://localhost:8000/api/v1/generate/test-cases" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://cloud.ru/calculator",
    "requirements": ["Проверить калькулятор"],
    "test_type": "manual",
    "options": {"manual_count": 15}
  }'
```

2. **Проверка статуса задачи:**
```bash
# Получите request_id из ответа предыдущего запроса
curl "http://localhost:8000/api/v1/tasks/{request_id}?include_tests=true"
```

3. **Проверка логов:**
```bash
docker-compose logs -f celery_worker | grep "{request_id}"
```

## Что проверять в логах

### ✅ Успешная генерация

Ищите в логах:
```
[GENERATION] Test generation completed (tests_generated=15+)
[GENERATION] Extracted 15+ tests from generated code
```

### ✅ Успешная валидация

Ищите в логах:
```
[VALIDATION] Validation completed (passed=True, score>=50)
[VALIDATION] Test X validation result (has_decorators=True)
```

### ✅ Правильный статус

Ищите в логах:
```
[STATUS] Test 'test_name' status determination (validation_status=passed)
```

### ⚠️ Проблемы

Если видите:
```
[VALIDATION] Test X has issues but will be added
[STATUS] Test 'test_name' status determination (validation_status=warning)
```

Проверьте:
- Есть ли синтаксические ошибки
- Есть ли декораторы
- Какой score

## Типичные проблемы и решения

### Проблема: Все тесты со статусом "warning"

**Причина:** Отсутствие декораторов или низкий score

**Решение:** 
1. Проверьте логи `[GENERATION]` - добавляются ли декораторы
2. Проверьте логи `[VALIDATION]` - какой score
3. Проверьте логи `[STATUS]` - почему статус warning

**Ожидаемое поведение:**
- Тесты с декораторами → статус "passed"
- Тесты без синтаксических ошибок и score >= 50 → статус "passed"
- Только тесты с синтаксическими ошибками → статус "warning"

### Проблема: Нет тестов в результате

**Причина:** LLM не сгенерировал тесты или ошибка извлечения

**Решение:**
1. Проверьте логи `[GENERATION]` - сколько тестов извлечено
2. Проверьте наличие ошибок в логах
3. Проверьте настройки LLM (API ключ, модель)

### Проблема: Низкий score валидации

**Причина:** Отсутствие assertions или декораторов

**Решение:**
1. Генератор должен автоматически добавлять декораторы
2. Генератор должен автоматически добавлять assertions
3. Проверьте логи `[GENERATION]` - добавляются ли они

## Мониторинг в реальном времени

Для мониторинга генерации в реальном времени:

```bash
# Все логи с фильтрацией
docker-compose logs -f | grep -E "\[GENERATION\]|\[VALIDATION\]|\[STATUS\]"

# Только ошибки и предупреждения
docker-compose logs -f | grep -E "WARNING|ERROR|\[VALIDATION\].*issues"

# Только успешные операции
docker-compose logs -f | grep -E "\[GENERATION\].*completed|\[VALIDATION\].*ACCEPTED|\[STATUS\].*passed"
```

## Структура логов

Все логи имеют структурированный формат:
```
[TAG] Message (extra={"key": "value", ...})
```

Где:
- `[GENERATION]` - процесс генерации тестов
- `[VALIDATION]` - процесс валидации тестов
- `[STATUS]` - определение статуса теста
- `[VALIDATOR]` - детали валидации

## Следующие шаги

1. ✅ Логирование добавлено
2. ✅ Скрипт проверки создан
3. ⏳ Запустить тестовую генерацию
4. ⏳ Проверить логи
5. ⏳ Убедиться что статусы правильные

