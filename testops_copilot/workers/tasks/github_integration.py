"""
GitHub интеграция для сохранения тестов в репозиторий
"""
from typing import Dict, Any, Optional
from github import Github, GithubException
from shared.config.settings import settings
from shared.utils.database import get_db
from shared.models.database import Request, TestCase
import uuid
import base64


class GitHubIntegration:
    """Интеграция с GitHub для сохранения тестов"""
    
    def __init__(self):
        if not settings.github_token or not settings.github_repo_name:
            raise ValueError("GitHub integration not configured. Set GITHUB_TOKEN and GITHUB_REPO_NAME in .env")
        
        self.github_token = settings.github_token
        self.repo_name = settings.github_repo_name
        
        # Инициализация GitHub клиента
        try:
            self.github = Github(self.github_token)
            self.repo = self.github.get_repo(self.repo_name)
        except Exception as e:
            raise ValueError(f"Failed to connect to GitHub: {str(e)}")
    
    def save_tests_to_repo(
        self,
        request_id: str,
        branch: str = "testops/generated-tests",
        commit_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Сохранение тестов в GitHub репозиторий
        
        Args:
            request_id: UUID запроса
            branch: Ветка для коммита
            commit_message: Сообщение коммита
        
        Returns:
            Результат операции
        """
        try:
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
            
            # Получение основной ветки (обычно main или master)
            try:
                main_branch = self.repo.get_branch("main")
            except GithubException:
                main_branch = self.repo.get_branch("master")
            
            # Создание или получение ветки
            try:
                new_branch = self.repo.get_branch(branch)
            except GithubException:
                # Создание новой ветки
                sha = main_branch.commit.sha
                self.repo.create_git_ref(ref=f"refs/heads/{branch}", sha=sha)
                new_branch = self.repo.get_branch(branch)
            
            commit_message = commit_message or f"Add generated tests for request {request_id}"
            
            # Подготовка файлов для коммита
            tree_items = []
            base_tree = self.repo.get_git_tree(new_branch.commit.sha)
            
            for test_case in test_cases:
                file_path = f"tests/generated/{test_case.test_name}.py"
                content = test_case.test_code
                content_encoded = base64.b64encode(content.encode()).decode()
                
                # Создание blob
                blob = self.repo.create_git_blob(content_encoded, "base64")
                
                tree_items.append({
                    "path": file_path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob.sha
                })
            
            # Создание tree
            tree = self.repo.create_git_tree(tree_items, base_tree)
            
            # Создание коммита
            parent = self.repo.get_git_commit(new_branch.commit.sha)
            commit = self.repo.create_git_commit(
                message=commit_message,
                tree=tree,
                parents=[parent]
            )
            
            # Обновление ветки
            ref = self.repo.get_git_ref(f"heads/{branch}")
            ref.edit(commit.sha)
            
            return {
                "success": True,
                "commit_id": commit.sha,
                "branch": branch,
                "files_count": len(tree_items),
                "message": f"Successfully saved {len(tree_items)} test files to GitHub"
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_pull_request(
        self,
        request_id: str,
        source_branch: str = "testops/generated-tests",
        target_branch: str = "main",
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создание Pull Request в GitHub
        
        Args:
            request_id: UUID запроса
            source_branch: Исходная ветка
            target_branch: Целевая ветка
            title: Заголовок PR
        
        Returns:
            Результат операции
        """
        try:
            title = title or f"Add generated tests for request {request_id}"
            
            # Создание Pull Request
            pr = self.repo.create_pull(
                title=title,
                body=f"Automatically generated tests for request {request_id}",
                head=source_branch,
                base=target_branch
            )
            
            return {
                "success": True,
                "pull_request_id": pr.number,
                "pull_request_url": pr.html_url,
                "title": title
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

