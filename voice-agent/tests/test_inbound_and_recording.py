"""
Unit tests for inbound number lookup using telephony_phone_numbers + telephony_configurations,
URL parameter encoding, tenant isolation, and recording metadata persistence.
"""

import unittest
from unittest.mock import patch, AsyncMock, MagicMock
import json


class TestInboundLookupAndRecording(unittest.IsolatedAsyncioTestCase):

    @patch("api.modules.phone_numbers.routes.database")
    @patch("api.modules.phone_numbers.routes.phone_sync_service")
    async def test_inbound_lookup_uses_telephony_tables_and_not_legacy(self, mock_sync, mock_db):
        """Test 1 - Verify lookup queries telephony_phone_numbers + telephony_configurations and NOT phone_numbers."""
        from api.modules.phone_numbers.routes import lookup_number
        
        mock_sync.get_cached_lookup.return_value = None
        mock_db.query = AsyncMock(side_effect=[
            # 1. telephony_phone_numbers + telephony_configurations JOIN
            [{
                "phone_number_id": "pn-123",
                "address": "+6498736772",
                "is_active": True,
                "agent_id": "agent-123",
                "telephony_configuration_id": "config-123",
                "client_id": "client-123",
                "provider": "twilio"
            }],
            # 2. client minutes_balance
            [{"minutes_balance": 100}],
            # 3. agents details
            [{
                "id": "agent-123",
                "name": "Test Support Agent",
                "status": "active",
                "call_type": "inbound",
                "activity_description": "You are a support agent.",
                "use_case": "Customer Support"
            }]
        ])
        
        result = await lookup_number("+6498736772")
        
        # Verify query executed against telephony_phone_numbers
        first_call_sql = mock_db.query.call_args_list[0][0][0]
        self.assertIn("telephony_phone_numbers", first_call_sql)
        self.assertIn("telephony_configurations", first_call_sql)
        self.assertNotIn("FROM phone_numbers", first_call_sql)
        
        # Verify correct result structure
        self.assertTrue(result["exists"])
        self.assertTrue(result["has_credits"])
        self.assertEqual(result["agent_id"], "agent-123")
        self.assertEqual(result["client_id"], "client-123")
        self.assertEqual(result["telephony_configuration_id"], "config-123")
        self.assertEqual(result["provider"], "twilio")

    @patch("api.modules.phone_numbers.routes.database")
    @patch("api.modules.phone_numbers.routes.phone_sync_service")
    async def test_inbound_lookup_unknown_number_returns_404(self, mock_sync, mock_db):
        """Test 2 - Verify lookup for unknown number returns 404 PHONE_NUMBER_NOT_FOUND."""
        from api.modules.phone_numbers.routes import lookup_number
        from fastapi import HTTPException
        
        mock_sync.get_cached_lookup.return_value = None
        mock_db.query = AsyncMock(return_value=[])
        
        with self.assertRaises(HTTPException) as ctx:
            await lookup_number("+19999999999")
            
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["error"], "PHONE_NUMBER_NOT_FOUND")

    @patch("api.modules.phone_numbers.routes.database")
    @patch("api.modules.phone_numbers.routes.phone_sync_service")
    async def test_tenant_isolation_derived_from_telephony_configuration(self, mock_sync, mock_db):
        """Test 3 - Verify tenant client_id is derived from telephony_configurations relationship."""
        from api.modules.phone_numbers.routes import lookup_number
        
        mock_sync.get_cached_lookup.return_value = None
        mock_db.query = AsyncMock(side_effect=[
            [{
                "phone_number_id": "pn-456",
                "address": "+6498736772",
                "is_active": True,
                "agent_id": "agent-tenant-2",
                "telephony_configuration_id": "config-tenant-2",
                "client_id": "tenant-client-uuid-999",
                "provider": "twilio"
            }],
            [{"minutes_balance": 50}],
            [{
                "id": "agent-tenant-2",
                "name": "Tenant 2 Agent",
                "status": "active",
                "call_type": "inbound",
                "activity_description": "Tenant 2 instructions",
                "use_case": "Tenant 2 Use Case"
            }]
        ])
        
        res = await lookup_number("+6498736772")
        self.assertEqual(res["client_id"], "tenant-client-uuid-999")
        self.assertEqual(res["telephony_configuration_id"], "config-tenant-2")

    @patch("api.modules.conversations.services.database")
    async def test_conversation_registration_by_agent_id_creates_recording(self, mock_db):
        """Test 4 - Verify ConversationsService.register_call resolves agent by agentId and inserts recording row."""
        from api.modules.conversations.services import ConversationsService
        
        service = ConversationsService()
        
        mock_conn = AsyncMock()
        mock_db.transaction.side_effect = lambda cb: cb(mock_conn)
        
        # Mock agent repository lookup by ID
        service.agent_repository.find_by_id = AsyncMock(return_value={
            "id": "agent-uuid-777",
            "name": "Agent 777",
            "user_id": "user-777",
            "client_id": "client-777"
        })
        
        # Mock conversation repository create
        service.conversation_repository.create = AsyncMock(return_value={
            "id": "conv-uuid-101",
            "agent_id": "agent-uuid-777"
        })
        
        # Mock recording repository create
        service.recording_repository.create = AsyncMock(return_value={
            "id": "rec-uuid-202",
            "conversation_id": "conv-uuid-101",
            "filename": "room1_rec.mp4",
            "duration": 45,
            "size": 720000,
            "s3_key": "recordings/room1_rec.mp4",
            "created_at": "2026-09-18T15:00:00Z"
        })
        
        # Mock transcript repository create
        service.transcript_repository.create = AsyncMock(return_value={})
        
        payload = {
            "agentId": "agent-uuid-777",
            "agentName": "Agent 777",
            "customerName": "Test Customer",
            "duration": 45,
            "recording": {
                "filename": "room1_rec.mp4",
                "duration": 45,
                "size": 720000,
                "s3_key": "recordings/room1_rec.mp4"
            }
        }
        
        result = await service.register_call(payload)
        
        # Verify agent was looked up by ID
        service.agent_repository.find_by_id.assert_called_with("agent-uuid-777", client=mock_conn)
        
        # Verify recording row creation was called
        service.recording_repository.create.assert_called_once()
        rec_arg = service.recording_repository.create.call_args[0][0]
        self.assertEqual(rec_arg["conversationId"], "conv-uuid-101")
        self.assertEqual(rec_arg["filename"], "room1_rec.mp4")
        self.assertEqual(rec_arg["s3_key"], "recordings/room1_rec.mp4")


if __name__ == "__main__":
    unittest.main()
