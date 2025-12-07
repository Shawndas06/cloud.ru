"""
Парсер OpenAPI спецификации для Cloud.ru API
"""
import yaml
import json
from typing import Dict, Any, List, Optional
import httpx


class OpenAPIParser:
    """Парсер OpenAPI спецификации"""
    
    def __init__(self):
        pass
    
    async def parse_from_url(self, url: str) -> Dict[str, Any]:
        """
        Парсинг OpenAPI спецификации из URL
        
        Args:
            url: URL к OpenAPI спецификации (YAML или JSON)
        
        Returns:
            Распарсенная OpenAPI спецификация
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                content = response.text
                
                # Определение формата
                if url.endswith('.yaml') or url.endswith('.yml') or content.strip().startswith('---'):
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError as e:
                        raise ValueError(f"Failed to parse YAML from {url}: {e}")
                else:
                    try:
                        return json.loads(content)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Failed to parse JSON from {url}: {e}")
        except httpx.HTTPStatusError as e:
            raise ValueError(f"HTTP error fetching OpenAPI spec from {url}: {e.response.status_code}")
        except Exception as e:
            raise ValueError(f"Error fetching OpenAPI spec from {url}: {e}")
    
    def parse_from_content(self, content: str, format: str = "yaml") -> Dict[str, Any]:
        """
        Парсинг OpenAPI спецификации из строки
        
        Args:
            content: Содержимое OpenAPI спецификации
            format: Формат (yaml или json)
        
        Returns:
            Распарсенная OpenAPI спецификация
        """
        if format.lower() == "yaml" or format.lower() == "yml":
            return yaml.safe_load(content)
        else:
            return json.loads(content)
    
    def extract_endpoints(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Извлечение endpoints из OpenAPI спецификации
        
        Args:
            spec: OpenAPI спецификация
        
        Returns:
            Список endpoints с методами и параметрами
        """
        endpoints = []
        paths = spec.get("paths", {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    endpoint_info = {
                        "path": path,
                        "method": method.upper(),
                        "operation_id": operation.get("operationId", f"{method}_{path.replace('/', '_')}"),
                        "summary": operation.get("summary", ""),
                        "description": operation.get("description", ""),
                        "parameters": operation.get("parameters", []),
                        "request_body": operation.get("requestBody", {}),
                        "responses": operation.get("responses", {}),
                        "tags": operation.get("tags", []),
                        "security": operation.get("security", [])
                    }
                    endpoints.append(endpoint_info)
        
        return endpoints
    
    def extract_schemas(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлечение схем из OpenAPI спецификации
        
        Args:
            spec: OpenAPI спецификация
        
        Returns:
            Словарь схем
        """
        components = spec.get("components", {})
        schemas = components.get("schemas", {})
        return schemas
    
    def extract_examples(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Извлечение примеров из OpenAPI спецификации
        
        Args:
            spec: OpenAPI спецификация
        
        Returns:
            Словарь примеров
        """
        examples = {}
        paths = spec.get("paths", {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    operation_id = operation.get("operationId", f"{method}_{path.replace('/', '_')}")
                    
                    # Примеры из requestBody
                    request_body = operation.get("requestBody", {})
                    if request_body:
                        content = request_body.get("content", {})
                        for content_type, content_schema in content.items():
                            if "example" in content_schema:
                                examples[f"{operation_id}_request"] = content_schema["example"]
                    
                    # Примеры из responses
                    responses = operation.get("responses", {})
                    for status_code, response_schema in responses.items():
                        content = response_schema.get("content", {})
                        for content_type, content_schema in content.items():
                            if "example" in content_schema:
                                examples[f"{operation_id}_response_{status_code}"] = content_schema["example"]
        
        return examples
    
    def get_endpoint_test_cases(self, endpoint: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Генерация списка тест-кейсов для endpoint
        
        Args:
            endpoint: Информация об endpoint
        
        Returns:
            Список тест-кейсов
        """
        test_cases = []
        
        # Positive test case
        test_cases.append({
            "type": "positive",
            "name": f"Test {endpoint['method']} {endpoint['path']} - Success",
            "description": f"Проверка успешного запроса {endpoint['method']} {endpoint['path']}",
            "expected_status": [200, 201, 204]
        })
        
        # Negative test cases
        responses = endpoint.get("responses", {})
        
        # 400 Bad Request
        if "400" in responses:
            test_cases.append({
                "type": "negative_validation",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Validation Error",
                "description": f"Проверка ошибки валидации {endpoint['method']} {endpoint['path']}",
                "expected_status": [400]
            })
        
        # 401 Unauthorized
        if "401" in responses:
            test_cases.append({
                "type": "negative_auth",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Unauthorized",
                "description": f"Проверка ошибки авторизации {endpoint['method']} {endpoint['path']}",
                "expected_status": [401]
            })
        
        # 403 Forbidden
        if "403" in responses:
            test_cases.append({
                "type": "negative_forbidden",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Forbidden",
                "description": f"Проверка ошибки доступа {endpoint['method']} {endpoint['path']}",
                "expected_status": [403]
            })
        
        # 404 Not Found
        if "404" in responses:
            test_cases.append({
                "type": "negative_not_found",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Not Found",
                "description": f"Проверка ошибки не найден {endpoint['method']} {endpoint['path']}",
                "expected_status": [404]
            })
        
        # 422 Validation Error
        if "422" in responses:
            test_cases.append({
                "type": "negative_validation",
                "name": f"Test {endpoint['method']} {endpoint['path']} - Validation Error",
                "description": f"Проверка ошибки валидации {endpoint['method']} {endpoint['path']}",
                "expected_status": [422]
            })
        
        return test_cases

