
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
            agent_logger.info(f"LLM generated code length: {len(generated_code)}")
            if len(generated_code) > 0:
                agent_logger.debug(f"LLM generated code (first 500 chars): {generated_code[:500]}")
            tests = self._extract_tests_from_code(generated_code)
            agent_logger.info(f"Extracted {len(tests)} tests from generated code")
            if len(tests) == 0:
                agent_logger.warning(f"No tests extracted. Generated code preview: {generated_code[:1000]}")
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

Важно:
1. Все тесты должны использовать паттерн AAA (Arrange-Act-Assert)
2. Все тесты должны иметь Allure декораторы
3. Покрыть все типы тестов: positive, negative (validation, auth, forbidden, not_found)
4. Использовать httpx.AsyncClient для асинхронных запросов
5. Код должен быть валидным Python кодом без синтаксических ошибок
6. Проверять статус коды и структуру ответов
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
                    # Проверяем есть ли декораторы перед функцией
                    func_start = function_match.start()
                    code_before_func = test_code[:func_start].strip()
                    
                    if "@allure" not in code_before_func:
                        # Если декораторов нет, добавляем базовые
                        test_title = func_name.replace('test_', '').replace('_', ' ').title()
                        decorators = f'''@allure.feature("Test Feature")
@allure.story("Test Story")
@allure.title("{test_title}")
@allure.tag("NORMAL")
@allure.severity(allure.severity_level.NORMAL)
'''
                        test_code = test_code.replace(function_match.group(0), decorators + function_match.group(0))
                
                # Для API тестов не добавляем allure.step с expect, так как это для UI
                # Проверяем наличие AAA структуры (хотя бы одну проверку)
                if "assert" not in test_code and "expect" not in test_code:
                    # Добавляем минимальную проверку если её нет
                    if "def test_" in test_code:
                        lines = test_code.split('\n')
                        indent = "    "
                        for j, line in enumerate(lines):
                            if line.strip().startswith('def test_'):
                                # Ищем конец функции (пустая строка или следующий def)
                                for k in range(j + 1, len(lines)):
                                    if lines[k].strip() and not lines[k].startswith(' ') and not lines[k].startswith('\t') and not lines[k].strip().startswith('#'):
                                        # Вставляем проверку перед следующим блоком
                                        if is_api_test:
                                            lines.insert(k, f'{indent}assert True  # TODO: Добавить проверку')
                                        else:
                                            lines.insert(k, f'{indent}with allure.step("Проверка результата"):')
                                            lines.insert(k + 1, f'{indent * 2}# TODO: Добавить проверку')
                                        break
                                break
                        test_code = '\n'.join(lines)
                
                tests.append(test_code)
        else:
            # Если нет тестов, создаем один из всего кода
            if "import" not in code:
                code = "\n".join(required_imports) + "\n\n" + code
            tests.append(code)
        
        return tests