"""
Recording service for LiveKit egress with S3 upload support.
Handles room recording and uploading to AWS S3.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional
from livekit import api
from livekit.protocol import egress, room
from config import get_settings

logger = logging.getLogger(__name__)


class RecordingService:
    """Service for managing LiveKit room recordings and S3 uploads."""
    
    def __init__(self):
        self.settings = get_settings()
        self._client_cache = None
        
    def _get_client(self):
        """Get or create LiveKit API client. Creates fresh client for each call."""
        # Validate LiveKit configuration
        if not self.settings.livekit_url:
            raise ValueError("LIVEKIT_URL not configured")
        if not self.settings.livekit_api_key:
            raise ValueError("LIVEKIT_API_KEY not configured")
        if not self.settings.livekit_api_secret:
            raise ValueError("LIVEKIT_API_SECRET not configured")
        
        # Always create a fresh client to avoid connection reuse issues
        # in self-hosted deployments with multiple consecutive calls
        return api.LiveKitAPI(
            self.settings.livekit_url,
            self.settings.livekit_api_key,
            self.settings.livekit_api_secret
        )
        
    async def start_room_recording(self, room_name: str, max_retries: int = 3, timeout_sec: int = 30):
        """
        Start recording a room to S3 with exponential backoff retry.
        For self-hosted LiveKit, includes timeout to handle egress service delays.
        
        Args:
            room_name: Name of the room to record
            max_retries: Maximum number of retry attempts (default 3)
            timeout_sec: Timeout per attempt in seconds (default 30s for self-hosted)
            
        Returns:
            Tuple of (Egress ID if successful else None, filename)
        """
        # Validate room name
        if not room_name or not isinstance(room_name, str) or not room_name.strip():
            logger.error(f"Invalid room_name for recording: {room_name}")
            return None, ""
        
        room_name = room_name.strip()
        
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{room_name}_{timestamp}.mp4"
        
        # Validate S3 configuration
        if not self.settings.s3_bucket_name or not self.settings.aws_access_key_id or not self.settings.aws_secret_access_key:
            logger.error("S3 configuration incomplete: missing bucket name or AWS credentials")
            return None, filename
        
        # Verify room exists before attempting to record (only on first attempt)
        try:
            client = self._get_client()
            try:
                logger.debug(f"Verifying room exists: {room_name}")
                room_info = await asyncio.wait_for(
                    client.room.list_rooms(room.ListRoomsRequest()),
                    timeout=10.0
                )
                logger.debug(f"Available rooms: {[r.name for r in room_info.rooms]}")
                room_exists = any(r.name == room_name for r in room_info.rooms)
                if not room_exists:
                    logger.error(f"Room does not exist: {room_name}. Available rooms: {[r.name for r in room_info.rooms]}")
                    return None, filename
                logger.debug(f"Room verified: {room_name}")
            finally:
                await client.aclose()
        except Exception as e:
            logger.warning(f"Could not verify room existence: {e}, proceeding with recording attempt")
        
        for attempt in range(max_retries):
            try:
                s3_key = f"{self.settings.s3_bucket_path}{filename}"
                
                # Configure S3 upload
                s3_upload = egress.S3Upload(
                    access_key=self.settings.aws_access_key_id,
                    secret=self.settings.aws_secret_access_key,
                    region=self.settings.aws_region,
                    bucket=self.settings.s3_bucket_name
                )
                
                # Configure file output
                file_output = egress.EncodedFileOutput(
                    file_type=egress.EncodedFileType.MP4,
                    filepath=s3_key,
                    s3=s3_upload
                )
                
                # Start room composite egress
                request = egress.RoomCompositeEgressRequest(
                    room_name=room_name,
                    file=file_output,
                    layout="grid"  # Use grid layout for all participants
                )
                
                logger.info(f"Starting recording (attempt {attempt + 1}/{max_retries}): {room_name}")
                logger.debug(f"Recording request details: room_name={room_name}, s3_key={s3_key}, layout=grid")
                logger.debug(f"S3 bucket={self.settings.s3_bucket_name}, region={self.settings.aws_region}")
                logger.debug(f"LiveKit URL={self.settings.livekit_url}, API key={self.settings.livekit_api_key[:10]}...")
                
                client = self._get_client()
                logger.debug(f"LiveKit API client created: {client}")
                
                try:
                    # Add timeout for self-hosted egress service responsiveness
                    try:
                        logger.debug(f"Calling start_room_composite_egress with timeout {timeout_sec}s")
                        egress_info = await asyncio.wait_for(
                            client.egress.start_room_composite_egress(request),
                            timeout=timeout_sec
                        )
                        logger.info(f"Recording started: egress_id={egress_info.egress_id}, room={room_name}")
                        return egress_info.egress_id, filename
                    except asyncio.TimeoutError as te:
                        logger.error(f"Egress service timeout after {timeout_sec}s: {te}")
                        raise TimeoutError(f"Egress service timeout after {timeout_sec}s")
                    except Exception as inner_err:
                        logger.error(f"Error calling start_room_composite_egress: {inner_err}", exc_info=True)
                        raise
                finally:
                    # Always close the client to prevent unclosed session warnings
                    try:
                        logger.debug("Closing LiveKit API client")
                        await client.aclose()
                        logger.debug("LiveKit API client closed successfully")
                    except Exception as close_err:
                        logger.debug(f"Error closing LiveKit client: {close_err}")
                
            except Exception as e:
                logger.error(f"Exception in recording attempt {attempt + 1}/{max_retries}: {type(e).__name__}: {e}", exc_info=True)
                error_str = str(e).lower()
                
                # Check if this is a 503 error (retryable)
                is_503_error = '503' in error_str or 'unavailable' in error_str
                
                # Fail fast on configuration/auth errors (don't retry)
                is_config_error = (
                    isinstance(e, ValueError) or  # Configuration errors
                    any(x in error_str for x in [
                        'authentication', 'unauthorized', 'forbidden', 'invalid', 
                        'credentials', 'access denied', 'permission denied', 'not found',
                        'not configured'
                    ])
                )
                
                # 503 errors are retryable
                if is_503_error:
                    logger.warning(f"Egress service unavailable (503), will retry: {e}")
                
                if is_config_error:
                    logger.error(
                        f"Recording start failed (configuration error, not retrying): {e}",
                        exc_info=True
                    )
                    return None, filename
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Recording start failed (attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Recording start failed after {max_retries} attempts: {e}",
                        exc_info=True
                    )
                    return None, filename
    
    async def stop_recording(self, egress_id: str, timeout_sec: int = 10) -> bool:
        """
        Stop a recording by egress ID.
        Idempotent - safe to call multiple times.
        
        Args:
            egress_id: ID of the egress to stop
            timeout_sec: Timeout for stop operation (default 10s)
            
        Returns:
            True if successful, False otherwise
        """
        if not egress_id:
            logger.warning("Cannot stop recording: egress_id is None")
            return False
            
        try:
            logger.info(f"Stopping recording: egress_id={egress_id}")
            client = self._get_client()
            
            try:
                # Add timeout for self-hosted egress service
                try:
                    await asyncio.wait_for(
                        client.egress.stop_egress(egress.StopEgressRequest(egress_id=egress_id)),
                        timeout=timeout_sec
                    )
                    logger.info(f"Recording stopped: egress_id={egress_id}")
                    return True
                except asyncio.TimeoutError:
                    logger.warning(f"Stop recording timeout after {timeout_sec}s: egress_id={egress_id}")
                    return False
            finally:
                # Always close the client
                try:
                    await client.aclose()
                except Exception as close_err:
                    logger.debug(f"Error closing LiveKit client: {close_err}")
            
        except Exception as e:
            # Idempotent: if egress already stopped or doesn't exist, still return success
            error_str = str(e).lower()
            if any(x in error_str for x in ['not found', 'does not exist', 'no egress']):
                logger.info(f"Egress already stopped or not found: egress_id={egress_id}")
                return True
            
            logger.error(f"Failed to stop recording: egress_id={egress_id}, error={e}", exc_info=True)
            return False
    
    async def get_recording_status(self, egress_id: str):
        """
        Get the status of a recording.
        
        Args:
            egress_id: ID of the egress to check
            
        Returns:
            EgressInfo if found, None otherwise
        """
        try:
            client = self._get_client()
            response = await client.egress.list_egress(egress.ListEgressRequest(egress_id=egress_id))
            for egress_info in response.items:
                if egress_info.egress_id == egress_id:
                    return egress_info
            return None
            
        except Exception as e:
            logger.error(f"Failed to get recording status for {egress_id}: {e}")
            return None
    
    async def list_active_recordings(self):
        """
        List all active recordings.
        
        Returns:
            List of active egress recordings
        """
        try:
            client = self._get_client()
            response = await client.egress.list_egress(egress.ListEgressRequest())
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
    
    async def cleanup_orphaned_egress(self, room_name: str):
        """
        Clean up any orphaned egress sessions for a room.
        Useful for recovery after unexpected disconnects.
        
        Args:
            room_name: Name of the room to clean up
            
        Returns:
            Number of egress sessions cleaned up
        """
        cleaned_count = 0
        try:
            client = self._get_client()
            response = await client.egress.list_egress(egress.ListEgressRequest())
            
            for egress_info in response.items:
                # Check if this egress is for our room and is still active
                if (hasattr(egress_info, 'room_name') and 
                    egress_info.room_name == room_name and
                    egress_info.status in [
                        egress.EgressStatus.EGRESS_STARTING,
                        egress.EgressStatus.EGRESS_ACTIVE,
                        egress.EgressStatus.EGRESS_ENDING
                    ]):
                    try:
                        await self.stop_recording(egress_info.egress_id)
                        cleaned_count += 1
                        logger.info(f"Cleaned up orphaned egress: {egress_info.egress_id}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up egress {egress_info.egress_id}: {e}")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned egress for room {room_name}: {e}")
            return 0
    
    async def verify_s3_upload(self, s3_key: str, max_retries: int = 5, retry_delay: float = 2.0) -> bool:
        """
        Verify that a recording has been uploaded to S3.
        Retries with exponential backoff to account for egress upload delay.
        
        Args:
            s3_key: S3 key of the recording file
            max_retries: Maximum number of verification attempts
            retry_delay: Initial delay between retries in seconds
            
        Returns:
            True if file exists in S3, False otherwise
        """
        import boto3
        
        try:
            endpoint_url = f"https://s3.{self.settings.aws_region}.amazonaws.com" if self.settings.aws_region else None
            s3_client = boto3.client(
                's3',
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                region_name=self.settings.aws_region,
                endpoint_url=endpoint_url
            )
            
            for attempt in range(max_retries):
                try:
                    # Use asyncio.to_thread to avoid blocking event loop
                    exists = await asyncio.to_thread(
                        lambda: s3_client.head_object(
                            Bucket=self.settings.s3_bucket_name,
                            Key=s3_key
                        )
                    )
                    logger.info(f"S3 upload verified: {s3_key}")
                    return True
                except s3_client.exceptions.NoSuchKey:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        logger.info(f"S3 file not yet available, retrying in {wait_time}s: {s3_key}")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"S3 upload verification failed after {max_retries} attempts: {s3_key}")
                        return False
                except Exception as e:
                    logger.error(f"S3 verification error: {e}")
                    return False
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to verify S3 upload: {e}", exc_info=True)
            return False
    
    async def close(self):
        """No-op, connections are handled via async context manager on demand."""
        pass

# Global recording service instance
recording_service = RecordingService()
