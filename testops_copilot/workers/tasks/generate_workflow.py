"""
Celery задача для генерации UI тест-кейсов
"""
from celery import Task
from workers.celery_app import celery_app
from shared.utils.database import get_db
from shared.models.database import Request, TestCase
from agents.reconnaissance.reconnaissance_agent import ReconnaissanceAgent
from agents.generator.generator_agent import GeneratorAgent
from agents.validator.validator_agent import ValidatorAgent
from agents.optimizer.optimizer_agent import OptimizerAgent
from shared.utils.redis_client import redis_client
import uuid
import json
import hashlib
from datetime import datetime
import asyncio


class GenerateWorkflowTask(Task):
    """Базовый класс для задачи генерации с обработкой ошибок"""
    
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
    base=GenerateWorkflowTask,
    name="workers.tasks.generate_workflow.generate_test_cases_task"
)
def generate_test_cases_task(
    self,
    request_id: str,
    url: str,
    requirements: list,
    test_type: str,
    options: dict = None
):
    """
    Генерация UI тест-кейсов
    
    Args:
        request_id: UUID запроса
        url: URL для тестирования
        requirements: Список требований
        test_type: Тип тестов (manual, automated, both)
        options: Дополнительные параметры
    """
    options = options or {}
    
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
            {"status": "processing", "step": "reconnaissance"}
        )
        
        # Шаг 1: Reconnaissance - анализ страницы
        recon_agent = ReconnaissanceAgent()
        page_structure = recon_agent.analyze_page(url, timeout=60)
        
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "generation"}
        )
        
        # Шаг 2: Generation - генерация тестов
        generator = GeneratorAgent()
        
        # Запуск асинхронной генерации
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            tests = loop.run_until_complete(
                generator.generate_ui_tests(
                    url=url,
                    page_structure=page_structure,
                    requirements=requirements,
                    test_type=test_type,
                    options=options
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
                # Логируем ошибки валидации, но не блокируем процесс
                print(f"Validation failed for test: {validation_result.get('errors', [])}")
        
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "optimization", "validated_count": len(validated_tests)}
        )
        
        # Шаг 4: Optimization - оптимизация (если включено)
        optimized_tests = validated_tests
        if options.get("optimize", True) and len(validated_tests) > 1:
            optimizer = OptimizerAgent()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                optimization_result = loop.run_until_complete(
                    optimizer.optimize(
                        tests=[{"test_id": str(uuid.uuid4()), "test_code": t["code"]} for t in validated_tests],
                        requirements=requirements,
                        options=options
                    )
                )
                optimized_tests = [
                    {"code": t["test_code"], "validation": validated_tests[i].get("validation", {})}
                    for i, t in enumerate(optimization_result.get("optimized_tests", []))
                ]
            finally:
                loop.close()
        
        # Шаг 5: Сохранение в БД
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            
            saved_tests = []
            for test_data in optimized_tests:
                test_code = test_data["code"]
                code_hash = hashlib.sha256(test_code.encode()).hexdigest()
                
                # Определение типа теста из кода
                test_name = "Generated Test"
                if "def test_" in test_code:
                    import re
                    match = re.search(r'def\s+(test_\w+)', test_code)
                    if match:
                        test_name = match.group(1)
                
                # Определение типа (manual/automated)
                actual_test_type = "automated" if "def test_" in test_code else "manual"
                
                test_case = TestCase(
                    request_id=request.request_id,
                    test_name=test_name,
                    test_code=test_code,
                    test_type=actual_test_type,
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
                "tests_optimized": len(optimized_tests),
                "test_type": test_type
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
        print(f"Error in generate_test_cases_task: {error_msg}")
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


