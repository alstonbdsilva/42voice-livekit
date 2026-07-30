import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import {
  Archive,
  Calculator,
  Globe,
  Phone,
  PhoneForwarded,
  PhoneOff,
  Plug,
  Plus,
  RotateCcw,
  Search,
  Trash2,
} from "lucide-react";

import { CredentialSelector } from "@/components/http";
import PageHeader from "@/components/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { formatApiErrorDetail } from "@/lib/utils";
import ToolsService, { CreateToolDto } from "@/services/tools.service";
import { Tool, ToolCategory } from "@/types";

interface ToolCategoryConfig {
  value: ToolCategory;
  label: string;
  description: string;
  icon: typeof Globe;
  iconColor: string;
  autoFill?: { name: string; description: string };
}

const TOOL_CATEGORIES: ToolCategoryConfig[] = [
  {
    value: "http_api",
    label: "External HTTP API",
    description: "Make HTTP requests to external APIs",
    icon: Globe,
    iconColor: "#3B82F6",
  },
  {
    value: "end_call",
    label: "End Call",
    description: "End the call when conditions are met",
    icon: PhoneOff,
    iconColor: "#EF4444",
    autoFill: {
      name: "End Call",
      description:
        "End the call when either user asks to disconnect the call, or when you believe it's time to end the conversation",
    },
  },
  {
    value: "transfer_call",
    label: "Transfer Call",
    description: "Transfer the call to another phone number",
    icon: PhoneForwarded,
    iconColor: "#10B981",
    autoFill: {
      name: "Transfer Call",
      description: "Transfer the caller to another phone number when requested",
    },
  },
  {
    value: "calculator",
    label: "Calculator",
    description: "Built-in calculator for arithmetic operations",
    icon: Calculator,
    iconColor: "#F59E0B",
    autoFill: {
      name: "Calculator",
      description: "Perform arithmetic calculations (supports +, -, *, /, and parentheses)",
    },
  },
  {
    value: "mcp",
    label: "MCP Server",
    description: "Connect an MCP server; its tools become available to the agent",
    icon: Plug,
    iconColor: "#8B5CF6",
  },
];

function getCategoryConfig(category: string): ToolCategoryConfig | undefined {
  return TOOL_CATEGORIES.find((c) => c.value === category);
}

function renderToolIcon(category: string, className = "w-4 h-4 text-white") {
  const config = getCategoryConfig(category);
  const Icon = config?.icon ?? Globe;
  return <Icon className={className} />;
}

function getCategoryBadge(category: string) {
  const config = getCategoryConfig(category);
  return <Badge variant="outline">{config?.label ?? category}</Badge>;
}

function createDefinitionForCategory(category: ToolCategory, mcpUrl = "", mcpCredentialUuid = "", mcpToolsFilter = "") {
  switch (category) {
    case "end_call":
      return { schema_version: 1, type: "end_call" as const, config: { messageType: "none" as const, endCallReason: false } };
    case "transfer_call":
      return { schema_version: 1, type: "transfer_call" as const, config: { destination: "", messageType: "none" as const, timeout: 30 } };
    case "calculator":
      return { schema_version: 1, type: "calculator" as const, config: {} };
    case "mcp":
      return {
        schema_version: 1,
        type: "mcp" as const,
        config: {
          transport: "streamable_http" as const,
          url: mcpUrl.trim(),
          credential_uuid: mcpCredentialUuid || null,
          tools_filter: mcpToolsFilter
            ? mcpToolsFilter.split(",").map((s) => s.trim()).filter((s) => s.length > 0)
            : [],
        }
      };
    case "http_api":
    default:
      return { schema_version: 1, type: "http_api" as const, config: { method: "POST" as const, url: "" } };
  }
}

export default function Tools() {
  const nav = useNavigate();

  const [tools, setTools] = useState<Tool[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newCategory, setNewCategory] = useState<ToolCategory>("http_api");
  const [mcpUrl, setMcpUrl] = useState("");
  const [mcpCredentialUuid, setMcpCredentialUuid] = useState("");
  const [mcpToolsFilter, setMcpToolsFilter] = useState("");

  const fetchTools = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await ToolsService.getAll({ status: "active,archived" });
      setTools(data);
    } catch {
      toast.error("Failed to fetch tools");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTools();
  }, [fetchTools]);

  const resetCreateForm = () => {
    setNewName("");
    setNewDescription("");
    setNewCategory("http_api");
    setMcpUrl("");
    setMcpCredentialUuid("");
    setMcpToolsFilter("");
    setCreateError(null);
  };

  const handleCreate = async () => {
    if (!newName.trim()) {
      setCreateError("Please enter a name for the tool");
      return;
    }
    if (newCategory === "mcp" && !mcpUrl.trim()) {
      setCreateError("Please enter the MCP server URL");
      return;
    }

    try {
      setIsCreating(true);
      setCreateError(null);
      const categoryConfig = getCategoryConfig(newCategory);
      const definition = createDefinitionForCategory(newCategory, mcpUrl, mcpCredentialUuid, mcpToolsFilter);

      const dto: CreateToolDto = {
        name: newName,
        description: newDescription || undefined,
        category: newCategory,
        icon: categoryConfig?.value === "mcp" ? "puzzle" : categoryConfig?.value,
        icon_color: categoryConfig?.iconColor || "#3B82F6",
        definition,
      };

      const created = await ToolsService.create(dto);
      setIsCreateOpen(false);
      resetCreateForm();
      nav(`/tools/${created.toolUuid}`);
    } catch (err: any) {
      setCreateError(formatApiErrorDetail(err?.response?.data?.message || err?.message || "Failed to create tool"));
    } finally {
      setIsCreating(false);
    }
  };

  const handleArchive = async (toolUuid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to archive this tool?")) return;
    try {
      await ToolsService.archive(toolUuid);
      toast.success("Tool archived");
      fetchTools();
    } catch {
      toast.error("Failed to archive tool");
    }
  };

  const handleUnarchive = async (toolUuid: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await ToolsService.unarchive(toolUuid);
      toast.success("Tool restored");
      fetchTools();
    } catch {
      toast.error("Failed to unarchive tool");
    }
  };

  const filteredTools = tools.filter(
    (tool) =>
      tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (tool.description || "").toLowerCase().includes(searchQuery.toLowerCase())
  );
  const activeTools = filteredTools.filter((t) => t.status === "active");
  const archivedTools = filteredTools.filter((t) => t.status === "archived");

  return (
    <div data-testid="tools-page">
      <PageHeader
        title="Tools"
        subtitle="Manage reusable tools that can be used by your voice agents"
        actions={
          <Button onClick={() => setIsCreateOpen(true)} className="flex items-center gap-1.5" data-testid="create-tool-btn">
            <Plus className="w-4 h-4" /> Create Tool
          </Button>
        }
      />

      <div className="bg-white border border-zinc-200 rounded-sm shadow-xs">
        <div className="p-4 border-b border-zinc-100">
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-400" />
            <Input
              placeholder="Search tools..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        <div className="p-4">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-sm bg-zinc-50 border border-zinc-100 animate-pulse" />
              ))}
            </div>
          ) : activeTools.length === 0 && archivedTools.length === 0 ? (
            <div className="text-center py-12">
              <Phone className="w-10 h-10 text-zinc-300 mx-auto mb-3" />
              <p className="text-sm text-zinc-500 mb-4">
                {searchQuery ? "No tools match your search" : "No tools found. Create one to get started."}
              </p>
              {!searchQuery && (
                <Button onClick={() => setIsCreateOpen(true)}>Create Your First Tool</Button>
              )}
            </div>
          ) : (
            <>
              {activeTools.length > 0 && (
                <div className="space-y-2">
                  {activeTools.map((tool) => (
                    <div
                      key={tool.toolUuid}
                      onClick={() => nav(`/tools/${tool.toolUuid}`)}
                      className="flex items-center justify-between p-4 border border-zinc-200 rounded-sm hover:bg-zinc-50 cursor-pointer transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="w-9 h-9 shrink-0 rounded-md flex items-center justify-center"
                          style={{ backgroundColor: tool.iconColor || getCategoryConfig(tool.category)?.iconColor || "#3B82F6" }}
                        >
                          {renderToolIcon(tool.category)}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-zinc-950">{tool.name}</span>
                            {getCategoryBadge(tool.category)}
                          </div>
                          {tool.description && (
                            <p className="text-xs text-zinc-500 mt-0.5">{tool.description}</p>
                          )}
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={(e) => handleArchive(tool.toolUuid, e)}
                        className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {archivedTools.length > 0 && (
                <div className="mt-8">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-3 flex items-center gap-1.5">
                    <Archive className="w-3.5 h-3.5" /> Archived Tools
                  </h3>
                  <div className="space-y-2">
                    {archivedTools.map((tool) => (
                      <div
                        key={tool.toolUuid}
                        onClick={() => nav(`/tools/${tool.toolUuid}`)}
                        className="flex items-center justify-between p-4 border border-zinc-200 rounded-sm hover:bg-zinc-50 cursor-pointer transition-colors opacity-60"
                      >
                        <div className="flex items-center gap-3">
                          <div
                            className="w-9 h-9 shrink-0 rounded-md flex items-center justify-center"
                            style={{ backgroundColor: tool.iconColor || getCategoryConfig(tool.category)?.iconColor || "#3B82F6" }}
                          >
                            {renderToolIcon(tool.category)}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-zinc-950">{tool.name}</span>
                              {getCategoryBadge(tool.category)}
                              <Badge variant="secondary">Archived</Badge>
                            </div>
                            {tool.description && (
                              <p className="text-xs text-zinc-500 mt-0.5">{tool.description}</p>
                            )}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => handleUnarchive(tool.toolUuid, e)}
                          className="text-zinc-700 hover:text-zinc-950"
                          title="Restore tool"
                        >
                          <RotateCcw className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <Dialog
        open={isCreateOpen}
        onOpenChange={(open) => {
          setIsCreateOpen(open);
          if (!open) resetCreateForm();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create New Tool</DialogTitle>
            <DialogDescription>Create a new tool that can be used by your voice agents.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>Tool Type</Label>
              <Select
                value={newCategory}
                onValueChange={(v) => {
                  const category = v as ToolCategory;
                  setNewCategory(category);
                  setCreateError(null);
                  const config = getCategoryConfig(category);
                  if (config?.autoFill) {
                    setNewName(config.autoFill.name);
                    setNewDescription(config.autoFill.description);
                  }
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TOOL_CATEGORIES.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-zinc-500">{getCategoryConfig(newCategory)?.description}</p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tool-name">Tool Name</Label>
              <Input
                id="tool-name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g., Book Appointment, Check Inventory"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="tool-description">Description (Optional)</Label>
              <Input
                id="tool-description"
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="What does this tool do?"
              />
            </div>
            {newCategory === "mcp" && (
              <>
                <div className="grid gap-2">
                  <Label htmlFor="mcp-url">MCP Server URL</Label>
                  <Input
                    id="mcp-url"
                    value={mcpUrl}
                    onChange={(e) => setMcpUrl(e.target.value)}
                    placeholder="https://your-mcp-server.example.com/mcp"
                  />
                </div>
                <div className="grid gap-2">
                  <Label>Transport</Label>
                  <Input value="Streamable HTTP" disabled readOnly />
                </div>
                <CredentialSelector
                  value={mcpCredentialUuid}
                  onChange={setMcpCredentialUuid}
                  label="Credential (Optional)"
                  description="Select a credential for authenticating with the MCP server, or leave empty for no auth."
                />
                <div className="grid gap-2">
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
              </>
            )}
          </div>
          {createError && (
            <div className="p-3 bg-rose-50 border border-rose-200 rounded-sm text-rose-700 text-sm">
              {createError}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={isCreating}>
              {isCreating ? "Creating..." : "Create Tool"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

