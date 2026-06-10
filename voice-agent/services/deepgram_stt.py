"""
Deepgram Speech-to-Text service.
Handles audio transcription using Deepgram's STT API.
"""

import httpx
import logging
from typing import Optional
from config import get_settings

logger = logging.getLogger(__name__)


class DeepgramSTT:
    """Service for Speech-to-Text using Deepgram."""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.deepgram_api_key
        self.model = self.settings.deepgram_stt_model
        self.language = self.settings.deepgram_stt_language
        self.base_url = "https://api.deepgram.com/v1"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """
        Transcribe audio data to text.
        
        Args:
            audio_data: Raw audio bytes
            language: Language code (default: hi for Hindi)
            model: Optional model override
            
        Returns:
            Transcribed text
        """
        try:
            language = language or self.language
            model = model or self.model
            
            # Prepare headers
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/octet-stream"
            }
            
            # Prepare query parameters
            params = {
                "model": model,
                "language": language,
                "punctuate": True,
                "smart_format": True
            }
            
            # Make request to Deepgram API
            url = f"{self.base_url}/listen"
            response = await self.client.post(
                url,
                content=audio_data,
                headers=headers,
                params=params
            )
            
            if response.status_code != 200:
                logger.error(f"Deepgram API error: {response.status_code} - {response.text}")
                raise Exception(f"Deepgram STT failed: {response.status_code}")
            
            # Extract transcribed text from response
            result = response.json()
            
            # Navigate through the response structure
            if "results" in result and "channels" in result["results"]:
                transcript = ""
                for channel in result["results"]["channels"]:
                    for alternative in channel.get("alternatives", []):
                        transcript = alternative.get("transcript", "")
                        if transcript:
                            break
                    if transcript:
                        break
                
                if transcript:
                    logger.info(f"Successfully transcribed audio")
                    return transcript
            
            logger.warning("No transcript found in Deepgram response")
            return ""
            
        except Exception as e:
            logger.error(f"Error during Deepgram transcription: {str(e)}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
