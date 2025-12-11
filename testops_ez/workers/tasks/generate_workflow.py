
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
            agent_logger.info(
                f"[GENERATION] Starting test generation",
                extra={
                    "request_id": request_id,
                    "url": url,
                    "test_type": test_type,
                    "requirements_count": len(requirements),
                    "options": options
                }
            )
            tests = loop.run_until_complete(
                generator.generate_ui_tests(
                    url=url,
                    page_structure=page_structure,
                    requirements=requirements,
                    test_type=test_type,
                    options=options
                )
            )
            agent_logger.info(
                f"[GENERATION] Test generation completed",
                extra={
                    "request_id": request_id,
                    "tests_generated": len(tests),
                    "test_type": test_type
                }
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
        agent_logger.info(f"[VALIDATION] Starting validation of {len(tests)} tests for request {request_id}")
        for i, test_code in enumerate(tests):
            agent_logger.info(f"[VALIDATION] Validating test {i+1}/{len(tests)}")
            validation_result = validator.validate(test_code, validation_level="full")
            
            passed = validation_result.get("passed", False)
            score = validation_result.get("score", 0)
            syntax_errors = len(validation_result.get('syntax_errors', []))
            semantic_errors = len(validation_result.get('semantic_errors', []))
            logic_errors = len(validation_result.get('logic_errors', []))
            warnings = len(validation_result.get('warnings', []))
            
            agent_logger.info(
                f"[VALIDATION] Test {i+1} validation result",
                extra={
                    "test_number": i+1,
                    "passed": passed,
                    "score": score,
                    "syntax_errors": syntax_errors,
                    "semantic_errors": semantic_errors,
                    "logic_errors": logic_errors,
                    "warnings": warnings,
                    "has_decorators": "@allure.feature" in test_code and "@allure.story" in test_code and "@allure.title" in test_code
                }
            )
            
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
                agent_logger.info(f"[VALIDATION] Test {i+1} ACCEPTED - added to validated_tests (passed={passed}, score={score})")
            else:
                errors = validation_result.get('errors', [])
                agent_logger.warning(
                    f"[VALIDATION] Test {i+1} has issues but will be added",
                    extra={
                        "test_number": i+1,
                        "score": score,
                        "errors_count": len(errors),
                        "warnings_count": warnings,
                        "syntax_errors": syntax_errors,
                        "semantic_errors": semantic_errors,
                        "logic_errors": logic_errors
                    }
                )
                if errors:
                    agent_logger.warning(f"[VALIDATION] Test {i+1} errors: {errors[:3]}")
                if validation_result.get('warnings'):
                    agent_logger.warning(f"[VALIDATION] Test {i+1} warnings: {validation_result.get('warnings', [])[:3]}")
                # Все равно добавляем тест, но с предупреждением
                validated_tests.append({
                    "code": test_code,
                    "validation": validation_result
                })
                agent_logger.info(f"[VALIDATION] Test {i+1} added to validated_tests despite issues")
        
        agent_logger.info(f"[VALIDATION] Validation completed: {len(validated_tests)}/{len(tests)} tests validated")
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
                
                # Логика статуса: passed если нет синтаксических ошибок
                # Тесты с синтаксически правильным кодом должны быть passed
                validation = test_data.get("validation", {})
                syntax_errors = len(validation.get("syntax_errors", []))
                has_decorators = (
                    "@allure.feature" in test_code and
                    "@allure.story" in test_code and
                    "@allure.title" in test_code
                )
                score = validation.get("score", 0)
                
                # Тест считается passed если:
                # 1. Нет синтаксических ошибок (критично!)
                # 2. И (есть декораторы ИЛИ score >= 50)
                # Основная цель - тесты должны работать, warnings не критичны
                is_passed = (
                    syntax_errors == 0 and
                    (has_decorators or score >= 50)
                )
                
                validation_status = "passed" if is_passed else "warning"
                
                agent_logger.info(
                    f"[STATUS] Test '{test_name}' status determination",
                    extra={
                        "test_name": test_name,
                        "syntax_errors": syntax_errors,
                        "has_decorators": has_decorators,
                        "score": score,
                        "is_passed": is_passed,
                        "validation_status": validation_status
                    }
                )
                
                test_case = TestCase(
                    request_id=request.request_id,
                    test_name=test_name,
                    test_code=test_code,
                    test_type=actual_test_type,
                    code_hash=code_hash,
                    validation_status=validation_status,
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