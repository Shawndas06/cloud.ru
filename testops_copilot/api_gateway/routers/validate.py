"""
Роутер для валидации тест-кейсов
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

from agents.validator.validator_agent import ValidatorAgent

router = APIRouter(prefix="/validate", tags=["Validation"])


class ValidateRequest(BaseModel):
    """Запрос на валидацию теста"""
    test_code: str = Field(..., description="Python код тест-кейса")
    validation_level: Literal["syntax", "semantic", "full"] = Field(
        default="full",
        description="Уровень валидации"
    )


class ValidationError(BaseModel):
    """Ошибка валидации"""
    type: str
    line: Optional[int] = None
    message: str


class ValidationResponse(BaseModel):
    """Ответ валидации"""
    valid: bool
    score: int = Field(..., ge=0, le=100, description="Оценка качества 0-100")
    syntax_errors: List[ValidationError] = []
    semantic_errors: List[ValidationError] = []
    logic_errors: List[ValidationError] = []
    safety_issues: List[dict] = []
    warnings: List[str] = []
    recommendations: List[str] = []


@router.post("/tests", response_model=ValidationResponse)
async def validate_tests(
    request: ValidateRequest
):
    """
    Валидация предоставленного тест-кейса
    
    Запускает валидацию без генерации
    """
    validator = ValidatorAgent()
    
    try:
        result = validator.validate(
            test_code=request.test_code,
            validation_level=request.validation_level
        )
        
        return ValidationResponse(
            valid=result.get("passed", False),
            score=result.get("score", 0),
            syntax_errors=result.get("syntax_errors", []),
            semantic_errors=result.get("semantic_errors", []),
            logic_errors=result.get("logic_errors", []),
            safety_issues=result.get("safety_issues", []),
            warnings=result.get("warnings", []),
            recommendations=result.get("recommendations", [])
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation error: {str(e)}"
        )

