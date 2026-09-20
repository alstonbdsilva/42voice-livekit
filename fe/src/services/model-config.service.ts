import { API_ENDPOINTS } from "../constants/apiEndpoints";
import { api } from "./api";

export interface ModelConfigRecord {
  id: string;
  client_id: string;
  user_id?: string;
  name: string;
  description?: string;
  status: "active" | "inactive" | string;
  stt_provider: string;
  stt_model?: string;
  stt_credential_source: string;
  stt_credential_id?: string;
  stt_options?: Record<string, any>;
  llm_provider: string;
  llm_model?: string;
  llm_credential_source: string;
  llm_credential_id?: string;
  llm_options?: Record<string, any>;
  tts_provider: string;
  tts_model?: string;
  tts_voice?: string;
  tts_credential_source: string;
  tts_credential_id?: string;
  tts_options?: Record<string, any>;
  created_at?: string;
  updated_at?: string;
}

export interface CreateModelConfigDto {
  name: string;
  description?: string;
  stt_provider?: string;
  stt_model?: string;
  stt_credential_source?: string;
  stt_credential_id?: string;
  stt_options?: Record<string, any>;
  llm_provider?: string;
  llm_model?: string;
  llm_credential_source?: string;
  llm_credential_id?: string;
  llm_options?: Record<string, any>;
  tts_provider?: string;
  tts_model?: string;
  tts_voice?: string;
  tts_credential_source?: string;
  tts_credential_id?: string;
  tts_options?: Record<string, any>;
}

export interface UpdateModelConfigDto {
  name?: string;
  description?: string;
  status?: string;
  stt_provider?: string;
  stt_model?: string;
  stt_credential_source?: string;
  stt_credential_id?: string;
  stt_options?: Record<string, any>;
  llm_provider?: string;
  llm_model?: string;
  llm_credential_source?: string;
  llm_credential_id?: string;
  llm_options?: Record<string, any>;
  tts_provider?: string;
  tts_model?: string;
  tts_voice?: string;
  tts_credential_source?: string;
  tts_credential_id?: string;
  tts_options?: Record<string, any>;
}

class ModelConfigServiceClass {
  async listModelConfigs(): Promise<ModelConfigRecord[]> {
    const res = await api.get<any>(API_ENDPOINTS.MODEL_CONFIGS);
    const data = res?.data ?? res;
    return Array.isArray(data) ? data : (data?.data ?? []);
  }

  async getModelConfig(configId: string): Promise<ModelConfigRecord> {
    const res = await api.get<any>(`${API_ENDPOINTS.MODEL_CONFIGS}/${configId}`);
    return res?.data ?? res;
  }

  async createModelConfig(dto: CreateModelConfigDto): Promise<ModelConfigRecord> {
    const res = await api.post<any>(API_ENDPOINTS.MODEL_CONFIGS, dto);
    return res?.data ?? res;
  }

  async updateModelConfig(configId: string, dto: UpdateModelConfigDto): Promise<ModelConfigRecord> {
    const res = await api.put<any>(`${API_ENDPOINTS.MODEL_CONFIGS}/${configId}`, dto);
    return res?.data ?? res;
  }

  async deleteModelConfig(configId: string): Promise<any> {
    const res = await api.delete<any>(`${API_ENDPOINTS.MODEL_CONFIGS}/${configId}`);
    return res?.data ?? res;
  }
}

export const ModelConfigService = new ModelConfigServiceClass();
export default ModelConfigService;
