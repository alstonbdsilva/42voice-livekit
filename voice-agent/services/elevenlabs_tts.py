"""
ElevenLabs Text-to-Speech service.
Handles text-to-speech conversion using ElevenLabs' TTS API.
"""

import httpx
import logging
from typing import Optional
from config import get_settings

logger = logging.getLogger(__name__)


class ElevenLabsTTS:
    """Service for Text-to-Speech using ElevenLabs."""
    
    def __init__(self):
        self.settings = get_settings()
        self.api_key = self.settings.elevenlabs_api_key
        self.model = self.settings.elevenlabs_tts_model
        self.voice_id = self.settings.elevenlabs_tts_voice_id
        self.language = self.settings.elevenlabs_tts_language
        self.base_url = "https://api.elevenlabs.io/v1"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def synthesize(
        self,
        text: str,
        language: Optional[str] = None,
        model: Optional[str] = None,
        voice_id: Optional[str] = None
    ) -> bytes:
        """
        Convert text to speech audio.
        
        Args:
            text: Text to convert to speech
            language: Language code (default from config)
            model: Optional model override
            voice_id: Optional voice ID override
            
        Returns:
            Audio bytes (MP3 format)
        """
        try:
            language = language or self.language
            model = model or self.model
            voice_id = voice_id or self.voice_id
            
            # Prepare request
            headers = {
                "xi-api-key": self.api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "text": text,
                "model_id": model,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
            
            # Make request to ElevenLabs API
            url = f"{self.base_url}/text-to-speech/{voice_id}"
            response = await self.client.post(
                url,
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"ElevenLabs API error: {response.status_code} - {response.text}")
                raise Exception(f"ElevenLabs TTS failed: {response.status_code}")
            
            # Return audio bytes
            audio_data = response.content
            logger.info(f"Successfully synthesized audio ({len(audio_data)} bytes)")
            return audio_data
            
        except Exception as e:
            logger.error(f"Error during ElevenLabs synthesis: {str(e)}")
            raise
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
