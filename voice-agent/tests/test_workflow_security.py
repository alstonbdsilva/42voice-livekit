"""
Unit tests for Workflow tenant isolation and tool security.
"""

import json
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from api.modules.workflows.services import WorkflowService
from api.modules.agents.services import AgentService
from api.utils.errors import ForbiddenError, NotFoundError, BadRequestError


class TestWorkflowSecurity(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.wf_service = WorkflowService()
        self.agent_service = AgentService()

        self.client_a_context = {
            "id": str(uuid.uuid4()),
            "client_id": str(uuid.uuid4()),
            "reseller_id": None,
            "role": "CLIENT"
        }
        self.client_b_context = {
            "id": str(uuid.uuid4()),
            "client_id": str(uuid.uuid4()),
            "reseller_id": None,
            "role": "CLIENT"
        }

    @patch("api.database.query")
    async def test_01_client_a_cannot_read_client_b_workflow(self, mock_query):
        """Verify cross-tenant access to GET /workflows/{id} is rejected with ForbiddenError."""
        b_wf_id = str(uuid.uuid4())
        mock_b_wf = {
            "id": uuid.UUID(b_wf_id),
            "client_id": uuid.UUID(self.client_b_context["client_id"]),
            "user_id": uuid.UUID(self.client_b_context["id"]),
            "name": "Client B Secret Workflow",
            "status": "active",
            "created_at": MagicMock(),
            "updated_at": MagicMock()
        }
        mock_query.return_value = [mock_b_wf]

        with self.assertRaises(ForbiddenError):
            await self.wf_service.get_workflow_by_id(b_wf_id, self.client_a_context)

    @patch("api.database.query")
    async def test_02_client_a_cannot_update_client_b_draft(self, mock_query):
        """Verify cross-tenant PUT /workflows/{id}/draft is rejected with ForbiddenError."""
        b_wf_id = str(uuid.uuid4())
        mock_b_wf = {
            "id": uuid.UUID(b_wf_id),
            "client_id": uuid.UUID(self.client_b_context["client_id"]),
            "user_id": uuid.UUID(self.client_b_context["id"]),
            "name": "Client B Secret Workflow",
            "status": "active"
        }
        mock_query.return_value = [mock_b_wf]

        with self.assertRaises(ForbiddenError):
            await self.wf_service.update_draft(b_wf_id, {"definition": {}}, self.client_a_context)

    @patch("api.database.query")
    async def test_03_client_a_cannot_publish_client_b_workflow(self, mock_query):
        """Verify cross-tenant POST /workflows/{id}/publish is rejected with ForbiddenError."""
        b_wf_id = str(uuid.uuid4())
        mock_b_wf = {
            "id": uuid.UUID(b_wf_id),
            "client_id": uuid.UUID(self.client_b_context["client_id"]),
            "user_id": uuid.UUID(self.client_b_context["id"]),
            "name": "Client B Workflow",
            "status": "active"
        }
        mock_query.return_value = [mock_b_wf]

        with self.assertRaises(ForbiddenError):
            await self.wf_service.publish_workflow(b_wf_id, self.client_a_context)

    @patch("api.database.query")
    async def test_04_client_a_cannot_assign_client_b_published_version(self, mock_query):
        """Verify AgentService rejects assigning a workflow version belonging to a different tenant."""
        b_wf_id = uuid.uuid4()
        b_version_id = str(uuid.uuid4())
        a_agent_id = str(uuid.uuid4())

        mock_version_row = {
            "id": uuid.UUID(b_version_id),
            "workflow_id": b_wf_id,
            "version_number": 1,
            "lifecycle_status": "published",
            "definition": "{}"
        }
        mock_parent_wf = {
            "id": b_wf_id,
            "client_id": uuid.UUID(self.client_b_context["client_id"]),
            "user_id": uuid.UUID(self.client_b_context["id"]),
            "name": "Client B Workflow"
        }

        mock_query.side_effect = [
            [mock_version_row], # find_version_by_id
            [mock_parent_wf]    # find parent workflow by id
        ]

        with self.assertRaises(ForbiddenError):
            await self.agent_service.update_agent_details(
                a_agent_id,
                {"publishedWorkflowVersionId": b_version_id},
                user_context=self.client_a_context
            )

    @patch("api.database.query")
    async def test_05_cannot_assign_draft_version_to_agent(self, mock_query):
        """Verify AgentService rejects assigning a draft workflow version."""
        draft_version_id = str(uuid.uuid4())
        a_agent_id = str(uuid.uuid4())

        mock_version_row = {
            "id": uuid.UUID(draft_version_id),
            "workflow_id": uuid.uuid4(),
            "version_number": 0,
            "lifecycle_status": "draft",
            "definition": "{}"
        }
        mock_query.return_value = [mock_version_row]

        with self.assertRaises(BadRequestError):
            await self.agent_service.update_agent_details(
                a_agent_id,
                {"publishedWorkflowVersionId": draft_version_id},
                user_context=self.client_a_context
            )


if __name__ == "__main__":
    unittest.main()
