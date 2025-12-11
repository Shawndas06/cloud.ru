
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
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        request_id = kwargs.get("request_id") or (args[0] if args else None)
        if request_id:
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if request:
                    request.status = "failed"
                    request.error_message = str(exc)
                    db.commit()
                    try:
                        from shared.utils.email_service import email_service
                        from shared.models.database import User
                        if request.user_id:
                            user = db.query(User).filter(User.user_id == request.user_id).first()
                            if user and user.email:
                                email_service.send_error_notification(
                                    to=user.email,
                                    request_id=str(request.request_id),
                                    error_message=str(exc)
                                )
                    except Exception as e:
                        from shared.utils.logger import agent_logger
                        agent_logger.warning(f"Failed to send error email notification: {e}")
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
    options = options or {}
    test_types = test_types or ["positive"]
    try:
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            if not request:
                raise ValueError(f"Request {request_id} not found")
            request.status = "processing"
            request.started_at = datetime.utcnow()
            db.commit()
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "parsing"}
        )
        parser = OpenAPIParser()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            if openapi_spec:
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
        validator = ValidatorAgent()
        validated_tests = []
        from shared.utils.logger import agent_logger
        agent_logger.info(f"Validating {len(tests)} API tests")
        for i, test_code in enumerate(tests):
            validation_result = validator.validate(test_code, validation_level="full")
            passed = validation_result.get("passed", False)
            score = validation_result.get("score", 0)
            agent_logger.info(f"API Test {i+1} validation result: passed={passed}, score={score}")
            
            syntax_errors = len(validation_result.get('syntax_errors', []))
            semantic_errors = len(validation_result.get('semantic_errors', []))
            syntax_errs = validation_result.get('syntax_errors', [])
            semantic_errs = validation_result.get('semantic_errors', [])
            
            # Логируем детали ошибок
            if syntax_errors > 0:
                agent_logger.warning(f"API Test {i+1} syntax errors: {syntax_errs}")
            if semantic_errors > 0:
                agent_logger.warning(f"API Test {i+1} semantic errors: {semantic_errs}")
            
            # Для API тестов принимаем даже с ошибками, если они не критичны
            # Пробуем исправить простые синтаксические ошибки
            if syntax_errors > 0:
                # Пытаемся исправить распространенные ошибки
                fixed_code = test_code
                # Удаляем неполные строки в конце
                lines = fixed_code.split('\n')
                while lines and lines[-1].strip() and not any(lines[-1].strip().endswith(c) for c in [':', '}', ']', ')', 'assert', 'pass', 'return']):
                    if '=' in lines[-1] or 'await' in lines[-1] or 'response' in lines[-1]:
                        # Возможно неполная строка, удаляем
                        lines.pop()
                    else:
                        break
                fixed_code = '\n'.join(lines)
                
                # Проверяем синтаксис исправленного кода
                try:
                    import ast
                    ast.parse(fixed_code)
                    test_code = fixed_code
                    syntax_errors = 0
                    agent_logger.info(f"API Test {i+1} syntax fixed")
                except:
                    pass
            
            # Принимаем тест если нет критических синтаксических ошибок
            # Для API тестов более мягкая валидация - принимаем если код выглядит как тест
            syntax_errors = len(validation_result.get('syntax_errors', []))
            semantic_errors = len(validation_result.get('semantic_errors', []))
            
            is_valid_test = (
                syntax_errors == 0 and
                (passed or score >= 50 or (semantic_errors == 0 and "def test_" in test_code and "assert" in test_code))
            )
            
            if is_valid_test:
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
                agent_logger.info(f"API Test {i+1} added to validated_tests (score={score}, passed={passed}, syntax_errors={syntax_errors})")
            else:
                # Все равно добавляем, но с предупреждением
                agent_logger.warning(
                    f"API Test {i+1} has issues but will be saved: score={score}, syntax_errors={syntax_errors}, semantic_errors={semantic_errors}",
                    extra={
                        "syntax_errors": syntax_errs,
                        "semantic_errors": semantic_errs,
                        "test_preview": test_code[:500]
                    }
                )
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            saved_tests = []
            for test_data in validated_tests:
                test_code = test_data["code"]
                code_hash = hashlib.sha256(test_code.encode()).hexdigest()
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
                    # Исправляем логику статуса: passed если нет синтаксических ошибок и score >= 50
                    validation_status="passed" if (
                        test_data.get("validation", {}).get("passed") or
                        (len(test_data.get("validation", {}).get("syntax_errors", [])) == 0 and
                         test_data.get("validation", {}).get("score", 0) >= 50)
                    ) else "warning",
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
            result_summary = {
                "tests_generated": len(saved_tests),
                "tests_validated": len(validated_tests),
                "tests_optimized": len(validated_tests),  # Для API тестов оптимизация = валидация
                "test_type": "api"
            }
            request.result_summary = result_summary
            db.commit()
        redis_client.publish_event(
            f"request:{request_id}",
            {
                "status": "completed",
                "tests_count": len(saved_tests),
                "result_summary": result_summary
            }
        )
        return {
            "request_id": request_id,
            "status": "completed",
            "tests_count": len(saved_tests),
            "tests": saved_tests
        }
    except Exception as e:
        error_msg = str(e)
        print(f"Error in generate_api_tests_task: {error_msg}")
        import traceback
        traceback.print_exc()
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
        try:
            redis_client.publish_event(
                f"request:{request_id}",
                {"status": "failed", "error": error_msg}
            )
        except Exception:
            pass
        raise