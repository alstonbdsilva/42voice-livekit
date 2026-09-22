"""
Agents Database Repository.
Queries agent configuration details and logs operational statistics.
"""

import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal
import json
from api import database

logger = logging.getLogger("voice-agent.api.agents.repositories")


class AgentRepository:
    select_query_base = """
        SELECT a.id, a.name, a.type, a.call_type, a.use_case, a.activity_description, a.channels, a.status,
                a.total_calls, a.total_messages, a.total_minutes, a.success_rate, a.escalation_rate,
                a.prompt_version, a.kb_version, a.total_cost, a.last_activity, a.user_id, a.client_id, a.created_at, a.updated_at,
                a.voice_name, a.voice_gender, a.tts_provider, a.tts_model, a.tts_voice_id, a.tts_voice_name,
                a.guardrails, a.custom_guardrails, a.knowledge_items, a.tool_ids,
                COALESCE(
                  (SELECT json_agg(json_build_object('id', r.id, 'name', r.name))
                   FROM agent_resellers ar JOIN resellers r ON ar.reseller_id = r.id
                   WHERE ar.agent_id = a.id), '[]'::json
                ) AS assigned_resellers,
                COALESCE(
                  (SELECT json_agg(json_build_object('id', c.id, 'name', c.name))
                   FROM agent_clients ac JOIN clients c ON ac.client_id = c.id
                   WHERE ac.agent_id = a.id), '[]'::json
                ) AS assigned_clients
        FROM agents a
    """

    async def find_all(self, filter_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch all agents based on role and organization context."""
        role = filter_data.get("role")
        user_id = filter_data.get("userId")
        client_id = filter_data.get("clientId")
        reseller_id = filter_data.get("resellerId")
        
        if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
            return await database.query(
                f"{self.select_query_base} ORDER BY a.name ASC"
            )
            
        if role == "RESELLER" and reseller_id:
            return await database.query(
                f"""{self.select_query_base}
                   WHERE a.id IN (SELECT agent_id FROM agent_resellers WHERE reseller_id = $1)
                      OR a.id IN (SELECT agent_id FROM agent_clients WHERE client_id IN (SELECT id FROM clients WHERE reseller_id = $1))
                      OR a.client_id IN (SELECT id FROM clients WHERE reseller_id = $1) 
                      OR a.user_id = $2 
                   ORDER BY a.name ASC""",
                [reseller_id, user_id]
            )
            
        if client_id:
            return await database.query(
                f"""{self.select_query_base}
                   WHERE a.id IN (SELECT agent_id FROM agent_clients WHERE client_id = $1)
                      OR a.client_id = $1 
                      OR a.user_id = $2 
                   ORDER BY a.name ASC""",
                [client_id, user_id]
            )
            
        return await database.query(
            f"{self.select_query_base} WHERE a.user_id = $1 ORDER BY a.name ASC",
            [user_id]
        )

    async def find_by_id(self, agent_id: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Find an agent by ID with its assignments."""
        rows = await database.query(
            f"{self.select_query_base} WHERE a.id = $1",
            [agent_id],
            client=client
        )
        return rows[0] if rows else None

    async def find_by_name(self, name: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Find a single agent by name (case-insensitive)."""
        rows = await database.query(
            f"{self.select_query_base} WHERE LOWER(a.name) = LOWER($1)",
            [name.strip()],
            client=client
        )
        return rows[0] if rows else None

    async def update_status(self, agent_id: str, status: str) -> Optional[Dict[str, Any]]:
        """Update agent status field."""
        await database.query(
            """UPDATE agents 
               SET status = $1, updated_at = CURRENT_TIMESTAMP 
               WHERE id = $2""",
            [status, agent_id]
        )
        return await self.find_by_id(agent_id)

    async def create(self, data: Dict[str, Any], client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Create a new agent record and associate multi-reseller/client assignments."""
        status = data.get("status", "active")
        channels = data.get("channels", ["voice"])
        call_type = data.get("callType", "inbound")
        use_case = data.get("useCase", "")
        activity_description = data.get("activityDescription", "")
        agent_type = data.get("type", "Inbound Voice" if call_type == "inbound" else "Outbound Voice")
        user_id = data.get("userId")
        client_id = data.get("clientId")
        reseller_ids = data.get("resellerIds", [])
        client_ids = data.get("clientIds", [])
        
        voice_name = data.get("voiceName", "aria")
        voice_gender = data.get("voiceGender", "female")
        tts_provider = data.get("ttsProvider")
        tts_model = data.get("ttsModel")
        tts_voice_id = data.get("ttsVoiceId")
        tts_voice_name = data.get("ttsVoiceName") or voice_name
        guardrails = data.get("guardrails", {})
        custom_guardrails = data.get("customGuardrails", "")
        knowledge_items = data.get("knowledgeItems", [])
        tool_ids = data.get("toolIds", [])
        
        rows = await database.query(
            """INSERT INTO agents (name, type, call_type, use_case, activity_description, channels, status, user_id, client_id,
                                   voice_name, voice_gender, tts_provider, tts_model, tts_voice_id, tts_voice_name,
                                   guardrails, custom_guardrails, knowledge_items, tool_ids)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
               RETURNING id""",
            [
                data["name"].strip(),
                agent_type,
                call_type,
                use_case,
                activity_description,
                channels,
                status,
                user_id,
                client_id,
                voice_name,
                voice_gender,
                tts_provider,
                tts_model,
                tts_voice_id,
                tts_voice_name,
                json.dumps(guardrails),
                custom_guardrails,
                json.dumps(knowledge_items),
                json.dumps(tool_ids)
            ],
            client=client
        )
        agent_id = rows[0]["id"]

        # Insert reseller assignments
        for rid in reseller_ids:
            await database.query(
                "INSERT INTO agent_resellers (agent_id, reseller_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                [agent_id, rid],
                client=client
            )

        # Insert client assignments
        for cid in client_ids:
            await database.query(
                "INSERT INTO agent_clients (agent_id, client_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                [agent_id, cid],
                client=client
            )

        agent = await self.find_by_id(agent_id, client=client)
        if not agent:
            agent = {
                "id": agent_id,
                "name": data["name"].strip(),
                "type": agent_type,
                "call_type": call_type,
                "use_case": use_case,
                "activity_description": activity_description,
                "channels": channels,
                "status": status,
                "total_calls": 0,
                "total_messages": 0,
                "total_minutes": 0,
                "success_rate": Decimal("0.00"),
                "escalation_rate": Decimal("0.00"),
                "prompt_version": 1,
                "kb_version": 1,
                "total_cost": Decimal("0.0000"),
                "user_id": user_id,
                "client_id": client_id,
                "assigned_resellers": reseller_ids,
                "assigned_clients": client_ids,
                "voice_name": voice_name,
                "voice_gender": voice_gender,
                "tts_provider": tts_provider,
                "tts_model": tts_model,
                "tts_voice_id": tts_voice_id,
                "tts_voice_name": tts_voice_name,
                "guardrails": guardrails,
                "custom_guardrails": custom_guardrails,
                "knowledge_items": knowledge_items
            }
        return agent

    async def update_assignments(self, agent_id: str, reseller_ids: Optional[List[str]] = None, client_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Update reseller and client assignments for an agent."""
        if reseller_ids is not None:
            await database.query("DELETE FROM agent_resellers WHERE agent_id = $1", [agent_id])
            for rid in reseller_ids:
                await database.query(
                    "INSERT INTO agent_resellers (agent_id, reseller_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    [agent_id, rid]
                )
        if client_ids is not None:
            await database.query("DELETE FROM agent_clients WHERE agent_id = $1", [agent_id])
            for cid in client_ids:
                await database.query(
                    "INSERT INTO agent_clients (agent_id, client_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    [agent_id, cid]
                )
        return await self.find_by_id(agent_id)

    async def clone_agent(self, agent_id: str, reseller_ids: Optional[List[str]] = None, client_ids: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """Clone an existing agent configuration into a new independent agent record for a reseller or client."""
        original = await self.find_by_id(agent_id)
        if not original:
            return None
        
        clone_data = {
            "name": original["name"],
            "type": original["type"],
            "callType": original["call_type"],
            "useCase": original.get("use_case", ""),
            "activityDescription": original.get("activity_description", ""),
            "channels": original.get("channels", ["voice"]),
            "status": "active",
            "userId": original.get("user_id"),
            "resellerIds": reseller_ids or [],
            "clientIds": client_ids or [],
            "voiceName": original.get("voice_name") or "aria",
            "voiceGender": original.get("voice_gender") or "female",
            "ttsProvider": original.get("tts_provider"),
            "ttsModel": original.get("tts_model"),
            "ttsVoiceId": original.get("tts_voice_id"),
            "ttsVoiceName": original.get("tts_voice_name"),
            "guardrails": original.get("guardrails") or {},
            "customGuardrails": original.get("custom_guardrails") or "",
            "knowledgeItems": original.get("knowledge_items") or [],
            "toolIds": original.get("tool_ids") or []
        }
        return await self.create(clone_data)

    async def update_details(self, agent_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update configurable agent details (name, use_case, activity_description, voice, tts, guardrails)."""
        fields = []
        params = []
        param_idx = 1
        
        if "name" in data and data["name"] is not None:
            fields.append(f"name = ${param_idx}")
            params.append(data["name"].strip())
            param_idx += 1
            
        if "useCase" in data and data["useCase"] is not None:
            fields.append(f"use_case = ${param_idx}")
            params.append(data["useCase"].strip())
            param_idx += 1

        if "activityDescription" in data and data["activityDescription"] is not None:
            fields.append(f"activity_description = ${param_idx}")
            params.append(data["activityDescription"].strip())
            param_idx += 1

        if "callType" in data and data["callType"] is not None:
            fields.append(f"call_type = ${param_idx}")
            params.append(data["callType"])
            param_idx += 1

        if "voiceName" in data and data["voiceName"] is not None:
            fields.append(f"voice_name = ${param_idx}")
            params.append(data["voiceName"])
            param_idx += 1

        if "voiceGender" in data and data["voiceGender"] is not None:
            fields.append(f"voice_gender = ${param_idx}")
            params.append(data["voiceGender"])
            param_idx += 1

        if "ttsProvider" in data and data["ttsProvider"] is not None:
            fields.append(f"tts_provider = ${param_idx}")
            params.append(data["ttsProvider"])
            param_idx += 1

        if "ttsModel" in data and data["ttsModel"] is not None:
            fields.append(f"tts_model = ${param_idx}")
            params.append(data["ttsModel"])
            param_idx += 1

        if "ttsVoiceId" in data and data["ttsVoiceId"] is not None:
            fields.append(f"tts_voice_id = ${param_idx}")
            params.append(data["ttsVoiceId"])
            param_idx += 1

        if "ttsVoiceName" in data and data["ttsVoiceName"] is not None:
            fields.append(f"tts_voice_name = ${param_idx}")
            params.append(data["ttsVoiceName"])
            param_idx += 1

        if "guardrails" in data and data["guardrails"] is not None:
            fields.append(f"guardrails = ${param_idx}")
            params.append(json.dumps(data["guardrails"]))
            param_idx += 1

        if "customGuardrails" in data and data["customGuardrails"] is not None:
            fields.append(f"custom_guardrails = ${param_idx}")
            params.append(data["customGuardrails"])
            param_idx += 1

        if "knowledgeItems" in data and data["knowledgeItems"] is not None:
            fields.append(f"knowledge_items = ${param_idx}")
            params.append(json.dumps(data["knowledgeItems"]))
            param_idx += 1

        if "toolIds" in data and data["toolIds"] is not None:
            fields.append(f"tool_ids = ${param_idx}")
            params.append(json.dumps(data["toolIds"]))
            param_idx += 1
            
        if not fields:
            return await self.find_by_id(agent_id)

        fields.append(f"updated_at = CURRENT_TIMESTAMP")
        params.append(agent_id)
        
        query = f"UPDATE agents SET {', '.join(fields)} WHERE id = ${param_idx}"
        await database.query(query, params)
        return await self.find_by_id(agent_id)

    async def increment_stats(self, agent_id: Any, stats: Dict[str, Any], client: Optional[Any] = None) -> None:
        """Increment call and message metrics for an agent atomically without prior SELECT."""
        calls_inc = int(stats.get("callCount", 0))
        messages_inc = int(stats.get("messageCount", 0))
        minutes_inc = int(stats.get("durationMinutes", 0))
        cost_inc = Decimal(str(stats.get("cost", 0.0)))
        success_inc = 1 if (calls_inc > 0 and stats.get("is_success")) else 0
        escalation_inc = 1 if (calls_inc > 0 and stats.get("is_escalated")) else 0

        query = """
            UPDATE agents
            SET total_calls = COALESCE(total_calls, 0) + $1,
                total_messages = COALESCE(total_messages, 0) + $2,
                total_minutes = COALESCE(total_minutes, 0) + $3,
                total_cost = COALESCE(total_cost, 0) + $4,
                success_rate = CASE
                    WHEN (COALESCE(total_calls, 0) + $1) > 0 THEN
                        ROUND(
                            ((ROUND((COALESCE(success_rate, 0.00) / 100.0) * COALESCE(total_calls, 0)) + $5) /
                             (COALESCE(total_calls, 0) + $1)::numeric) * 100.0,
                            2
                        )
                    ELSE 0.00
                END,
                escalation_rate = CASE
                    WHEN (COALESCE(total_calls, 0) + $1) > 0 THEN
                        ROUND(
                            ((ROUND((COALESCE(escalation_rate, 0.00) / 100.0) * COALESCE(total_calls, 0)) + $6) /
                             (COALESCE(total_calls, 0) + $1)::numeric) * 100.0,
                            2
                        )
                    ELSE 0.00
                END,
                last_activity = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $7
        """
        await database.query(
            query,
            [
                calls_inc,
                messages_inc,
                minutes_inc,
                cost_inc,
                success_inc,
                escalation_inc,
                agent_id
            ],
            client=client
        )
