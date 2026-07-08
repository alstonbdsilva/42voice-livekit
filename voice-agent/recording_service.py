"""
Recording service for LiveKit egress with S3 upload support.
Handles room recording and uploading to AWS S3.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from livekit import api
from livekit.protocol import egress
from .config import get_settings

logger = logging.getLogger(__name__)

class RecordingService:
    """Service for managing LiveKit room recordings and S3 uploads."""
    
    def __init__(self):
        self.settings = get_settings()
        self.livekit_client = api.LiveKitAPI(
            self.settings.livekit_url,
            self.settings.livekit_api_key,
            self.settings.livekit_api_secret
        )
        
    async def start_room_recording(self, room_name: str) -> Optional[str]:
        """
        Start recording a room to S3.
        
        Args:
            room_name: Name of the room to record
            
        Returns:
            Egress ID if successful, None otherwise
        """
        try:
            # Generate unique filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{room_name}_{timestamp}.mp4"
            s3_key = f"{self.settings.s3_bucket_path}{filename}"
            
            # Configure S3 upload
            s3_upload = egress.S3Upload(
                access_key=self.settings.aws_access_key_id,
                secret=self.settings.aws_secret_access_key,
                region=self.settings.aws_region,
                bucket=self.settings.s3_bucket_name,
                key=s3_key
            )
            
            # Configure file output
            file_output = egress.EncodedFileOutput(
                file_type=egress.EncodedFileType.MP4,
                file_path=filename,
                upload=s3_upload
            )
            
            # Start room composite egress
            request = egress.RoomCompositeEgressRequest(
                room_name=room_name,
                output=file_output,
                layout="grid"  # Use grid layout for all participants
            )
            
            logger.info(f"Starting recording for room: {room_name}")
            egress_info = await self.livekit_client.egress.start_room_composite_egress(request)
            
            logger.info(f"Recording started with egress ID: {egress_info.egress_id}")
            return egress_info.egress_id
            
        except Exception as e:
            logger.error(f"Failed to start recording for room {room_name}: {e}")
            return None
    
    async def stop_recording(self, egress_id: str) -> bool:
        """
        Stop a recording by egress ID.
        
        Args:
            egress_id: ID of the egress to stop
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"Stopping recording with egress ID: {egress_id}")
            await self.livekit_client.egress.stop_egress(egress_id)
            logger.info(f"Recording stopped successfully: {egress_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop recording {egress_id}: {e}")
            return False
    
    async def get_recording_status(self, egress_id: str) -> Optional[egress.EgressInfo]:
        """
        Get the status of a recording.
        
        Args:
            egress_id: ID of the egress to check
            
        Returns:
            EgressInfo if found, None otherwise
        """
        try:
            response = await self.livekit_client.egress.list_egress()
            for egress_info in response.items:
                if egress_info.egress_id == egress_id:
                    return egress_info
            return None
            
        except Exception as e:
            logger.error(f"Failed to get recording status for {egress_id}: {e}")
            return None
    
    async def list_active_recordings(self) -> list[egress.EgressInfo]:
        """
        List all active recordings.
        
        Returns:
            List of active egress recordings
        """
        try:
            response = await self.livekit_client.egress.list_egress()
            active_recordings = []
            
            for egress_info in response.items:
                if egress_info.status in [
                    egress.EgressStatus.EGRESS_STARTING,
                    egress.EgressStatus.EGRESS_ACTIVE,
                    egress.EgressStatus.EGRESS_ENDING
                ]:
                    active_recordings.append(egress_info)
            
            return active_recordings
            
        except Exception as e:
            logger.error(f"Failed to list active recordings: {e}")
            return []
    
    async def close(self):
        """Close the LiveKit client connection."""
        await self.livekit_client.close()

# Global recording service instance
recording_service = RecordingService()
