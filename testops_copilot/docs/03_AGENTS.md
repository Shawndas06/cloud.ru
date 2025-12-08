# Agents - Подробное объяснение для Junior разработчиков

## 📋 Содержание
1. [Что такое AI-агенты?](#что-такое-ai-агенты)
2. [Архитектура агентов](#архитектура-агентов)
3. [ReconnaissanceAgent - Анализ веб-страниц](#reconnaissanceagent---анализ-веб-страниц)
4. [GeneratorAgent - Генерация тестов](#generatoragent---генерация-тестов)
5. [ValidatorAgent - Валидация тестов](#validatoragent---валидация-тестов)
6. [OptimizerAgent - Оптимизация тестов](#optimizeragent---оптимизация-тестов)
7. [SafetyGuard - Система безопасности](#safetyguard---система-безопасности)
8. [TestPlanGeneratorAgent - Генерация тест-планов](#testplangeneratoragent---генерация-тест-планов)
9. [Полезные ссылки](#полезные-ссылки)

---

## Что такое AI-агенты?

### Концепция агентов

**AI-агент** - это программный компонент, который использует искусственный интеллект (LLM) для выполнения конкретной задачи.

**В нашем проекте агенты:**
- Анализируют веб-страницы
- Генерируют код тестов
- Валидируют качество кода
- Оптимизируют наборы тестов
- Создают тест-планы

### Почему агенты, а не просто функции?

**Преимущества:**
1. **Модульность** - каждый агент решает свою задачу
2. **Переиспользование** - агенты можно использовать в разных контекстах
3. **Тестируемость** - каждый агент тестируется отдельно
4. **Расширяемость** - легко добавить новый агент

**Аналогия:** Как специалисты в команде - каждый эксперт в своей области.

---

## Архитектура агентов

### Структура

```
agents/
├── reconnaissance/      # Анализ веб-страниц
│   └── reconnaissance_agent.py
├── generator/           # Генерация тестов
│   ├── generator_agent.py
│   ├── openapi_parser.py
│   └── cloud_ru_api_generator.py
├── validator/           # Валидация тестов
│   ├── validator_agent.py
│   └── safety_guard.py
├── optimizer/           # Оптимизация тестов
│   └── optimizer_agent.py
└── test_plan/          # Генерация тест-планов
    ├── test_plan_generator_agent.py
    ├── defect_analyzer.py
    └── defect_integration.py
```

### Общие компоненты

Все агенты используют:
- **LLMClient** (`shared/utils/llm_client.py`) - для запросов к LLM API
- **Logger** (`shared/utils/logger.py`) - для логирования
- **Database** (`shared/utils/database.py`) - для сохранения результатов

---

## ReconnaissanceAgent - Анализ веб-страниц

### Назначение

**ReconnaissanceAgent** анализирует структуру веб-страницы и извлекает информацию о:
- Кнопках
- Поля ввода
- Ссылках
- Селекторах

Эта информация используется для генерации тестов.

### Как работает

#### Шаг 1: Запуск браузера

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0..."
    )
    page = context.new_page()
```

**Что происходит:**
- Запускается Chromium браузер в headless режиме (без UI)
- Создается контекст с настройками viewport
- Открывается новая страница

**Почему Playwright?**
- Современный инструмент для автоматизации браузеров
- Поддерживает все современные браузеры
- Быстрый и надежный

**Полезная ссылка:** [Playwright Documentation](https://playwright.dev/python/)

#### Шаг 2: Загрузка страницы

```python
page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
```

**Параметры:**
- `wait_until="networkidle"` - ждать, пока сеть не станет неактивной (страница загружена)
- `timeout` - максимальное время ожидания

**Альтернативы `wait_until`:**
- `"load"` - ждать события `load`
- `"domcontentloaded"` - ждать загрузки DOM
- `"networkidle"` - ждать отсутствия сетевых запросов (лучше для SPA)

#### Шаг 3: Извлечение элементов

```python
buttons = page.evaluate("""
    () => {
        const buttons = [];
        document.querySelectorAll('button, [role="button"], a[href]').forEach(btn => {
            const text = btn.textContent?.trim() || '';
            const selector = btn.getAttribute('data-testid') || 
                           btn.getAttribute('id') || 
                           btn.className;
            if (text || selector) {
                buttons.push({
                    text: text,
                    selector: selector || '',
                    visible: btn.offsetParent !== null
                });
            }
        });
        return buttons;
    }
""")
```

**Что происходит:**
- `page.evaluate()` - выполняет JavaScript код в контексте страницы
- Находит все кнопки (button, [role="button"], ссылки)
- Извлекает текст и селектор
- Проверяет видимость (`offsetParent !== null`)

**Приоритет селекторов:**
1. `data-testid` - лучший вариант (специально для тестов)
2. `id` - уникальный идентификатор
3. `className` - класс (менее надежно)

#### Шаг 4: Генерация селекторов

```python
def _generate_selectors(self, page: Page) -> Dict[str, str]:
    """Генерация рекомендуемых селекторов"""
    selectors = {}
    
    # Поиск элементов с data-testid (приоритет 1)
    testid_elements = page.evaluate("""
        () => {
            const elements = {};
            document.querySelectorAll('[data-testid]').forEach(el => {
                const testid = el.getAttribute('data-testid');
                elements[testid] = `[data-testid="${testid}"]`;
            });
            return elements;
        }
    """)
    selectors.update(testid_elements)
    
    return selectors
```

**Результат:**
```python
{
    "title": "Login Page",
    "url": "https://example.com/login",
    "buttons": [
        {"text": "Login", "selector": "[data-testid='login-btn']", "visible": True},
        {"text": "Cancel", "selector": "#cancel-btn", "visible": True}
    ],
    "inputs": [
        {"name": "username", "type": "text", "selector": "#username", "visible": True},
        {"name": "password", "type": "password", "selector": "#password", "visible": True}
    ],
    "links": [
        {"text": "Forgot password?", "href": "/forgot", "visible": True}
    ],
    "selectors": {
        "login-btn": "[data-testid='login-btn']",
        "username": "#username"
    }
}
```

### Обработка ошибок

```python
max_retries = 2

for attempt in range(max_retries):
    try:
        # Попытка анализа
        page_structure = self._extract_page_structure(page, url)
        return page_structure
    except PlaywrightTimeoutError:
        if attempt < max_retries - 1:
            time.sleep(2)  # Пауза перед retry
            continue
        raise Exception(f"Page load timeout after {max_retries} attempts")
```

**Стратегия retry:**
- При таймауте - повторная попытка
- Максимум 2 попытки
- Пауза между попытками

---

## GeneratorAgent - Генерация тестов

### Назначение

**GeneratorAgent** использует LLM для генерации тест-кейсов на основе:
- Структуры страницы (от ReconnaissanceAgent)
- Требований пользователя
- Типа тестов (manual/automated)

### Системные промпты

#### UI тесты

```python
UI_SYSTEM_PROMPT = """Ты — senior QA automation engineer с 10+ годами опыта...
ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ К КОДУ:

1. Allure декораторы (обязательно для каждого теста):
   - @allure.feature("Название фичи")
   - @allure.story("Название user story")
   - @allure.title("Понятное название")
   - @allure.tag("CRITICAL|NORMAL|LOW")
   - @allure.severity(allure.severity_level.CRITICAL)

2. Структура теста (паттерн AAA):
   - Arrange - подготовка
   - Act - выполнение
   - Assert - проверка
...
"""
```

**Зачем системный промпт?**
- Задает роль AI (senior QA engineer)
- Определяет требования к коду
- Обеспечивает единообразие

**Полезная ссылка:** [Prompt Engineering Guide](https://www.promptingguide.ai/)

#### API тесты

```python
API_SYSTEM_PROMPT = """Ты — senior QA automation engineer...
Типы тестов для каждого endpoint:
- Positive: успешный запрос (200, 201, 204)
- Negative: Validation - невалидные данные (400, 422)
- Negative: Auth - без токена (401)
- Negative: Forbidden - нет прав (403)
- Negative: Not Found - несуществующий ресурс (404)
...
"""
```

### Генерация UI тестов

```python
async def generate_ui_tests(
    self,
    url: str,
    page_structure: Dict[str, Any],
    requirements: List[str],
    test_type: str = "both",
    options: Dict[str, Any] = None
) -> List[str]:
    """Генерация UI тест-кейсов"""
    
    # Построение промпта
    user_prompt = self._build_ui_prompt(url, page_structure, requirements, test_type, options)
    
    # Вызов LLM
    response = await llm_client.generate(
        prompt=user_prompt,
        system_prompt=self.UI_SYSTEM_PROMPT,
        model=None,  # Используется модель по умолчанию
        temperature=0.3,  # Низкая температура = более детерминированный ответ
        max_tokens=4096
    )
    
    # Парсинг ответа
    generated_code = response["choices"][0]["message"]["content"]
    tests = self._extract_tests_from_code(generated_code)
    
    return tests
```

**Параметры LLM:**
- `temperature=0.3` - низкая температура = более предсказуемый код
- `max_tokens=4096` - максимум токенов в ответе
- `model=None` - используется модель по умолчанию из настроек

**Полезная ссылка:** [LLM Parameters Explained](https://platform.openai.com/docs/api-reference/completions/create)

### Построение промпта

```python
def _build_ui_prompt(
    self,
    url: str,
    page_structure: Dict,
    requirements: List[str],
    test_type: str,
    options: Dict
) -> str:
    """Построение промпта для UI тестов"""
    
    buttons = page_structure.get("buttons", [])[:10]
    inputs = page_structure.get("inputs", [])[:10]
    
    prompt = f"""Сгенерируй полные, production-ready тест-кейсы для веб-страницы.

КОНТЕКСТ:
URL: {url}
Заголовок страницы: {page_structure.get('title', 'N/A')}

ДОСТУПНЫЕ ЭЛЕМЕНТЫ СТРАНИЦЫ:

Кнопки:
{chr(10).join(f'- {btn.get("text", "")} (селектор: {btn.get("selector", "")})' for btn in buttons)}

Поля ввода:
{chr(10).join(f'- {inp.get("name", "")} (тип: {inp.get("type", "")})' for inp in inputs)}

ТРЕБОВАНИЯ ПОЛЬЗОВАТЕЛЯ:
{chr(10).join(f'{i+1}. {req}' for i, req in enumerate(requirements))}

ИНСТРУКЦИИ:
1. Сгенерируй тест-кейсы в формате Allure TestOps as Code
2. Каждый тест должен быть полным и независимым
3. Используй data-testid селекторы (приоритет 1)
4. Оборачивай каждое действие в allure.step()
"""
    return prompt
```

**Структура промпта:**
1. Контекст (URL, заголовок)
2. Доступные элементы (кнопки, поля)
3. Требования пользователя
4. Инструкции по генерации

### Извлечение тестов из кода

```python
def _extract_tests_from_code(self, code: str) -> List[str]:
    """Извлечение отдельных тестов из сгенерированного кода"""
    
    # Поиск функций test_*
    test_pattern = r'def\s+(test_\w+)\s*\([^)]*\):'
    matches = list(re.finditer(test_pattern, code))
    
    if not matches:
        return [code]  # Возвращаем весь код как один тест
    
    tests = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(code)
        test_code = code[start:end].strip()
        
        # Добавление импортов если их нет
        if "import allure" not in test_code:
            test_code = "import allure\nfrom playwright.sync_api import Page, expect\n\n" + test_code
        
        tests.append(test_code)
    
    return tests
```

**Что происходит:**
- Ищет все функции `test_*` через regex
- Разделяет код на отдельные тесты
- Добавляет необходимые импорты

---

## ValidatorAgent - Валидация тестов

### Назначение

**ValidatorAgent** проверяет качество сгенерированных тестов на нескольких уровнях:
1. **Синтаксис** - валидный ли Python код?
2. **Семантика** - есть ли обязательные декораторы?
3. **Логика** - нет ли бесконечных циклов?
4. **Безопасность** - нет ли опасного кода?

### Многоуровневая валидация

```python
def validate(
    self,
    test_code: str,
    validation_level: str = "full"
) -> Dict[str, Any]:
    """Валидация тест-кейса"""
    
    result = {
        "passed": True,
        "score": 100,
        "syntax_errors": [],
        "semantic_errors": [],
        "logic_errors": [],
        "safety_issues": [],
        "warnings": []
    }
    
    # Layer 1: Syntax Validation
    syntax_result = self._validate_syntax(test_code)
    if syntax_result["errors"]:
        result["passed"] = False
        result["score"] = 0
        return result
    
    # Layer 2: Semantic Validation
    semantic_result = self._validate_semantic(test_code)
    if semantic_result["errors"]:
        result["passed"] = False
        result["score"] -= 30
    
    # Layer 3: Logic Validation
    logic_result = self._validate_logic(test_code)
    if logic_result["errors"]:
        result["passed"] = False
        result["score"] -= 20
    
    # Layer 4: Safety Guard
    safety_result = self.safety_guard.validate(test_code)
    if safety_result.get("risk_level") in ["HIGH", "CRITICAL"]:
        result["passed"] = False
        result["score"] = 0
    
    return result
```

**Уровни валидации:**
- `syntax` - только синтаксис
- `semantic` - синтаксис + семантика
- `full` - все уровни

### Синтаксическая валидация

```python
def _validate_syntax(self, test_code: str) -> Dict[str, List]:
    """Валидация синтаксиса через AST"""
    errors = []
    try:
        ast.parse(test_code)  # Парсинг в AST
    except SyntaxError as e:
        errors.append({
            "line": e.lineno,
            "message": f"SyntaxError: {e.msg}"
        })
    return {"errors": errors}
```

**AST (Abstract Syntax Tree)** - дерево синтаксического разбора кода.

**Почему AST?**
- Быстрая проверка синтаксиса
- Не выполняет код (безопасно)
- Точное указание ошибки

**Полезная ссылка:** [Python AST Module](https://docs.python.org/3/library/ast.html)

### Семантическая валидация

```python
def _validate_semantic(self, test_code: str) -> Dict[str, List]:
    """Валидация семантики (Allure декораторы, AAA pattern)"""
    errors = []
    warnings = []
    
    # Проверка Allure декораторов
    required_decorators = {
        "@allure.feature": r"@allure\.feature\s*\(",
        "@allure.story": r"@allure\.story\s*\(",
        "@allure.title": r"@allure\.title\s*\(",
        "@allure.tag": r"@allure\.tag\s*\("
    }
    
    for decorator, pattern in required_decorators.items():
        if not re.search(pattern, test_code):
            errors.append({
                "type": "missing_decorator",
                "message": f"Отсутствует {decorator} декоратор"
            })
    
    # Проверка assertions
    if not re.search(r"(assert\s+|expect\()", test_code):
        errors.append({
            "type": "missing_assertion",
            "message": "Тест должен содержать хотя бы одну assertion"
        })
    
    return {"errors": errors, "warnings": warnings}
```

**Что проверяется:**
- Наличие обязательных Allure декораторов
- Наличие assertions (проверок)
- Использование `allure.step()`

### Логическая валидация

```python
def _validate_logic(self, test_code: str) -> Dict[str, List]:
    """Валидация логики"""
    errors = []
    warnings = []
    
    # Проверка бесконечных циклов
    if re.search(r"while\s+True\s*:", test_code):
        if "break" not in test_code:
            errors.append({
                "type": "infinite_loop",
                "message": "Обнаружен while True без break"
            })
    
    # Проверка time.sleep (не рекомендуется)
    if "time.sleep" in test_code:
        warnings.append("Использование time.sleep() не рекомендуется")
    
    return {"errors": errors, "warnings": warnings}
```

**Что проверяется:**
- Бесконечные циклы без `break`
- Использование `time.sleep()` (лучше использовать явные waits)

---

## OptimizerAgent - Оптимизация тестов

### Назначение

**OptimizerAgent** оптимизирует набор тестов:
- Удаляет дубликаты (точные и семантические)
- Анализирует покрытие требований
- Предлагает рекомендации

### Процесс оптимизации

```python
async def optimize(
    self,
    tests: List[Dict[str, str]],
    requirements: List[str],
    options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Оптимизация набора тестов"""
    
    # Level 1: Exact Match Deduplication
    exact_duplicates = self._find_exact_duplicates(tests)
    
    # Level 2: Semantic Similarity
    semantic_duplicates = await self._find_semantic_duplicates(tests, similarity_threshold)
    
    # Coverage Analysis
    coverage_result = self._analyze_coverage(tests, requirements)
    
    # Формирование результата
    all_duplicates = exact_duplicates + semantic_duplicates
    unique_tests = self._remove_duplicates(tests, all_duplicates)
    
    return {
        "optimized_tests": unique_tests,
        "duplicates_found": len(all_duplicates),
        "coverage_score": coverage_result["score"],
        "gaps": coverage_result["gaps"]
    }
```

### Точные дубликаты

```python
def _find_exact_duplicates(self, tests: List[Dict]) -> List[Dict]:
    """Level 1: Exact Match - сравнение по хешу"""
    duplicates = []
    seen_hashes = {}
    
    for test in tests:
        code_hash = hashlib.sha256(test["test_code"].encode()).hexdigest()
        
        if code_hash in seen_hashes:
            duplicates.append({
                "test_ids": [seen_hashes[code_hash], test["test_id"]],
                "type": "exact",
                "similarity_score": 1.0
            })
        else:
            seen_hashes[code_hash] = test["test_id"]
    
    return duplicates
```

**Как работает:**
- Вычисляет SHA256 хеш кода каждого теста
- Если хеш совпадает - это точный дубликат
- Быстро и точно

### Семантические дубликаты

```python
async def _find_semantic_duplicates(
    self,
    tests: List[Dict],
    threshold: float
) -> List[Dict]:
    """Level 2: Semantic Similarity с использованием embeddings"""
    
    # Генерация embeddings для всех тестов
    embeddings = []
    for test in tests:
        test_text = f"{test.get('test_name', '')} {test.get('test_code', '')}"
        embedding = await llm_client.generate_embeddings(test_text)
        embeddings.append(embedding)
    
    # Поиск семантически похожих тестов
    duplicates = []
    for i in range(len(tests)):
        for j in range(i + 1, len(tests)):
            similarity = self._cosine_similarity(
                embeddings[i],
                embeddings[j]
            )
            
            if similarity >= threshold:
                duplicates.append({
                    "test_ids": [tests[i]["test_id"], tests[j]["test_id"]],
                    "type": "semantic",
                    "similarity_score": float(similarity)
                })
    
    return duplicates
```

**Как работает:**
1. Генерирует embeddings (векторные представления) для каждого теста
2. Вычисляет косинусное сходство между парами
3. Если сходство >= threshold (например, 0.85) - это семантический дубликат

**Embeddings** - числовые векторы, представляющие смысл текста.

**Косинусное сходство:**
```python
def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Вычисление косинусного сходства"""
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    return float(similarity)
```

**Формула:** `cos(θ) = (A · B) / (||A|| * ||B||)`

**Результат:** от -1 до 1, где 1 = идентичные, 0 = разные

**Полезная ссылка:** [Cosine Similarity Explained](https://www.machinelearningplus.com/nlp/cosine-similarity/)

### Анализ покрытия

```python
def _analyze_coverage(
    self,
    tests: List[Dict],
    requirements: List[str]
) -> Dict:
    """Анализ покрытия требований"""
    coverage_details = {}
    gaps = []
    
    for idx, requirement in enumerate(requirements):
        covering_tests = []
        
        # Упрощенная проверка - ищем упоминание требования в коде
        for test in tests:
            if requirement.lower() in test["test_code"].lower():
                covering_tests.append(test["test_id"])
        
        is_covered = len(covering_tests) > 0
        coverage_details[f"requirement_{idx}"] = {
            "text": requirement,
            "covered": is_covered,
            "tests": covering_tests,
            "quality": "good" if len(covering_tests) >= 2 else "insufficient"
        }
        
        if not is_covered:
            gaps.append({
                "requirement": f"requirement_{idx}",
                "description": f"Отсутствуют тесты для: {requirement}"
            })
    
    # Расчет coverage_score
    covered_count = sum(1 for detail in coverage_details.values() if detail["covered"])
    coverage_score = covered_count / len(requirements) if requirements else 0.0
    
    return {
        "score": coverage_score,
        "details": coverage_details,
        "gaps": gaps
    }
```

**Что происходит:**
- Для каждого требования проверяется, есть ли тесты, которые его покрывают
- Вычисляется процент покрытия
- Находятся пробелы (непокрытые требования)

---

## SafetyGuard - Система безопасности

### Назначение

**SafetyGuard** - 4-уровневая система защиты от опасного кода:
1. **Static Analysis** - поиск опасных паттернов через regex
2. **AST Analysis** - проверка импортов и структуры через AST
3. **Behavioral Analysis** - проверка файловых и сетевых операций
4. **Sandbox** (опционально) - выполнение в изолированной среде

### Уровень 1: Static Analysis

```python
CRITICAL_BLACKLIST = [
    r'\beval\s\(',
    r'\bexec\s\(',
    r'\bcompile\s\(',
    r'\b__import__\s\(',
    r'\bos\.system\s\(',
    r'\bsubprocess\.',
    r'\bsocket\.',
    ...
]

def _static_analysis(self, test_code: str) -> Dict[str, List]:
    """Level 1: Static Analysis - regex поиск опасных паттернов"""
    blocked = []
    
    for pattern in self.CRITICAL_BLACKLIST:
        if re.search(pattern, test_code, re.IGNORECASE):
            blocked.append(pattern)
    
    return {"blocked": blocked}
```

**Что блокируется:**
- `eval()`, `exec()` - выполнение произвольного кода
- `os.system()` - выполнение системных команд
- `subprocess` - запуск процессов
- `socket` - сетевые операции

**Почему опасно?**
- Может выполнить вредоносный код
- Может получить доступ к файловой системе
- Может отправить данные на внешние серверы

### Уровень 2: AST Analysis

```python
ALLOWED_IMPORTS = {
    'pytest', 'allure', 'playwright', 'httpx', 'json', ...
}

def _ast_analysis(self, test_code: str) -> Dict[str, List]:
    """Level 2: AST Analysis - проверка импортов"""
    blocked = []
    
    tree = ast.parse(test_code)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split('.')[0]
                if module not in self.ALLOWED_IMPORTS:
                    blocked.append(f"Forbidden import: {module}")
        
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in ['eval', 'exec', 'compile']:
                    blocked.append(f"Forbidden function call: {node.func.id}")
    
    return {"blocked": blocked}
```

**Что проверяется:**
- Разрешенные импорты (whitelist)
- Запрещенные вызовы функций

**Почему AST, а не regex?**
- Точнее (понимает структуру кода)
- Не дает ложных срабатываний
- Может анализировать вложенные вызовы

### Уровень 3: Behavioral Analysis

```python
def _behavioral_analysis(self, test_code: str) -> Dict[str, List]:
    """Level 3: Behavioral Analysis - проверка файловых операций"""
    warnings = []
    
    # Проверка записи в файлы
    if re.search(r'open\s*\([^)]*["\']w["\']', test_code):
        warnings.append("File write operation detected")
    
    # Проверка удаления файлов
    if re.search(r'(os\.remove|os\.unlink|shutil\.rmtree)', test_code):
        warnings.append("File deletion operation detected")
    
    return {"warnings": warnings}
```

**Что проверяется:**
- Запись в файлы
- Удаление файлов

**Почему warning, а не блокировка?**
- Иногда нужно (например, создание временных файлов)
- Но нужно предупредить пользователя

### Результат валидации

```python
{
    "risk_level": "SAFE|LOW|MEDIUM|HIGH|CRITICAL",
    "issues": [...],
    "blocked_patterns": [...],
    "action_taken": "allowed|blocked|warning|regenerate"
}
```

**Уровни риска:**
- **SAFE** - код безопасен
- **LOW** - есть предупреждения
- **MEDIUM** - есть проблемы, но не критично
- **HIGH** - опасный код, блокируется
- **CRITICAL** - критически опасный код, блокируется

---

## TestPlanGeneratorAgent - Генерация тест-планов

### Назначение

**TestPlanGeneratorAgent** генерирует структурированные тест-планы на основе:
- Требований пользователя
- Анализа дефектов (из Jira/Allure TestOps)
- Компонентов системы

### Процесс генерации

```python
async def generate_test_plan(
    self,
    requirements: List[str],
    project_key: str = None,
    components: List[str] = None,
    defect_analysis: Dict[str, Any] = None,
    options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Генерация тест-плана"""
    
    # Анализ дефектов, если не передан
    if defect_analysis is None and project_key:
        defect_analysis = await self.defect_analyzer.analyze_defect_history(
            project_key=project_key,
            days_back=90,
            components=components
        )
    
    # Построение промпта
    user_prompt = self._build_test_plan_prompt(
        requirements=requirements,
        defect_analysis=defect_analysis,
        components=components,
        options=options
    )
    
    # Генерация через LLM
    response = await llm_client.generate(
        prompt=user_prompt,
        system_prompt=self.SYSTEM_PROMPT,
        temperature=0.3,
        max_tokens=4096
    )
    
    # Парсинг результата
    generated_content = response["choices"][0]["message"]["content"]
    test_plan = self._parse_test_plan(generated_content, requirements, defect_analysis)
    
    return test_plan
```

### Приоритизация тестов

```python
def prioritize_tests(
    self,
    tests: List[Dict[str, Any]],
    defect_analysis: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """Приоритизация тестов на основе анализа дефектов"""
    
    risk_areas = defect_analysis.get("risk_areas", [])
    
    prioritized_tests = []
    for test in tests:
        # Расчет приоритета на основе рискованных областей
        priority = self.defect_analyzer.calculate_priority(
            test_info=test,
            risk_areas=risk_areas,
            defect_history=defect_analysis.get("defects", [])
        )
        
        test_copy = test.copy()
        test_copy["priority"] = priority
        prioritized_tests.append(test_copy)
    
    # Сортировка по приоритету
    prioritized_tests.sort(key=lambda x: x.get("priority", 5), reverse=True)
    
    return prioritized_tests
```

**Как работает приоритизация:**
- Если тест покрывает компонент с большим количеством дефектов - приоритет выше
- Если тест покрывает критическую функциональность - приоритет выше

---

## Полезные ссылки

### AI/LLM

- [Prompt Engineering Guide](https://www.promptingguide.ai/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
- [LLM Best Practices](https://platform.openai.com/docs/guides/prompt-engineering)

### Playwright

- [Playwright Documentation](https://playwright.dev/python/)
- [Playwright Best Practices](https://playwright.dev/python/docs/best-practices)

### Python AST

- [Python AST Module](https://docs.python.org/3/library/ast.html)
- [AST Tutorial](https://greentreesnakes.com/)

### Machine Learning

- [Cosine Similarity Explained](https://www.machinelearningplus.com/nlp/cosine-similarity/)
- [Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)

---

## Часто задаваемые вопросы

### Q: Почему используется несколько уровней валидации?

**A:** Каждый уровень проверяет разные аспекты:
- Синтаксис - быстрая проверка
- Семантика - проверка структуры
- Логика - проверка корректности
- Безопасность - защита от опасного кода

### Q: Как работает генерация embeddings?

**A:** В текущей реализации используется hash-based подход (быстро, без зависимостей). В будущем можно использовать настоящие embeddings от LLM API.

### Q: Почему SafetyGuard блокирует некоторые операции?

**A:** Для безопасности - тесты не должны выполнять системные команды или отправлять данные на внешние серверы. Это защита от вредоносного кода.

---

## Заключение

Agents - это "мозг" системы, который:
- Анализирует веб-страницы
- Генерирует тесты через LLM
- Валидирует качество кода
- Оптимизирует наборы тестов
- Обеспечивает безопасность

Понимание работы агентов критично для понимания всей системы!

