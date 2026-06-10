"""
OpenAI LLM service.
Handles text generation using OpenAI's API.
"""

import httpx
import logging
from typing import Optional, List, Dict, Any
from config import get_settings

logger = logging.getLogger(__name__)


class OpenAILLM:
    """Service for LLM inference using OpenAI."""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.openai_api_key
        self.model = self.settings.openai_model
        self.temperature = self.settings.openai_temperature
        self.max_tokens = self.settings.openai_max_tokens
        self.base_url = "https://api.openai.com/v1"
        self.client = httpx.AsyncClient(timeout=60.0)
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Generate text response using OpenAI LLM.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            model: Model to use
            
        Returns:
            Generated text
        """
        try:
            temperature = temperature or self.temperature
            max_tokens = max_tokens or self.max_tokens
            model = model or self.model
            
            # Prepare headers
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Prepare messages
            messages = []
            if system_prompt:
                messages.append({
                    "role": "system",
                    "content": system_prompt
                })
            messages.append({
                "role": "user",
                "content": prompt
            })
            
            # Prepare request payload
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # Make request to OpenAI API
            url = f"{self.base_url}/chat/completions"
            response = await self.client.post(
                url,
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"OpenAI API error: {response.status_code} - {response.text}")
                raise Exception(f"OpenAI LLM failed: {response.status_code}")
            
            # Extract response text
            result = response.json()
            
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                text = message.get("content", "").strip()
                
                if text:
                    logger.info(f"Successfully generated response ({len(text)} characters)")
                    return text
            
            logger.warning("No response text found in OpenAI response")
            return ""
            
        except Exception as e:
            logger.error(f"Error during OpenAI generation: {str(e)}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
