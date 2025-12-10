
from typing import Dict, Any, List
import json
from shared.utils.llm_client import llm_client
from agents.generator.openapi_parser import OpenAPIParser
class CloudRuAPIGenerator:
    SYSTEM_PROMPT = """Ты — senior QA automation engineer, специализирующийся на API тестировании Cloud.ru API.
Генерируй высококачественные тесты в формате Allure TestOps as Code с использованием httpx и pytest.
Всегда используй правильную аутентификацию через IAM API и проверяй все статус коды и структуры ответов."""
    def __init__(self):
        self.parser = OpenAPIParser()
    async def generate_tests_for_endpoints(
        self,
        openapi_spec: Dict[str, Any],
        endpoints: List[str] = None,
        test_types: List[str] = None
    ) -> List[str]:
        test_types = test_types or ["positive", "negative_validation", "negative_auth"]
        all_endpoints = self.parser.extract_endpoints(openapi_spec)
        if endpoints:
            filtered_endpoints = [
                ep for ep in all_endpoints
                if any(ep["path"].startswith(e) or e in ep["path"] for e in endpoints)
            ]
        else:
            filtered_endpoints = all_endpoints[:10]
        all_tests = []
        for endpoint in filtered_endpoints:
            test_cases = self.parser.get_endpoint_test_cases(endpoint)
            filtered_test_cases = [
                tc for tc in test_cases
                if tc["type"] in test_types or tc["type"].startswith("positive")
            ]
            for test_case in filtered_test_cases:
                prompt = self._build_test_prompt(endpoint, test_case, openapi_spec)
                try:
                    response = await llm_client.generate(
                        prompt=prompt,
                        system_prompt=self.SYSTEM_PROMPT,
                        model=None,
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
        request_schema = {}
        if endpoint.get("request_body"):
            content = endpoint["request_body"].get("content", {})
            for content_type, schema in content.items():
                if "application/json" in content_type:
                    request_schema = schema.get("schema", {})
        response_schema = {}
        expected_status = test_case.get("expected_status", [200])[0]
        if str(expected_status) in endpoint.get("responses", {}):
            response = endpoint["responses"][str(expected_status)]
            content = response.get("content", {})
            for content_type, schema in content.items():
                if "application/json" in content_type:
                    response_schema = schema.get("schema", {})
        prompt = f
        return prompt
    def _extract_tests_from_code(self, code: str) -> List[str]:
        import re
        test_pattern = r'def\s+(test_\w+)\s*\([^)]*\):'
        matches = list(re.finditer(test_pattern, code))
        if not matches:
            return [code]
        tests = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(code)
            test_code = code[start:end].strip()
            if "import allure" not in test_code:
                test_code = "import allure\nimport httpx\nimport pytest\n\n" + test_code
            tests.append(test_code)
        return tests