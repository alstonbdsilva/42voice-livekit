"""
Workflows entity models and data mapping structures.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime


def map_workflow_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Format raw database workflow record for public API consumption."""
    if not row:
        return {}
    return {
        "id": str(row["id"]),
        "clientId": str(row["client_id"]) if row.get("client_id") else None,
        "userId": str(row["user_id"]) if row.get("user_id") else None,
        "name": row.get("name"),
        "description": row.get("description"),
        "status": row.get("status", "active"),
        "createdAt": row["created_at"].isoformat() if isinstance(row.get("created_at"), datetime) else row.get("created_at"),
        "updatedAt": row["updated_at"].isoformat() if isinstance(row.get("updated_at"), datetime) else row.get("updated_at"),
        "latestPublishedVersionId": str(row["latest_published_version_id"]) if row.get("latest_published_version_id") else None,
        "latestPublishedVersionNumber": row.get("latest_published_version_number")
    }


def map_workflow_version_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Format raw database workflow version record for public API consumption."""
    if not row:
        return {}
    import json
    definition = row.get("definition")
    if isinstance(definition, str):
        try:
            definition = json.loads(definition)
        except Exception:
            definition = {"nodes": [], "edges": []}

    ui_metadata = row.get("ui_metadata")
    if isinstance(ui_metadata, str):
        try:
            ui_metadata = json.loads(ui_metadata)
        except Exception:
            ui_metadata = {}

    validation_metadata = row.get("validation_metadata")
    if isinstance(validation_metadata, str):
        try:
            validation_metadata = json.loads(validation_metadata)
        except Exception:
            validation_metadata = {}

    return {
        "id": str(row["id"]),
        "workflowId": str(row["workflow_id"]),
        "versionNumber": row.get("version_number"),
        "lifecycleStatus": row.get("lifecycle_status", "draft"),
        "definition": definition or {"nodes": [], "edges": []},
        "uiMetadata": ui_metadata or {},
        "schemaVersion": row.get("schema_version", "1.0"),
        "engineVersion": row.get("engine_version", "1.0"),
        "validationMetadata": validation_metadata or {},
        "createdAt": row["created_at"].isoformat() if isinstance(row.get("created_at"), datetime) else row.get("created_at"),
        "publishedAt": row["published_at"].isoformat() if isinstance(row.get("published_at"), datetime) else row.get("published_at"),
        "createdBy": str(row["created_by"]) if row.get("created_by") else None
    }


def map_workflow_run_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Format raw database workflow run record for public API consumption."""
    if not row:
        return {}
    import json
    safe_metadata = row.get("safe_metadata")
    if isinstance(safe_metadata, str):
        try:
            safe_metadata = json.loads(safe_metadata)
        except Exception:
            safe_metadata = {}

    return {
        "id": str(row["id"]),
        "runId": row.get("run_id"),
        "workflowId": str(row["workflow_id"]) if row.get("workflow_id") else None,
        "workflowVersionId": str(row["workflow_version_id"]) if row.get("workflow_version_id") else None,
        "agentId": str(row["agent_id"]) if row.get("agent_id") else None,
        "clientId": str(row["client_id"]) if row.get("client_id") else None,
        "roomName": row.get("room_name"),
        "status": row.get("status", "running"),
        "startedAt": row["started_at"].isoformat() if isinstance(row.get("started_at"), datetime) else row.get("started_at"),
        "completedAt": row["completed_at"].isoformat() if isinstance(row.get("completed_at"), datetime) else row.get("completed_at"),
        "errorCategory": row.get("error_category"),
        "conversationId": str(row["conversation_id"]) if row.get("conversation_id") else None,
        "recordingId": str(row["recording_id"]) if row.get("recording_id") else None,
        "safeMetadata": safe_metadata or {}
    }
