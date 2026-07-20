"""
Conversations Service.
Manages call session registrations, agent statistics updates, and associated logs in database transactions.
"""

import math
import logging
from typing import Dict, Any, List, Optional
from api import database
from api.modules.conversations.repositories import ConversationRepository
from api.modules.agents.repositories import AgentRepository
from api.modules.recordings.repositories import RecordingRepository
from api.modules.transcripts.repositories import TranscriptRepository

logger = logging.getLogger("voice-agent.api.conversations.services")


class ConversationsService:
    def __init__(self):
        self.conversation_repository = ConversationRepository()
        self.agent_repository = AgentRepository()
        self.recording_repository = RecordingRepository()
        self.transcript_repository = TranscriptRepository()

    async def get_all_conversations(self, agent_id: Optional[str] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all conversation records."""
        convs = await self.conversation_repository.find_all(agent_id=agent_id, limit=limit)
        return [self.map_to_response(c) for c in convs]

    async def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Fetch conversation by ID."""
        conv = await self.conversation_repository.find_by_id(conversation_id)
        if not conv:
            return None
        return self.map_to_response(conv)

    async def register_call(self, dto: Dict[str, Any]) -> Dict[str, Any]:
        """
        Register a new call session, recording, and transcript.
        Executes inside a database transaction block and dynamically increments agent stats.
        """
        async def trans_cb(conn):
            # 1. Resolve agent by name (case-insensitive)
            agent_name = dto["agentName"]
            agent = await self.agent_repository.find_by_name(agent_name)
            
            if not agent:
                # Create a new agent dynamically if not found
                agent = await self.agent_repository.create({
                    "name": agent_name,
                    "type": dto.get("intent") or "general",
                    "channels": [dto["channel"]],
                    "status": "active",
                    "userId": dto.get("userId"),
                    "clientId": dto.get("clientId")
                })
                
            # 2. Create the conversation record
            conv_data = {
                "agentId": agent["id"],
                "customerName": dto["customerName"],
                "customerContact": dto.get("customerContact"),
                "channel": dto["channel"],
                "duration": dto["duration"],
                "cost": dto["cost"],
                "sentiment": dto["sentiment"],
                "outcome": dto["outcome"],
                "summary": dto.get("summary"),
                "intent": dto.get("intent"),
                "leadScore": dto.get("leadScore", 0),
                "sentimentScore": dto.get("sentimentScore", 0.00),
                "humanHandoff": dto.get("humanHandoff", False),
                "escalationReason": dto.get("escalationReason"),
                "userId": dto.get("userId") or agent["user_id"],
                "clientId": dto.get("clientId") or agent["client_id"]
            }
            conv = await self.conversation_repository.create(conv_data, client=conn)
            
            # 3. Create the recording log if provided
            if dto.get("recording"):
                rec_dto = dto["recording"]
                await self.recording_repository.create({
                    "conversationId": conv["id"],
                    "filename": rec_dto["filename"],
                    "duration": rec_dto["duration"],
                    "size": rec_dto["size"],
                    "s3_key": rec_dto["s3_key"]
                }, client=conn)
                
            # 4. Create the transcript log if provided
            if dto.get("transcript"):
                trans_dto = dto["transcript"]
                await self.transcript_repository.create({
                    "conversationId": conv["id"],
                    "fullText": trans_dto["fullText"],
                    "lines": trans_dto["lines"],
                    "actionItems": trans_dto["actionItems"]
                }, client=conn)
                
            # 5. Update agent stats in database
            duration_minutes = math.ceil(dto["duration"] / 60)
            message_count = len(dto["transcript"]["lines"]) if dto.get("transcript") else 0
            
            outcome = dto["outcome"]
            is_success = outcome in ["resolved", "lead_captured", "booked_appointment"]
            is_escalated = dto.get("humanHandoff", False) or outcome == "escalated_to_human"
            
            await self.agent_repository.increment_stats(
                agent["id"],
                {
                    "callCount": 1,
                    "messageCount": message_count,
                    "durationMinutes": duration_minutes,
                    "cost": float(dto["cost"]),
                    "is_success": is_success,
                    "is_escalated": is_escalated
                }
            )
            
            # Retrieve complete conversation for payload formatting
            full_conv = await self.conversation_repository.find_by_id(conv["id"], client=conn)
            return full_conv
            
        result = await database.transaction(trans_cb)
        return self.map_to_response(result)

    def map_to_response(self, c: Dict[str, Any]) -> Dict[str, Any]:
        """Convert snake_case column maps to camelCase payload properties."""
        return {
            "id": str(c["id"]),
            "agentId": str(c["agent_id"]),
            "agentName": c.get("agent_name") or "AI Orchestrator",
            "customerName": c["customer_name"],
            "customerContact": c["customer_contact"] or "",
            "summary": c["summary"] or "",
            "channel": c["channel"],
            "outcome": c["outcome"],
            "startedAt": c["started_at"].isoformat() if hasattr(c["started_at"], "isoformat") else c["started_at"],
            "cost": float(c["cost"]),
            "sentiment": c["sentiment"],
            "duration": c["duration"],
            "intent": c["intent"] or "",
            "leadScore": c["lead_score"],
            "sentimentScore": float(c["sentiment_score"]),
            "humanHandoff": c["human_handoff"],
            "escalationReason": c["escalation_reason"] or ""
        }
