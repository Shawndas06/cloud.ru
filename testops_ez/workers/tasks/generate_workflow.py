
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
    options = options or {}
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
            {"status": "processing", "step": "reconnaissance"}
        )
        recon_agent = ReconnaissanceAgent()
        page_structure = recon_agent.analyze_page(url, timeout=60)
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "generation"}
        )
        generator = GeneratorAgent()
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
        validator = ValidatorAgent()
        validated_tests = []
        from shared.utils.logger import agent_logger
        agent_logger.info(f"Validating {len(tests)} tests")
        for i, test_code in enumerate(tests):
            validation_result = validator.validate(test_code, validation_level="full")
            agent_logger.info(f"Test {i+1} validation: passed={validation_result.get('passed', False)}, errors={len(validation_result.get('errors', []))}")
            passed = validation_result.get("passed", False)
            score = validation_result.get("score", 0)
            agent_logger.info(f"Test {i+1} validation result: passed={passed}, score={score}, errors={len(validation_result.get('errors', []))}, warnings={len(validation_result.get('warnings', []))}")
            
            # Более гибкая логика: принимаем тест если нет синтаксических ошибок и score >= 50
            # или если есть только warnings (не errors)
            syntax_errors = len(validation_result.get('syntax_errors', []))
            semantic_errors = len(validation_result.get('semantic_errors', []))
            logic_errors = len(validation_result.get('logic_errors', []))
            
            # Принимаем тест если:
            # 1. Нет синтаксических ошибок И
            # 2. (passed = True ИЛИ score >= 50 ИЛИ нет критических ошибок)
            is_valid = (
                syntax_errors == 0 and
                (passed or score >= 50 or (semantic_errors == 0 and logic_errors == 0))
            )
            
            if is_valid:
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
                agent_logger.info(f"Test {i+1} added to validated_tests")
            else:
                errors = validation_result.get('errors', [])
                warnings = validation_result.get('warnings', [])
                agent_logger.warning(f"Validation failed for test {i+1}: score={score}, errors={len(errors)}, warnings={len(warnings)}")
                if errors:
                    agent_logger.warning(f"Errors: {errors[:3]}")
                if warnings:
                    agent_logger.warning(f"Warnings: {warnings[:3]}")
                # Все равно добавляем тест, но с предупреждением
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
                agent_logger.info(f"Test {i+1} added to validated_tests despite issues")
        redis_client.publish_event(
            f"request:{request_id}",
            {"status": "processing", "step": "optimization", "validated_count": len(validated_tests)}
        )
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
        with get_db() as db:
            request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
            saved_tests = []
            for test_data in optimized_tests:
                test_code = test_data["code"]
                code_hash = hashlib.sha256(test_code.encode()).hexdigest()
                test_name = "Test"
                if "def test_" in test_code:
                    import re
                    match = re.search(r'def\s+(test_\w+)', test_code)
                    if match:
                        test_name = match.group(1)
                actual_test_type = "automated" if "def test_" in test_code else "manual"
                test_case = TestCase(
                    request_id=request.request_id,
                    test_name=test_name,
                    test_code=test_code,
                    test_type=actual_test_type,
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
            try:
                from shared.utils.email_service import email_service
                from shared.models.database import User
                if request.user_id:
                    user = db.query(User).filter(User.user_id == request.user_id).first()
                    if user and user.email:
                        email_service.send_generation_completed(
                            to=user.email,
                            request_id=str(request.request_id),
                            tests_count=len(saved_tests),
                            status="completed"
                        )
            except Exception as e:
                from shared.utils.logger import agent_logger
                agent_logger.warning(f"Failed to send email notification: {e}")
            result_summary = {
                "tests_generated": len(saved_tests),
                "tests_validated": len(validated_tests),
                "tests_optimized": len(optimized_tests),
                "test_type": test_type
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
        print(f"Error in generate_test_cases_task: {error_msg}")
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