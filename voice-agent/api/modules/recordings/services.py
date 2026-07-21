"""
Recordings Service.
Generates presigned download URLs from AWS S3 using boto3.
"""

import boto3
import logging
from botocore.config import Config
from typing import Dict, Any, List, Optional
from api.modules.recordings.repositories import RecordingRepository
from config import get_settings

logger = logging.getLogger("voice-agent.api.recordings.services")


class RecordingsService:
    def __init__(self):
        self.recording_repository = RecordingRepository()
        settings = get_settings()
        
        # Configure AWS S3 Client with region-specific endpoint
        endpoint_url = f"https://s3.{settings.aws_region}.amazonaws.com" if settings.aws_region else None
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
            endpoint_url=endpoint_url,
            config=Config(signature_version="s3v4")
        )

    async def get_all_recordings(self) -> List[Dict[str, Any]]:
        """Fetch all recording records."""
        recs = await self.recording_repository.find_all()
        return [self.map_to_response(r) for r in recs]

    async def get_recording_by_id(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """Fetch individual recording metadata."""
        rec = await self.recording_repository.find_by_id(recording_id)
        if not rec:
            return None
        return self.map_to_response(rec)

    async def get_recordings_by_conversation_id(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Fetch recording records linked to a specific call session."""
        recs = await self.recording_repository.find_by_conversation_id(conversation_id)
        return [self.map_to_response(r) for r in recs]

    async def generate_signed_url(self, recording_id: str) -> Dict[str, Any]:
        """Generate a pre-signed S3 download URL valid for 60 seconds."""
        rec = await self.recording_repository.find_by_id(recording_id)
        if not rec:
            raise KeyError("Recording not found")
            
        settings = get_settings()
        
        # Check for mock or missing S3 configurations
        if not settings.aws_access_key_id or settings.aws_access_key_id == "mock":
            logger.info("AWS S3 credentials set to mock. Yielding local fallback mp3.")
            return {
                "url": settings.fallback_audio_url,
                "filename": rec["filename"]
            }
            
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.s3_bucket_name,
                    "Key": rec["s3_key"]
                },
                ExpiresIn=60
            )
            return {
                "url": url,
                "filename": rec["filename"]
            }
        except Exception as e:
            logger.error(f"Failed to generate S3 pre-signed URL: {e}. Yielding fallback.")
            return {
                "url": settings.fallback_audio_url,
                "filename": rec["filename"]
            }

    def map_to_response(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Convert snake_case recording columns to camelCase React DataTable bindings."""
        return {
            "id": str(r["id"]),
            "filename": r["filename"],
            "duration": r["duration"],
            "size": int(r["size"]),
            "createdAt": r["created_at"].isoformat() if hasattr(r["created_at"], "isoformat") else r["created_at"],
            "conversationId": str(r["conversation_id"])
        }
