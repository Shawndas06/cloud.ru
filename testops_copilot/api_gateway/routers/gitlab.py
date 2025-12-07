"""
GitLab интеграция endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID

from shared.utils.database import get_db_dependency, Session
from shared.config.settings import settings

# Опциональный импорт GitLab
try:
    from workers.tasks.gitlab_integration import GitLabIntegration
    GITLAB_AVAILABLE = True
except ImportError:
    GITLAB_AVAILABLE = False
    GitLabIntegration = None

router = APIRouter(prefix="/gitlab", tags=["GitLab"])


class SaveToGitLabRequest(BaseModel):
    """Запрос на сохранение тестов в GitLab"""
    request_id: UUID
    branch: str = Field(default="testops/generated-tests", description="Ветка для коммита")
    commit_message: Optional[str] = Field(default=None, description="Сообщение коммита")


class CreateMRRequest(BaseModel):
    """Запрос на создание Merge Request"""
    request_id: UUID
    source_branch: str = Field(default="testops/generated-tests", description="Исходная ветка")
    target_branch: str = Field(default="main", description="Целевая ветка")
    title: Optional[str] = Field(default=None, description="Заголовок MR")


@router.post("/save", status_code=status.HTTP_200_OK)
async def save_tests_to_gitlab(
    request: SaveToGitLabRequest,
    db: Session = Depends(get_db_dependency)
):
    """
    Сохранение тест-кейсов в GitLab репозиторий
    """
    if not GITLAB_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitLab integration not available. Install python-gitlab: pip install python-gitlab"
        )
    
    if not settings.gitlab_url or not settings.gitlab_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitLab integration not configured"
        )
    
    try:
        gitlab_integration = GitLabIntegration()
        result = gitlab_integration.save_tests_to_repo(
            request_id=str(request.request_id),
            branch=request.branch,
            commit_message=request.commit_message
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to save tests to GitLab")
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitLab integration error: {str(e)}"
        )


@router.post("/merge-request", status_code=status.HTTP_201_CREATED)
async def create_merge_request(
    request: CreateMRRequest,
    db: Session = Depends(get_db_dependency)
):
    """
    Создание Merge Request в GitLab
    """
    if not GITLAB_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitLab integration not available. Install python-gitlab: pip install python-gitlab"
        )
    
    if not settings.gitlab_url or not settings.gitlab_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitLab integration not configured"
        )
    
    try:
        gitlab_integration = GitLabIntegration()
        result = gitlab_integration.create_merge_request(
            request_id=str(request.request_id),
            source_branch=request.source_branch,
            target_branch=request.target_branch,
            title=request.title
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create merge request")
            )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitLab integration error: {str(e)}"
        )
