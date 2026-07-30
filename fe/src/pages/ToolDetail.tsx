"use client";

import { ArrowLeft, Code, ExternalLink, FlaskConical, Loader2, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { api } from "@/services/api";
import ToolsService from "@/services/tools.service";
import { Recording, Tool } from "@/types";
import {
    CredentialSelector,
    type HttpMethod,
    type KeyValueItem,
    type PresetToolParameter,
    type ToolParameter,
    validateUrl,
} from "@/components/http";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { formatApiErrorDetail } from "@/lib/utils";

import {
    BuiltinToolConfig,
    EndCallToolConfig,
    HttpApiToolConfig,
    HttpToolTestDialog,
    TransferCallToolConfig,
} from "./tools/components";

// Local types & configs aligned to reference
export type ToolCategory = "http_api" | "end_call" | "transfer_call" | "calculator" | "mcp";
export type EndCallMessageType = "none" | "custom" | "audio";
export type TransferDestinationSource = "static" | "dynamic" | "context_mapping";

export interface ContextDestinationRouteRow {
    id: string;
    context_value: string;
    destination: string;
}

const createUuid = () => crypto.randomUUID?.() || Math.random().toString(36).substring(2, 15);

const TOOL_DOCUMENTATION_URLS: Record<string, string> = {
    http_api: "https://docs.dograh.com/voice-agent/tools/http-api",
    end_call: "https://docs.dograh.com/voice-agent/tools/end-call",
    transfer_call: "https://docs.dograh.com/voice-agent/tools/transfer-call",
    calculator: "https://docs.dograh.com/voice-agent/tools/calculator",
    mcp: "https://docs.dograh.com/voice-agent/tools/mcp",
};

export const DEFAULT_END_CALL_REASON_DESCRIPTION =
    "The reason for ending the call (e.g., 'voicemail_detected', 'issue_resolved', 'customer_requested')";

export const MCP_URL_PATTERN = /^https?:\/\//i;

function normalizeParameterType(value: string | null | undefined): "string" | "number" | "boolean" | "object" | "array" {
    switch (value) {
        case "number":
        case "boolean":
        case "object":
        case "array":
            return value;
        default:
            return "string";
    }
}

function headersToRows(headers: Record<string, string> | undefined | null): KeyValueItem[] {
    if (!headers) return [];
    return Object.entries(headers).map(([key, value]) => ({ key, value }));
}

function rowsToHeaders(rows: KeyValueItem[]): Record<string, string> {
    const out: Record<string, string> = {};
    rows.forEach((r) => {
        if (r.key.trim()) out[r.key.trim()] = r.value;
    });
    return out;
}

export function buildHttpToolTestSnapshot(fields: any): string {
    const normalizedHeaders = Object.fromEntries(
        (fields.headers || []).filter((h: any) => h.key).map((h: any) => [h.key, h.value])
    );
    return JSON.stringify({ ...fields, headers: normalizedHeaders });
}

export default function ToolDetail() {
    const { toolUuid } = useParams<{ toolUuid: string }>();
    const nav = useNavigate();

    const [tool, setTool] = useState<Tool | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [saveSuccess, setSaveSuccess] = useState(false);
    const [showCodeDialog, setShowCodeDialog] = useState(false);
    const [showTestDialog, setShowTestDialog] = useState(false);
    const [savedHttpTestSnapshot, setSavedHttpTestSnapshot] = useState<string | null>(null);

    // Common form state
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");

    // Shared form state
    const [customMessage, setCustomMessage] = useState("");

    // HTTP API form state
    const [httpMethod, setHttpMethod] = useState<HttpMethod>("POST");
    const [url, setUrl] = useState("");
    const [credentialUuid, setCredentialUuid] = useState("");
    const [headers, setHeaders] = useState<KeyValueItem[]>([]);
    const [parameters, setParameters] = useState<ToolParameter[]>([]);
    const [presetParameters, setPresetParameters] = useState<PresetToolParameter[]>([]);
    const [timeoutMs, setTimeoutMs] = useState(5000);

    // End Call form state
    const [endCallMessageType, setEndCallMessageType] = useState<EndCallMessageType>("none");
    const [endCallReason, setEndCallReason] = useState(false);
    const [endCallReasonDescription, setEndCallReasonDescription] = useState("");
    const [audioRecordingId, setAudioRecordingId] = useState("");

    const handleEndCallReasonChange = (enabled: boolean) => {
        setEndCallReason(enabled);
        if (enabled && !endCallReasonDescription) {
            setEndCallReasonDescription(DEFAULT_END_CALL_REASON_DESCRIPTION);
        }
    };

    // Transfer Call form state
    const [transferDestinationSource, setTransferDestinationSource] =
        useState<TransferDestinationSource>("static");
    const [transferDestination, setTransferDestination] = useState("");
    const [transferMessageType, setTransferMessageType] = useState<EndCallMessageType>("none");
    const [transferTimeout, setTransferTimeout] = useState(30);
    const [transferAudioRecordingId, setTransferAudioRecordingId] = useState("");
    const [transferResolverUrl, setTransferResolverUrl] = useState("");
    const [transferResolverCredentialUuid, setTransferResolverCredentialUuid] = useState("");
    const [transferResolverHeaders, setTransferResolverHeaders] = useState<KeyValueItem[]>([]);
    const [transferResolverTimeoutMs, setTransferResolverTimeoutMs] = useState(3000);
    const [transferResolverWaitMessage, setTransferResolverWaitMessage] = useState("");
    const [transferParameters, setTransferParameters] = useState<ToolParameter[]>([]);
    const [transferPresetParameters, setTransferPresetParameters] = useState<PresetToolParameter[]>([]);
    const [transferContextMappingPath, setTransferContextMappingPath] = useState("");
    const [transferContextDestinationRoutes, setTransferContextDestinationRoutes] =
        useState<ContextDestinationRouteRow[]>([]);
    const [transferFallbackDestination, setTransferFallbackDestination] = useState("");

    // HTTP API form state - custom message type
    const [customMessageType, setCustomMessageType] = useState<'text' | 'audio'>('text');
    const [customMessageRecordingId, setCustomMessageRecordingId] = useState("");

    // MCP form state
    const [mcpUrl, setMcpUrl] = useState("");
    const [mcpCredentialUuid, setMcpCredentialUuid] = useState("");
    const [mcpToolsFilter, setMcpToolsFilter] = useState("");
    const [discoveredTools, setDiscoveredTools] = useState<{ name: string; description?: string }[]>([]);
    const [isRefreshingMcp, setIsRefreshingMcp] = useState(false);

    // Org-level recordings for audio dropdowns
    const [recordings, setRecordings] = useState<Recording[]>([]);

    const populateFormFromTool = (tool: Tool) => {
        setName(tool.name);
        setDescription(tool.description || "");

        const config: any = tool.definition?.config || {};

        if (tool.category === "end_call") {
            setEndCallMessageType(config.messageType || "none");
            setCustomMessage(config.customMessage || "");
            setAudioRecordingId(config.audioRecordingId || "");
            setEndCallReason(config.endCallReason ?? false);
            setEndCallReasonDescription(config.endCallReasonDescription || "");
        } else if (tool.category === "transfer_call") {
            const resolver = config.resolver || undefined;
            setTransferDestinationSource(config.destination_source || (resolver ? "dynamic" : "static"));
            setTransferDestination(config.destination || "");
            setTransferMessageType(config.messageType || "none");
            setCustomMessage(config.customMessage || "");
            setTransferAudioRecordingId(config.audioRecordingId || "");
            setTransferTimeout(config.timeout ?? 30);
            setTransferResolverUrl(resolver?.url || "");
            setTransferResolverCredentialUuid(resolver?.credential_uuid || "");
            setTransferResolverHeaders(headersToRows(resolver?.headers));
            setTransferResolverTimeoutMs(resolver?.timeout_ms ?? 3000);
            setTransferResolverWaitMessage(resolver?.wait_message || "");
            setTransferParameters(
                (resolver?.parameters || config.parameters || []).map((p: any) => ({
                    name: p.name || "",
                    type: normalizeParameterType(p.type),
                    description: p.description || "",
                    required: p.required ?? true,
                }))
            );
            setTransferPresetParameters(
                (resolver?.preset_parameters || []).map((p: any) => ({
                    name: p.name || "",
                    type: normalizeParameterType(p.type),
                    valueTemplate: p.value_template || "",
                    required: p.required ?? true,
                }))
            );
            setTransferContextMappingPath(config.context_mapping?.context_path || "");
            setTransferContextDestinationRoutes(
                (config.context_mapping?.routes || []).map((route: any) => ({
                    ...route,
                    id: createUuid(),
                }))
            );
            setTransferFallbackDestination(config.context_mapping?.fallback_destination || "");
        } else if (tool.category === "mcp") {
            setMcpUrl(config.url || "");
            setMcpCredentialUuid(config.credential_uuid || "");
            setMcpToolsFilter(Array.isArray(config.tools_filter) ? config.tools_filter.join(", ") : "");
            setDiscoveredTools(config.discovered_tools || []);
        } else {
            const loadedHttpMethod = (config.method as HttpMethod) || "POST";
            const loadedUrl = config.url || "";
            const loadedCredentialUuid = config.credential_uuid || "";
            const loadedTimeoutMs = config.timeout_ms || 5000;
            const loadedCustomMessage = config.customMessage || "";
            const loadedCustomMessageType = config.customMessageType || "text";
            const loadedCustomMessageRecordingId = config.customMessageRecordingId || "";
            setHttpMethod(loadedHttpMethod);
            setUrl(loadedUrl);
            setCredentialUuid(loadedCredentialUuid);
            setTimeoutMs(loadedTimeoutMs);
            setCustomMessage(loadedCustomMessage);
            setCustomMessageType(loadedCustomMessageType);
            setCustomMessageRecordingId(loadedCustomMessageRecordingId);
            setHeaders(headersToRows(config.headers));
            setParameters(
                (config.parameters || []).map((p: any) => ({
                    name: p.name || "",
                    type: normalizeParameterType(p.type),
                    description: p.description || "",
                    required: p.required ?? true,
                }))
            );
            setPresetParameters(
                (config.preset_parameters || []).map((p: any) => ({
                    name: p.name || "",
                    type: normalizeParameterType(p.type),
                    valueTemplate: p.value_template || "",
                    required: p.required ?? true,
                }))
            );
            setSavedHttpTestSnapshot(
                buildHttpToolTestSnapshot({
                    name: tool.name,
                    description: tool.description || "",
                    httpMethod: loadedHttpMethod,
                    url: loadedUrl,
                    credentialUuid: loadedCredentialUuid,
                    headers: headersToRows(config.headers),
                    parameters: config.parameters || [],
                    presetParameters: config.preset_parameters || [],
                    timeoutMs: loadedTimeoutMs,
                    customMessage: loadedCustomMessage,
                    customMessageType: loadedCustomMessageType,
                    customMessageRecordingId: loadedCustomMessageRecordingId,
                })
            );
        }
    };

    const loadTool = useCallback(async () => {
        if (!toolUuid) return;
        try {
            setIsLoading(true);
            setError(null);
            const data = await ToolsService.getByUuid(toolUuid);
            setTool(data);
            populateFormFromTool(data);
        } catch (err: any) {
            setError("Failed to fetch tool");
            console.error(err);
        } finally {
            setIsLoading(false);
        }
    }, [toolUuid]);

    const fetchRecordings = useCallback(async () => {
        try {
            const res = await api.get<{ data: Recording[] }>("/recordings");
            setRecordings(res.data || []);
        } catch {
            // Silently ignore recordings fetch failures
        }
    }, []);

    useEffect(() => {
        loadTool();
        fetchRecordings();
    }, [loadTool, fetchRecordings]);

    const handleSave = async () => {
        if (!tool) return;

        const normalizedTransferDestination = transferDestination.trim();

        // Standard validation
        if (tool.category === "calculator") {
            // Always valid
        } else if (tool.category === "transfer_call") {
            if (transferDestinationSource === "static" && !normalizedTransferDestination) {
                setError("Please enter a transfer destination");
                return;
            }
            if (transferDestinationSource === "dynamic") {
                const resolverUrlValidation = validateUrl(transferResolverUrl);
                if (!resolverUrlValidation.valid) {
                    setError(resolverUrlValidation.error || "Invalid resolver URL");
                    return;
                }

                const invalidTransferParams = transferParameters.filter(
                    (p) => !p.name.trim() || !p.description.trim()
                );
                if (invalidTransferParams.length > 0) {
                    setError("All resolver arguments must have a name and description");
                    return;
                }
                const transferParamNames = transferParameters
                    .map((p) => p.name.trim())
                    .filter(Boolean);
                if (new Set(transferParamNames).size !== transferParamNames.length) {
                    setError("Resolver argument names must be unique");
                    return;
                }
                const invalidPresetTransferParams = transferPresetParameters.filter(
                    (p) => !p.name.trim() || !p.valueTemplate.trim()
                );
                if (invalidPresetTransferParams.length > 0) {
                    setError("All resolver preset parameters must have a name and a value");
                    return;
                }
                const transferPresetParamNames = transferPresetParameters
                    .map((p) => p.name.trim())
                    .filter(Boolean);
                if (new Set(transferPresetParamNames).size !== transferPresetParamNames.length) {
                    setError("Resolver preset parameter names must be unique");
                    return;
                }
            }
            if (transferDestinationSource === "context_mapping") {
                if (!transferContextMappingPath.trim()) {
                    setError("Please enter a gathered-context field for PBX routing");
                    return;
                }
                if (
                    transferContextDestinationRoutes.length === 0 ||
                    transferContextDestinationRoutes.some(
                        (route) => !route.context_value.trim() || !route.destination.trim()
                    )
                ) {
                    setError("Add at least one complete context value to destination mapping");
                    return;
                }
                const routeValues = transferContextDestinationRoutes.map((route) =>
                    route.context_value.trim().toLocaleLowerCase()
                );
                if (new Set(routeValues).size !== routeValues.length) {
                    setError("Destination mapping context values must be unique");
                    return;
                }
            }
        } else if (tool.category === "mcp") {
            if (!mcpUrl.trim()) {
                setError("Please enter the MCP server URL");
                return;
            }
            if (!MCP_URL_PATTERN.test(mcpUrl.trim())) {
                setError("MCP server URL must start with http:// or https://");
                return;
            }
        } else if (tool.category !== "end_call") {
            const urlValidation = validateUrl(url);
            if (!urlValidation.valid) {
                setError(urlValidation.error || "Invalid URL");
                return;
            }

            const invalidParams = parameters.filter((p) => !p.name.trim());
            if (invalidParams.length > 0) {
                setError("All parameters must have a name");
                return;
            }
            const paramNames = parameters.map((p) => p.name.trim()).filter(Boolean);
            if (new Set(paramNames).size !== paramNames.length) {
                setError("Parameter names must be unique");
                return;
            }

            const invalidPresetParams = presetParameters.filter(
                (p) => !p.name.trim() || !p.valueTemplate.trim()
            );
            if (invalidPresetParams.length > 0) {
                setError("All preset parameters must have a name and a value");
                return;
            }
        }

        try {
            setIsSaving(true);
            setError(null);
            setSaveSuccess(false);

            let definition: any;

            if (tool.category === "calculator") {
                definition = {
                    schema_version: 1,
                    type: "calculator",
                };
            } else if (tool.category === "end_call") {
                definition = {
                    schema_version: 1,
                    type: "end_call",
                    config: {
                        messageType: endCallMessageType,
                        customMessage: endCallMessageType === "custom" ? customMessage : undefined,
                        audioRecordingId: endCallMessageType === "audio" ? audioRecordingId || undefined : undefined,
                        endCallReason,
                        endCallReasonDescription: endCallReason ? endCallReasonDescription || undefined : undefined,
                    },
                };
            } else if (tool.category === "transfer_call") {
                const resolverHeadersObject = rowsToHeaders(transferResolverHeaders);
                const validTransferParameters = transferParameters.filter((p) => p.name.trim());
                const validTransferPresetParameters = transferPresetParameters.filter(
                    (p) => p.name.trim() && p.valueTemplate.trim()
                );

                const transferConfig = {
                    destination_source: transferDestinationSource,
                    destination: transferDestinationSource === "static" ? normalizedTransferDestination : "",
                    messageType: transferMessageType,
                    customMessage: transferMessageType === "custom" ? customMessage : undefined,
                    audioRecordingId: transferMessageType === "audio" ? transferAudioRecordingId || undefined : undefined,
                    timeout: transferTimeout,
                    resolver: transferDestinationSource === "dynamic"
                        ? {
                            type: "http",
                            url: transferResolverUrl.trim(),
                            credential_uuid: transferResolverCredentialUuid || undefined,
                            headers:
                                Object.keys(resolverHeadersObject).length > 0
                                    ? resolverHeadersObject
                                    : undefined,
                            timeout_ms: transferResolverTimeoutMs,
                            wait_message: transferResolverWaitMessage.trim() || undefined,
                            parameters:
                                validTransferParameters.length > 0
                                    ? validTransferParameters.map((p) => ({
                                        name: p.name.trim(),
                                        type: p.type,
                                        description: p.description.trim(),
                                        required: p.required,
                                    }))
                                    : undefined,
                            preset_parameters:
                                validTransferPresetParameters.length > 0
                                    ? validTransferPresetParameters.map((p) => ({
                                        name: p.name.trim(),
                                        type: p.type,
                                        value_template: p.valueTemplate.trim(),
                                        required: p.required,
                                    }))
                                    : undefined,
                        }
                        : undefined,
                    context_mapping: transferDestinationSource === "context_mapping"
                        ? {
                            context_path: transferContextMappingPath.trim(),
                            routes: transferContextDestinationRoutes.map((route) => ({
                                context_value: route.context_value.trim(),
                                destination: route.destination.trim(),
                            })),
                            fallback_destination:
                                transferFallbackDestination.trim() || undefined,
                        }
                        : undefined,
                };
                definition = {
                    schema_version: 1,
                    type: "transfer_call",
                    config: transferConfig,
                };
            } else if (tool.category === "mcp") {
                definition = {
                    schema_version: 1,
                    type: "mcp",
                    config: {
                        transport: "streamable_http",
                        url: mcpUrl.trim(),
                        credential_uuid: mcpCredentialUuid || null,
                        tools_filter: mcpToolsFilter
                            ? mcpToolsFilter.split(",").map((s) => s.trim()).filter((s) => s.length > 0)
                            : [],
                        discovered_tools: discoveredTools,
                    }
                };
            } else {
                const headersObject = rowsToHeaders(headers);
                const validParameters = parameters.filter((p) => p.name.trim());
                const validPresetParameters = presetParameters.filter(
                    (p) => p.name.trim() && p.valueTemplate.trim()
                );

                definition = {
                    schema_version: 1,
                    type: "http_api",
                    config: {
                        method: httpMethod,
                        url: url.trim(),
                        credential_uuid: credentialUuid || undefined,
                        headers:
                            Object.keys(headersObject).length > 0
                                ? headersObject
                                : undefined,
                        parameters:
                            validParameters.length > 0 ? validParameters : undefined,
                        preset_parameters:
                            validPresetParameters.length > 0
                                ? validPresetParameters.map((p) => ({
                                    name: p.name,
                                    type: p.type,
                                    value_template: p.valueTemplate,
                                    required: p.required,
                                }))
                                : undefined,
                        timeout_ms: timeoutMs,
                        customMessage: customMessageType === 'text' ? (customMessage || undefined) : undefined,
                        customMessageType,
                        customMessageRecordingId: customMessageType === 'audio' ? (customMessageRecordingId || undefined) : undefined,
                    },
                };
            }

            const updated = await ToolsService.update(toolUuid!, {
                name,
                description: description || undefined,
                definition,
            });

            setTool(updated);
            setSaveSuccess(true);
            toast.success("Tool saved successfully");
            setTimeout(() => setSaveSuccess(false), 3000);
            if (tool.category === "http_api") {
                setSavedHttpTestSnapshot(
                    buildHttpToolTestSnapshot({
                        name,
                        description,
                        httpMethod,
                        url,
                        credentialUuid,
                        headers,
                        parameters,
                        presetParameters,
                        timeoutMs,
                        customMessage,
                        customMessageType,
                        customMessageRecordingId,
                    })
                );
            }
        } catch (err: any) {
            setError(formatApiErrorDetail(err?.response?.data?.message || err?.message || "Failed to save tool"));
            toast.error("Failed to save tool");
        } finally {
            setIsSaving(false);
        }
    };

    const handleRefreshMcp = async () => {
        if (!toolUuid) return;
        try {
            setIsRefreshingMcp(true);
            const result = await ToolsService.refreshMcp(toolUuid);
            if (result.error) {
                toast.error(result.error);
            } else {
                toast.success(`Discovered ${result.discovered_tools.length} tool(s)`);
            }
            setDiscoveredTools(result.discovered_tools || []);
        } catch (err: any) {
            toast.error("Failed to refresh MCP tools");
            console.error(err);
        } finally {
            setIsRefreshingMcp(false);
        }
    };

    const getCodeSnippet = () => {
        if (!tool) return "";

        const headersObj: Record<string, string> = {
            "Content-Type": "application/json",
        };
        headers.filter((h) => h.key && h.value).forEach((h) => {
            headersObj[h.key] = h.value;
        });

        const exampleBody: Record<string, unknown> = {};
        parameters.forEach((p) => {
            if (p.type === "number") {
                exampleBody[p.name] = 0;
            } else if (p.type === "boolean") {
                exampleBody[p.name] = true;
            } else {
                exampleBody[p.name] = `<${p.name}>`;
            }
        });
        presetParameters.forEach((p) => {
            if (p.type === "number") {
                exampleBody[p.name] = p.valueTemplate || 0;
            } else if (p.type === "boolean") {
                exampleBody[p.name] = p.valueTemplate || true;
            } else {
                exampleBody[p.name] = p.valueTemplate || `<${p.name}>`;
            }
        });

        const hasBody =
            httpMethod !== "GET" &&
            httpMethod !== "DELETE" &&
            (parameters.length > 0 || presetParameters.length > 0);

        return `// ${tool.name}
// ${tool.description || "HTTP API Tool"}

const response = await fetch("${url}", {
    method: "${httpMethod}",
    headers: ${JSON.stringify(headersObj, null, 4)},${hasBody ? `
    body: JSON.stringify(${JSON.stringify(exampleBody, null, 4)}),` : ""}
});

const data = await response.json();`;
    };

    if (isLoading) {
        return (
            <div className="container mx-auto px-4 py-8">
                <div className="max-w-4xl mx-auto space-y-6">
                    <Skeleton className="h-8 w-48" />
                    <Skeleton className="h-64 w-full" />
                </div>
            </div>
        );
    }

    if (!tool) {
        return (
            <div className="container mx-auto px-4 py-8">
                <div className="max-w-4xl mx-auto text-center py-12">
                    <h1 className="text-2xl font-bold mb-4">Tool not found</h1>
                    <Button onClick={() => nav("/tools")}>
                        <ArrowLeft className="w-4 h-4 mr-2" />
                        Back to Tools
                    </Button>
                </div>
            </div>
        );
    }

    const isEndCallTool = tool.category === "end_call";
    const isTransferCallTool = tool.category === "transfer_call";
    const isBuiltinTool = tool.category === "calculator";
    const isMcpTool = tool.category === "mcp";
    const isHttpApiTool = tool.category === "http_api";

    const hasUnsavedHttpChanges =
        isHttpApiTool &&
        (savedHttpTestSnapshot === null ||
            buildHttpToolTestSnapshot({
                name,
                description,
                httpMethod,
                url,
                credentialUuid,
                headers,
                parameters,
                presetParameters,
                timeoutMs,
                customMessage,
                customMessageType,
                customMessageRecordingId,
            }) !== savedHttpTestSnapshot);

    const getToolTypeLabel = (cat: string) => {
        switch (cat) {
            case "end_call":
                return "End Call Tool";
            case "transfer_call":
                return "Transfer Call Tool";
            case "http_api":
                return "HTTP API Tool";
            case "calculator":
                return "Calculator Tool";
            case "mcp":
                return "MCP Server Tool";
            default:
                return "Tool";
        }
    };

    return (
        <div className="min-h-screen">
            <div className="container mx-auto px-4 py-8">
                <div className="max-w-4xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-4">
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => nav("/tools")}
                            >
                                <ArrowLeft className="w-4 h-4 mr-2" />
                                Back
                            </Button>
                            <div>
                                <h1 className="text-xl font-bold">{name}</h1>
                                <p className="text-sm text-muted-foreground">
                                    {getToolTypeLabel(tool.category)}
                                </p>
                            </div>
                        </div>
                        <div className="flex items-center gap-2">
                            {isHttpApiTool && (
                                <Button
                                    variant="outline"
                                    onClick={() => setShowCodeDialog(true)}
                                >
                                    <Code className="w-4 h-4 mr-2" />
                                    View Code
                                </Button>
                            )}
                            {TOOL_DOCUMENTATION_URLS[tool.category] && (
                                <a
                                    href={TOOL_DOCUMENTATION_URLS[tool.category]}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
                                >
                                    Docs
                                    <ExternalLink className="h-3.5 w-3.5" />
                                </a>
                            )}
                        </div>
                    </div>

                    {isBuiltinTool ? (
                        <BuiltinToolConfig
                            name={name}
                            onNameChange={setName}
                            description={description}
                            onDescriptionChange={setDescription}
                            title="Calculator Configuration"
                            subtitle="Built-in calculator for arithmetic operations. No additional configuration needed."
                        />
                    ) : isEndCallTool ? (
                        <EndCallToolConfig
                            name={name}
                            onNameChange={setName}
                            description={description}
                            onDescriptionChange={setDescription}
                            messageType={endCallMessageType}
                            onMessageTypeChange={setEndCallMessageType}
                            customMessage={customMessage}
                            onCustomMessageChange={setCustomMessage}
                            audioRecordingId={audioRecordingId}
                            onAudioRecordingIdChange={setAudioRecordingId}
                            recordings={recordings}
                            endCallReason={endCallReason}
                            onEndCallReasonChange={handleEndCallReasonChange}
                            endCallReasonDescription={endCallReasonDescription}
                            onEndCallReasonDescriptionChange={setEndCallReasonDescription}
                        />
                    ) : isTransferCallTool ? (
                        <TransferCallToolConfig
                            name={name}
                            onNameChange={setName}
                            description={description}
                            onDescriptionChange={setDescription}
                            destinationSource={transferDestinationSource}
                            onDestinationSourceChange={setTransferDestinationSource}
                            destination={transferDestination}
                            onDestinationChange={setTransferDestination}
                            messageType={transferMessageType}
                            onMessageTypeChange={setTransferMessageType}
                            customMessage={customMessage}
                            onCustomMessageChange={setCustomMessage}
                            audioRecordingId={transferAudioRecordingId}
                            onAudioRecordingIdChange={setTransferAudioRecordingId}
                            recordings={recordings}
                            timeout={transferTimeout}
                            onTimeoutChange={setTransferTimeout}
                            resolverUrl={transferResolverUrl}
                            onResolverUrlChange={setTransferResolverUrl}
                            resolverCredentialUuid={transferResolverCredentialUuid}
                            onResolverCredentialUuidChange={setTransferResolverCredentialUuid}
                            resolverHeaders={transferResolverHeaders}
                            onResolverHeadersChange={setTransferResolverHeaders}
                            resolverTimeoutMs={transferResolverTimeoutMs}
                            onResolverTimeoutMsChange={setTransferResolverTimeoutMs}
                            resolverWaitMessage={transferResolverWaitMessage}
                            onResolverWaitMessageChange={setTransferResolverWaitMessage}
                            parameters={transferParameters}
                            onParametersChange={setTransferParameters}
                            presetParameters={transferPresetParameters}
                            onPresetParametersChange={setTransferPresetParameters}
                            externalPbxRoutingEnabled={true}
                            contextMappingPath={transferContextMappingPath}
                            onContextMappingPathChange={setTransferContextMappingPath}
                            contextDestinationRoutes={transferContextDestinationRoutes}
                            onContextDestinationRoutesChange={setTransferContextDestinationRoutes}
                            fallbackDestination={transferFallbackDestination}
                            onFallbackDestinationChange={setTransferFallbackDestination}
                        />
                    ) : isMcpTool ? (
                        <Card>
                            <CardHeader>
                                <CardTitle>MCP Server Configuration</CardTitle>
                                <CardDescription>
                                    Configure the MCP server endpoint. Its tools become available to the agent.
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-6">
                                <div className="space-y-2">
                                    <Label htmlFor="mcp-name">Tool Name</Label>
                                    <Input
                                        id="mcp-name"
                                        value={name}
                                        onChange={(e) => setName(e.target.value)}
                                        placeholder="e.g., Customer MCP Server"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="mcp-description">Description</Label>
                                    <p className="text-xs text-muted-foreground">
                                        Provide a description which makes it easy for LLM to understand what this tool does
                                    </p>
                                    <Textarea
                                        id="mcp-description"
                                        value={description}
                                        onChange={(e) => setDescription(e.target.value)}
                                        placeholder="What does this MCP server provide?"
                                        rows={3}
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="mcp-url">MCP Server URL</Label>
                                    <Input
                                        id="mcp-url"
                                        value={mcpUrl}
                                        onChange={(e) => setMcpUrl(e.target.value)}
                                        placeholder="https://your-mcp-server.example.com/mcp"
                                    />
                                </div>

                                <div className="space-y-2">
                                    <Label>Transport</Label>
                                    <Input
                                        value="Streamable HTTP"
                                        disabled
                                        readOnly
                                    />
                                </div>

                                <CredentialSelector
                                    value={mcpCredentialUuid}
                                    onChange={setMcpCredentialUuid}
                                    label="Credential (Optional)"
                                    description="Select a credential for authenticating with the MCP server, or leave empty for no auth."
                                />

                                <div className="space-y-2">
                                    <Label htmlFor="mcp-tools-filter">Tools Filter (Optional)</Label>
                                    <Input
                                        id="mcp-tools-filter"
                                        value={mcpToolsFilter}
                                        onChange={(e) => setMcpToolsFilter(e.target.value)}
                                        placeholder="e.g., tool_one, tool_two"
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Comma-separated list of tool names to allow. Leave empty to expose all tools from the server.
                                    </p>
                                </div>

                                <div className="border-t border-zinc-100 pt-4">
                                  <div className="flex items-center justify-between mb-2">
                                    <Label>Discovered Tools</Label>
                                    <Button variant="outline" size="sm" onClick={handleRefreshMcp} disabled={isRefreshingMcp}>
                                      {isRefreshingMcp ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
                                      Refresh
                                    </Button>
                                  </div>
                                  {discoveredTools.length === 0 ? (
                                    <p className="text-xs text-zinc-400">No tools discovered yet. Save the URL and click Refresh.</p>
                                  ) : (
                                    <div className="flex flex-wrap gap-1.5">
                                      {discoveredTools.map((t) => (
                                        <Badge key={t.name} variant="outline" title={t.description}>
                                          {t.name}
                                        </Badge>
                                      ))}
                                    </div>
                                  )}
                                </div>
                            </CardContent>
                        </Card>
                    ) : (
                        <HttpApiToolConfig
                            name={name}
                            onNameChange={setName}
                            description={description}
                            onDescriptionChange={setDescription}
                            httpMethod={httpMethod}
                            onHttpMethodChange={setHttpMethod}
                            url={url}
                            onUrlChange={setUrl}
                            credentialUuid={credentialUuid}
                            onCredentialUuidChange={setCredentialUuid}
                            headers={headers}
                            onHeadersChange={setHeaders}
                            parameters={parameters}
                            onParametersChange={setParameters}
                            presetParameters={presetParameters}
                            onPresetParametersChange={setPresetParameters}
                            timeoutMs={timeoutMs}
                            onTimeoutMsChange={setTimeoutMs}
                            customMessage={customMessage}
                            onCustomMessageChange={setCustomMessage}
                            customMessageType={customMessageType}
                            onCustomMessageTypeChange={setCustomMessageType}
                            customMessageRecordingId={customMessageRecordingId}
                            onCustomMessageRecordingIdChange={setCustomMessageRecordingId}
                            recordings={recordings}
                        />
                    )}

                    {isHttpApiTool && (
                        <HttpToolTestDialog
                            open={showTestDialog}
                            onOpenChange={setShowTestDialog}
                            toolUuid={toolUuid || ""}
                            httpMethod={httpMethod}
                            url={url}
                            parameters={parameters}
                            presetParameters={presetParameters}
                        />
                    )}

                    {error && (
                        <div className="mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-destructive text-sm font-medium">
                            {error}
                        </div>
                    )}

                    {saveSuccess && (
                        <div className="mt-4 p-4 bg-green-500/10 border border-green-500/20 rounded-lg text-green-600 text-sm font-medium">
                            Tool saved successfully!
                        </div>
                    )}

                    <div className="flex justify-end gap-2 mt-6">
                        {isHttpApiTool && (
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setShowTestDialog(true)}
                                disabled={isSaving || hasUnsavedHttpChanges}
                                title={hasUnsavedHttpChanges ? "Save changes to test the tool" : ""}
                            >
                                <FlaskConical className="w-4 h-4 mr-2" />
                                Test Tool
                            </Button>
                        )}
                        <Button onClick={handleSave} disabled={isSaving}>
                            {isSaving ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                    Saving...
                                </>
                            ) : (
                                <>
                                    <Save className="w-4 h-4 mr-2" />
                                    Save
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </div>

            {/* Code View Dialog */}
            <Dialog open={showCodeDialog} onOpenChange={setShowCodeDialog}>
                <DialogContent className="max-w-2xl">
                    <DialogHeader>
                        <DialogTitle>Code Preview</DialogTitle>
                        <DialogDescription>
                            JavaScript code to make this API call
                        </DialogDescription>
                    </DialogHeader>
                    <div className="bg-muted rounded-lg p-4 font-mono text-sm overflow-auto max-h-96">
                        <pre>{getCodeSnippet()}</pre>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
