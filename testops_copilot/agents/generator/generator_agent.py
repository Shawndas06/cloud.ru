"""
Generator Agent - генерация тест-кейсов через LLM
"""
from typing import Dict, Any, List
import re
import json
from shared.utils.llm_client import llm_client
import asyncio


class GeneratorAgent:
    """Агент генерации тест-кейсов"""
    
    # Системные промпты
    UI_SYSTEM_PROMPT = """Ты — senior QA automation engineer с 10+ годами опыта, специализирующийся на Playwright и Python.
Твоя задача — генерировать высококачественные, production-ready автотесты в формате Allure TestOps as Code.

ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ К КОДУ:

1. Allure декораторы (обязательно для каждого теста):
   - @allure.feature("Название фичи") - группировка по функциональности
   - @allure.story("Название user story") - группировка по user story
   - @allure.title("Понятное, описательное название теста")
   - @allure.tag("CRITICAL|NORMAL|LOW") - приоритет теста
   - @allure.severity(allure.severity_level.CRITICAL|NORMAL|MINOR|TRIVIAL) - серьезность

2. Структура теста (паттерн AAA):
   ```python
   @allure.feature("Feature Name")
   @allure.story("User Story")
   @allure.title("Test Title")
   def test_example(page: Page):
       # Arrange - подготовка данных и состояния
       with allure.step("Подготовка тестовых данных"):
           # код подготовки
       
       # Act - выполнение тестируемого действия
       with allure.step("Выполнение действия"):
           # код действия
       
       # Assert - проверка результата
       with allure.step("Проверка результата"):
           expect(...).to_be_visible()
   ```

3. Best Practices:
   - Используй page.wait_for_selector() или expect().to_be_visible() вместо time.sleep()
   - Используй data-testid селекторы (приоритет 1), затем id, затем CSS селекторы
   - Оборачивай каждое логическое действие в allure.step()
   - Используй понятные имена переменных и комментарии
   - Проверяй не только наличие элементов, но и их состояние (enabled, visible, etc.)

4. ЗАПРЕЩЕНО:
   - time.sleep() - используй page.wait_for_* методы
   - Хардкод абсолютных URL - используй относительные пути или переменные
   - Пустые assertions - всегда проверяй результат
   - Неиспользуемые импорты
   - Магические числа - используй константы

5. Примеры хороших тестов:
   ```python
   @allure.feature("User Authentication")
   @allure.story("Login Flow")
   @allure.title("Успешный вход в систему с валидными credentials")
   @allure.tag("CRITICAL")
   @allure.severity(allure.severity_level.CRITICAL)
   def test_successful_login(page: Page):
       with allure.step("Открытие страницы входа"):
           page.goto("/login")
           expect(page.locator('[data-testid="login-form"]')).to_be_visible()
       
       with allure.step("Ввод валидных credentials"):
           page.fill('[data-testid="username-input"]', "test_user")
           page.fill('[data-testid="password-input"]', "test_password")
       
       with allure.step("Нажатие кнопки входа"):
           page.click('[data-testid="login-button"]')
       
       with allure.step("Проверка успешного входа"):
           expect(page.locator('[data-testid="user-dashboard"]')).to_be_visible()
           expect(page).to_have_url("/dashboard")
   ```
"""
    
    API_SYSTEM_PROMPT = """Ты — senior QA automation engineer с 10+ годами опыта, специализирующийся на API тестировании с Python.
Твоя задача — генерировать высококачественные, production-ready API автотесты в формате Allure TestOps as Code.

ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:

1. Allure декораторы (обязательно для каждого теста):
   - @allure.feature("API: Resource Name") - например "API: VMs", "API: Disks"
   - @allure.story("Operation Type") - например "CRUD Operations", "List Resources"
   - @allure.title("Descriptive Test Title") - понятное название
   - @allure.tag("API", "CRITICAL|NORMAL|LOW")
   - @allure.severity(allure.severity_level.CRITICAL|NORMAL|MINOR)

2. Типы тестов для каждого endpoint (обязательно покрыть):
   - Positive: успешный запрос с валидными данными (200, 201, 204)
   - Negative: Validation - невалидные данные (400, 422)
   - Negative: Auth - без токена / невалидный токен (401)
   - Negative: Forbidden - нет прав доступа (403)
   - Negative: Not Found - несуществующий ресурс (404)

3. Структура теста:
   ```python
   @allure.feature("API: VMs")
   @allure.story("Create VM")
   @allure.title("Создание виртуальной машины с валидными параметрами")
   @allure.tag("API", "CRITICAL")
   @allure.severity(allure.severity_level.CRITICAL)
   async def test_create_vm_success():
       async with httpx.AsyncClient() as client:
           with allure.step("Подготовка тестовых данных"):
               payload = {"name": "test-vm", "flavor": "small"}
               headers = {"Authorization": f"Bearer {token}"}
           
           with allure.step("Отправка POST запроса"):
               response = await client.post(
                   "/api/v1/vms",
                   json=payload,
                   headers=headers
               )
           
           with allure.step("Проверка статус кода"):
               assert response.status_code == 201
           
           with allure.step("Проверка структуры ответа"):
               data = response.json()
               assert "id" in data
               assert data["name"] == "test-vm"
   ```

4. Best Practices:
   - Используй httpx.AsyncClient для асинхронных запросов
   - Всегда проверяй статус код через assert
   - Проверяй структуру JSON ответа
   - Используй валидные тестовые данные
   - Оборачивай каждое действие в allure.step()
   - Используй pytest.mark.parametrize для параметризации

5. Аутентификация:
   - Используй Bearer token в заголовке Authorization
   - Токен получается через IAM API: POST https://iam.api.cloud.ru/api/v1/auth/token
   - Формат: {"keyId": "...", "secret": "..."}
"""
    
    async def generate_ui_tests(
        self,
        url: str,
        page_structure: Dict[str, Any],
        requirements: List[str],
        test_type: str = "both",
        options: Dict[str, Any] = None
    ) -> List[str]:
        """
        Генерация UI тест-кейсов
        
        Args:
            url: URL для тестирования
            page_structure: Структура страницы от Reconnaissance Agent
            requirements: Список требований
            test_type: manual, automated, both
            options: Дополнительные параметры
        
        Returns:
            Список сгенерированных тестов (Python code strings)
        """
        options = options or {}
        manual_count = options.get("manual_count", 15)
        automated_count = options.get("automated_count", 10)
        
        # Построение промпта
        user_prompt = self._build_ui_prompt(url, page_structure, requirements, test_type, options)
        
        # Вызов LLM
        try:
            response = await llm_client.generate(
                prompt=user_prompt,
                system_prompt=self.UI_SYSTEM_PROMPT,
                model=None,  # Используется модель по умолчанию из settings
                temperature=0.3,
                max_tokens=4096
            )
            
            # Парсинг ответа - извлечение Python кода
            if not response or "choices" not in response or len(response["choices"]) == 0:
                print("LLM response is empty or invalid")
                return []
            
            generated_code = response["choices"][0]["message"]["content"]
            tests = self._extract_tests_from_code(generated_code)
            
            return tests
        except Exception as e:
            print(f"Error generating UI tests: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    async def generate_api_tests(
        self,
        openapi_spec: Dict[str, Any] = None,
        openapi_url: str = None,
        endpoints: List[str] = None,
        test_types: List[str] = None
    ) -> List[str]:
        """
        Генерация API тест-кейсов
        
        Args:
            openapi_spec: OpenAPI спецификация (parsed YAML/JSON)
            openapi_url: URL к OpenAPI спецификации
            endpoints: Список endpoints для покрытия
            test_types: Типы тестов (positive, negative, security)
        
        Returns:
            Список сгенерированных тестов
        """
        test_types = test_types or ["positive"]
        
        # Если передан URL, парсим спецификацию
        if openapi_url and not openapi_spec:
            from agents.generator.openapi_parser import OpenAPIParser
            parser = OpenAPIParser()
            openapi_spec = await parser.parse_from_url(openapi_url)
        
        # Если спецификация для Cloud.ru API, используем специальный генератор
        if openapi_spec and self._is_cloud_ru_api(openapi_spec):
            from agents.generator.cloud_ru_api_generator import CloudRuAPIGenerator
            generator = CloudRuAPIGenerator()
            return await generator.generate_tests_for_endpoints(
                openapi_spec=openapi_spec,
                endpoints=endpoints,
                test_types=test_types
            )
        
        # Стандартная генерация для других API
        if not openapi_spec:
            raise ValueError("openapi_spec or openapi_url is required")
        
        # Построение промпта
        user_prompt = self._build_api_prompt(openapi_spec, endpoints, test_types)
        
        # Вызов LLM
        try:
            response = await llm_client.generate(
                prompt=user_prompt,
                system_prompt=self.API_SYSTEM_PROMPT,
                model=None,  # Используется модель по умолчанию из settings
                temperature=0.3,
                max_tokens=4096
            )
            
            # Парсинг ответа
            if not response or "choices" not in response or len(response["choices"]) == 0:
                print("LLM response is empty or invalid")
                return []
            
            generated_code = response["choices"][0]["message"]["content"]
            tests = self._extract_tests_from_code(generated_code)
            
            return tests
        except Exception as e:
            print(f"Error generating API tests: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def _is_cloud_ru_api(self, spec: Dict[str, Any]) -> bool:
        """Проверка, является ли спецификация Cloud.ru API"""
        # Проверка по URL или заголовкам
        info = spec.get("info", {})
        title = info.get("title", "").lower()
        description = info.get("description", "").lower()
        
        return (
            "cloud.ru" in title or
            "cloud.ru" in description or
            "cloud.ru" in str(spec.get("servers", []))
        )
    
    def _build_ui_prompt(
        self,
        url: str,
        page_structure: Dict,
        requirements: List[str],
        test_type: str,
        options: Dict
    ) -> str:
        """Построение промпта для UI тестов"""
        
        # Извлечение ключевых элементов страницы
        buttons = page_structure.get("buttons", [])[:10]  # Топ-10 кнопок
        inputs = page_structure.get("inputs", [])[:10]  # Топ-10 полей ввода
        links = page_structure.get("links", [])[:10]  # Топ-10 ссылок
        
        prompt = f"""Сгенерируй полные, production-ready тест-кейсы для веб-страницы.

КОНТЕКСТ:
URL: {url}
Заголовок страницы: {page_structure.get('title', 'N/A')}

ДОСТУПНЫЕ ЭЛЕМЕНТЫ СТРАНИЦЫ:

Кнопки (доступные для взаимодействия):
{chr(10).join(f'- {btn.get("text", "")} (селектор: {btn.get("selector", "")})' for btn in buttons if btn.get("visible"))}

Поля ввода:
{chr(10).join(f'- {inp.get("name", "")} (тип: {inp.get("type", "")}, селектор: {inp.get("selector", "")})' for inp in inputs if inp.get("visible"))}

Ссылки:
{chr(10).join(f'- {link.get("text", "")} -> {link.get("href", "")}' for link in links if link.get("visible"))}

ТРЕБОВАНИЯ ПОЛЬЗОВАТЕЛЯ:
{chr(10).join(f'{i+1}. {req}' for i, req in enumerate(requirements))}

ПАРАМЕТРЫ:
Тип тестов: {test_type}
Фреймворк: {options.get('framework', 'playwright')}
Количество тестов: {options.get('automated_count', 10) if test_type in ['automated', 'both'] else 0} автоматизированных, {options.get('manual_count', 15) if test_type in ['manual', 'both'] else 0} ручных

ИНСТРУКЦИИ:
1. Сгенерируй тест-кейсы в формате Allure TestOps as Code (Python)
2. Каждый тест должен быть полным, независимым и следовать паттерну AAA
3. Используй data-testid селекторы (приоритет 1), затем id, затем CSS
4. Оборачивай каждое действие в allure.step()
5. Используй page.wait_for_selector() или expect().to_be_visible() вместо time.sleep()
6. Для каждого требования создай минимум 1 тест
7. Покрой основные пользовательские сценарии (happy path + edge cases)
8. Добавь проверки на видимость, доступность и корректность данных

ВАЖНО: Генерируй только валидный Python код, готовый к выполнению!
"""
        return prompt
    
    def _build_api_prompt(
        self,
        openapi_spec: Dict,
        endpoints: List[str],
        test_types: List[str]
    ) -> str:
        """Построение промпта для API тестов"""
        prompt = f"""Сгенерируй API тест-кейсы на основе OpenAPI спецификации.

Endpoints для покрытия:
{chr(10).join(f'- {ep}' for ep in (endpoints or []))}

Типы тестов: {', '.join(test_types)}

OpenAPI спецификация:
{json.dumps(openapi_spec, indent=2, ensure_ascii=False)[:2000]}...

Сгенерируй тесты в формате pytest + httpx с Allure декораторами.
"""
        return prompt
    
    def _extract_tests_from_code(self, code: str) -> List[str]:
        """Извлечение отдельных тестов из сгенерированного кода"""
        # Разделение по функциям test_*
        test_pattern = r'def\s+(test_\w+)\s*\([^)]*\):'
        matches = list(re.finditer(test_pattern, code))
        
        if not matches:
            # Если не найдено, возвращаем весь код как один тест
            return [code]
        
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

