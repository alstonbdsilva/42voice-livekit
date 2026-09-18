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
        
        IMPORTANT: Agent must already exist in the database.
        Agents are created explicitly through the Agents API, not implicitly during call registration.
        This maintains data integrity and ensures proper agent configuration.
        """
        async def trans_cb(conn):
            # 1. Resolve agent by explicit agentId/agent_id first, then by name
            agent_id = dto.get("agentId") or dto.get("agent_id")
            agent = None
            if agent_id:
                agent = await self.agent_repository.find_by_id(agent_id, client=conn)
            if not agent:
                agent_name = (dto.get("agentName") or "Voice Agent").strip()
                agent = await self.agent_repository.find_by_name(agent_name, client=conn)
            if not agent and (dto.get("clientId") or dto.get("client_id")):
                c_id = dto.get("clientId") or dto.get("client_id")
                c_rows = await database.query("SELECT * FROM agents WHERE client_id = $1::uuid LIMIT 1", [c_id], client=conn)
                if c_rows:
                    agent = c_rows[0]

            if not agent:
                agent_name = (dto.get("agentName") or "Voice Agent").strip()
                logger.error(f"Agent '{agent_name}' (ID: {agent_id}) not found in database. Cannot register call without explicit agent. "
                           f"Client: {dto.get('clientId')}, User: {dto.get('userId')}")
                raise ValueError(f"Agent '{agent_name}' does not exist. Agents must be created explicitly before calls can be registered.")
                
            # 2. Create the conversation record
            conv_data = {
                "agentId": agent["id"],
                "customerName": dto.get("customerName") or "Customer",
                "customerContact": dto.get("customerContact"),
                "channel": dto.get("channel") or "voice",
                "duration": dto.get("duration") or 0,
                "cost": dto.get("cost") or 0.0,
                "sentiment": dto.get("sentiment") or "neutral",
                "outcome": dto.get("outcome") or "resolved",
                "summary": dto.get("summary"),
                "intent": dto.get("intent"),
                "leadScore": dto.get("leadScore", 0),
                "sentimentScore": dto.get("sentimentScore", 0.00),
                "humanHandoff": dto.get("humanHandoff", False),
                "escalationReason": dto.get("escalationReason"),
                "userId": dto.get("userId") or agent.get("user_id"),
                "clientId": dto.get("clientId") or agent.get("client_id")
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
            
            outcome = dto.get("outcome", "resolved")
            is_success = outcome in ["resolved", "lead_captured", "booked_appointment"]
            is_escalated = dto.get("humanHandoff", False) or outcome == "escalated_to_human"
            
            await self.agent_repository.increment_stats(
                agent["id"],
                {
                    "callCount": 1,
                    "messageCount": message_count,
                    "durationMinutes": duration_minutes,
                    "cost": float(dto.get("cost", 0.0)),
                    "is_success": is_success,
                    "is_escalated": is_escalated
                },
                client=conn
            )
            
            # 6. Deduct minutes from Client / Reseller balance
            resolved_client_id = dto.get("clientId") or agent.get("client_id")
            if resolved_client_id:
                await conn.execute(
                    "UPDATE clients SET minutes_balance = GREATEST(minutes_balance - $1, 0) WHERE id = $2",
                    duration_minutes, resolved_client_id
                )
                logger.info(f"Deducted {duration_minutes} minutes from Client {resolved_client_id} balance.")
            else:
                user_id = dto.get("userId") or agent.get("user_id")
                if user_id:
                    reseller_rows = await conn.fetch("SELECT reseller_id FROM users WHERE id = $1", user_id)
                    if reseller_rows and reseller_rows[0]["reseller_id"]:
                        res_id = reseller_rows[0]["reseller_id"]
                        await conn.execute(
                            "UPDATE resellers SET minutes_balance = GREATEST(minutes_balance - $1, 0) WHERE id = $2",
                            duration_minutes, res_id
                        )
                        logger.info(f"Deducted {duration_minutes} minutes from Reseller {res_id} balance.")
            
            # Retrieve complete conversation for payload formatting
            full_conv = await self.conversation_repository.find_by_id(conv["id"], client=conn)
            return full_conv or conv
            
        result = await database.transaction(trans_cb)
        return self.map_to_response(result)

    def map_to_response(self, c: Dict[str, Any]) -> Dict[str, Any]:
        """Convert snake_case column maps to camelCase payload properties for React DataTable bindings."""
        if not c:
            return {}
        started_at = c.get("started_at") or c.get("created_at")
        started_at_str = (
            started_at.isoformat()
            if (started_at is not None and hasattr(started_at, "isoformat"))
            else (str(started_at) if started_at else "")
        )
        return {
            "id": str(c.get("id", "")),
            "agentId": str(c.get("agent_id", "")),
            "agentName": c.get("agent_name") or "AI Orchestrator",
            "customerName": c.get("customer_name") or c.get("customer_contact") or "Unknown Customer",
            "customerContact": c.get("customer_contact") or "",
            "summary": c.get("summary") or "",
            "channel": c.get("channel") or "voice",
            "outcome": c.get("outcome") or "resolved",
            "startedAt": started_at_str,
            "cost": float(c.get("cost") or 0.0),
            "sentiment": c.get("sentiment") or "neutral",
            "duration": int(c.get("duration") or c.get("duration_seconds") or 0),
            "intent": c.get("intent") or "",
            "leadScore": int(c.get("lead_score") or 0),
            "sentimentScore": float(c.get("sentiment_score") or 0.0),
            "humanHandoff": bool(c.get("human_handoff", False)),
            "escalationReason": c.get("escalation_reason") or "",
            "transcript": c.get("transcript") or [],
            "status": c.get("status") or "completed",
            "metrics": {
                "durationSeconds": c.get("duration_seconds") or c.get("duration") or 0,
                "sentimentScore": float(c.get("sentiment_score") or 0.0),
                "cost": float(c.get("cost") or 0.0),
            },
            "createdAt": started_at_str,
        }
