"""Custom tool execution helper for user-defined HTTP API and Transfer Call tools."""

import json
import re
import base64
import logging
import httpx
import uuid
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from api import database
from api.utils.template_renderer import render_template
from api.modules.tools.services import build_auth_header

logger = logging.getLogger("voice-agent.custom_tools")

TYPE_MAP = {
    "string": "string",
    "number": "number",
    "boolean": "boolean",
    "object": "object",
    "array": "array",
}


def serialize_query_params(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-stringify dict/list values so they're safe to pass as query params."""
    return {
        k: json.dumps(v) if isinstance(v, (dict, list)) else v
        for k, v in arguments.items()
    }


def tool_to_function_schema(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a database Tool row to an LLM function schema.

    Args:
        tool: Tool record dict with name, description, and definition

    Returns:
        Function schema dict compatible with OpenAI function calling
    """
    definition = tool.get("definition") or {}
    if isinstance(definition, str):
        definition = json.loads(definition)
    config = definition.get("config", {})
    parameters = config.get("parameters", []) or []

    tool_type = definition.get("type", "http_api")

    if tool_type == "transfer_call" and config.get("destination_source", "static") != "dynamic":
        parameters = []
    elif tool_type == "transfer_call" and config.get("destination_source", "static") == "dynamic":
        resolver = config.get("resolver")
        if isinstance(resolver, dict):
            parameters = resolver.get("parameters", []) or []
        else:
            parameters = []

    # Build properties and required list from parameters
    properties = {}
    required = []

    for param in parameters:
        param_name = param.get("name", "")
        param_type = param.get("type", "string")
        param_desc = param.get("description", "")
        param_required = param.get("required", True)

        if not param_name:
            continue

        schema_type = TYPE_MAP.get(param_type, "string")
        if schema_type == "object":
            properties[param_name] = {
                "type": "object",
                "additionalProperties": True,
                "description": param_desc,
            }
        elif schema_type == "array":
            properties[param_name] = {
                "type": "array",
                "items": {},
                "description": param_desc,
            }
        else:
            properties[param_name] = {
                "type": schema_type,
                "description": param_desc,
            }

        if param_required:
            required.append(param_name)

    # If this is an end_call tool with endCallReason enabled, add a required 'reason' parameter
    if tool_type == "end_call" and config.get("endCallReason", False):
        default_description = (
            "The reason for ending the call (e.g., 'voicemail_detected', "
            "'issue_resolved', 'customer_requested')"
        )
        properties["reason"] = {
            "type": "string",
            "description": config.get("endCallReasonDescription") or default_description,
        }
        required.append("reason")

    # Sanitize tool name for function name (lowercase, underscores only)
    function_name = re.sub(r"[^a-z0-9_]", "_", tool["name"].lower())
    # Remove consecutive underscores and trim
    function_name = re.sub(r"_+", "_", function_name).strip("_")

    return {
        "type": "function",
        "function": {
            "name": function_name,
            "description": tool.get("description") or f"Execute {tool['name']} tool",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
        "_tool_uuid": str(tool["tool_uuid"]),
    }


def _coerce_parameter_value(value: Any, param_type: str) -> Any:
    """Coerce a rendered preset parameter into the configured JSON type."""
    if value is None:
        return None

    if param_type == "string":
        if isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    if param_type == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value

        rendered = str(value).strip()
        if rendered == "":
            return None

        if re.fullmatch(r"[-+]?\d+", rendered):
            return int(rendered)

        return float(rendered)

    if param_type == "boolean":
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return bool(value)

        rendered = str(value).strip().lower()
        if rendered in {"true", "1", "yes", "y", "on"}:
            return True
        if rendered in {"false", "0", "no", "n", "off"}:
            return False

        raise ValueError(f"Cannot convert '{value}' to boolean")

    if param_type == "object":
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Cannot convert '{value}' to object") from exc
        if isinstance(value, dict):
            return value
        raise ValueError(f"Cannot convert '{value}' to object")

    if param_type == "array":
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Cannot convert '{value}' to array") from exc
        if isinstance(value, list):
            return value
        raise ValueError(f"Cannot convert '{value}' to array")

    return value


def _resolve_preset_parameters(
    config: Dict[str, Any],
    call_context_vars: Optional[Dict[str, Any]],
    gathered_context_vars: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Resolve fixed/template-backed parameters before executing the HTTP request."""
    preset_parameters = config.get("preset_parameters", []) or []
    if not preset_parameters:
        return {}

    initial_context = dict(call_context_vars or {})
    render_context: Dict[str, Any] = {
        **initial_context,
        "initial_context": initial_context,
        "gathered_context": dict(gathered_context_vars or {}),
    }

    resolved: Dict[str, Any] = {}
    for param in preset_parameters:
        param_name = (param.get("name") or "").strip()
        if not param_name:
            continue

        rendered = render_template(param.get("value_template", ""), render_context)
        if rendered in (None, ""):
            if param.get("required", True):
                raise ValueError(
                    f"Preset parameter '{param_name}' resolved to an empty value"
                )
            continue

        resolved[param_name] = _coerce_parameter_value(
            rendered, param.get("type", "string")
        )

    return resolved


async def execute_http_tool(
    tool: Dict[str, Any],
    arguments: Dict[str, Any],
    call_context_vars: Optional[Dict[str, Any]] = None,
    gathered_context_vars: Optional[Dict[str, Any]] = None,
    preset_params: Optional[Dict[str, Any]] = None,
    client_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute an HTTP API tool."""
    definition = tool.get("definition") or {}
    if isinstance(definition, str):
        definition = json.loads(definition)
    config = definition.get("config", {})

    # Get HTTP method and URL
    method = config.get("method", "POST").upper()
    url = config.get("url", "")

    # Get headers from config
    headers = dict(config.get("headers", {}) or {})

    # Add auth header if credential is configured
    credential_uuid = config.get("credential_uuid")
    if credential_uuid and client_id:
        try:
            from api.modules.credentials.repositories import CredentialRepository
            repo = CredentialRepository()
            credential = await repo.find_by_uuid(credential_uuid, client_id)
            if credential:
                auth_headers = build_auth_header(credential)
                headers.update(auth_headers)
                logger.debug(f"Applied credential to tool request")
            else:
                logger.warning(
                    f"Credential {credential_uuid} not found for tool '{tool['name']}'"
                )
        except Exception as e:
            logger.error(f"Failed to fetch credential for tool '{tool['name']}': {e}")

    # Get timeout
    timeout_ms = config.get("timeout_ms", 5000)
    timeout_seconds = timeout_ms / 1000

    if preset_params is None:
        try:
            preset_arguments = _resolve_preset_parameters(
                config, call_context_vars, gathered_context_vars
            )
        except ValueError as e:
            logger.error(f"Custom tool '{tool['name']}' preset parameter error: {e}")
            return {"status": "error", "error": str(e)}
    else:
        preset_arguments = dict(preset_params)

    resolved_arguments = {**(arguments or {}), **preset_arguments}

    # Build request: JSON body for POST/PUT/PATCH, query params for GET/DELETE
    body = None
    params = None
    if method in ("POST", "PUT", "PATCH"):
        body = resolved_arguments
    elif method in ("GET", "DELETE") and resolved_arguments:
        params = serialize_query_params(resolved_arguments)

    logger.info(
        f"Executing custom tool '{tool['name']}' ({tool['tool_uuid']}): {method} {url}"
    )

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body,
                params=params,
            )

            # Try to parse JSON response
            try:
                response_data = response.json()
            except Exception:
                response_data = {"raw_response": response.text}

            result = {
                "status": "success",
                "status_code": response.status_code,
                "data": response_data,
            }

            logger.debug(
                f"Custom tool '{tool['name']}' completed with status {response.status_code}"
            )
            return result

    except httpx.TimeoutException:
        logger.error(f"Custom tool '{tool['name']}' timed out after {timeout_seconds}s")
        return {
            "status": "error",
            "error": f"Request timed out after {timeout_seconds} seconds",
        }
    except httpx.RequestError as e:
        logger.error(f"Custom tool '{tool['name']}' request failed: {e}")
        return {
            "status": "error",
            "error": f"Request failed: {str(e)}",
        }
    except Exception as e:
        logger.error(f"Custom tool '{tool['name']}' execution failed: {e}")
        return {
            "status": "error",
            "error": f"Tool execution failed: {str(e)}",
        }


async def call_mcp_tool(
    url: str,
    tool_name: str,
    arguments: Dict[str, Any],
    credential: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute an MCP tool call over JSON-RPC HTTP transport."""
    if config is None:
        config = {}
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
            # 1. Initialize
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

            # 2. Call tool
            call_resp = await client.post(
                url,
                headers=request_headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                },
            )

            from api.modules.tools.services import _parse_mcp_payload
            payload = _parse_mcp_payload(call_resp)
            if not payload:
                return {"status": "error", "error": "Empty or invalid response from MCP server"}
            
            if "error" in payload:
                return {"status": "error", "error": payload["error"]}
                
            result = payload.get("result", {})
            return {"status": "success", "result": result}
            
    except Exception as e:
        logger.warning(f"MCP call failed for {url}/{tool_name}: {e}")
        return {"status": "error", "error": str(e)}


# --- Call Transfer Resolver Helpers ---

@dataclass
class ResolvedTransferConfig:
    destination: str
    timeout_seconds: int
    message: Optional[str] = None
    source: str = "static"
    resolution_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TransferResolutionError(ValueError):
    """Raised when a transfer destination cannot be resolved safely."""
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def _render_value(
    value: Any,
    call_context_vars: Optional[Dict[str, Any]],
    gathered_context_vars: Optional[Dict[str, Any]],
) -> str:
    initial_context = dict(call_context_vars or {})
    render_context: Dict[str, Any] = {
        **initial_context,
        "initial_context": initial_context,
        "gathered_context": dict(gathered_context_vars or {}),
    }
    rendered = render_template(value, render_context)
    if rendered is None:
        return ""
    return str(rendered).strip()


def _base_timeout(config: dict[str, Any]) -> int:
    timeout = config.get("timeout", 30)
    try:
        timeout_int = int(timeout)
    except (TypeError, ValueError):
        timeout_int = 30
    return min(max(timeout_int, 5), 120)


def _resolve_static_transfer(
    config: dict[str, Any],
    call_context_vars: Optional[Dict[str, Any]],
    gathered_context_vars: Optional[Dict[str, Any]],
) -> ResolvedTransferConfig:
    return ResolvedTransferConfig(
        destination=_render_value(
            config.get("destination", ""), call_context_vars, gathered_context_vars
        ),
        timeout_seconds=_base_timeout(config),
    )


def _context_value(
    path: str,
    call_context_vars: Optional[Dict[str, Any]],
    gathered_context_vars: Optional[Dict[str, Any]],
) -> Any:
    initial = call_context_vars or {}
    gathered = gathered_context_vars or {}
    normalized = path.strip()
    if normalized.startswith("initial_context."):
        current: Any = initial
        parts = normalized.removeprefix("initial_context.").split(".")
    elif normalized.startswith("gathered_context."):
        current = gathered
        parts = normalized.removeprefix("gathered_context.").split(".")
    else:
        current = gathered
        parts = normalized.split(".")

    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    if current is None and "." not in normalized:
        extracted = gathered.get("extracted_variables")
        if isinstance(extracted, dict):
            current = extracted.get(normalized)
    return current


def _resolve_context_mapping_transfer(
    config: dict[str, Any],
    call_context_vars: Optional[Dict[str, Any]],
    gathered_context_vars: Optional[Dict[str, Any]],
) -> ResolvedTransferConfig:
    mapping = config.get("context_mapping")
    if not isinstance(mapping, dict):
        raise TransferResolutionError(
            "invalid_context_mapping", "Transfer context mapping is missing"
        )
    path = str(mapping.get("context_path", "")).strip()
    raw_value = _context_value(path, call_context_vars, gathered_context_vars)
    match_value = "" if raw_value is None else str(raw_value).strip().casefold()
    destination = ""
    for route in mapping.get("routes") or []:
        if not isinstance(route, dict):
            continue
        if str(route.get("context_value", "")).strip().casefold() == match_value:
            destination = str(route.get("destination", "")).strip()
            break
    if not destination:
        destination = str(mapping.get("fallback_destination") or "").strip()
    if not destination:
        raise TransferResolutionError(
            "no_context_mapping_match",
            f"No destination mapping matched gathered context path '{path}'",
        )
    return ResolvedTransferConfig(
        destination=destination,
        timeout_seconds=_base_timeout(config),
        source="context_mapping",
        metadata={"context_path": path, "matched": bool(match_value)},
    )


def _resolver_arguments(
    *,
    resolver: dict[str, Any],
    arguments: dict[str, Any],
    call_context_vars: Optional[Dict[str, Any]],
    gathered_context_vars: Optional[Dict[str, Any]],
) -> dict[str, Any]:
    try:
        preset_arguments = _resolve_preset_parameters(
            resolver, call_context_vars, gathered_context_vars
        )
    except ValueError as exc:
        raise TransferResolutionError("preset_parameter_error", str(exc)) from exc
    return {**(arguments or {}), **preset_arguments}


async def _execute_http_resolver(
    *,
    resolver: dict[str, Any],
    resolved_arguments: dict[str, Any],
    client_id: Optional[str],
    resolution_id: str,
) -> dict[str, Any]:
    url = resolver.get("url", "")
    method = "POST"
    headers = dict(resolver.get("headers", {}) or {})
    if method in ("POST", "PUT", "PATCH"):
        headers.setdefault("Content-Type", "application/json")

    credential_uuid = resolver.get("credential_uuid")
    if credential_uuid and client_id:
        try:
            from api.modules.credentials.repositories import CredentialRepository
            repo = CredentialRepository()
            credential = await repo.find_by_uuid(credential_uuid, client_id)
            if credential:
                headers.update(build_auth_header(credential))
            else:
                raise TransferResolutionError(
                    "credential_not_found",
                    "Transfer resolver credential was not found for this client organization",
                )
        except Exception as e:
            if isinstance(e, TransferResolutionError):
                raise
            raise TransferResolutionError("credential_lookup_failed", str(e)) from e

    body = resolved_arguments
    timeout_seconds = float(resolver.get("timeout_ms", 3000)) / 1000.0

    try:
        started_at = time.monotonic()
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body,
            )
        duration_ms = int((time.monotonic() - started_at) * 1000)
    except httpx.TimeoutException as exc:
        raise TransferResolutionError(
            "resolver_timeout",
            f"Transfer resolver timed out after {timeout_seconds:.1f} seconds",
        ) from exc
    except httpx.RequestError as exc:
        raise TransferResolutionError(
            "resolver_request_failed", f"Transfer resolver request failed: {exc}"
        ) from exc

    if response.status_code < 200 or response.status_code >= 300:
        raise TransferResolutionError(
            "resolver_http_error",
            f"Transfer resolver returned HTTP {response.status_code}",
        )

    try:
        data = response.json()
    except Exception as exc:
        raise TransferResolutionError(
            "invalid_resolver_response", "Transfer resolver returned non-JSON response"
        ) from exc

    if not isinstance(data, dict):
        raise TransferResolutionError(
            "invalid_resolver_response",
            "Transfer resolver response must be a JSON object",
        )
    return data


def _resolve_from_response(
    *,
    response_data: dict[str, Any],
    config: dict[str, Any],
    resolution_id: str,
) -> ResolvedTransferConfig:
    transfer_context = response_data.get("transfer_context")
    if not isinstance(transfer_context, dict):
        raise TransferResolutionError(
            "invalid_resolver_response",
            "Transfer resolver response must contain transfer_context object",
        )

    destination = transfer_context.get("destination")
    if not isinstance(destination, str) or not destination.strip():
        raise TransferResolutionError(
            "no_destination",
            "Transfer resolver response must contain transfer_context.destination",
        )

    custom_message = transfer_context.get("custom_message")
    if custom_message is not None and not isinstance(custom_message, str):
        raise TransferResolutionError(
            "invalid_custom_message",
            "transfer_context.custom_message must be a string when provided",
        )

    return ResolvedTransferConfig(
        destination=destination.strip(),
        timeout_seconds=_base_timeout(config),
        message=custom_message.strip() if custom_message else None,
        source="http_resolver",
        resolution_id=resolution_id,
    )


async def resolve_transfer_config(
    *,
    tool: Dict[str, Any],
    config: dict[str, Any],
    arguments: dict[str, Any],
    call_context_vars: Optional[Dict[str, Any]],
    gathered_context_vars: Optional[Dict[str, Any]],
    client_id: Optional[str],
) -> ResolvedTransferConfig:
    """Resolve transfer destination and options for a transfer tool call."""
    destination_source = config.get("destination_source", "static")
    if destination_source == "context_mapping":
        resolved = _resolve_context_mapping_transfer(
            config, call_context_vars, gathered_context_vars
        )
        return resolved

    resolver = config.get("resolver")
    if config.get("destination_source", "static") != "dynamic" or not isinstance(
        resolver, dict
    ):
        resolved = _resolve_static_transfer(
            config, call_context_vars, gathered_context_vars
        )
        return resolved

    resolution_id = str(uuid.uuid4())
    resolved_arguments = _resolver_arguments(
        resolver=resolver,
        arguments=arguments,
        call_context_vars=call_context_vars,
        gathered_context_vars=gathered_context_vars,
    )
    response_data = await _execute_http_resolver(
        resolver=resolver,
        resolved_arguments=resolved_arguments,
        client_id=client_id,
        resolution_id=resolution_id,
    )
    resolved = _resolve_from_response(
        response_data=response_data,
        config=config,
        resolution_id=resolution_id,
    )
    return resolved


def safe_calculator(expr: str) -> float:
    """Parse arithmetic expressions using ast and support + - * / ** and parentheses."""
    import ast
    allowed_nodes = {
        ast.Expression,
        ast.BinOp,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Constant,
        ast.Load,
        ast.Mod,
    }

    node = ast.parse(expr, mode="eval")
    if not all(isinstance(n, tuple(allowed_nodes)) for n in ast.walk(node)):
        raise ValueError("Unsupported expression")
    return eval(compile(node, "<safe_calculator>", mode="eval"))


def get_calculator_tools() -> list[Dict[str, Any]]:
    """Get calculator tool definitions for LLM function calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": "safe_calculator",
                "description": "Perform simple arithmetic calculations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Arithmetic expression to evaluate (supports +, -, *, /, **, %, and parentheses). Example: 2000 + 5000",
                        }
                    },
                    "required": ["expression"],
                },
            },
        }
    ]
