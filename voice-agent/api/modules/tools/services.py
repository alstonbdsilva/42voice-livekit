"""
Tools Service.
Business logic for creating/updating reusable tools, executing HTTP API
tool test requests, and best-effort MCP tool discovery.
"""

import base64
import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from api.modules.tools.repositories import ToolRepository
from api.utils.errors import BadRequestError, NotFoundError

logger = logging.getLogger("voice-agent.api.tools.services")

VALID_CATEGORIES = {"http_api", "end_call", "transfer_call", "calculator", "mcp"}
VALID_STATUSES = {"active", "draft", "archived"}


def build_auth_header(credential: Dict[str, Any]) -> Dict[str, str]:
    cred_type = credential.get("credential_type")
    cred_data = credential.get("credential_data") or {}
    if isinstance(cred_data, str):
        cred_data = json.loads(cred_data)

    if cred_type == "bearer_token":
        token = cred_data.get("token", "")
        return {"Authorization": f"Bearer {token}"}

    elif cred_type == "api_key":
        header_name = cred_data.get("header_name", "X-API-Key")
        api_key = cred_data.get("api_key", "")
        return {header_name: api_key}

    elif cred_type == "basic_auth":
        username = cred_data.get("username", "")
        password = cred_data.get("password", "")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    elif cred_type == "custom_header":
        header_name = cred_data.get("header_name", "X-Custom")
        header_value = cred_data.get("header_value", "")
        return {header_name: header_value}

    return {}


def _credential_uuids_from_definition(definition: Dict[str, Any]) -> List[str]:
    credential_uuids = []
    config = definition.get("config")
    if isinstance(config, dict):
        credential_uuid = config.get("credential_uuid")
        if isinstance(credential_uuid, str) and credential_uuid:
            credential_uuids.append(credential_uuid)
        resolver = config.get("resolver")
        if isinstance(resolver, dict):
            resolver_credential_uuid = resolver.get("credential_uuid")
            if isinstance(resolver_credential_uuid, str) and resolver_credential_uuid:
                credential_uuids.append(resolver_credential_uuid)
    return list(dict.fromkeys(credential_uuids))


async def validate_tool_credential_references(definition: Dict[str, Any], client_id: str) -> None:
    from api.modules.credentials.repositories import CredentialRepository
    repo = CredentialRepository()
    for credential_uuid in _credential_uuids_from_definition(definition):
        credential = await repo.find_by_uuid(credential_uuid, client_id)
        if not credential:
            raise BadRequestError(
                f"Credential '{credential_uuid}' was not found in this client organization. Create it in the UI first.",
                "CREDENTIAL_NOT_FOUND",
            )


async def populate_discovered_tools(definition: Dict[str, Any], client_id: str) -> Dict[str, Any]:
    if not isinstance(definition, dict) or definition.get("type") != "mcp":
        return definition
    config = definition.get("config", {})
    url = config.get("url")
    if not url:
        return definition

    credential = None
    credential_uuid = config.get("credential_uuid")
    if credential_uuid and client_id:
        from api.modules.credentials.repositories import CredentialRepository
        credential = await CredentialRepository().find_by_uuid(credential_uuid, client_id)

    try:
        discovered, _ = await discover_mcp_tools(url, credential, config)
    except Exception as e:
        logger.warning(f"MCP discovery failed; caching empty list: {e}")
        discovered = []

    config["discovered_tools"] = discovered
    definition["config"] = config
    return definition


class ToolService:
    def __init__(self):
        self.tool_repository = ToolRepository()

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def validate_category(category: str) -> None:
        if category not in VALID_CATEGORIES:
            raise BadRequestError(
                f"Invalid category '{category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}",
                "INVALID_CATEGORY",
            )

    @staticmethod
    def validate_status(status: str) -> None:
        statuses = [s.strip() for s in status.split(",")]
        for s in statuses:
            if s not in VALID_STATUSES:
                raise BadRequestError(
                    f"Invalid status '{s}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}",
                    "INVALID_STATUS",
                )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def list_tools(self, filter_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        tools = await self.tool_repository.find_all(filter_data)
        return [self.map_to_response(t) for t in tools]

    async def get_tool(self, tool_uuid: str, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        tool = await self.tool_repository.find_by_uuid(tool_uuid, filter_data)
        if not tool:
            raise NotFoundError("Tool not found", "TOOL_NOT_FOUND")
        return self.map_to_response(tool)

    async def create_tool(
        self, payload: Dict[str, Any], user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        category = payload.get("category", "http_api")
        self.validate_category(category)

        client_id = user_context.get("client_id")
        definition = payload.get("definition", {})
        if client_id:
            await validate_tool_credential_references(definition, client_id)
            definition = await populate_discovered_tools(definition, client_id)

        created = await self.tool_repository.create(
            {
                "name": payload["name"],
                "description": payload.get("description"),
                "category": category,
                "icon": payload.get("icon"),
                "icon_color": payload.get("icon_color"),
                "status": "active",
                "definition": definition,
                "user_id": user_context.get("id"),
                "client_id": client_id,
            }
        )
        return self.map_to_response(created)

    async def update_tool(
        self, tool_uuid: str, payload: Dict[str, Any], filter_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        if payload.get("status"):
            self.validate_status(payload["status"])

        client_id = filter_data.get("clientId")
        definition = payload.get("definition")
        if definition and client_id:
            await validate_tool_credential_references(definition, client_id)
            definition = await populate_discovered_tools(definition, client_id)
            payload["definition"] = definition

        updated = await self.tool_repository.update(tool_uuid, payload, filter_data)
        if not updated:
            raise NotFoundError("Tool not found", "TOOL_NOT_FOUND")
        return self.map_to_response(updated)

    async def archive_tool(self, tool_uuid: str, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        updated = await self.tool_repository.set_status(tool_uuid, "archived", filter_data)
        if not updated:
            raise NotFoundError("Tool not found", "TOOL_NOT_FOUND")
        return self.map_to_response(updated)

    async def unarchive_tool(self, tool_uuid: str, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        updated = await self.tool_repository.set_status(tool_uuid, "active", filter_data)
        if not updated:
            raise NotFoundError("Tool not found", "TOOL_NOT_FOUND")
        return self.map_to_response(updated)

    # ------------------------------------------------------------------
    # HTTP API tool test execution
    # ------------------------------------------------------------------

    async def test_http_tool(
        self, tool_uuid: str, llm_params: Dict[str, Any], preset_params: Dict[str, Any], filter_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        tool = await self.tool_repository.find_by_uuid(tool_uuid, filter_data)
        if not tool:
            raise NotFoundError("Tool not found", "TOOL_NOT_FOUND")
        if tool["category"] != "http_api":
            raise BadRequestError("Only HTTP API tools can be tested", "NOT_HTTP_API_TOOL")

        definition = tool["definition"]
        if isinstance(definition, str):
            definition = json.loads(definition)
        config = definition.get("config", {}) if isinstance(definition, dict) else {}

        method = (config.get("method") or "GET").upper()
        url = config.get("url", "")
        headers = dict(config.get("headers") or {})

        # Resolve credential
        credential_uuid = config.get("credential_uuid")
        client_id = filter_data.get("clientId")
        if credential_uuid and client_id:
            from api.modules.credentials.repositories import CredentialRepository
            credential = await CredentialRepository().find_by_uuid(credential_uuid, client_id)
            if credential:
                headers.update(build_auth_header(credential))

        resolved_arguments = {**llm_params, **preset_params}

        request_body: Optional[Dict[str, Any]] = None
        request_params: Optional[Dict[str, Any]] = None
        if method in ("POST", "PUT", "PATCH"):
            request_body = resolved_arguments
        elif resolved_arguments:
            request_params = resolved_arguments

        timeout_ms = config.get("timeout_ms", 5000)
        started_at = time.perf_counter()
        status = "success"
        status_code: Optional[int] = None
        data: Any = None
        error: Optional[str] = None

        try:
            async with httpx.AsyncClient(timeout=timeout_ms / 1000) as client:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    json=request_body if request_body is not None else None,
                    params=request_params if request_params is not None else None,
                )
            status_code = response.status_code
            try:
                data = response.json()
            except ValueError:
                data = response.text
            if status_code >= 400:
                status = "error"
        except httpx.TimeoutException:
            status = "error"
            error = "Request timed out"
        except Exception as e:  # noqa: BLE001
            status = "error"
            error = str(e)

        duration_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        hint = self._hint_for_status_code(status_code, method)

        return {
            "status": status,
            "status_code": status_code,
            "data": data,
            "error": error,
            "hint": hint,
            "request_method": method,
            "request_url": url,
            "request_headers": headers,
            "request_body": request_body,
            "request_params": request_params,
            "duration_ms": duration_ms,
        }

    @staticmethod
    def _hint_for_status_code(status_code: Optional[int], method: str) -> Optional[str]:
        if status_code is None:
            return None
        hints = {
            400: "HTTP 400 Bad Request — the server rejected the request payload. Verify the arguments/body match what this endpoint expects.",
            401: "HTTP 401 Unauthorized — the request wasn't authenticated. Check the configured Authentication is present and valid.",
            403: "HTTP 403 Forbidden — authenticated, but the configured credential doesn't have permission for this endpoint/action.",
            404: f"HTTP 404 Not Found — verify the endpoint URL is correct and that {method} is a valid method for it.",
            405: f"HTTP 405 Method Not Allowed — the endpoint rejected the configured method ({method}).",
            408: "HTTP 408 Request Timeout — the endpoint didn't respond in time.",
            409: "HTTP 409 Conflict — the endpoint rejected the request due to a conflicting resource state.",
            415: "HTTP 415 Unsupported Media Type — check the Content-Type header matches the format this endpoint expects.",
            422: "HTTP 422 Unprocessable Entity — the request structure or field types don't match what this endpoint expects.",
            429: "HTTP 429 Too Many Requests — the endpoint is rate-limiting. Wait and retry.",
        }
        if status_code in hints:
            return hints[status_code]
        if 500 <= status_code < 600:
            return f"HTTP {status_code} — the endpoint itself errored. This is likely an issue on the API's side."
        return None

    # ------------------------------------------------------------------
    # MCP discovery (best-effort, no external SDK dependency)
    # ------------------------------------------------------------------

    async def refresh_mcp_tool(self, tool_uuid: str, filter_data: Dict[str, Any]) -> Dict[str, Any]:
        tool = await self.tool_repository.find_by_uuid(tool_uuid, filter_data)
        if not tool:
            raise NotFoundError("Tool not found", "TOOL_NOT_FOUND")
        if tool["category"] != "mcp":
            raise BadRequestError("Tool is not an MCP tool", "NOT_MCP_TOOL")

        definition = tool["definition"]
        if isinstance(definition, str):
            definition = json.loads(definition)
        config = definition.get("config", {}) if isinstance(definition, dict) else {}
        url = config.get("url")

        if not url:
            return {"tool_uuid": tool_uuid, "discovered_tools": [], "error": "MCP server URL is not configured"}

        # Resolve credential
        credential = None
        credential_uuid = config.get("credential_uuid")
        client_id = filter_data.get("clientId")
        if credential_uuid and client_id:
            from api.modules.credentials.repositories import CredentialRepository
            credential = await CredentialRepository().find_by_uuid(credential_uuid, client_id)

        discovered, error = await discover_mcp_tools(url, credential, config)

        if not discovered:
            return {
                "tool_uuid": tool_uuid,
                "discovered_tools": [],
                "error": error or f"Could not reach the MCP server at {url} (or it exposes no tools). Previously cached list retained.",
            }

        new_definition = dict(definition)
        new_config = dict(config)
        new_config["discovered_tools"] = discovered
        new_definition["config"] = new_config
        await self.tool_repository.update(tool_uuid, {"definition": new_definition}, filter_data)

        return {"tool_uuid": tool_uuid, "discovered_tools": discovered, "error": None}

    # ------------------------------------------------------------------
    # Response mapping
    # ------------------------------------------------------------------

    def map_to_response(self, t: Dict[str, Any]) -> Dict[str, Any]:
        definition = t.get("definition")
        if isinstance(definition, str):
            definition = json.loads(definition)

        return {
            "id": str(t["id"]),
            "toolUuid": str(t["tool_uuid"]),
            "name": t["name"],
            "description": t.get("description"),
            "category": t["category"],
            "icon": t.get("icon"),
            "iconColor": t.get("icon_color"),
            "status": t["status"],
            "definition": definition or {},
            "createdAt": t["created_at"].isoformat() if hasattr(t["created_at"], "isoformat") else t["created_at"],
            "updatedAt": t["updated_at"].isoformat() if t.get("updated_at") and hasattr(t["updated_at"], "isoformat") else t.get("updated_at"),
            "createdByEmail": t.get("created_by_email"),
        }


async def discover_mcp_tools(url: str, credential: Optional[Dict[str, Any]], config: Dict[str, Any]) -> tuple[List[Dict[str, Any]], Optional[str]]:
    """Best-effort MCP tool catalog discovery over the Streamable HTTP transport.

    Performs a minimal JSON-RPC initialize -> tools/list handshake. Any
    failure results in an empty list and a human-readable error, never
    raising, so callers can treat discovery as non-blocking.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if credential:
        headers.update(build_auth_header(credential))
    else:
        auth_type = config.get("auth_type", "none")
        if auth_type == "bearer" and config.get("auth_value"):
            headers["Authorization"] = f"Bearer {config['auth_value']}"
        elif auth_type == "api_key" and config.get("auth_value"):
            headers[config.get("auth_header") or "X-API-Key"] = config["auth_value"]

    timeout_secs = config.get("timeout_secs", 10)

    try:
        async with httpx.AsyncClient(timeout=timeout_secs) as client:
            init_resp = await client.post(
                url,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "42voice-tools", "version": "1.0"},
                    },
                },
            )
            session_id = init_resp.headers.get("Mcp-Session-Id")
            request_headers = dict(headers)
            if session_id:
                request_headers["Mcp-Session-Id"] = session_id

            await client.post(
                url,
                headers=request_headers,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )

            list_resp = await client.post(
                url,
                headers=request_headers,
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            )

            payload = _parse_mcp_payload(list_resp)
            tools = (payload or {}).get("result", {}).get("tools", [])
            discovered = [
                {"name": tool.get("name"), "description": tool.get("description", "")}
                for tool in tools
                if isinstance(tool, dict) and tool.get("name")
            ]
            return discovered, None
    except Exception as e:  # noqa: BLE001
        logger.warning(f"MCP discovery failed for {url}: {e}")
        return [], str(e)


def _parse_mcp_payload(response: httpx.Response) -> Optional[Dict[str, Any]]:
    """Parse either a plain JSON body or a text/event-stream SSE body."""
    content_type = response.headers.get("content-type", "")
    if "text/event-stream" in content_type:
        for line in response.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                try:
                    return json.loads(line[len("data:"):].strip())
                except (ValueError, json.JSONDecodeError):
                    continue
        return None
    try:
        return response.json()
    except ValueError:
        return None
