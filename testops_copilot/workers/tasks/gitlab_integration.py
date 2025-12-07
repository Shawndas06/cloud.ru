"""
GitLab интеграция для сохранения тестов в репозиторий
"""
from typing import Dict, Any, Optional
import gitlab
from shared.config.settings import settings
from shared.utils.database import get_db
from shared.models.database import Request, TestCase
import uuid


class GitLabIntegration:
    """Интеграция с GitLab для сохранения тестов"""
    
    def __init__(self):
        if not settings.gitlab_url or not settings.gitlab_token:
            raise ValueError("GitLab integration not configured. Set GITLAB_URL and GITLAB_TOKEN in .env")
        
        self.gitlab_url = settings.gitlab_url
        self.gitlab_token = settings.gitlab_token
        self.project_id = settings.gitlab_project_id
        
        # Инициализация GitLab клиента
        try:
            self.gl = gitlab.Gitlab(self.gitlab_url, private_token=self.gitlab_token)
            self.gl.auth()
        except Exception as e:
            raise ValueError(f"Failed to connect to GitLab: {str(e)}")
    
    def save_tests_to_repo(
        self,
        request_id: str,
        branch: str = "testops/generated-tests",
        commit_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Сохранение тестов в GitLab репозиторий
        
        Args:
            request_id: UUID запроса
            branch: Ветка для коммита
            commit_message: Сообщение коммита
        
        Returns:
            Результат операции
        """
        if not self.project_id:
            raise ValueError("GITLAB_PROJECT_ID not configured")
        
        try:
            # Получение проекта
            project = self.gl.projects.get(self.project_id)
            
            # Получение тестов из БД
            with get_db() as db:
                request = db.query(Request).filter(Request.request_id == uuid.UUID(request_id)).first()
                if not request:
                    raise ValueError(f"Request {request_id} not found")
                
                test_cases = db.query(TestCase).filter(TestCase.request_id == request.request_id).all()
            
            if not test_cases:
                return {
                    "success": False,
                    "error": "No test cases found for this request"
                }
            
            # Создание или переключение на ветку
            try:
                project.branches.get(branch)
            except gitlab.exceptions.GitlabGetError:
                # Создание новой ветки от main
                main_branch = project.branches.get("main")
                project.branches.create({
                    "branch": branch,
                    "ref": main_branch.name
                })
            
            # Подготовка файлов для коммита
            commit_message = commit_message or f"Add generated tests for request {request_id}"
            actions = []
            
            for test_case in test_cases:
                # Определение пути файла
                file_path = f"tests/generated/{test_case.test_name}.py"
                
                actions.append({
                    "action": "create",
                    "file_path": file_path,
                    "content": test_case.test_code
                })
            
            # Создание коммита
            commit = project.commits.create({
                "branch": branch,
                "commit_message": commit_message,
                "actions": actions
            })
            
            return {
                "success": True,
                "commit_id": commit.id,
                "branch": branch,
                "files_count": len(actions),
                "message": f"Successfully saved {len(actions)} test files to GitLab"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_merge_request(
        self,
        request_id: str,
        source_branch: str = "testops/generated-tests",
        target_branch: str = "main",
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создание Merge Request в GitLab
        
        Args:
            request_id: UUID запроса
            source_branch: Исходная ветка
            target_branch: Целевая ветка
            title: Заголовок MR
        
        Returns:
            Результат операции
        """
        if not self.project_id:
            raise ValueError("GITLAB_PROJECT_ID not configured")
        
        try:
            project = self.gl.projects.get(self.project_id)
            
            title = title or f"Add generated tests for request {request_id}"
            
            # Создание Merge Request
            mr = project.mergerequests.create({
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
                "description": f"Automatically generated tests for request {request_id}"
            })
            
            return {
                "success": True,
                "merge_request_id": mr.id,
                "merge_request_url": mr.web_url,
                "title": title
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

