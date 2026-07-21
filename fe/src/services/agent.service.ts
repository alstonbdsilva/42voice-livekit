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
}

export const AgentService = new AgentServiceClass();
export default AgentService;
