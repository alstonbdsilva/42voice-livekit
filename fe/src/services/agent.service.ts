import { API_ENDPOINTS } from "@/constants/apiEndpoints";
import { api } from "./api";
import { Agent } from "@/types";

export interface CreateAgentDto {
  name: string;
  callType?: string;
  useCase?: string;
  activityDescription?: string;
  resellerIds?: string[];
  clientIds?: string[];
  voiceName?: string;
  voiceGender?: string;
  guardrails?: any;
  customGuardrails?: string;
  knowledgeItems?: any[];
}

interface ApiSuccessResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

class AgentServiceClass {
  async getAll(): Promise<Agent[]> {
    const res = await api.get<any>(API_ENDPOINTS.AGENTS);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }

  async getById(id: string): Promise<Agent> {
    const res = await api.get<any>(`${API_ENDPOINTS.AGENTS}/${id}`);
    return res?.data ?? res;
  }

  async create(dto: CreateAgentDto): Promise<Agent> {
    const res = await api.post<ApiSuccessResponse<Agent>>(API_ENDPOINTS.AGENTS, dto);
    return res?.data ?? (res as any);
  }

  async updateStatus(id: string, status: string): Promise<Agent> {
    const res = await api.patch<ApiSuccessResponse<Agent>>(`${API_ENDPOINTS.AGENTS}/${id}`, { status });
    return res?.data ?? (res as any);
  }

  async updateAssignments(id: string, resellerIds?: string[], clientIds?: string[]): Promise<Agent> {
    const res = await api.patch<ApiSuccessResponse<Agent>>(`${API_ENDPOINTS.AGENTS}/${id}`, { resellerIds, clientIds });
    return res?.data ?? (res as any);
  }

  async updateDetails(id: string, details: { name?: string; useCase?: string; activityDescription?: string; callType?: string }): Promise<Agent> {
    const res = await api.patch<ApiSuccessResponse<Agent>>(`${API_ENDPOINTS.AGENTS}/${id}`, details);
    return res?.data ?? (res as any);
  }

  async uploadFile(file: File): Promise<{ s3Key: string; s3Url: string; filename: string; contentType: string }> {
    const formData = new FormData();
    formData.append("file", file);
    const res = await api.post<ApiSuccessResponse<{ s3Key: string; s3Url: string; filename: string; contentType: string }>>(
      `${API_ENDPOINTS.AGENTS}/upload`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return res?.data ?? (res as any);
  }
}

export const AgentService = new AgentServiceClass();
export default AgentService;
