"""
Генератор тестов для Cloud.ru VMs API
"""
from typing import Dict, Any, List
import json
from shared.utils.llm_client import llm_client
from agents.generator.openapi_parser import OpenAPIParser


class CloudRuAPIGenerator:
    """Генератор тестов для Cloud.ru API"""
    
    SYSTEM_PROMPT = """Ты — senior QA automation engineer с 10+ годами опыта, специализирующийся на API тестировании с Python.
Твоя задача — генерировать высококачественные, production-ready API автотесты для Cloud.ru VMs API в формате Allure TestOps as Code.

ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:

1. Allure декораторы (обязательно для каждого теста):
   - @allure.feature("API: Cloud.ru VMs") - или "API: Disks", "API: Networks" в зависимости от ресурса
   - @allure.story("Resource Name") - например "VMs", "Disks", "Networks", "Security Groups"
   - @allure.title("Descriptive Test Title") - понятное, описательное название
   - @allure.tag("API", "CRITICAL|NORMAL|LOW")
   - @allure.severity(allure.severity_level.CRITICAL|NORMAL|MINOR|TRIVIAL)

2. Типы тестов для каждого endpoint (обязательно покрыть все):
   - Positive: успешный запрос с валидными данными (200, 201, 204)
   - Negative: Validation - невалидные данные (400, 422)
   - Negative: Auth - без токена / невалидный токен (401)
   - Negative: Forbidden - нет прав доступа (403)
   - Negative: Not Found - несуществующий ресурс (404)

3. Структура теста (паттерн AAA):
   ```python
   @allure.feature("API: Cloud.ru VMs")
   @allure.story("Create VM")
   @allure.title("Создание виртуальной машины с валидными параметрами")
   @allure.tag("API", "CRITICAL")
   @allure.severity(allure.severity_level.CRITICAL)
   async def test_create_vm_success():
       async with httpx.AsyncClient(base_url="https://compute.api.cloud.ru") as client:
           with allure.step("Получение IAM токена"):
               token_response = await client.post(
                   "https://iam.api.cloud.ru/api/v1/auth/token",
                   json={"keyId": "...", "secret": "..."}
               )
               token = token_response.json()["access_token"]
           
           with allure.step("Подготовка тестовых данных"):
               payload = {
                   "name": "test-vm",
                   "flavor": "small",
                   "image": "ubuntu-20.04"
               }
               headers = {"Authorization": f"Bearer {token}"}
           
           with allure.step("Отправка POST запроса на создание VM"):
               response = await client.post(
                   "/api/v1/vms",
                   json=payload,
                   headers=headers
               )
           
           with allure.step("Проверка статус кода"):
               assert response.status_code == 201, f"Expected 201, got {response.status_code}"
           
           with allure.step("Проверка структуры ответа"):
               data = response.json()
               assert "id" in data, "Response should contain 'id' field"
               assert data["name"] == "test-vm"
               assert data["status"] in ["creating", "active"]
   ```

4. Best Practices:
   - Используй httpx.AsyncClient для асинхронных запросов
   - Всегда проверяй статус код через assert с понятным сообщением
   - Проверяй структуру JSON ответа (наличие обязательных полей)
   - Используй валидные тестовые данные согласно OpenAPI схеме
   - Оборачивай каждое действие в allure.step()
   - Используй pytest.mark.parametrize для параметризации похожих тестов
   - Обрабатывай ошибки и проверяй error messages в negative тестах

5. Аутентификация Cloud.ru:
   - Используй Bearer token в заголовке Authorization
   - Токен получается через IAM API: POST https://iam.api.cloud.ru/api/v1/auth/token
   - Формат запроса: {"keyId": "...", "secret": "..."}
   - Формат ответа: {"access_token": "...", "expires_in": 3600}
   - Токен действителен 1 час, обновляй при необходимости

6. Примеры для разных типов тестов:
   - Positive: валидные данные, ожидаем 200/201/204
   - Negative Validation: невалидные данные (пустые поля, неверный формат), ожидаем 400/422
   - Negative Auth: без токена или с невалидным токеном, ожидаем 401
   - Negative Forbidden: валидный токен, но нет прав, ожидаем 403
   - Negative Not Found: валидный запрос к несуществующему ресурсу, ожидаем 404

ВАЖНО: Генерируй только валидный Python код, готовый к выполнению!
"""

    def __init__(self):
        self.parser = OpenAPIParser()
    
    async def generate_tests_for_endpoints(
        self,
        openapi_spec: Dict[str, Any],
        endpoints: List[str] = None,
        test_types: List[str] = None
    ) -> List[str]:
        """
        Генерация тестов для указанных endpoints
        
        Args:
            openapi_spec: OpenAPI спецификация
            endpoints: Список endpoints для покрытия (например, ["/api/v1/vms", "/api/v1/disks"])
            test_types: Типы тестов (positive, negative_validation, negative_auth, etc.)
        
        Returns:
            Список сгенерированных тестов (Python code strings)
        """
        test_types = test_types or ["positive", "negative_validation", "negative_auth"]
        
        # Извлечение endpoints из спецификации
        all_endpoints = self.parser.extract_endpoints(openapi_spec)
        
        # Фильтрация по указанным endpoints
        if endpoints:
            filtered_endpoints = [
                ep for ep in all_endpoints
                if any(ep["path"].startswith(e) or e in ep["path"] for e in endpoints)
            ]
        else:
            filtered_endpoints = all_endpoints[:10]  # Ограничение для MVP
        
        # Генерация тестов для каждого endpoint
        all_tests = []
        
        for endpoint in filtered_endpoints:
            # Получение тест-кейсов для endpoint
            test_cases = self.parser.get_endpoint_test_cases(endpoint)
            
            # Фильтрация по типам тестов
            filtered_test_cases = [
                tc for tc in test_cases
                if tc["type"] in test_types or tc["type"].startswith("positive")
            ]
            
            # Генерация тестов через LLM
            for test_case in filtered_test_cases:
                prompt = self._build_test_prompt(endpoint, test_case, openapi_spec)
                
                try:
                    response = await llm_client.generate(
                        prompt=prompt,
                        system_prompt=self.SYSTEM_PROMPT,
                        model=None,  # Используется модель по умолчанию из settings
                        temperature=0.3,
                        max_tokens=2048
                    )
                    
                    if not response or "choices" not in response or len(response["choices"]) == 0:
                        print(f"Empty LLM response for {endpoint['path']}")
                        continue
                    
                    generated_code = response["choices"][0]["message"]["content"]
                    tests = self._extract_tests_from_code(generated_code)
                    all_tests.extend(tests)
                
                except Exception as e:
                    print(f"Error generating test for {endpoint['path']}: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
        
        return all_tests
    
    def _build_test_prompt(
        self,
        endpoint: Dict[str, Any],
        test_case: Dict[str, Any],
        openapi_spec: Dict[str, Any]
    ) -> str:
        """Построение промпта для генерации теста"""
        
        # Извлечение схемы запроса
        request_schema = {}
        if endpoint.get("request_body"):
            content = endpoint["request_body"].get("content", {})
            for content_type, schema in content.items():
                if "application/json" in content_type:
                    request_schema = schema.get("schema", {})
        
        # Извлечение схемы ответа
        response_schema = {}
        expected_status = test_case.get("expected_status", [200])[0]
        if str(expected_status) in endpoint.get("responses", {}):
            response = endpoint["responses"][str(expected_status)]
            content = response.get("content", {})
            for content_type, schema in content.items():
                if "application/json" in content_type:
                    response_schema = schema.get("schema", {})
        
        prompt = f"""Сгенерируй API тест для Cloud.ru VMs API.

Endpoint: {endpoint['method']} {endpoint['path']}
Operation ID: {endpoint.get('operation_id', '')}
Summary: {endpoint.get('summary', '')}
Description: {endpoint.get('description', '')}

Тип теста: {test_case['type']}
Ожидаемый статус: {test_case.get('expected_status', [200])}

Параметры запроса:
{json.dumps(endpoint.get('parameters', []), indent=2, ensure_ascii=False)}

Схема запроса:
{json.dumps(request_schema, indent=2, ensure_ascii=False)[:1000]}

Схема ответа:
{json.dumps(response_schema, indent=2, ensure_ascii=False)[:1000]}

Сгенерируй полный тест в формате pytest + httpx + Allure TestOps as Code.
Тест должен быть независимым и следовать паттерну AAA (Arrange-Act-Assert).
"""
        return prompt
    
    def _extract_tests_from_code(self, code: str) -> List[str]:
        """Извлечение отдельных тестов из сгенерированного кода"""
        import re
        
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
                test_code = "import allure\nimport httpx\nimport pytest\n\n" + test_code
            
            tests.append(test_code)
        
        return tests

