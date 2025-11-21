"""
Модуль для работы с ChatGPT API
"""
import os
from typing import Optional, List, Dict
from openai import AsyncOpenAI
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)


class LLMClient:
    """Клиент для работы с ChatGPT API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Инициализация клиента OpenAI
        
        Args:
            api_key: API ключ OpenAI. Если не указан, берется из переменной окружения OPENAI_API_KEY
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY не найден. Укажите его в .env файле или передайте при инициализации.")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = "gpt-4o-mini"  # Используем более доступную модель
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Выполнение запроса к ChatGPT API
        
        Args:
            messages: Список сообщений в формате [{"role": "user", "content": "..."}]
            temperature: Параметр температуры (0.0 - 2.0), контролирует случайность ответа
            max_tokens: Максимальное количество токенов в ответе
        
        Returns:
            Текст ответа от модели
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка при обращении к ChatGPT API: {e}")
            raise
    
    async def generate_response(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> str:
        """
        Генерация ответа на сообщение пользователя
        
        Args:
            user_message: Сообщение пользователя
            system_prompt: Системный промпт для настройки поведения модели
            conversation_history: История диалога (список предыдущих сообщений)
            temperature: Параметр температуры
            max_tokens: Максимальное количество токенов
        
        Returns:
            Ответ модели
        """
        messages = []
        
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        if conversation_history:
            messages.extend(conversation_history)
        
        messages.append({"role": "user", "content": user_message})
        
        return await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )


# Глобальный экземпляр клиента (инициализируется при первом использовании)
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Получить глобальный экземпляр LLM клиента"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client

