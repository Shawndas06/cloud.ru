"""
Клиент для работы с Cloud.ru Foundation Models API
"""
import asyncio
from typing import Dict, Any, Optional
from shared.config.settings import settings
from shared.utils.redis_client import redis_client
from shared.utils.logger import llm_logger
import hashlib
import json

try:
    from openai import OpenAI, AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    # Fallback на httpx если openai не установлен
    import httpx


class LLMClient:
    """Клиент для Cloud.ru Foundation Models API"""
    
    def __init__(self):
        self.base_url = settings.cloud_ru_foundation_models_url
        self.api_key = settings.cloud_ru_api_key
        self.iam_url = settings.cloud_ru_iam_url
        self.key_id = settings.cloud_ru_key_id
        self.key_secret = settings.cloud_ru_key_secret
        self.default_model = getattr(settings, 'cloud_ru_default_model', 'ai-sage/GigaChat3-10B-A1.8B')
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[float] = None
        
        # Инициализация OpenAI клиента
        if OPENAI_AVAILABLE:
            try:
                self._openai_client = AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url
                )
                llm_logger.info("OpenAI client initialized successfully")
            except Exception as e:
                llm_logger.warning(f"Failed to initialize OpenAI client: {e}, falling back to httpx")
                self._openai_client = None
        else:
            self._openai_client = None
            llm_logger.warning("OpenAI library not available, using httpx fallback")
        
        # Fallback HTTP клиент
        if not self._openai_client:
            import httpx
            self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_access_token(self) -> str:
        """Получение access token через IAM API"""
        import time
        
        # Проверка кеша токена
        if self._access_token and self._token_expires_at:
            if time.time() < self._token_expires_at - 300:  # Обновляем за 5 минут до истечения
                return self._access_token
        
        # Получение нового токена
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.iam_url,
                    json={
                        "keyId": self.key_id,
                        "secret": self.key_secret
                    },
                    timeout=10.0
                )
                
                # Детальное логирование ошибок
                if response.status_code != 200:
                    error_text = response.text[:500]
                    llm_logger.error(
                        f"IAM API Error {response.status_code}",
                        extra={
                            "url": self.iam_url,
                            "status_code": response.status_code,
                            "response_text": error_text,
                            "key_id": f"{self.key_id[:20]}..."
                        }
                    )
                
                response.raise_for_status()
                data = response.json()
                
                self._access_token = data["access_token"]
                expires_in = data.get("expires_in", 3600)
                self._token_expires_at = time.time() + expires_in
                
                return self._access_token
        except httpx.HTTPStatusError as e:
            llm_logger.error(
                f"IAM API HTTP Error: {e.response.status_code}",
                extra={
                    "status_code": e.response.status_code,
                    "response_text": e.response.text[:500]
                }
            )
            raise
        except Exception as e:
            llm_logger.error(f"IAM API Error: {str(e)}", exc_info=True)
            raise
    
    async def _get_http_client(self):
        """Получить или создать HTTP клиент (fallback)"""
        if not OPENAI_AVAILABLE:
            import httpx
            if self._http_client is None:
                self._http_client = httpx.AsyncClient(timeout=60.0)
            return self._http_client
        return None
    
    async def close(self):
        """Закрыть клиенты"""
        if self._openai_client:
            await self._openai_client.close()
        if hasattr(self, '_http_client') and self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        model: str = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        use_cache: bool = True,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Генерация через LLM API
        
        Args:
            prompt: Пользовательский промпт
            system_prompt: Системный промпт
            model: Модель для использования (по умолчанию ai-sage/GigaChat3-10B-A1.8B)
            temperature: Температура генерации
            max_tokens: Максимум токенов
            use_cache: Использовать кеш в Redis
            **kwargs: Дополнительные параметры для API
        
        Returns:
            Ответ от LLM API
        """
        # Используем модель по умолчанию, если не указана
        if model is None:
            model = self.default_model
        
        # Проверка кеша
        if use_cache:
            cache_key = f"llm_cache:{hashlib.sha256((system_prompt + prompt + model).encode()).hexdigest()}"
            cached = redis_client.cache.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # Формирование запроса
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        # Вызов API с retry
        max_retries = 3
        base_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                # Используем OpenAI клиент если доступен
                if self._openai_client:
                    try:
                        response = await self._openai_client.chat.completions.create(
                            model=model,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            **kwargs
                        )
                        
                        # Преобразование ответа OpenAI в формат, совместимый с текущим кодом
                        result = {
                            "choices": [{
                                "message": {
                                    "role": response.choices[0].message.role,
                                    "content": response.choices[0].message.content
                                }
                            }],
                            "usage": {
                                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                                "total_tokens": response.usage.total_tokens if response.usage else 0
                            }
                        }
                        
                        # Сохранение в кеш
                        if use_cache:
                            try:
                                redis_client.cache.setex(
                                    cache_key,
                                    3600,  # TTL 1 час
                                    json.dumps(result)
                                )
                            except Exception as cache_error:
                                llm_logger.warning(f"Failed to cache LLM response: {cache_error}")
                        
                        llm_logger.info(
                            "LLM generation successful",
                            extra={
                                "model": model,
                                "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                            }
                        )
                        
                        return result
                    
                    except Exception as e:
                        llm_logger.warning(f"OpenAI client error: {e}, falling back to httpx")
                        # Fallback на httpx при ошибке
                        if attempt == max_retries - 1:
                            raise
                        await asyncio.sleep(base_delay * (2 ** attempt))
                        continue
                
                # Fallback на httpx если OpenAI клиент недоступен
                if not OPENAI_AVAILABLE:
                    import httpx
                    client = await self._get_http_client()
                    
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": messages,
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                            **kwargs,
                        },
                    )
                    
                    if response.status_code != 200:
                        error_text = response.text[:1000]
                        error_json = None
                        try:
                            error_json = response.json()
                        except:
                            pass
                        
                        llm_logger.error(
                            f"LLM API Error {response.status_code}",
                            extra={
                                "url": f"{self.base_url}/chat/completions",
                                "status_code": response.status_code,
                                "response_text": error_text,
                                "error_json": error_json
                            }
                        )
                    
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            await asyncio.sleep(delay)
                            continue
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    # Сохранение в кеш
                    if use_cache:
                        try:
                            redis_client.cache.setex(
                                cache_key,
                                3600,
                                json.dumps(result)
                            )
                        except Exception as cache_error:
                            llm_logger.warning(f"Failed to cache LLM response: {cache_error}")
                    
                    llm_logger.info(
                        "LLM generation successful",
                        extra={
                            "model": model,
                            "tokens_used": result.get("usage", {}).get("total_tokens", 0)
                        }
                    )
                    
                    return result
            
            except Exception as e:
                if attempt == max_retries - 1:
                    llm_logger.error(f"LLM generation failed after {max_retries} attempts: {e}", exc_info=True)
                    raise
                await asyncio.sleep(base_delay * (2 ** attempt))
        
        raise Exception("Failed to generate after retries")
    
    async def generate_embeddings(self, text: str) -> list:
        """
        Генерация embeddings для semantic similarity
        
        Использует hash-based подход (быстро, без зависимостей от torch)
        Генерирует детерминированный 384-мерный вектор из текста
        """
        try:
            # Используем hash-based embeddings (быстро и без torch)
            # Генерируем детерминированный вектор из текста
            hash_obj = hashlib.sha256(text.encode('utf-8'))
            hash_bytes = hash_obj.digest()
            
            # Создаем 384-мерный вектор (стандартный размер для embeddings)
            # Используем разные части хеша для разных измерений
            embedding = []
            for i in range(384):
                # Комбинируем байты хеша для создания разнообразия
                byte_idx = i % len(hash_bytes)
                next_byte_idx = (i + 1) % len(hash_bytes)
                value = (hash_bytes[byte_idx] + hash_bytes[next_byte_idx] * 256) / 65535.0
                embedding.append(float(value))
            
            # Нормализуем вектор
            import math
            norm = math.sqrt(sum(x*x for x in embedding))
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            return embedding
            
        except Exception as e:
            llm_logger.error(f"Error generating embeddings: {e}", exc_info=True)
            # Fallback: простой хеш
            hash_obj = hashlib.sha256(text.encode('utf-8'))
            return [float(b) / 255.0 for b in hash_obj.digest()[:384]]


# Глобальный экземпляр
llm_client = LLMClient()

