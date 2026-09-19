"""
Workflows database repository.
Handles persistence for workflows, immutable workflow_versions, workflow_runs, and events.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from api import database

logger = logging.getLogger("voice-agent.api.workflows.repositories")


class WorkflowRepository:
    """Repository handling database operations for workflows, versioning, and runs."""

    select_workflow_base = """
        SELECT w.id, w.client_id, w.user_id, w.name, w.description, w.status, w.created_at, w.updated_at,
               (SELECT wv.id FROM workflow_versions wv 
                WHERE wv.workflow_id = w.id AND wv.lifecycle_status = 'published' 
                ORDER BY wv.version_number DESC LIMIT 1) AS latest_published_version_id,
               (SELECT wv.version_number FROM workflow_versions wv 
                WHERE wv.workflow_id = w.id AND wv.lifecycle_status = 'published' 
                ORDER BY wv.version_number DESC LIMIT 1) AS latest_published_version_number
        FROM workflows w
    """

    select_version_base = """
        SELECT wv.id, wv.workflow_id, wv.version_number, wv.lifecycle_status, wv.definition,
               wv.ui_metadata, wv.schema_version, wv.engine_version, wv.validation_metadata,
               wv.created_at, wv.published_at, wv.created_by
        FROM workflow_versions wv
    """

    select_run_base = """
        SELECT wr.id, wr.run_id, wr.workflow_id, wr.workflow_version_id, wr.agent_id, wr.client_id,
               wr.room_name, wr.status, wr.started_at, wr.completed_at, wr.error_category,
               wr.conversation_id, wr.recording_id, wr.safe_metadata, wr.created_at
        FROM workflow_runs wr
    """

    async def create_workflow(self, data: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Create a new logical workflow and bootstrap its initial draft version."""
        async def _tx(conn):
            # 1. Insert workflow container
            q_wf = """
                INSERT INTO workflows (client_id, user_id, name, description, status)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id, client_id, user_id, name, description, status, created_at, updated_at
            """
            rows = await conn.fetch(
                q_wf,
                data.get("clientId") or data.get("client_id"),
                data.get("userId") or data.get("user_id"),
                data["name"],
                data.get("description"),
                data.get("status", "active")
            )
            wf_row = dict(rows[0])
            wf_id = wf_row["id"]

            # 2. Insert initial draft version (version_number = 0 or initial draft marker)
            initial_def = {
                "version": 1,
                "workflow_id": str(wf_id),
                "name": data["name"],
                "start_node": "start_node",
                "global_prompt": "",
                "variables": {},
                "nodes": {
                    "start_node": {
                        "id": "start_node",
                        "name": "Start",
                        "type": "START",
                        "prompt": "",
                        "tools": [],
                        "config": {"next_node": "agent_node"}
                    },
                    "agent_node": {
                        "id": "agent_node",
                        "name": "Main Agent",
                        "type": "AGENT",
                        "prompt": "You are a helpful voice assistant.",
                        "tools": ["end_call"],
                        "config": {}
                    },
                    "end_node": {
                        "id": "end_node",
                        "name": "End Call",
                        "type": "END",
                        "prompt": "Thank you for calling. Goodbye!",
                        "tools": ["end_call"],
                        "config": {}
                    }
                },
                "edges": [
                    {
                        "id": "edge_start_to_agent",
                        "source": "start_node",
                        "target": "agent_node",
                        "type": "default",
                        "description": "Proceed to agent"
                    },
                    {
                        "id": "edge_agent_to_end",
                        "source": "agent_node",
                        "target": "end_node",
                        "type": "tool",
                        "description": "End the call upon completion"
                    }
                ]
            }

            q_ver = """
                INSERT INTO workflow_versions (
                    workflow_id, version_number, lifecycle_status, definition, ui_metadata,
                    schema_version, engine_version, created_by
                )
                VALUES ($1, $2, 'draft', $3::jsonb, $4::jsonb, '1.0', '1.0', $5)
                RETURNING id
            """
            await conn.fetch(
                q_ver,
                wf_id,
                0,  # version 0 represents editable draft
                json.dumps(initial_def),
                json.dumps({}),
                data.get("userId") or data.get("user_id")
            )
            return wf_row

        if client is not None:
            return await _tx(client)
        return await database.transaction(_tx)

    async def find_all(self, filter_data: Dict[str, Any], client: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Fetch all workflows matching tenant/role permissions."""
        role = filter_data.get("role")
        user_id = filter_data.get("userId") or filter_data.get("user_id")
        client_id = filter_data.get("clientId") or filter_data.get("client_id")
        reseller_id = filter_data.get("resellerId") or filter_data.get("reseller_id")

        if role in ["SUPER_ADMIN", "FINANCE_ADMIN"]:
            return await database.query(
                f"{self.select_workflow_base} WHERE w.status != 'archived' ORDER BY w.created_at DESC",
                client=client
            )

        if role == "RESELLER" and reseller_id:
            return await database.query(
                f"""{self.select_workflow_base}
                    WHERE w.status != 'archived'
                      AND (w.client_id IN (SELECT id FROM clients WHERE reseller_id = $1)
                           OR w.user_id = $2)
                    ORDER BY w.created_at DESC""",
                [reseller_id, user_id],
                client=client
            )

        if client_id:
            return await database.query(
                f"""{self.select_workflow_base}
                    WHERE w.status != 'archived'
                      AND (w.client_id = $1 OR w.user_id = $2)
                    ORDER BY w.created_at DESC""",
                [client_id, user_id],
                client=client
            )

        return await database.query(
            f"{self.select_workflow_base} WHERE w.status != 'archived' AND w.user_id = $1 ORDER BY w.created_at DESC",
            [user_id],
            client=client
        )

    async def find_by_id(self, workflow_id: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Fetch single workflow by ID."""
        rows = await database.query(
            f"{self.select_workflow_base} WHERE w.id = $1",
            [workflow_id],
            client=client
        )
        return rows[0] if rows else None

    async def update_workflow(self, workflow_id: str, data: Dict[str, Any], client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Update top-level metadata of a workflow container."""
        fields = []
        params = [workflow_id]
        idx = 2

        if "name" in data and data["name"] is not None:
            fields.append(f"name = ${idx}")
            params.append(data["name"])
            idx += 1

        if "description" in data:
            fields.append(f"description = ${idx}")
            params.append(data["description"])
            idx += 1

        if "status" in data and data["status"] is not None:
            fields.append(f"status = ${idx}")
            params.append(data["status"])
            idx += 1

        if not fields:
            return await self.find_by_id(workflow_id, client=client)

        fields.append("updated_at = CURRENT_TIMESTAMP")
        q = f"""
            UPDATE workflows
            SET {', '.join(fields)}
            WHERE id = $1
            RETURNING id
        """
        rows = await database.query(q, params, client=client)
        if not rows:
            return None
        return await self.find_by_id(workflow_id, client=client)

    async def get_or_create_draft(self, workflow_id: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Get the active editable draft version for a workflow."""
        rows = await database.query(
            f"{self.select_version_base} WHERE wv.workflow_id = $1 AND wv.lifecycle_status = 'draft' LIMIT 1",
            [workflow_id],
            client=client
        )
        if rows:
            return rows[0]

        # If no draft exists, create one cloned from latest published version or empty
        latest_pub = await self.get_latest_published_version(workflow_id, client=client)
        definition = latest_pub.get("definition") if latest_pub else {"nodes": [], "edges": []}
        ui_metadata = latest_pub.get("ui_metadata") if latest_pub else {}

        q = """
            INSERT INTO workflow_versions (
                workflow_id, version_number, lifecycle_status, definition, ui_metadata, schema_version, engine_version
            )
            VALUES ($1, 0, 'draft', $2::jsonb, $3::jsonb, '1.0', '1.0')
            RETURNING *
        """
        new_rows = await database.query(
            q,
            [workflow_id, json.dumps(definition), json.dumps(ui_metadata)],
            client=client
        )
        return new_rows[0] if new_rows else None

    async def update_draft(
        self,
        workflow_id: str,
        definition: Dict[str, Any],
        ui_metadata: Optional[Dict[str, Any]] = None,
        validation_metadata: Optional[Dict[str, Any]] = None,
        client: Optional[Any] = None
    ) -> Optional[Dict[str, Any]]:
        """Update mutable draft definition and UI metadata."""
        draft = await self.get_or_create_draft(workflow_id, client=client)
        if not draft:
            return None

        q = """
            UPDATE workflow_versions
            SET definition = $2::jsonb,
                ui_metadata = COALESCE($3::jsonb, ui_metadata),
                validation_metadata = COALESCE($4::jsonb, validation_metadata),
                created_at = CURRENT_TIMESTAMP
            WHERE id = $1 AND lifecycle_status = 'draft'
            RETURNING *
        """
        rows = await database.query(
            q,
            [
                draft["id"],
                json.dumps(definition),
                json.dumps(ui_metadata) if ui_metadata is not None else None,
                json.dumps(validation_metadata) if validation_metadata is not None else None
            ],
            client=client
        )
        return rows[0] if rows else None

    async def get_latest_published_version(self, workflow_id: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Fetch the highest version_number published version."""
        rows = await database.query(
            f"""{self.select_version_base}
                WHERE wv.workflow_id = $1 AND wv.lifecycle_status = 'published'
                ORDER BY wv.version_number DESC
                LIMIT 1""",
            [workflow_id],
            client=client
        )
        return rows[0] if rows else None

    async def find_version_by_id(self, version_id: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Fetch a specific workflow version by ID."""
        rows = await database.query(
            f"{self.select_version_base} WHERE wv.id = $1",
            [version_id],
            client=client
        )
        return rows[0] if rows else None

    async def list_versions(self, workflow_id: str, client: Optional[Any] = None) -> List[Dict[str, Any]]:
        """List all published versions for a workflow in descending version order."""
        return await database.query(
            f"""{self.select_version_base}
                WHERE wv.workflow_id = $1 AND wv.lifecycle_status = 'published'
                ORDER BY wv.version_number DESC""",
            [workflow_id],
            client=client
        )

    async def publish_version(
        self,
        workflow_id: str,
        definition: Dict[str, Any],
        ui_metadata: Optional[Dict[str, Any]] = None,
        validation_metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish an immutable workflow version with strict concurrency locking on the parent workflow.
        
        Locking Protocol:
        1. BEGIN transaction
        2. Lock parent workflow row: SELECT id FROM workflows WHERE id = $1 FOR UPDATE
        3. Compute next version: SELECT COALESCE(MAX(version_number), 0) + 1 FROM workflow_versions WHERE workflow_id = $1 AND lifecycle_status = 'published'
        4. Insert immutable published version snapshot
        5. Update workflow.updated_at
        6. COMMIT
        """
        async def _publish_tx(conn):
            # 1. Lock the parent workflow row first
            lock_q = "SELECT id FROM workflows WHERE id = $1 FOR UPDATE"
            lock_res = await conn.fetch(lock_q, workflow_id)
            if not lock_res:
                raise ValueError(f"Workflow '{workflow_id}' not found for publication.")

            # 2. Compute next sequential version number inside the locked transaction
            next_ver_q = """
                SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version
                FROM workflow_versions
                WHERE workflow_id = $1 AND lifecycle_status = 'published'
            """
            ver_res = await conn.fetch(next_ver_q, workflow_id)
            next_version = ver_res[0]["next_version"]

            # 3. Insert immutable published version
            pub_q = """
                INSERT INTO workflow_versions (
                    workflow_id, version_number, lifecycle_status, definition, ui_metadata,
                    schema_version, engine_version, validation_metadata, published_at, created_by
                )
                VALUES ($1, $2, 'published', $3::jsonb, $4::jsonb, '1.0', '1.0', $5::jsonb, CURRENT_TIMESTAMP, $6)
                RETURNING *
            """
            pub_res = await conn.fetch(
                pub_q,
                workflow_id,
                next_version,
                json.dumps(definition),
                json.dumps(ui_metadata or {}),
                json.dumps(validation_metadata or {}),
                user_id
            )
            pub_row = dict(pub_res[0])

            # 4. Touch parent workflow updated_at
            await conn.execute("UPDATE workflows SET updated_at = CURRENT_TIMESTAMP WHERE id = $1", workflow_id)

            logger.info(f"[WF_PUBLISH] workflow_id={workflow_id} version={next_version} version_id={pub_row['id']}")
            return pub_row

        return await database.transaction(_publish_tx)

    # --- Workflow Runs & Events Persistence ---

    async def create_workflow_run(self, run_data: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Insert a first-class workflow run record."""
        q = """
            INSERT INTO workflow_runs (
                run_id, workflow_id, workflow_version_id, agent_id, client_id,
                room_name, status, error_category, conversation_id, recording_id, safe_metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb)
            ON CONFLICT (run_id) DO UPDATE SET
                status = EXCLUDED.status,
                workflow_version_id = COALESCE(EXCLUDED.workflow_version_id, workflow_runs.workflow_version_id)
            RETURNING *
        """
        rows = await database.query(
            q,
            [
                run_data["run_id"],
                run_data.get("workflow_id"),
                run_data.get("workflow_version_id"),
                run_data.get("agent_id"),
                run_data.get("client_id"),
                run_data.get("room_name"),
                run_data.get("status", "running"),
                run_data.get("error_category"),
                run_data.get("conversation_id"),
                run_data.get("recording_id"),
                json.dumps(run_data.get("safe_metadata", {}))
            ],
            client=client
        )
        return rows[0] if rows else {}

    async def update_workflow_run(self, run_id: str, update_data: Dict[str, Any], client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Update workflow run status, completion time, error category, or correlation IDs."""
        fields = []
        params = [run_id]
        idx = 2

        if "status" in update_data and update_data["status"] is not None:
            fields.append(f"status = ${idx}")
            params.append(update_data["status"])
            idx += 1

        if "error_category" in update_data:
            fields.append(f"error_category = ${idx}")
            params.append(update_data["error_category"])
            idx += 1

        if "conversation_id" in update_data and update_data["conversation_id"] is not None:
            fields.append(f"conversation_id = ${idx}")
            params.append(update_data["conversation_id"])
            idx += 1

        if "recording_id" in update_data and update_data["recording_id"] is not None:
            fields.append(f"recording_id = ${idx}")
            params.append(update_data["recording_id"])
            idx += 1

        if "completed_at" in update_data and update_data["completed_at"] is not None:
            fields.append(f"completed_at = ${idx}")
            params.append(update_data["completed_at"])
            idx += 1
        elif update_data.get("status") in ["completed", "failed", "aborted"]:
            fields.append("completed_at = CURRENT_TIMESTAMP")

        if not fields:
            return await self.find_run_by_run_id(run_id, client=client)

        q = f"""
            UPDATE workflow_runs
            SET {', '.join(fields)}
            WHERE run_id = $1
            RETURNING *
        """
        rows = await database.query(q, params, client=client)
        return rows[0] if rows else None

    async def find_run_by_run_id(self, run_id: str, client: Optional[Any] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single workflow run by run_id."""
        rows = await database.query(
            f"{self.select_run_base} WHERE wr.run_id = $1",
            [run_id],
            client=client
        )
        return rows[0] if rows else None

    async def append_run_event(self, event_data: Dict[str, Any], client: Optional[Any] = None) -> Dict[str, Any]:
        """Append an event to workflow_run_events with idempotent sequence handling."""
        q = """
            INSERT INTO workflow_run_events (
                run_id, sequence_number, event_type, node_id, edge_id, safe_metadata
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            ON CONFLICT (run_id, sequence_number) DO NOTHING
            RETURNING *
        """
        rows = await database.query(
            q,
            [
                event_data["run_id"],
                event_data["sequence_number"],
                event_data["event_type"],
                event_data.get("node_id"),
                event_data.get("edge_id"),
                json.dumps(event_data.get("safe_metadata", {}))
            ],
            client=client
        )
        return rows[0] if rows else {}
