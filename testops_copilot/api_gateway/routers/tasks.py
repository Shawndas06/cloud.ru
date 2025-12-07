"""
Роутер для управления задачами
"""
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel
from uuid import UUID
from typing import Optional, List
from datetime import datetime

from shared.utils.database import get_db_dependency, Session
from shared.models.database import Request, TestCase, GenerationMetric

router = APIRouter(prefix="/tasks", tags=["Tasks"])


class TaskStatusResponse(BaseModel):
    """Ответ со статусом задачи"""
    request_id: UUID
    status: str
    current_step: Optional[str] = None
    progress: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    result_summary: Optional[dict] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None
    tests: Optional[List[dict]] = None
    metrics: Optional[List[dict]] = None


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: UUID,
    include_tests: bool = Query(False, description="Включить сгенерированные тесты"),
    include_metrics: bool = Query(False, description="Включить метрики выполнения"),
    db: Session = Depends(get_db_dependency)
):
    """
    Получение статуса выполнения задачи
    
    Возвращает текущий статус и результаты выполнения задачи
    """
    # Поиск запроса по request_id (task_id = request_id)
    request = db.query(Request).filter(Request.request_id == task_id).first()
    
    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with ID {task_id} not found"
        )
    
    response_data = {
        "request_id": request.request_id,
        "status": request.status,
        "started_at": request.started_at,
        "completed_at": request.completed_at,
        "retry_count": request.retry_count
    }
    
    # Добавление текущего шага и прогресса для processing статуса
    if request.status == "processing":
        # Определяем шаг на основе langgraph_thread_id или других полей
        response_data["current_step"] = "generator"  # Упрощенно, в реальности из checkpoint
        response_data["progress"] = 50  # Упрощенно, в реальности вычисляется
        if request.started_at:
            from datetime import timedelta
            response_data["estimated_completion"] = request.started_at + timedelta(minutes=2)
    
    # Добавление результатов для completed статуса
    if request.status == "completed":
        response_data["result_summary"] = request.result_summary
        
        if include_tests:
            tests = db.query(TestCase).filter(TestCase.request_id == task_id).all()
            response_data["tests"] = [
                {
                    "test_id": str(test.test_id),
                    "test_name": test.test_name,
                    "test_code": test.test_code,
                    "priority": test.priority,
                    "allure_tags": test.allure_tags
                }
                for test in tests
            ]
        
        if include_metrics:
            metrics = db.query(GenerationMetric).filter(GenerationMetric.request_id == task_id).all()
            response_data["metrics"] = [
                {
                    "agent_name": metric.agent_name,
                    "duration_ms": metric.duration_ms,
                    "status": metric.status,
                    "llm_tokens_total": metric.llm_tokens_total
                }
                for metric in metrics
            ]
    
    # Добавление ошибки для failed статуса
    if request.status == "failed":
        response_data["error_message"] = request.error_message
    
    return TaskStatusResponse(**response_data)

