import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { Tool, ToolCategory, ToolTestResult } from "@/types";

export interface CreateToolDto {
  name: string;
  description?: string;
  category: ToolCategory;
  icon?: string;
  icon_color?: string;
  definition: Record<string, any>;
}

export interface UpdateToolDto {
  name?: string;
  description?: string;
  icon?: string;
  icon_color?: string;
  definition?: Record<string, any>;
  status?: string;
}

export interface ToolTestDto {
  llm_params?: Record<string, any>;
  preset_params?: Record<string, any>;
}

interface ApiSuccessResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

class ToolsServiceClass {
  async getAll(params?: { status?: string; category?: string }): Promise<Tool[]> {
    const query = new URLSearchParams();
    if (params?.status) query.set("status", params.status);
    if (params?.category) query.set("category", params.category);
    const qs = query.toString();
    const res = await api.get<ApiSuccessResponse<Tool[]>>(
      `${API_ENDPOINTS.TOOLS}${qs ? `?${qs}` : ""}`
    );
    return res?.data ?? [];
  }

  async getByUuid(toolUuid: string): Promise<Tool> {
    const res = await api.get<ApiSuccessResponse<Tool>>(`${API_ENDPOINTS.TOOLS}/${toolUuid}`);
    return res?.data as Tool;
  }

  async create(dto: CreateToolDto): Promise<Tool> {
    const res = await api.post<ApiSuccessResponse<Tool>>(API_ENDPOINTS.TOOLS, dto);
    return res?.data as Tool;
  }

  async update(toolUuid: string, dto: UpdateToolDto): Promise<Tool> {
    const res = await api.put<ApiSuccessResponse<Tool>>(`${API_ENDPOINTS.TOOLS}/${toolUuid}`, dto);
    return res?.data as Tool;
  }

  async archive(toolUuid: string): Promise<Tool> {
    const res = await api.delete<ApiSuccessResponse<Tool>>(`${API_ENDPOINTS.TOOLS}/${toolUuid}`);
    return res?.data as Tool;
  }

  async unarchive(toolUuid: string): Promise<Tool> {
    const res = await api.post<ApiSuccessResponse<Tool>>(`${API_ENDPOINTS.TOOLS}/${toolUuid}/unarchive`);
    return res?.data as Tool;
  }

  async test(toolUuid: string, dto: ToolTestDto): Promise<ToolTestResult> {
    const res = await api.post<ApiSuccessResponse<ToolTestResult>>(
      `${API_ENDPOINTS.TOOLS}/${toolUuid}/test`,
      dto
    );
    return res?.data as ToolTestResult;
  }

  async refreshMcp(toolUuid: string): Promise<{ tool_uuid: string; discovered_tools: any[]; error: string | null }> {
    const res = await api.post<ApiSuccessResponse<any>>(`${API_ENDPOINTS.TOOLS}/${toolUuid}/mcp/refresh`);
    return res?.data;
  }
}

export const ToolsService = new ToolsServiceClass();
export default ToolsService;
