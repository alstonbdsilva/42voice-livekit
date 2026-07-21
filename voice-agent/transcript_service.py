"""
Transcript service for voice agent.
Handles real-time transcription and storage to S3.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError
from config import get_settings

logger = logging.getLogger(__name__)

class TranscriptService:
    """Service for managing voice call transcripts and S3 storage."""
    
    def __init__(self):
        self.settings = get_settings()
        self.s3_client = None
        self.sessions = {}
    
    def _get_s3_client(self):
        """Get or create S3 client lazily."""
        if self.s3_client is None:
            endpoint_url = f"https://s3.{self.settings.aws_region}.amazonaws.com" if self.settings.aws_region else None
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                region_name=self.settings.aws_region,
                endpoint_url=endpoint_url
            )
        return self.s3_client
        
    def create_transcript_session(self, room_name: str, participant_id: str) -> str:
        """
        Create a new transcript session.
        
        Args:
            room_name: LiveKit room name
            participant_id: Unique participant identifier
            
        Returns:
            Session ID for the transcript
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"{room_name}_{participant_id}_{timestamp}"
        
        # Initialize transcript data
        self.sessions[session_id] = []
        
        logger.info(f"Created transcript session: {session_id}")
        return session_id
    
    def add_transcript_entry(self, session_id: str, speaker: str, text: str, 
                           timestamp: Optional[str] = None, confidence: Optional[float] = None):
        """
        Add a transcript entry to the session.
        
        Args:
            session_id: Transcript session ID
            speaker: Who spoke (user/agent)
            text: What was said
            timestamp: Optional timestamp (auto-generated if not provided)
            confidence: Optional speech recognition confidence score
        """
        if not timestamp:
            timestamp = datetime.utcnow().isoformat()
            
        entry = {
            "timestamp": timestamp,
            "speaker": speaker,
            "text": text,
            "confidence": confidence
        }
        
        if session_id in self.sessions:
            self.sessions[session_id].append(entry)
            
        logger.info(f"Transcript entry added to {session_id}: {speaker}: {text}")
        return entry
    
    def finalize_transcript(self, session_id: str, summary: Optional[str] = None,
                          recording_url: Optional[str] = None) -> dict:
        """
        Finalize and prepare transcript for storage.
        
        Args:
            session_id: Transcript session ID
            summary: Optional conversation summary
            recording_url: Optional URL to the recording
            
        Returns:
            Complete transcript data ready for storage
        """
        entries = self.sessions.get(session_id, [])
        full_text = "\n".join([f"{e['speaker'].upper()}: {e['text']}" for e in entries])
        
        transcript_data = {
            "session_id": session_id,
            "end_time": datetime.utcnow().isoformat(),
            "summary": summary,
            "recording_url": recording_url,
            "processed_at": datetime.utcnow().isoformat(),
            "lines": entries,
            "full_text": full_text
        }
        
        # Clean up session in-memory state
        if session_id in self.sessions:
            del self.sessions[session_id]
            
        return transcript_data
    
    async def save_transcript_to_s3(self, session_id: str, transcript_data: Dict) -> bool:
        """
        Save transcript to S3.
        
        Args:
            session_id: Transcript session ID
            transcript_data: Complete transcript data
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate S3 key
            timestamp = datetime.now().strftime("%Y%m%d")
            s3_key = f"transcripts/{timestamp}/{session_id}.json"
            
            # Convert to JSON
            json_data = json.dumps(transcript_data, indent=2, default=str)
            
            # Upload to S3
            s3_client = self._get_s3_client()
            s3_client.put_object(
                Bucket=self.settings.s3_bucket_name,
                Key=s3_key,
                Body=json_data,
                ContentType='application/json',
                Metadata={
                    'session_id': session_id,
                    'room_name': transcript_data.get('room_name', ''),
                    'participant_id': transcript_data.get('participant_id', '')
                }
            )
            
            logger.info(f"Transcript saved to S3: {s3_key}")
            
            # Generate S3 URL
            s3_url = f"s3://{self.settings.s3_bucket_name}/{s3_key}"
            transcript_data['s3_url'] = s3_url
            
            return True
            
        except ClientError as e:
            logger.error(f"Failed to save transcript to S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving transcript: {e}")
            return False
    
    async def get_transcript_from_s3(self, session_id: str, date: Optional[str] = None) -> Optional[Dict]:
        """
        Retrieve transcript from S3.
        
        Args:
            session_id: Transcript session ID
            date: Optional date (YYYYMMDD format)
            
        Returns:
            Transcript data if found, None otherwise
        """
        try:
            if not date:
                date = datetime.now().strftime("%Y%m%d")
                
            s3_key = f"transcripts/{date}/{session_id}.json"
            
            s3_client = self._get_s3_client()
            response = s3_client.get_object(
                Bucket=self.settings.s3_bucket_name,
                Key=s3_key
            )
            
            json_data = response['Body'].read().decode('utf-8')
            transcript_data = json.loads(json_data)
            
            logger.info(f"Retrieved transcript from S3: {s3_key}")
            return transcript_data
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                logger.warning(f"Transcript not found: {session_id}")
            else:
                logger.error(f"Failed to retrieve transcript from S3: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving transcript: {e}")
            return None
    
    async def list_transcripts(self, date: Optional[str] = None) -> List[str]:
        """
        List available transcripts.
        
        Args:
            date: Optional date to filter (YYYYMMDD format)
            
        Returns:
            List of transcript session IDs
        """
        try:
            prefix = "transcripts/"
            if date:
                prefix += f"{date}/"
                
            s3_client = self._get_s3_client()
            response = s3_client.list_objects_v2(
                Bucket=self.settings.s3_bucket_name,
                Prefix=prefix
            )
            
            transcripts = []
            for obj in response.get('Contents', []):
                key = obj['Key']
                if key.endswith('.json'):
                    # Extract session ID from key
                    session_id = key.split('/')[-1].replace('.json', '')
                    transcripts.append(session_id)
            
            logger.info(f"Found {len(transcripts)} transcripts")
            return transcripts
            
        except Exception as e:
            logger.error(f"Failed to list transcripts: {e}")
            return []

# Global transcript service instance
transcript_service = TranscriptService()
