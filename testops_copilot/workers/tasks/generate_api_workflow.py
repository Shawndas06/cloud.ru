"""
Celery задача для генерации API тест-кейсов
"""
from celery import Task
from workers.celery_app import celery_app
from shared.utils.database import get_db
from shared.models.database import Request, TestCase
from agents.generator.generator_agent import GeneratorAgent
from agents.generator.openapi_parser import OpenAPIParser
from agents.validator.validator_agent import ValidatorAgent
from shared.utils.redis_client import redis_client
import uuid
import hashlib
from datetime import datetime
import asyncio


class GenerateAPIWorkflowTask(Task):
    """Базовый класс для задачи генерации API тестов"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Обработка ошибок задачи"""
        request_id = kwargs.get("request_id") or (args[0] if args else None)
        if request_id:
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "failed"
                    request.error_message = str(exc)
                    db.commit()


@celery_app.task(
    bind=True,
    base=GenerateAPIWorkflowTask,
    name="workers.tasks.generate_api_workflow.generate_api_tests_task"
)
def generate_api_tests_task(
    self,
    request_id: str,
    openapi_url: str = None,
    openapi_spec: str = None,
    endpoints: list = None,
    test_types: list = None,
    options: dict = None
):
    """
    Генерация API тест-кейсов
    
    Args:
        request_id: UUID запроса
        openapi_url: URL к OpenAPI спецификации
        openapi_spec: YAML/JSON содержимое OpenAPI (если файл загружен)
        endpoints: Список endpoints для покрытия
        test_types: Типы тестов (positive, negative, security)
        options: Дополнительные параметры
    """
    options = options or {}
    test_types = test_types or ["positive"]
    
    try:
        # Обновление статуса
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            if not request:
                raise ValueError(f"Request {request_id} not found")
            
            request.status = "processing"
            request.started_at = datetime.utcnow()
            db.commit()
        
        # Публикация события начала
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "parsing"}
        )
        
        # Шаг 1: Парсинг OpenAPI спецификации
        parser = OpenAPIParser()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if openapi_spec:
                # Если спецификация передана как строка
                import yaml
                import json
                try:
                    spec_dict = yaml.safe_load(openapi_spec)
                except:
                    spec_dict = json.loads(openapi_spec)
            elif openapi_url:
                spec_dict = loop.run_until_complete(parser.parse_from_url(openapi_url))
            else:
                raise ValueError("openapi_url or openapi_spec is required")
        finally:
            loop.close()
        
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "generation"}
        )
        
        # Шаг 2: Generation - генерация API тестов
        generator = GeneratorAgent()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tests = loop.run_until_complete(
                generator.generate_api_tests(
                    openapi_spec=spec_dict,
                    openapi_url=openapi_url,
                    endpoints=endpoints,
                    test_types=test_types
                )
            )
        finally:
            loop.close()
        
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "validation", "tests_count": len(tests)}
        )
        
        # Шаг 3: Validation - валидация тестов
        validator = ValidatorAgent()
        validated_tests = []
        
        for test_code in tests:
            validation_result = validator.validate(test_code, validation_level="full")
            
            if validation_result.get("passed", False):
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
            else:
                print(f"Validation failed for API test: {validation_result.get('errors', [])}")
        
        # Шаг 4: Сохранение в БД
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            
            saved_tests = []
            for test_data in validated_tests:
                test_code = test_data["code"]
                code_hash = hashlib.sha256(test_code.encode()).hexdigest()
                
                # Определение имени теста
                test_name = "Generated API Test"
                if "def test_" in test_code:
                    import re
                    match = re.search(r'def\s+(test_\w+)', test_code)
                    if match:
                        test_name = match.group(1)
                
                test_case = TestCase(
                    request_id=request.request_id,
                    test_name=test_name,
                    test_code=test_code,
                    test_type="api",
                    code_hash=code_hash,
                    validation_status="passed" if test_data.get("validation", {}).get("passed") else "warning",
                    validation_issues=test_data.get("validation", {}).get("errors", [])
                )
                db.add(test_case)
                saved_tests.append({
                    "test_id": str(test_case.test_id),
                    "test_name": test_name
                })
            
            request.status = "completed"
            request.completed_at = datetime.utcnow()
            request.result_summary = {
                "tests_generated": len(saved_tests),
                "tests_validated": len(validated_tests),
                "endpoints_covered": len(endpoints) if endpoints else "all",
                "test_types": test_types
            }
            db.commit()
        
        # Публикация события завершения
        redis_client.publish_event(
            f"request:{request_id}",
            {
                "status": "completed",
                "tests_count": len(saved_tests),
                "result_summary": request.result_summary
            }
        )
        
        return {
            "request_id": request_id,
            "status": "completed",
            "tests_count": len(saved_tests),
            "tests": saved_tests
        }
    
    except Exception as e:
        # Обработка ошибок
        error_msg = str(e)
        print(f"Error in generate_api_tests_task: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Обновление статуса в БД
        try:
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "failed"
                    request.error_message = error_msg
                    request.completed_at = datetime.utcnow()
                    db.commit()
        except Exception as db_error:
            print(f"Error updating request status: {db_error}")
        
        # Публикация события об ошибке
        try:
            redis_client.publish_event(
                f"request:{request_id}",
                {"status": "failed", "error": error_msg}
            )
        except Exception:
            pass
        
        raise


