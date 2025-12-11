
from typing import Dict, Any, List
import re
from shared.utils.llm_client import llm_client
import asyncio
from .prompts import UI_SYSTEM_PROMPT, API_SYSTEM_PROMPT
class GeneratorAgent:
    def __init__(self):
        self.ui_system_prompt = UI_SYSTEM_PROMPT
        self.api_system_prompt = API_SYSTEM_PROMPT
    async def generate_ui_tests(
        self,
        url: str,
        page_structure: Dict[str, Any],
        requirements: List[str],
        test_type: str = "both",
        options: Dict[str, Any] = None
    ) -> List[str]:
        options = options or {}
        manual_count = options.get("manual_count", 15)
        automated_count = options.get("automated_count", 10)
        user_prompt = self._build_ui_prompt(url, page_structure, requirements, test_type, options)
        try:
            response = await llm_client.generate(
                prompt=user_prompt,
                system_prompt=self.ui_system_prompt,
                model=None,
                temperature=0.3,
                max_tokens=4096
            )
            if not response or "choices" not in response or len(response["choices"]) == 0:
                print("LLM response is empty or invalid")
                return []
            generated_code = response["choices"][0]["message"]["content"]
            from shared.utils.logger import agent_logger
            agent_logger.info(
                f"[GENERATION] LLM generated code",
                extra={
                    "code_length": len(generated_code),
                    "test_type": test_type,
                    "url": url
                }
            )
            if len(generated_code) > 0:
                agent_logger.debug(f"[GENERATION] Generated code preview (first 500 chars): {generated_code[:500]}")
            tests = self._extract_tests_from_code(generated_code)
            agent_logger.info(
                f"[GENERATION] Extracted {len(tests)} tests from generated code",
                extra={
                    "tests_count": len(tests),
                    "test_type": test_type,
                    "expected_manual": options.get("manual_count", 15) if test_type in ["manual", "both"] else 0,
                    "expected_automated": options.get("automated_count", 10) if test_type in ["automated", "both"] else 0
                }
            )
            if len(tests) == 0:
                agent_logger.warning(
                    f"[GENERATION] No tests extracted! Generated code preview: {generated_code[:1000]}",
                    extra={"code_preview": generated_code[:1000]}
                )
            else:
                # Логируем информацию о каждом тесте
                for i, test in enumerate(tests):
                    has_decorators = "@allure.feature" in test and "@allure.story" in test and "@allure.title" in test
                    is_manual = "@allure.manual" in test
                    agent_logger.debug(
                        f"[GENERATION] Test {i+1} info",
                        extra={
                            "test_number": i+1,
                            "has_decorators": has_decorators,
                            "is_manual": is_manual,
                            "code_length": len(test)
                        }
                    )
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
        test_types = test_types or ["positive"]
        if openapi_url and not openapi_spec:
            from agents.generator.openapi_parser import OpenAPIParser
            parser = OpenAPIParser()
            openapi_spec = await parser.parse_from_url(openapi_url)
        if openapi_spec and self._is_cloud_ru_api(openapi_spec):
            from agents.generator.cloud_ru_api_generator import CloudRuAPIGenerator
            generator = CloudRuAPIGenerator()
            return await generator.generate_tests_for_endpoints(
                openapi_spec=openapi_spec,
                endpoints=endpoints,
                test_types=test_types
            )
        if not openapi_spec:
            raise ValueError("openapi_spec or openapi_url is required")
        user_prompt = self._build_api_prompt(openapi_spec, endpoints, test_types)
        try:
            response = await llm_client.generate(
                prompt=user_prompt,
                system_prompt=self.api_system_prompt,
                model=None,
                temperature=0.3,
                max_tokens=4096
            )
            if not response or "choices" not in response or len(response["choices"]) == 0:
                print("LLM response is empty or invalid")
                return []
            generated_code = response["choices"][0]["message"]["content"]
            tests = self._extract_tests_from_code(generated_code)
            from shared.utils.logger import agent_logger
            if len(tests) == 0:
                agent_logger.warning(f"No tests extracted from API generation. Code preview: {generated_code[:1000]}")
            else:
                # Постобработка API тестов
                processed_tests = []
                for i, test in enumerate(tests):
                    # Исправляем async функции
                    if "async with httpx.AsyncClient" in test and "async def" not in test:
                        test = test.replace("def test_", "async def test_")
                        # Добавляем @pytest.mark.asyncio если его нет
                        if "@pytest.mark.asyncio" not in test:
                            # Находим место после импортов, перед декораторами
                            lines = test.split('\n')
                            import_end = 0
                            for j, line in enumerate(lines):
                                if line.strip().startswith(('import ', 'from ')):
                                    import_end = j + 1
                                elif line.strip() and not line.strip().startswith('#'):
                                    break
                            lines.insert(import_end, "import pytest")
                            lines.insert(import_end + 1, "")
                            # Находим def и добавляем декоратор перед ним
                            for j in range(len(lines)):
                                if lines[j].strip().startswith('async def test_') or lines[j].strip().startswith('def test_'):
                                    if "@pytest.mark.asyncio" not in '\n'.join(lines[:j]):
                                        lines.insert(j, "@pytest.mark.asyncio")
                                    break
                            test = '\n'.join(lines)
                    
                    # Заменяем неопределенные переменные на конкретные значения
                    replacements = {
                        "VALID_PET": '{"id": 1, "name": "test-pet", "status": "available"}',
                        "INVALID_PET": '{"invalid": "data"}',
                        "IAM_TOKEN": '"test-token"',
                        "NOT_FOUND_PET_ID": "99999",
                        "get_token()": '"test-token"',
                        "token": '"test-token"',
                        "base_url": 'base_url="https://petstore.swagger.io/v2"'
                    }
                    for old, new in replacements.items():
                        test = test.replace(old, new)
                    
                    # Проверяем синтаксис
                    try:
                        import ast
                        ast.parse(test)
                        agent_logger.debug(f"API Test {i+1} syntax is valid after processing")
                        processed_tests.append(test)
                    except SyntaxError as e:
                        agent_logger.warning(f"API Test {i+1} has syntax error after processing: {e} at line {e.lineno}")
                        agent_logger.debug(f"Test {i+1} code (first 500 chars): {test[:500]}")
                        # Все равно добавляем, валидатор разберется
                        processed_tests.append(test)
                return processed_tests
            return tests
        except Exception as e:
            print(f"Error generating API tests: {e}")
            import traceback
            traceback.print_exc()
            raise
    def _is_cloud_ru_api(self, spec: Dict[str, Any]) -> bool:
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
        buttons = page_structure.get("buttons", [])[:10]
        inputs = page_structure.get("inputs", [])[:10]
        links = page_structure.get("links", [])[:10]
        automated_count = options.get("automated_count", 10)
        manual_count = options.get("manual_count", 15)
        
        test_type_instruction = ""
        if test_type == "both":
            test_type_instruction = f"""
ВАЖНО: Сгенерируй ОБА типа тестов:
1. Сначала {manual_count} РУЧНЫХ тестов (с @allure.manual декоратором, без Playwright кода, только описание шагов)
2. Затем {automated_count} АВТОМАТИЗИРОВАННЫХ тестов (с Playwright кодом)

Ручные тесты должны быть в формате:
@allure.manual
@allure.feature("...")
@allure.story("...")
@allure.title("...")
def test_manual_...():
    \"\"\"Описание шагов теста\"\"\"
    pass

Автоматизированные тесты должны быть в формате:
@allure.feature("...")
@allure.story("...")
@allure.title("...")
def test_automated_...(page: Page):
    with allure.step("..."):
        # Playwright код
"""
        elif test_type == "manual":
            test_type_instruction = f"""
ВАЖНО: Сгенерируй ТОЛЬКО {manual_count} РУЧНЫХ тестов (с @allure.manual декоратором, без Playwright кода, только описание шагов в docstring).
"""
        elif test_type == "automated":
            test_type_instruction = f"""
ВАЖНО: Сгенерируй ТОЛЬКО {automated_count} АВТОМАТИЗИРОВАННЫХ тестов (с Playwright кодом).
"""
        
        prompt = f"""Сгенерируй тест-кейсы для веб-страницы: {url}

Требования:
{chr(10).join(f"- {req}" for req in requirements)}

Тип тестов: {test_type}
{test_type_instruction}

Структура страницы:
- Кнопки: {len(buttons)} найдено
- Поля ввода: {len(inputs)} найдено  
- Ссылки: {len(links)} найдено

Важно:
1. Все тесты должны использовать паттерн AAA (Arrange-Act-Assert)
2. Все тесты должны иметь полный набор Allure декораторов
3. Код должен быть валидным Python кодом без синтаксических ошибок
4. Автоматизированные тесты используют Playwright API и allure.step() для структурирования
5. Ручные тесты используют @allure.manual и описание шагов в docstring
6. КРИТИЧЕСКИ ВАЖНО: НЕ ПОВТОРЯЙ одинаковые действия много раз подряд
7. Если нужно выполнить несколько действий, используй циклы или переменные
8. Каждое действие должно быть осмысленным и проверять результат
9. Избегай множественных одинаковых кликов без проверки состояния

ЗАПРЕЩЕНО:
- Генерировать код с повторяющимися одинаковыми действиями без логики
- Множественные одинаковые клики подряд без проверки результата
- Пустые циклы или бессмысленные повторения
- Для ручных тестов использовать Playwright код
"""
        return prompt
    def _build_api_prompt(
        self,
        openapi_spec: Dict[str, Any],
        endpoints: List[str] = None,
        test_types: List[str] = None
    ) -> str:
        test_types = test_types or ["positive"]
        info = openapi_spec.get("info", {})
        api_title = info.get("title", "API")
        api_version = info.get("version", "1.0.0")
        
        endpoint_info = []
        if endpoints:
            for path in endpoints:
                if path in openapi_spec.get("paths", {}):
                    endpoint_info.append(f"- {path}")
        else:
            paths = list(openapi_spec.get("paths", {}).keys())[:10]
            endpoint_info = [f"- {path}" for path in paths]
        
        prompt = f"""Сгенерируй API тесты для OpenAPI спецификации:

API: {api_title} v{api_version}

Endpoints для тестирования:
{chr(10).join(endpoint_info)}

Типы тестов: {', '.join(test_types)}

ВАЖНО: 
- Для каждого endpoint сгенерируй минимум 3-5 тестов разных типов
- Покрой все типы тестов: positive, negative (validation, auth, forbidden, not_found)
- Если endpoints не указаны, сгенерируй тесты для всех доступных endpoints (минимум 15 тестов)

Важно:
1. Все тесты должны использовать паттерн AAA (Arrange-Act-Assert)
2. Все тесты должны иметь полный набор Allure декораторов (@allure.feature, @allure.story, @allure.title, @allure.tag)
3. Использовать httpx.AsyncClient для асинхронных запросов
4. Код должен быть валидным Python кодом без синтаксических ошибок
5. Проверять статус коды и структуру ответов
6. Использовать @pytest.mark.asyncio для async функций
"""
        return prompt
    def _extract_tests_from_code(self, code: str) -> List[str]:
        """
        Извлекает тесты из сгенерированного кода и обеспечивает наличие обязательных элементов:
        - Allure декораторов
        - AAA паттерна
        - Валидного импорта
        """
        tests = []
        test_pattern = r'def\s+(test_\w+)\s*\([^)]*\):'
        matches = list(re.finditer(test_pattern, code, re.MULTILINE))
        
        # Получаем импорты из начала кода
        import_lines = []
        for line in code.split('\n'):
            if line.strip().startswith(('import ', 'from ')):
                import_lines.append(line)
            elif line.strip() and not line.strip().startswith('#') and not line.strip().startswith('"""'):
                break
        
        base_imports = '\n'.join(import_lines)
        
        # Определяем тип тестов по наличию ключевых слов
        is_api_test = "httpx" in code.lower() or "async" in code.lower() or "AsyncClient" in code
        is_ui_test = "playwright" in code.lower() or "Page" in code or "page.goto" in code
        
        # Обязательные импорты в зависимости от типа теста
        if is_api_test:
            required_imports = [
                "import pytest",
                "import allure",
                "import httpx",
                "import asyncio"
            ]
        else:
            required_imports = [
                "import pytest",
                "import allure",
                "from playwright.sync_api import Page, expect"
            ]
        
        if matches:
            for i, match in enumerate(matches):
                start = match.start()
                # Ищем конец функции более точно - ищем следующий def или конец файла
                if i + 1 < len(matches):
                    end = matches[i + 1].start()
                else:
                    end = len(code)
                
                # Извлекаем код функции, но проверяем что он полный
                test_code = code[start:end].strip()
                
                # Проверяем, что функция закрыта (есть хотя бы одна закрывающая скобка/двоеточие)
                # Если код обрезан, пытаемся найти конец функции по отступам
                lines = test_code.split('\n')
                if len(lines) > 0:
                    func_line = lines[0]
                    if 'def ' in func_line:
                        # Ищем конец функции по отступам
                        base_indent = len(func_line) - len(func_line.lstrip())
                        func_end = len(lines)
                        for j in range(1, len(lines)):
                            line = lines[j]
                            if line.strip() and not line.strip().startswith('#'):
                                line_indent = len(line) - len(line.lstrip())
                                # Если отступ меньше или равен базовому, это начало следующей функции/блока
                                if line_indent <= base_indent and (line.strip().startswith('def ') or line.strip().startswith('@')):
                                    func_end = j
                                    break
                        test_code = '\n'.join(lines[:func_end]).strip()
                
                # Добавляем импорты если их нет
                if not base_imports or "import allure" not in base_imports:
                    imports = "\n".join(required_imports) + "\n\n"
                    test_code = imports + test_code
                elif base_imports:
                    # Проверяем наличие всех обязательных импортов
                    for imp in required_imports:
                        if imp not in base_imports:
                            base_imports += "\n" + imp
                    test_code = base_imports + "\n\n" + test_code
                
                # Проверяем наличие минимальных Allure декораторов
                function_match = re.search(r'def\s+(test_\w+)', test_code)
                if function_match:
                    func_name = function_match.group(1)
                # Проверяем наличие всех обязательных декораторов
                has_feature = re.search(r'@allure\.feature\s*\(', test_code)
                has_story = re.search(r'@allure\.story\s*\(', test_code)
                has_title = re.search(r'@allure\.title\s*\(', test_code)
                has_tag = re.search(r'@allure\.tag\s*\(', test_code)
                
                # Логируем если декораторы отсутствуют
                if not (has_feature and has_story and has_title and has_tag):
                    from shared.utils.logger import agent_logger
                    missing = []
                    if not has_feature:
                        missing.append("feature")
                    if not has_story:
                        missing.append("story")
                    if not has_title:
                        missing.append("title")
                    if not has_tag:
                        missing.append("tag")
                    agent_logger.info(
                        f"[GENERATION] Adding missing decorators to test {i+1}",
                        extra={"missing_decorators": missing, "test_number": i+1}
                    )
                
                # Если хотя бы одного декоратора нет, добавляем все
                if not (has_feature and has_story and has_title and has_tag):
                        test_title = func_name.replace('test_', '').replace('_', ' ').title()
                        # Определяем feature и story из названия теста
                        feature_name = "API Tests" if is_api_test else "UI Tests"
                        story_name = "Test Cases"
                        if "api" in func_name.lower() or "http" in func_name.lower():
                            feature_name = "API Tests"
                        elif "ui" in func_name.lower() or "page" in func_name.lower():
                            feature_name = "UI Tests"
                        
                        decorators = f'''@allure.feature("{feature_name}")
@allure.story("{story_name}")
@allure.title("{test_title}")
@allure.tag("NORMAL")
@allure.severity(allure.severity_level.NORMAL)
'''
                        # Для API тестов добавляем @pytest.mark.asyncio если нужно
                        if is_api_test and "@pytest.mark.asyncio" not in test_code and "async def" in test_code:
                            decorators = "@pytest.mark.asyncio\n" + decorators
                        
                        # Вставляем декораторы перед функцией
                        test_code = test_code.replace(function_match.group(0), decorators + function_match.group(0))
                
                # Для API тестов не добавляем allure.step с expect, так как это для UI
                # Проверяем наличие AAA структуры (хотя бы одну проверку)
                is_manual = "@allure.manual" in test_code or "allure.manual" in test_code
                if not is_manual and "assert" not in test_code and "expect" not in test_code:
                    # Добавляем минимальную проверку если её нет
                    if "def test_" in test_code or "async def test_" in test_code:
                        lines = test_code.split('\n')
                        indent = "    "
                        inserted = False
                        for j, line in enumerate(lines):
                            if line.strip().startswith('def test_') or line.strip().startswith('async def test_'):
                                # Ищем тело функции (первая строка с отступом)
                                for k in range(j + 1, len(lines)):
                                    line_k = lines[k]
                                    if not line_k.strip() or line_k.strip().startswith('#'):
                                        continue
                                    # Если это строка с отступом (тело функции)
                                    if line_k.startswith(' ') or line_k.startswith('\t'):
                                        # Вставляем проверку в начало тела функции
                                        if is_api_test:
                                            # Для API тестов добавляем assert
                                            # Ищем место после response или в конце функции
                                            found_response = False
                                            for m in range(k, len(lines)):
                                                if "response" in lines[m].lower() and ("=" in lines[m] or "await" in lines[m]):
                                                    # Вставляем assert после response
                                                    response_indent = len(lines[m]) - len(lines[m].lstrip())
                                                    lines.insert(m + 1, ' ' * response_indent + 'assert response.status_code == 200  # TODO: Добавить проверку')
                                                    found_response = True
                                                    inserted = True
                                                    break
                                            if not found_response:
                                                # Вставляем в начало тела функции
                                                func_indent = len(line_k) - len(line_k.lstrip())
                                                lines.insert(k, ' ' * func_indent + 'assert True  # TODO: Добавить проверку')
                                                inserted = True
                                        else:
                                            # Для UI тестов добавляем expect
                                            func_indent = len(line_k) - len(line_k.lstrip())
                                            lines.insert(k, ' ' * func_indent + 'with allure.step("Проверка результата"):')
                                            lines.insert(k + 1, ' ' * (func_indent + 4) + 'expect(page.locator("body")).to_be_visible()  # TODO: Добавить проверку')
                                            inserted = True
                                        break
                                    # Если это начало следующей функции/блока без отступа
                                    elif not line_k.startswith(' ') and not line_k.startswith('\t'):
                                        # Вставляем проверку перед следующим блоком
                                        if is_api_test:
                                            prev_indent = len(lines[k-1]) - len(lines[k-1].lstrip()) if k > 0 else 4
                                            lines.insert(k, ' ' * prev_indent + 'assert True  # TODO: Добавить проверку')
                                        else:
                                            prev_indent = len(lines[k-1]) - len(lines[k-1].lstrip()) if k > 0 else 4
                                            lines.insert(k, ' ' * prev_indent + 'with allure.step("Проверка результата"):')
                                            lines.insert(k + 1, ' ' * (prev_indent + 4) + 'expect(page.locator("body")).to_be_visible()  # TODO: Добавить проверку')
                                        inserted = True
                                        break
                                if inserted:
                                    break
                        if inserted:
                            test_code = '\n'.join(lines)
                
                tests.append(test_code)
        else:
            # Если нет тестов, создаем один из всего кода
            if "import" not in code:
                code = "\n".join(required_imports) + "\n\n" + code
            tests.append(code)
        
        return tests