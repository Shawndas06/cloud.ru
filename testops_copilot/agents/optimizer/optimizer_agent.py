"""
Optimizer Agent - дедупликация и анализ покрытия
"""
import hashlib
import asyncio
import numpy as np
from typing import Dict, List, Any
from shared.utils.database import get_db
from shared.models.database import TestCase
from shared.utils.llm_client import llm_client
from shared.utils.logger import agent_logger


class OptimizerAgent:
    """Агент оптимизации тест-кейсов"""
    
    async def optimize(
        self,
        tests: List[Dict[str, str]],
        requirements: List[str],
        options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Оптимизация набора тестов
        
        Args:
            tests: Список тестов [{"test_id": "...", "test_code": "..."}]
            requirements: Список требований
            options: Опции (similarity_threshold, include_existing)
        
        Returns:
            Результаты оптимизации
        """
        options = options or {}
        similarity_threshold = options.get("similarity_threshold", 0.85)
        include_existing = options.get("include_existing", False)
        
        # Level 1: Exact Match Deduplication
        exact_duplicates = self._find_exact_duplicates(tests)
        
        # Level 2: Semantic Similarity (с embeddings)
        semantic_duplicates = await self._find_semantic_duplicates(tests, similarity_threshold)
        
        # Coverage Analysis
        coverage_result = self._analyze_coverage(tests, requirements)
        
        # Формирование результата
        all_duplicates = exact_duplicates + semantic_duplicates
        unique_tests = self._remove_duplicates(tests, all_duplicates)
        
        return {
            "optimized_tests": unique_tests,
            "duplicates_found": len(all_duplicates),
            "duplicates": all_duplicates,
            "coverage_score": coverage_result["score"],
            "coverage_details": coverage_result["details"],
            "gaps": coverage_result["gaps"],
            "recommendations": self._generate_recommendations(all_duplicates, coverage_result)
        }
    
    def _find_exact_duplicates(self, tests: List[Dict]) -> List[Dict]:
        """Level 1: Exact Match - сравнение по хешу"""
        duplicates = []
        seen_hashes = {}
        
        for test in tests:
            code_hash = hashlib.sha256(test["test_code"].encode()).hexdigest()
            
            if code_hash in seen_hashes:
                duplicates.append({
                    "test_ids": [seen_hashes[code_hash], test["test_id"]],
                    "type": "exact",
                    "similarity_score": 1.0
                })
            else:
                seen_hashes[code_hash] = test["test_id"]
        
        return duplicates
    
    async def _find_semantic_duplicates(self, tests: List[Dict], threshold: float) -> List[Dict]:
        """
        Level 2: Semantic Similarity с использованием embeddings
        
        Генерирует embeddings для каждого теста и находит семантически похожие тесты
        используя косинусное сходство.
        """
        if len(tests) < 2:
            return []
        
        try:
            # Генерация embeddings для всех тестов
            agent_logger.info(f"Generating embeddings for {len(tests)} tests")
            embeddings = []
            test_texts = []
            
            for test in tests:
                # Извлечение текста для embedding (название + код)
                test_text = f"{test.get('test_name', '')} {test.get('test_code', '')}"
                test_texts.append(test_text)
                
                # Генерация embedding
                embedding = await llm_client.generate_embeddings(test_text)
                embeddings.append(embedding)
            
            # Поиск семантически похожих тестов
            duplicates = []
            embeddings_array = np.array(embeddings)
            
            # Вычисление косинусного сходства для всех пар
            for i in range(len(tests)):
                for j in range(i + 1, len(tests)):
                    # Косинусное сходство
                    similarity = self._cosine_similarity(
                        embeddings_array[i],
                        embeddings_array[j]
                    )
                    
                    if similarity >= threshold:
                        duplicates.append({
                            "test_ids": [tests[i]["test_id"], tests[j]["test_id"]],
                            "type": "semantic",
                            "similarity_score": float(similarity),
                            "test_names": [
                                tests[i].get("test_name", ""),
                                tests[j].get("test_name", "")
                            ]
                        })
            
            agent_logger.info(f"Found {len(duplicates)} semantic duplicates")
            return duplicates
        
        except Exception as e:
            agent_logger.error(f"Error finding semantic duplicates: {e}", exc_info=True)
            # Fallback: возвращаем пустой список при ошибке
            return []
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Вычисление косинусного сходства между двумя векторами"""
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)
            
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
        
        except Exception as e:
            agent_logger.warning(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def _analyze_coverage(self, tests: List[Dict], requirements: List[str]) -> Dict:
        """Анализ покрытия требований"""
        coverage_details = {}
        gaps = []
        
        for idx, requirement in enumerate(requirements):
            covering_tests = []
            
            # Упрощенная проверка - ищем упоминание требования в коде
            for test in tests:
                if requirement.lower() in test["test_code"].lower():
                    covering_tests.append(test["test_id"])
            
            is_covered = len(covering_tests) > 0
            coverage_details[f"requirement_{idx}"] = {
                "text": requirement,
                "covered": is_covered,
                "tests": covering_tests,
                "quality": "good" if len(covering_tests) >= 2 else "insufficient"
            }
            
            if not is_covered:
                gaps.append({
                    "requirement": f"requirement_{idx}",
                    "description": f"Отсутствуют тесты для: {requirement}"
                })
        
        # Расчет coverage_score
        covered_count = sum(1 for detail in coverage_details.values() if detail["covered"])
        coverage_score = covered_count / len(requirements) if requirements else 0.0
        
        return {
            "score": coverage_score,
            "details": coverage_details,
            "gaps": gaps
        }
    
    def _remove_duplicates(self, tests: List[Dict], duplicates: List[Dict]) -> List[Dict]:
        """Удаление дубликатов из списка тестов"""
        duplicate_ids = set()
        for dup in duplicates:
            duplicate_ids.update(dup["test_ids"][1:])  # Оставляем первый, удаляем остальные
        
        return [test for test in tests if test["test_id"] not in duplicate_ids]
    
    def _generate_recommendations(self, duplicates: List[Dict], coverage: Dict) -> List[str]:
        """Генерация рекомендаций"""
        recommendations = []
        
        if duplicates:
            recommendations.append(f"Удалить {len(duplicates)} дубликатов")
        
        if coverage["gaps"]:
            recommendations.append(f"Добавить тесты для {len(coverage['gaps'])} непокрытых требований")
        
        return recommendations

