"""
Интеграция с системами дефектов (Jira, Allure TestOps, etc.)
"""
from typing import Dict, Any, List, Optional
import httpx
import asyncio
from shared.utils.logger import agent_logger
from shared.config.settings import settings


class DefectIntegration:
    """Интеграция с внешними системами дефектов"""
    
    def __init__(self):
        self.jira_url = getattr(settings, 'jira_url', None)
        self.jira_token = getattr(settings, 'jira_token', None)
        self.jira_email = getattr(settings, 'jira_email', None)  # Для Basic Auth
        self.allure_testops_url = getattr(settings, 'allure_testops_url', None)
        self.allure_testops_token = getattr(settings, 'allure_testops_token', None)
        
        # Валидация URL
        if self.jira_url and not self.jira_url.startswith(('http://', 'https://')):
            agent_logger.warning(f"Jira URL должен начинаться с http:// или https://: {self.jira_url}")
            self.jira_url = None
        
        if self.allure_testops_url and not self.allure_testops_url.startswith(('http://', 'https://')):
            agent_logger.warning(f"Allure TestOps URL должен начинаться с http:// или https://: {self.allure_testops_url}")
            self.allure_testops_url = None
    
    async def fetch_defects(
        self,
        project_key: str = None,
        status: List[str] = None,
        priority: List[str] = None,
        date_from: str = None,
        date_to: str = None,
        source: str = "allure"  # "jira", "allure", "all"
    ) -> List[Dict[str, Any]]:
        """
        Получение дефектов из внешних систем
        
        Args:
            project_key: Ключ проекта
            status: Список статусов (например, ["open", "in_progress"])
            priority: Список приоритетов (например, ["critical", "high"])
            date_from: Дата начала (ISO format)
            date_to: Дата окончания (ISO format)
            source: Источник данных ("jira", "allure", "all")
        
        Returns:
            Список дефектов
        """
        all_defects = []
        
        if source in ["allure", "all"] and self.allure_testops_url:
            try:
                allure_defects = await self._fetch_allure_defects(
                    project_key=project_key,
                    status=status,
                    priority=priority,
                    date_from=date_from,
                    date_to=date_to
                )
                all_defects.extend(allure_defects)
            except Exception as e:
                agent_logger.error(f"Error fetching Allure defects: {e}", exc_info=True)
        
        if source in ["jira", "all"] and self.jira_url:
            try:
                jira_defects = await self._fetch_jira_defects(
                    project_key=project_key,
                    status=status,
                    priority=priority,
                    date_from=date_from,
                    date_to=date_to
                )
                all_defects.extend(jira_defects)
            except Exception as e:
                agent_logger.error(f"Error fetching Jira defects: {e}", exc_info=True)
        
        return all_defects
    
    async def _fetch_allure_defects(
        self,
        project_key: str = None,
        status: List[str] = None,
        priority: List[str] = None,
        date_from: str = None,
        date_to: str = None
    ) -> List[Dict[str, Any]]:
        """Получение дефектов из Allure TestOps"""
        if not self.allure_testops_url or not self.allure_testops_token:
            agent_logger.warning("Allure TestOps credentials not configured")
            return []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {self.allure_testops_token}",
                "Content-Type": "application/json"
            }
            
            # Построение запроса
            params = {}
            if project_key:
                params["project"] = project_key
            if status:
                params["status"] = ",".join(status)
            if priority:
                params["priority"] = ",".join(priority)
            if date_from:
                params["dateFrom"] = date_from
            if date_to:
                params["dateTo"] = date_to
            
            try:
                # Пример endpoint для Allure TestOps API
                url = f"{self.allure_testops_url}/api/rs/defect"
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                defects = data.get("content", [])
                
                # Нормализация данных
                normalized = []
                for defect in defects:
                    normalized.append({
                        "id": defect.get("id"),
                        "key": defect.get("key"),
                        "summary": defect.get("name"),
                        "description": defect.get("description"),
                        "status": defect.get("status", {}).get("name"),
                        "priority": defect.get("priority", {}).get("name"),
                        "severity": defect.get("severity"),
                        "created_at": defect.get("createdDate"),
                        "updated_at": defect.get("updatedDate"),
                        "assignee": defect.get("assignee", {}).get("login"),
                        "reporter": defect.get("reporter", {}).get("login"),
                        "affected_components": defect.get("affectedComponents", []),
                        "source": "allure"
                    })
                
                return normalized
            
            except httpx.HTTPStatusError as e:
                agent_logger.error(f"Allure API error: {e.response.status_code} - {e.response.text}")
                return []
            except Exception as e:
                agent_logger.error(f"Error fetching Allure defects: {e}", exc_info=True)
                return []
    
    async def _fetch_jira_defects(
        self,
        project_key: str = None,
        status: List[str] = None,
        priority: List[str] = None,
        date_from: str = None,
        date_to: str = None
    ) -> List[Dict[str, Any]]:
        """Получение дефектов из Jira"""
        if not self.jira_url:
            agent_logger.warning("Jira URL not configured")
            return []
        
        if not self.jira_token and not self.jira_email:
            agent_logger.warning("Jira credentials not configured")
            return []
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Определение типа аутентификации
            if self.jira_email and self.jira_token:
                # Basic Auth (email + API token) - рекомендуемый способ для Jira Cloud
                import base64
                credentials = base64.b64encode(
                    f"{self.jira_email}:{self.jira_token}".encode()
                ).decode()
                headers = {
                    "Authorization": f"Basic {credentials}",
                    "Content-Type": "application/json"
                }
            else:
                # Bearer token
                headers = {
                    "Authorization": f"Bearer {self.jira_token}",
                    "Content-Type": "application/json"
                }
            
            # Построение JQL запроса
            jql_parts = []
            if project_key:
                jql_parts.append(f"project = {project_key}")
            if status:
                jql_parts.append(f"status IN ({', '.join(status)})")
            if priority:
                jql_parts.append(f"priority IN ({', '.join(priority)})")
            if date_from:
                jql_parts.append(f"created >= {date_from}")
            if date_to:
                jql_parts.append(f"created <= {date_to}")
            
            jql = " AND ".join(jql_parts) if jql_parts else "ORDER BY created DESC"
            
            try:
                url = f"{self.jira_url}/rest/api/3/search"
                payload = {
                    "jql": jql,
                    "maxResults": 100,
                    "fields": ["summary", "description", "status", "priority", "created", "updated", "assignee", "reporter", "components"]
                }
                
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                issues = data.get("issues", [])
                
                # Нормализация данных
                normalized = []
                for issue in issues:
                    fields = issue.get("fields", {})
                    normalized.append({
                        "id": issue.get("id"),
                        "key": issue.get("key"),
                        "summary": fields.get("summary"),
                        "description": fields.get("description"),
                        "status": fields.get("status", {}).get("name"),
                        "priority": fields.get("priority", {}).get("name"),
                        "severity": None,  # Jira не имеет severity по умолчанию
                        "created_at": fields.get("created"),
                        "updated_at": fields.get("updated"),
                        "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else None,
                        "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
                        "affected_components": [c.get("name") for c in fields.get("components", [])],
                        "source": "jira"
                    })
                
                return normalized
            
            except httpx.HTTPStatusError as e:
                agent_logger.error(f"Jira API error: {e.response.status_code} - {e.response.text}")
                return []
            except Exception as e:
                agent_logger.error(f"Error fetching Jira defects: {e}", exc_info=True)
                return []
    
    async def test_connection(self, source: str = "all") -> Dict[str, Any]:
        """
        Тестирование подключения к системам дефектов
        
        Args:
            source: "jira", "allure", "all"
        
        Returns:
            Результаты проверки подключения
        """
        results = {
            "jira": {"connected": False, "error": None},
            "allure": {"connected": False, "error": None}
        }
        
        if source in ["jira", "all"]:
            results["jira"] = await self._test_jira_connection()
        
        if source in ["allure", "all"]:
            results["allure"] = await self._test_allure_connection()
        
        return results
    
    async def _test_jira_connection(self) -> Dict[str, Any]:
        """Тестирование подключения к Jira"""
        if not self.jira_url:
            return {"connected": False, "error": "Jira URL не настроен"}
        
        if not self.jira_token and not self.jira_email:
            return {"connected": False, "error": "Jira token или email не настроен"}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Определение типа аутентификации
                if self.jira_email and self.jira_token:
                    # Basic Auth (email + API token)
                    import base64
                    credentials = base64.b64encode(
                        f"{self.jira_email}:{self.jira_token}".encode()
                    ).decode()
                    headers = {
                        "Authorization": f"Basic {credentials}",
                        "Content-Type": "application/json"
                    }
                else:
                    # Bearer token
                    headers = {
                        "Authorization": f"Bearer {self.jira_token}",
                        "Content-Type": "application/json"
                    }
                
                # Тестовый запрос - получение информации о текущем пользователе
                url = f"{self.jira_url}/rest/api/3/myself"
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    user_info = response.json()
                    return {
                        "connected": True,
                        "user": user_info.get("displayName"),
                        "email": user_info.get("emailAddress")
                    }
                else:
                    return {
                        "connected": False,
                        "error": f"HTTP {response.status_code}: {response.text[:200]}"
                    }
        
        except httpx.ConnectError:
            return {"connected": False, "error": "Не удалось подключиться к Jira серверу"}
        except httpx.TimeoutException:
            return {"connected": False, "error": "Таймаут подключения к Jira"}
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    async def _test_allure_connection(self) -> Dict[str, Any]:
        """Тестирование подключения к Allure TestOps"""
        if not self.allure_testops_url:
            return {"connected": False, "error": "Allure TestOps URL не настроен"}
        
        if not self.allure_testops_token:
            return {"connected": False, "error": "Allure TestOps token не настроен"}
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "Authorization": f"Bearer {self.allure_testops_token}",
                    "Content-Type": "application/json"
                }
                
                # Тестовый запрос - получение информации о пользователе или проектах
                # Пробуем несколько возможных endpoints
                test_urls = [
                    f"{self.allure_testops_url}/api/rs/user",
                    f"{self.allure_testops_url}/api/rs/project",
                    f"{self.allure_testops_url}/api/v1/user"
                ]
                
                for url in test_urls:
                    try:
                        response = await client.get(url, headers=headers)
                        if response.status_code == 200:
                            return {
                                "connected": True,
                                "endpoint": url,
                                "message": "Подключение успешно"
                            }
                    except:
                        continue
                
                # Если ни один endpoint не сработал, пробуем базовый
                base_url = f"{self.allure_testops_url}/api/rs"
                response = await client.get(base_url, headers=headers)
                
                if response.status_code in [200, 401, 403]:
                    # 401/403 означает что сервер доступен, но нет прав
                    return {
                        "connected": True,
                        "error": "Сервер доступен, но проверьте права доступа"
                    }
                
                return {
                    "connected": False,
                    "error": f"HTTP {response.status_code}: {response.text[:200]}"
                }
        
        except httpx.ConnectError:
            return {"connected": False, "error": "Не удалось подключиться к Allure TestOps серверу"}
        except httpx.TimeoutException:
            return {"connected": False, "error": "Таймаут подключения к Allure TestOps"}
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """
        Получение статуса конфигурации интеграций
        
        Returns:
            Словарь со статусом конфигурации
        """
        return {
            "jira": {
                "url_configured": bool(self.jira_url),
                "auth_configured": bool(self.jira_token or self.jira_email),
                "url": self.jira_url if self.jira_url else None,
                "auth_type": "basic" if self.jira_email else "bearer" if self.jira_token else None
            },
            "allure": {
                "url_configured": bool(self.allure_testops_url),
                "token_configured": bool(self.allure_testops_token),
                "url": self.allure_testops_url if self.allure_testops_url else None
            }
        }
    
    def analyze_defect_patterns(self, defects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Анализ паттернов дефектов
        
        Args:
            defects: Список дефектов
        
        Returns:
            Словарь с анализом паттернов
        """
        if not defects:
            return {
                "total_defects": 0,
                "by_component": {},
                "by_priority": {},
                "by_status": {},
                "risk_areas": [],
                "trends": {}
            }
        
        # Анализ по компонентам
        by_component = {}
        by_priority = {}
        by_status = {}
        
        for defect in defects:
            # Компоненты
            components = defect.get("affected_components", [])
            for component in components:
                by_component[component] = by_component.get(component, 0) + 1
            
            # Приоритеты
            priority = defect.get("priority", "unknown")
            by_priority[priority] = by_priority.get(priority, 0) + 1
            
            # Статусы
            status = defect.get("status", "unknown")
            by_status[status] = by_status.get(status, 0) + 1
        
        # Определение рискованных областей
        risk_areas = []
        for component, count in by_component.items():
            if count >= 3:  # Порог для рискованной области
                risk_areas.append({
                    "component": component,
                    "defect_count": count,
                    "risk_level": "high" if count >= 5 else "medium"
                })
        
        # Сортировка по количеству дефектов
        risk_areas.sort(key=lambda x: x["defect_count"], reverse=True)
        
        return {
            "total_defects": len(defects),
            "by_component": by_component,
            "by_priority": by_priority,
            "by_status": by_status,
            "risk_areas": risk_areas,
            "trends": {
                "critical_count": by_priority.get("critical", 0) + by_priority.get("blocker", 0),
                "high_count": by_priority.get("high", 0),
                "medium_count": by_priority.get("medium", 0),
                "low_count": by_priority.get("low", 0) + by_priority.get("trivial", 0)
            }
        }

