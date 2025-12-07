"""
Safety Guard - 4-уровневая система защиты от опасного кода
"""
import ast
import re
from typing import Dict, List, Any


class SafetyGuard:
    """Система безопасности для проверки сгенерированного кода"""
    
    # Blacklist паттерны
    CRITICAL_BLACKLIST = [
        r'\beval\s\(',
        r'\bexec\s\(',
        r'\bcompile\s\(',
        r'\b__import__\s\(',
        r'\bos\.system\s\(',
        r'\bos\.popen\s\(',
        r'\bsubprocess\.',
        r'\bsocket\.',
        r'\bpickle\.loads?\s\(',
        r'\bsetattr\s\(',
        r'\bdelattr\s\(',
        r'\bglobals\s*\(',
        r'\blocals\s*\(',
    ]
    
    # Whitelist разрешенных импортов
    ALLOWED_IMPORTS = {
        'pytest', 'pytest_asyncio', 'allure', 'allure_commons', 'allure_pytest',
        'playwright', 'playwright.sync_api', 'playwright.async_api',
        'selenium', 'selenium.webdriver',
        'httpx', 'requests', 'aiohttp',
        'json', 're', 'datetime', 'time', 'uuid', 'math', 'random',
        'typing', 'typing_extensions', 'dataclasses', 'enum',
        'collections', 'functools', 'itertools',
        'asyncio', 'logging'
    }
    
    def validate(self, test_code: str) -> Dict[str, Any]:
        """
        Полная валидация безопасности (4 уровня)
        
        Returns:
            {
                "risk_level": "SAFE|LOW|MEDIUM|HIGH|CRITICAL",
                "issues": [...],
                "blocked_patterns": [...],
                "action_taken": "allowed|blocked|warning|regenerate"
            }
        """
        result = {
            "risk_level": "SAFE",
            "issues": [],
            "blocked_patterns": [],
            "action_taken": "allowed"
        }
        
        # Level 1: Static Analysis (~1ms)
        level1_result = self._static_analysis(test_code)
        if level1_result["blocked"]:
            result["risk_level"] = "CRITICAL"
            result["blocked_patterns"] = level1_result["blocked"]
            result["action_taken"] = "blocked"
            return result
        
        # Level 2: AST Analysis (~10ms)
        level2_result = self._ast_analysis(test_code)
        if level2_result["blocked"]:
            result["risk_level"] = "HIGH"
            result["blocked_patterns"] = level2_result["blocked"]
            result["action_taken"] = "blocked"
            return result
        
        if level2_result["warnings"]:
            result["risk_level"] = "MEDIUM"
            result["issues"] = level2_result["warnings"]
            result["action_taken"] = "warning"
        
        # Level 3: Behavioral Analysis (~50ms)
        level3_result = self._behavioral_analysis(test_code)
        if level3_result["warnings"]:
            if result["risk_level"] == "SAFE":
                result["risk_level"] = "LOW"
            result["issues"].extend(level3_result["warnings"])
        
        # Level 4: Sandbox (опционально, не реализовано в MVP)
        # if settings.safety_guard_sandbox_enabled:
        #     level4_result = self._sandbox_execution(test_code)
        
        return result
    
    def _static_analysis(self, test_code: str) -> Dict[str, List]:
        """Level 1: Static Analysis - regex поиск опасных паттернов"""
        blocked = []
        
        for pattern in self.CRITICAL_BLACKLIST:
            if re.search(pattern, test_code, re.IGNORECASE):
                blocked.append(pattern)
        
        return {"blocked": blocked}
    
    def _ast_analysis(self, test_code: str) -> Dict[str, List]:
        """Level 2: AST Analysis - проверка импортов и структуры"""
        blocked = []
        warnings = []
        
        try:
            tree = ast.parse(test_code)
            
            # Проверка импортов
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name.split('.')[0]
                        if module not in self.ALLOWED_IMPORTS:
                            blocked.append(f"Forbidden import: {module}")
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        module = node.module.split('.')[0]
                        if module not in self.ALLOWED_IMPORTS:
                            blocked.append(f"Forbidden import: {module}")
                
                # Проверка запрещенных вызовов
                elif isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ['eval', 'exec', 'compile', '__import__']:
                            blocked.append(f"Forbidden function call: {node.func.id}")
        
        except SyntaxError:
            # Синтаксические ошибки обрабатываются в ValidatorAgent
            pass
        
        return {"blocked": blocked, "warnings": warnings}
    
    def _behavioral_analysis(self, test_code: str) -> Dict[str, List]:
        """Level 3: Behavioral Analysis - проверка файловых и сетевых операций"""
        warnings = []
        
        # Проверка записи в файлы
        if re.search(r'open\s*\([^)]*["\']w["\']', test_code):
            warnings.append("File write operation detected")
        
        # Проверка удаления файлов
        if re.search(r'(os\.remove|os\.unlink|shutil\.rmtree)', test_code):
            warnings.append("File deletion operation detected")
        
        return {"warnings": warnings}

