"""
Validator Agent - валидация тест-кейсов
"""
import ast
import re
from typing import Dict, List, Any
from agents.validator.safety_guard import SafetyGuard


class ValidatorAgent:
    """Агент валидации тест-кейсов"""
    
    def __init__(self):
        self.safety_guard = SafetyGuard()
    
    def validate(
        self,
        test_code: str,
        validation_level: str = "full"
    ) -> Dict[str, Any]:
        """
        Валидация тест-кейса
        
        Args:
            test_code: Python код теста
            validation_level: syntax, semantic, full
        
        Returns:
            Результаты валидации
        """
        result = {
            "passed": True,
            "score": 100,
            "syntax_errors": [],
            "semantic_errors": [],
            "logic_errors": [],
            "safety_issues": [],
            "warnings": [],
            "recommendations": []
        }
        
        # Layer 1: Syntax Validation
        syntax_result = self._validate_syntax(test_code)
        result["syntax_errors"] = syntax_result["errors"]
        if syntax_result["errors"]:
            result["passed"] = False
            result["score"] = 0
            return result
        
        if validation_level == "syntax":
            return result
        
        # Layer 2: Semantic Validation
        semantic_result = self._validate_semantic(test_code)
        result["semantic_errors"] = semantic_result["errors"]
        result["warnings"].extend(semantic_result["warnings"])
        if semantic_result["errors"]:
            result["passed"] = False
            result["score"] -= 30
        
        if validation_level == "semantic":
            return result
        
        # Layer 3: Logic Validation
        logic_result = self._validate_logic(test_code)
        result["logic_errors"] = logic_result["errors"]
        result["warnings"].extend(logic_result["warnings"])
        if logic_result["errors"]:
            result["passed"] = False
            result["score"] -= 20
        
        # Layer 4: Safety Guard
        safety_result = self.safety_guard.validate(test_code)
        result["safety_issues"] = safety_result.get("issues", [])
        if safety_result.get("risk_level") in ["HIGH", "CRITICAL"]:
            result["passed"] = False
            result["score"] = 0
        
        # Расчет финального score
        result["score"] = max(0, result["score"])
        result["recommendations"] = self._generate_recommendations(result)
        
        return result
    
    def _validate_syntax(self, test_code: str) -> Dict[str, List]:
        """Валидация синтаксиса через AST"""
        errors = []
        try:
            ast.parse(test_code)
        except SyntaxError as e:
            errors.append({
                "line": e.lineno,
                "message": f"SyntaxError: {e.msg}"
            })
        except Exception as e:
            errors.append({
                "line": None,
                "message": f"Parse error: {str(e)}"
            })
        
        return {"errors": errors}
    
    def _validate_semantic(self, test_code: str) -> Dict[str, List]:
        """Валидация семантики (Allure декораторы, AAA pattern)"""
        errors = []
        warnings = []
        
        # Проверка Allure декораторов
        required_decorators = {
            "@allure.feature": r"@allure\.feature\s*\(",
            "@allure.story": r"@allure\.story\s*\(",
            "@allure.title": r"@allure\.title\s*\(",
            "@allure.tag": r"@allure\.tag\s*\("
        }
        
        for decorator, pattern in required_decorators.items():
            if not re.search(pattern, test_code):
                errors.append({
                    "type": "missing_decorator",
                    "message": f"Отсутствует {decorator} декоратор"
                })
        
        # Проверка allure.step
        if "with allure.step" not in test_code:
            warnings.append("Рекомендуется использовать allure.step() для структурирования")
        
        # Проверка assertions
        if not re.search(r"(assert\s+|expect\()", test_code):
            errors.append({
                "type": "missing_assertion",
                "message": "Тест должен содержать хотя бы одну assertion"
            })
        
        return {"errors": errors, "warnings": warnings}
    
    def _validate_logic(self, test_code: str) -> Dict[str, List]:
        """Валидация логики"""
        errors = []
        warnings = []
        
        # Проверка бесконечных циклов
        if re.search(r"while\s+True\s*:", test_code):
            if "break" not in test_code:
                errors.append({
                    "type": "infinite_loop",
                    "message": "Обнаружен while True без break"
                })
        
        # Проверка time.sleep (не рекомендуется)
        if "time.sleep" in test_code:
            warnings.append("Использование time.sleep() не рекомендуется, используйте явные waits")
        
        return {"errors": errors, "warnings": warnings}
    
    def _generate_recommendations(self, result: Dict) -> List[str]:
        """Генерация рекомендаций на основе ошибок"""
        recommendations = []
        
        if result["semantic_errors"]:
            for error in result["semantic_errors"]:
                if error.get("type") == "missing_decorator":
                    recommendations.append(f"Добавить {error.get('message', '')}")
        
        if result["warnings"]:
            recommendations.extend(result["warnings"])
        
        return recommendations

