"""
Роутер для оптимизации тест-кейсов
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional

from agents.optimizer.optimizer_agent import OptimizerAgent

router = APIRouter(prefix="/optimize", tags=["Optimization"])


class TestInput(BaseModel):
    """Входной тест для оптимизации"""
    test_id: str
    test_code: str


class OptimizeRequest(BaseModel):
    """Запрос на оптимизацию"""
    tests: List[TestInput] = Field(..., min_items=1)
    requirements: List[str] = Field(..., min_items=1)
    options: Optional[dict] = Field(default=None)


class OptimizeResponse(BaseModel):
    """Ответ оптимизации"""
    optimized_tests: List[dict]
    duplicates_found: int
    duplicates: List[dict]
    coverage_score: float
    coverage_details: dict
    gaps: List[dict]
    recommendations: List[str]


@router.post("/tests", response_model=OptimizeResponse)
async def optimize_tests(
    request: OptimizeRequest
):
    """
    Оптимизация набора тест-кейсов
    
    Анализирует набор тестов на дубликаты и покрытие требований
    """
    optimizer = OptimizerAgent()
    
    try:
        result = await optimizer.optimize(
            tests=[{"test_id": t.test_id, "test_code": t.test_code} for t in request.tests],
            requirements=request.requirements,
            options=request.options or {}
        )
        
        return OptimizeResponse(
            optimized_tests=result.get("optimized_tests", []),
            duplicates_found=result.get("duplicates_found", 0),
            duplicates=result.get("duplicates", []),
            coverage_score=result.get("coverage_score", 0.0),
            coverage_details=result.get("coverage_details", {}),
            gaps=result.get("gaps", []),
            recommendations=result.get("recommendations", [])
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization error: {str(e)}"
        )

