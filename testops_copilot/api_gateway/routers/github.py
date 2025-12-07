"""
GitHub интеграция endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID

from shared.utils.database import get_db_dependency, Session
from workers.tasks.github_integration import GitHubIntegration
from shared.config.settings import settings

router = APIRouter(prefix="/github", tags=["GitHub"])


class SaveToGitHubRequest(BaseModel):
    """Запрос на сохранение тестов в GitHub"""
    request_id: UUID
    branch: str = Field(default="testops/generated-tests", description="Ветка для коммита")
    commit_message: Optional[str] = Field(default=None, description="Сообщение коммита")


class CreatePRRequest(BaseModel):
    """Запрос на создание Pull Request"""
    request_id: UUID
    source_branch: str = Field(default="testops/generated-tests", description="Исходная ветка")
    target_branch: str = Field(default="main", description="Целевая ветка")
    title: Optional[str] = Field(default=None, description="Заголовок PR")


@router.post("/save", status_code=status.HTTP_200_OK)
async def save_tests_to_github(
    request: SaveToGitHubRequest,
    db: Session = Depends(get_db_dependency)
):
    """
    Сохранение тест-кейсов в GitHub репозиторий
    """
    if not settings.github_token or not settings.github_repo_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub integration not configured. Add GITHUB_TOKEN and GITHUB_REPO_NAME to .env"
        )
    
    try:
        github_integration = GitHubIntegration()
        result = github_integration.save_tests_to_repo(
            request_id=str(request.request_id),
            branch=request.branch,
            commit_message=request.commit_message
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to save tests to GitHub")
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
            detail=f"GitHub integration error: {str(e)}"
        )


@router.post("/pull-request", status_code=status.HTTP_201_CREATED)
async def create_pull_request(
    request: CreatePRRequest,
    db: Session = Depends(get_db_dependency)
):
    """
    Создание Pull Request в GitHub
    """
    if not settings.github_token or not settings.github_repo_name:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub integration not configured. Add GITHUB_TOKEN and GITHUB_REPO_NAME to .env"
        )
    
    try:
        github_integration = GitHubIntegration()
        result = github_integration.create_pull_request(
            request_id=str(request.request_id),
            source_branch=request.source_branch,
            target_branch=request.target_branch,
            title=request.title
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to create pull request")
            )
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub integration error: {str(e)}"
        )

